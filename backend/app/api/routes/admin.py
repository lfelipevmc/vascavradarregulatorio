"""Admin endpoints for triggering data collection manually."""
import asyncio
import importlib
import logging
from typing import Literal

from fastapi import APIRouter, BackgroundTasks, Header, HTTPException

from app.config import settings

logger = logging.getLogger(__name__)

router = APIRouter()

FONTES = ["dou", "aneel", "antt", "anac", "anatel", "anm", "tcu", "camara", "senado", "stj_stf"]

COLLECTOR_MAP = {
    "dou": ("app.collectors.dou", "DouCollector"),
    "aneel": ("app.collectors.aneel", "AneelCollector"),
    "antt": ("app.collectors.antt", "AnttCollector"),
    "anac": ("app.collectors.anac", "AnacCollector"),
    "anatel": ("app.collectors.anatel", "AnatelCollector"),
    "anm": ("app.collectors.anm", "AnmCollector"),
    "tcu": ("app.collectors.tcu", "TcuCollector"),
    "camara": ("app.collectors.camara", "CamaraCollector"),
    "senado": ("app.collectors.senado", "SenadoCollector"),
    "stj_stf": ("app.collectors.stj_stf", "StjStfCollector"),
}


def _get_admin_key() -> str:
    return settings.secret_key[:32]


async def _run_collector(fonte: str) -> dict:
    module_path, class_name = COLLECTOR_MAP[fonte]
    mod = importlib.import_module(module_path)
    collector = getattr(mod, class_name)()
    result = await collector.executar()
    return result


def _run_in_thread(fonte: str) -> None:
    """Run async collector in a new event loop (for BackgroundTasks)."""
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(_run_collector(fonte))
        logger.info("Coleta %s finalizada: %s", fonte, result)
    except Exception as exc:
        logger.error("Erro na coleta background %s: %s", fonte, exc)
    finally:
        loop.close()


@router.post("/admin/collect/{fonte}")
async def trigger_collect(
    fonte: str,
    background_tasks: BackgroundTasks,
    x_admin_key: str = Header(...),
) -> dict:
    """Trigger a collector for a specific fonte. Runs in background."""
    if x_admin_key != _get_admin_key():
        raise HTTPException(status_code=403, detail="Invalid admin key")
    if fonte not in COLLECTOR_MAP and fonte != "all":
        raise HTTPException(status_code=400, detail=f"Fonte inválida. Opções: {FONTES + ['all']}")

    fontes_to_run = FONTES if fonte == "all" else [fonte]
    for f in fontes_to_run:
        background_tasks.add_task(_run_in_thread, f)

    return {
        "status": "started",
        "fontes": fontes_to_run,
        "message": f"Coleta de {len(fontes_to_run)} fonte(s) iniciada em background.",
    }


@router.get("/admin/collect/status")
async def collect_status(x_admin_key: str = Header(...)) -> dict:
    """Check recent job logs."""
    if x_admin_key != _get_admin_key():
        raise HTTPException(status_code=403, detail="Invalid admin key")

    from sqlalchemy import select, desc
    from app.database import AsyncSessionLocal
    from app.models.normativo import JobLog

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(JobLog).order_by(desc(JobLog.executado_em)).limit(20)
        )
        logs = result.scalars().all()

    return {
        "logs": [
            {
                "fonte": l.fonte,
                "status": l.status,
                "total_encontrados": l.total_encontrados,
                "total_novos": l.total_novos,
                "erro": l.erro,
                "executado_em": l.executado_em.isoformat() if l.executado_em else None,
            }
            for l in logs
        ]
    }
