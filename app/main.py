import uuid
from typing import List, Optional
from fastapi import FastAPI, Depends, HTTPException, status
from sqlalchemy.orm import Session
from unfurl import Unfurl 

# Importaciones locales
from app.db.session import get_db
from app.models.subscription import Subscription
from app.schemas.subscription import SubscriptionCreate, SubscriptionOut, SubscriptionUpdate

app = FastAPI(
    title="Hookshot API",
    description="Microservicio para gestión de Webhooks con reintentos y salud de suscripciones."
)

# --- ENDPOINTS DE SUSCRIPCIONES ---

@app.post("/subscriptions", response_model=SubscriptionOut, status_code=status.HTTP_201_CREATED)
def create_subscription(payload: SubscriptionCreate, db: Session = Depends(get_db)):
    """
    Crea una nueva suscripción. 
    Usa 'unfurl' para obtener metadata de la target_url (Bonus).
    """
    preview_title, preview_desc = None, None
    
    # Extraer Open Graph metadata
    try:
        unfurl_instance = Unfurl()
        unfurl_instance.add(str(payload.target_url))
        preview_title = unfurl_instance.meta.get('og:title') or unfurl_instance.meta.get('title')
        preview_desc = unfurl_instance.meta.get('og:description') or unfurl_instance.meta.get('description')
    except Exception:
        # Si falla Unfurl, no bloqueamos la creación 
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
    """Lista suscripciones activas, permitiendo filtrar por tipo de evento."""
    query = db.query(Subscription).filter(Subscription.is_active == True)
    if event_type:
        query = query.filter(Subscription.event_type == event_type)
    return query.all()

@app.get("/subscriptions/{subscription_id}", response_model=SubscriptionOut)
def get_subscription(subscription_id: str, db: Session = Depends(get_db)):
    """Obtiene el detalle de una suscripción específica."""
    sub = db.query(Subscription).filter(Subscription.id == subscription_id).first()
    if not sub:
        raise HTTPException(status_code=404, detail="Subscription not found")
    return sub

@app.patch("/subscriptions/{subscription_id}", response_model=SubscriptionOut)
def update_subscription(subscription_id: str, payload: SubscriptionUpdate, db: Session = Depends(get_db)):
    """Actualiza una suscripción (ej. para desactivarla)."""
    sub = db.query(Subscription).filter(Subscription.id == subscription_id).first()
    if not sub:
        raise HTTPException(status_code=404, detail="Subscription not found")
    
    # Actualizar solo campos enviados
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
    """Elimina físicamente una suscripción de la base de datos."""
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