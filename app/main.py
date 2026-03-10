from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.models.subscription import Subscription

app = FastAPI(title="Hookshot API")

@app.get("/subscriptions")
def list_subscriptions(event_type: str = None, db: Session = Depends(get_db)):
    query = db.query(Subscription).filter(Subscription.is_active == True)
    if event_type:
        query = query.filter(Subscription.event_type == event_type)
    return query.all()

@app.get("/")
def read_root():
    return {"message": "Hookshot is running"}