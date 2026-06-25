from celery import Celery
from celery.schedules import crontab

from app.config import settings

celery_app = Celery(
    "radar_regulatorio",
    broker=settings.redis_url,
    backend=settings.celery_result_backend,
    include=["app.tasks.coleta"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="America/Sao_Paulo",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_routes={
        "app.tasks.coleta.executar_coleta_dou": {"queue": "coleta"},
        "app.tasks.coleta.executar_coleta_agencias": {"queue": "coleta"},
        "app.tasks.coleta.executar_coleta_tcu": {"queue": "coleta"},
        "app.tasks.coleta.executar_coleta_legislativo": {"queue": "coleta"},
        "app.tasks.coleta.executar_coleta_completa": {"queue": "coleta"},
        "app.tasks.coleta.processar_normativo_ia": {"queue": "ia"},
    },
    beat_schedule={
        # Daily at 06:00 BRT - collect DOU (published in the morning)
        "coleta-dou-diaria": {
            "task": "app.tasks.coleta.executar_coleta_dou",
            "schedule": crontab(hour=6, minute=0),
        },
        # Daily at 07:00 BRT - collect all agencies
        "coleta-agencias-diaria": {
            "task": "app.tasks.coleta.executar_coleta_agencias",
            "schedule": crontab(hour=7, minute=0),
        },
        # Daily at 08:00 BRT - collect TCU
        "coleta-tcu-diaria": {
            "task": "app.tasks.coleta.executar_coleta_tcu",
            "schedule": crontab(hour=8, minute=0),
        },
        # Daily at 08:30 BRT - collect Congress bills
        "coleta-legislativo-diaria": {
            "task": "app.tasks.coleta.executar_coleta_legislativo",
            "schedule": crontab(hour=8, minute=30),
        },
        # Full run at 22:00 BRT as catch-up
        "coleta-completa-noturna": {
            "task": "app.tasks.coleta.executar_coleta_completa",
            "schedule": crontab(hour=22, minute=0),
        },
    },
)
