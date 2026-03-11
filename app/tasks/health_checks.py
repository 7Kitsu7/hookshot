from datetime import datetime, timedelta
from celery.utils.log import get_task_logger
from sqlalchemy import func

from app.core.celery_app import celery_app
from app.db.session import SessionLocal
from app.models.subscription import Subscription
from app.models.delivery import DeliveryAttempt, EventPayload
from app.tasks.webhooks import send_webhook_task
import uuid

logger = get_task_logger(__name__)

@celery_app.task(name="app.tasks.health_checks.run_health_checks")
def run_health_checks():
    db = SessionLocal()
    try:
        # 1. Definir el umbral de 2 horas atrás
        two_hours_ago = datetime.utcnow() - timedelta(hours=2)

        # 2. Identificar suscripciones que NO han tenido éxito en 2 horas
        # Primero obtenemos las que SÍ han tenido éxito para excluirlas
        successful_ids = db.query(DeliveryAttempt.subscription_id).filter(
            DeliveryAttempt.status == "success",
            DeliveryAttempt.attempted_at >= two_hours_ago
        ).distinct().all()
        
        successful_ids_list = [r[0] for r in successful_ids]

        # Buscamos todas las suscripciones activas que NO están en esa lista
        subs_to_check = db.query(Subscription).filter(
            Subscription.is_active == True,
            ~Subscription.id.in_(successful_ids_list)
        ).all()

        count_checked = len(subs_to_check)
        count_failed = 0

        # 3. Generar y publicar evento sintético 'health.check'
        if count_checked > 0:
            # Creamos un único registro de evento para este chequeo
            health_event = EventPayload(
                id=str(uuid.uuid4()),
                event_type="health.check",
                payload={"message": "Automatic health check due to inactivity or failure", "timestamp": str(datetime.utcnow())}
            )
            db.add(health_event)
            db.commit()
            db.refresh(health_event)

            for sub in subs_to_check:
                # Encolamos el envío individualmente
                send_webhook_task.delay(sub.id, health_event.id)
                count_failed += 1

        # 4. Registro en logs 
        logger.info(f"Health Check completado: {count_checked} suscripciones verificadas, {count_failed} eventos de salud disparados.")
        
        return f"Checked: {count_checked}, Triggered: {count_failed}"

    except Exception as exc:
        logger.error(f"Error crítico en el Beat Health Check: {exc}")
        raise exc
    finally:
        db.close()