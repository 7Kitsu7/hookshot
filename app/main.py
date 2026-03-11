import uuid
from typing import List, Optional
from fastapi import FastAPI, Depends, HTTPException, status
from sqlalchemy.orm import Session
from unfurl import Unfurl 

# Importaciones locales
from app.db.session import get_db
from app.models.subscription import Subscription
from app.models.delivery import EventPayload
from app.schemas.subscription import SubscriptionCreate, SubscriptionOut, SubscriptionUpdate
from app.schemas.event import EventCreate
from app.tasks.webhooks import send_webhook_task

app = FastAPI(
    title="Hookshot API",
    description="Microservicio para gestión de Webhooks con reintentos y salud de suscripciones."
)

# --- ENDPOINTS DE EVENTOS ---

@app.post("/events", status_code=status.HTTP_202_ACCEPTED)
def trigger_event(payload: EventCreate, db: Session = Depends(get_db)):
    """
    Recibe un evento, lo registra y encola el envío a los suscriptores.
    Retorna 202 Accepted ya que el procesamiento es asíncrono.
    """
    # 1. Registrar el evento en la base de datos
    db_event = EventPayload(
        id=str(uuid.uuid4()),
        event_type=payload.event_type,
        payload=payload.payload
    )
    db.add(db_event)
    db.commit()
    db.refresh(db_event)

    # 2. Buscar suscripciones activas que coincidan con el tipo de evento
    subscriptions = db.query(Subscription).filter(
        Subscription.event_type == payload.event_type,
        Subscription.is_active == True
    ).all()

    # 3. Encolar tareas en Celery para cada suscriptor
    for sub in subscriptions:
        send_webhook_task.delay(sub.id, db_event.id)

    return {
        "message": f"Event queued for {len(subscriptions)} subscriptions",
        "event_id": db_event.id
    }

# --- ENDPOINTS DE SUSCRIPCIONES ---

@app.post("/subscriptions", response_model=SubscriptionOut, status_code=status.HTTP_201_CREATED)
def create_subscription(payload: SubscriptionCreate, db: Session = Depends(get_db)):
    preview_title, preview_desc = None, None
    
    try:
        unfurl_instance = Unfurl()
        unfurl_instance.add(str(payload.target_url))
        preview_title = unfurl_instance.meta.get('og:title') or unfurl_instance.meta.get('title')
        preview_desc = unfurl_instance.meta.get('og:description') or unfurl_instance.meta.get('description')
    except Exception:
        pass

    new_sub = Subscription(
        id=str(uuid.uuid4()),
        name=payload.name,
        target_url=str(payload.target_url),
        event_type=payload.event_type,
        secret=payload.secret,
        preview_title=preview_title,
        preview_description=preview_desc
    )
    
    db.add(new_sub)
    db.commit()
    db.refresh(new_sub)
    return new_sub

@app.get("/subscriptions", response_model=List[SubscriptionOut])
def list_subscriptions(event_type: Optional[str] = None, db: Session = Depends(get_db)):
    query = db.query(Subscription).filter(Subscription.is_active == True)
    if event_type:
        query = query.filter(Subscription.event_type == event_type)
    return query.all()

@app.get("/subscriptions/{subscription_id}", response_model=SubscriptionOut)
def get_subscription(subscription_id: str, db: Session = Depends(get_db)):
    sub = db.query(Subscription).filter(Subscription.id == subscription_id).first()
    if not sub:
        raise HTTPException(status_code=404, detail="Subscription not found")
    return sub

@app.patch("/subscriptions/{subscription_id}", response_model=SubscriptionOut)
def update_subscription(subscription_id: str, payload: SubscriptionUpdate, db: Session = Depends(get_db)):
    sub = db.query(Subscription).filter(Subscription.id == subscription_id).first()
    if not sub:
        raise HTTPException(status_code=404, detail="Subscription not found")
    
    update_data = payload.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        if key == "target_url":
            setattr(sub, key, str(value))
        else:
            setattr(sub, key, value)
    
    db.commit()
    db.refresh(sub)
    return sub

@app.delete("/subscriptions/{subscription_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_subscription(subscription_id: str, db: Session = Depends(get_db)):
    sub = db.query(Subscription).filter(Subscription.id == subscription_id).first()
    if not sub:
        raise HTTPException(status_code=404, detail="Subscription not found")
    
    db.delete(sub)
    db.commit()
    return None

# --- HEALTH CHECK ---

@app.get("/")
def read_root():
    return {
        "status": "ready",
        "service": "Hookshot API",
        "version": "1.0.0"
    }