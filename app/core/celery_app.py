import os
from celery import Celery
from celery.schedules import crontab

# Configuración del broker y backend (Redis es obligatorio por el reto) [cite: 22, 35]
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

celery_app = Celery(
    "hookshot",
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=["app.tasks.webhooks", "app.tasks.health_checks"] # Ajusta según tus rutas
)

# Configuración de Celery
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    # Configuración de reintentos globales si se desea
    task_acks_late=True,
    worker_prefetch_multiplier=1,
)

# 3.3 Tarea periódica (El "Reto Difícil") [cite: 27, 28]
# Se configura Celery Beat para correr cada 5 minutos [cite: 29]
celery_app.conf.beat_schedule = {
    "check-subscriptions-health-every-5-minutes": {
        "task": "app.tasks.health_checks.run_health_checks",
        "schedule": 300.0, # 5 minutos en segundos [cite: 29]
    },
}