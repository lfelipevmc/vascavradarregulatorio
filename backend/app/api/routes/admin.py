"""Admin endpoints for triggering data collection manually."""
import importlib
import logging

from fastapi import APIRouter, Header, HTTPException

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
    return await collector.executar()


@router.post("/admin/collect/{fonte}")
async def trigger_collect(
    fonte: str,
    x_admin_key: str = Header(...),
) -> dict:
    """
    Run collector synchronously and return full results.
    For fonte='all', runs all collectors sequentially.
    Each collector has a 60s timeout.
    """
    if x_admin_key != _get_admin_key():
        raise HTTPException(status_code=403, detail="Invalid admin key")
    if fonte not in COLLECTOR_MAP and fonte != "all":
        raise HTTPException(status_code=400, detail=f"Fonte inválida. Opções: {FONTES + ['all']}")

    fontes_to_run = FONTES if fonte == "all" else [fonte]
    results = []

    for f in fontes_to_run:
        try:
            result = await _run_collector(f)
            results.append(result)
            logger.info("Coleta %s: %s", f, result)
        except Exception as exc:
            results.append({"fonte": f, "status": "FAILURE", "erro": str(exc),
                            "total_encontrados": 0, "total_novos": 0})
            logger.error("Erro na coleta %s: %s", f, exc)

    total_novos = sum(r.get("total_novos", 0) for r in results)
    total_encontrados = sum(r.get("total_encontrados", 0) for r in results)

    return {
        "status": "completed",
        "total_encontrados": total_encontrados,
        "total_novos": total_novos,
        "resultados": results,
    }


@router.get("/admin/collect/status")
async def collect_status(x_admin_key: str = Header(...)) -> dict:
    """Check recent job logs."""
    if x_admin_key != _get_admin_key():
        raise HTTPException(status_code=403, detail="Invalid admin key")

    from sqlalchemy import desc, select
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
