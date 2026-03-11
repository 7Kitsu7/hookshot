import hmac
import hashlib
import json
import httpx
from datetime import datetime
from celery.utils.log import get_task_logger

from app.core.celery_app import celery_app
from app.db.session import SessionLocal
from app.models.subscription import Subscription
from app.models.delivery import EventPayload, DeliveryAttempt

logger = get_task_logger(__name__)

@celery_app.task(
    bind=True, 
    max_retries=2, # Total: 1 intento original + 2 reintentos = 3 intentos máx.
    name="app.tasks.webhooks.send_webhook_task"
)
def send_webhook_task(self, subscription_id: str, event_id: str):
    db = SessionLocal()
    try:
        sub = db.query(Subscription).filter(Subscription.id == subscription_id).first()
        event = db.query(EventPayload).filter(EventPayload.id == event_id).first()

        if not sub or not event or not sub.is_active:
            return

        # Firma HMAC-SHA256
        payload_str = json.dumps(event.payload, separators=(',', ':'))
        signature = hmac.new(
            sub.secret.encode('utf-8'),
            payload_str.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()

        headers = {
            "Content-Type": "application/json",
            "X-Hookshot-Signature": signature,
            "X-Hookshot-Event": event.event_type
        }

        status_code = None
        response_text = ""
        should_retry = False

        try:
            with httpx.Client(timeout=10.0) as client:
                response = client.post(sub.target_url, content=payload_str, headers=headers)
                status_code = response.status_code
                response_text = response.text
                
                # REGLA: Reintentar si responde con 5xx (Server Error)
                if 500 <= status_code < 600:
                    should_retry = True
                
        except httpx.RequestError as exc:
            # REGLA: Reintentar si no responde (Error de red)
            should_retry = True
            response_text = f"No responde: {str(exc)}"

        # Registrar el intento
        success = status_code is not None and 200 <= status_code < 300
        attempt = DeliveryAttempt(
            subscription_id=sub.id,
            event_id=event.id,
            status="success" if success else "failed",
            http_status_code=status_code,
            response_body=response_text[:500]
        )
        db.add(attempt)
        db.commit()

        # Lógica de reintentos:
        # Intento 1 (fallido) -> retry en 30s
        # Intento 2 (fallido) -> retry en 90s
        # Intento 3 (fallido) -> marcar como failed (Celery deja de reintentar)
        if should_retry and self.request.retries < self.max_retries:
            # Definir segundos según el número de reintento actual
            retry_times = [30, 90]
            next_countdown = retry_times[self.request.retries]
            
            logger.info(f"Reintento {self.request.retries + 1} en {next_countdown}s para {sub.target_url}")
            raise self.retry(countdown=next_countdown)

    except Exception as exc:
        if isinstance(exc, self.MaxRetriesExceededError):
            logger.error(f"Máximo de 3 intentos alcanzado para {subscription_id}")
        raise exc
    finally:
        db.close()