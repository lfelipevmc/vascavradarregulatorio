import logging
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import health, normativos, admin
from app.config import settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description=(
        "API do Radar Regulatório - monitoramento de normas, resoluções e decisões "
        "das agências reguladoras, TCU, Congresso Nacional e tribunais superiores."
    ),
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, tags=["health"])
app.include_router(normativos.router, prefix=settings.api_prefix, tags=["normativos"])
app.include_router(admin.router, prefix=settings.api_prefix, tags=["admin"])


def _start_scheduler() -> None:
    """Start APScheduler with daily collection jobs (replaces Celery Beat on free tier)."""
    try:
        from apscheduler.schedulers.background import BackgroundScheduler
        from apscheduler.triggers.cron import CronTrigger
        import pytz

        brasilia = pytz.timezone("America/Sao_Paulo")
        scheduler = BackgroundScheduler(timezone=brasilia)

        def run_collector(fonte: str) -> None:
            try:
                import importlib
                mod = importlib.import_module(f"app.collectors.{fonte}")
                cls_name = "".join(p.capitalize() for p in fonte.split("_")) + "Collector"
                collector = getattr(mod, cls_name)()
                import asyncio
                asyncio.run(collector.coletar())
                logger.info("Coleta %s concluída", fonte)
            except Exception as exc:
                logger.error("Erro na coleta %s: %s", fonte, exc)

        # Coleta diária: DOU às 06h, agências às 07h, TCU às 08h, legislativo às 09h
        for fonte, hour in [("dou", 6), ("aneel", 7), ("antt", 7), ("anac", 7),
                             ("anatel", 7), ("anm", 7), ("tcu", 8),
                             ("camara", 9), ("senado", 9)]:
            scheduler.add_job(
                run_collector,
                trigger=CronTrigger(hour=hour, minute=0),
                args=[fonte],
                id=f"coleta_{fonte}",
                replace_existing=True,
            )

        scheduler.start()
        logger.info("APScheduler iniciado com %d jobs de coleta", len(scheduler.get_jobs()))
    except Exception as exc:
        logger.warning("APScheduler não iniciado: %s", exc)


@app.on_event("startup")
async def startup_event() -> None:
    logger.info("Starting %s v%s", settings.app_name, settings.app_version)
    logger.info("Environment: %s", settings.environment)

    if os.environ.get("ENABLE_SCHEDULER", "false").lower() == "true":
        _start_scheduler()
