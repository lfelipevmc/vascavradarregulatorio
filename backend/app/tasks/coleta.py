"""
Celery tasks for data collection and AI processing.
"""
import asyncio
import logging

from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


def _run_async(coro):
    """Run an async coroutine in a new event loop (required for Celery workers)."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@celery_app.task(
    name="app.tasks.coleta.executar_coleta_dou",
    bind=True,
    max_retries=2,
    default_retry_delay=300,
)
def executar_coleta_dou(self) -> dict:
    """Collect normativos from DOU (Diário Oficial da União)."""
    logger.info("[TASK] Iniciando coleta DOU")
    try:
        from app.collectors.dou import DOUCollector
        collector = DOUCollector()
        result = _run_async(collector.executar())
        logger.info(f"[TASK] DOU concluído: {result}")
        return result
    except Exception as exc:
        logger.error(f"[TASK] Falha na coleta DOU: {exc}", exc_info=True)
        raise self.retry(exc=exc)


@celery_app.task(
    name="app.tasks.coleta.executar_coleta_agencias",
    bind=True,
    max_retries=2,
    default_retry_delay=300,
)
def executar_coleta_agencias(self) -> dict:
    """Collect normativos from all regulatory agencies (ANEEL, ANTT, ANAC, ANATEL, ANM)."""
    logger.info("[TASK] Iniciando coleta agências reguladoras")
    results = {}

    collectors_map = {
        "ANEEL": "app.collectors.aneel.ANEELCollector",
        "ANTT": "app.collectors.antt.ANTTCollector",
        "ANAC": "app.collectors.anac.ANACCollector",
        "ANATEL": "app.collectors.anatel.ANATELCollector",
        "ANM": "app.collectors.anm.ANMCollector",
    }

    for name, class_path in collectors_map.items():
        try:
            module_path, class_name = class_path.rsplit(".", 1)
            import importlib
            module = importlib.import_module(module_path)
            CollectorClass = getattr(module, class_name)
            collector = CollectorClass()
            result = _run_async(collector.executar())
            results[name] = result
            logger.info(f"[TASK] {name}: {result['total_novos']} novos itens")
        except Exception as exc:
            logger.error(f"[TASK] Falha na coleta {name}: {exc}", exc_info=True)
            results[name] = {"status": "FAILURE", "erro": str(exc)}

    return results


@celery_app.task(
    name="app.tasks.coleta.executar_coleta_tcu",
    bind=True,
    max_retries=2,
    default_retry_delay=300,
)
def executar_coleta_tcu(self) -> dict:
    """Collect TCU acórdãos related to infrastructure regulation."""
    logger.info("[TASK] Iniciando coleta TCU")
    try:
        from app.collectors.tcu import TCUCollector
        collector = TCUCollector()
        result = _run_async(collector.executar())
        logger.info(f"[TASK] TCU concluído: {result}")
        return result
    except Exception as exc:
        logger.error(f"[TASK] Falha na coleta TCU: {exc}", exc_info=True)
        raise self.retry(exc=exc)


@celery_app.task(
    name="app.tasks.coleta.executar_coleta_legislativo",
    bind=True,
    max_retries=2,
    default_retry_delay=300,
)
def executar_coleta_legislativo(self) -> dict:
    """Collect bills from Câmara dos Deputados and Senado Federal."""
    logger.info("[TASK] Iniciando coleta legislativo")
    results = {}

    for name, class_path in [
        ("CAMARA", "app.collectors.camara.CamaraCollector"),
        ("SENADO", "app.collectors.senado.SenadoCollector"),
        ("STJ_STF", "app.collectors.stj_stf.STJSTFCollector"),
    ]:
        try:
            module_path, class_name = class_path.rsplit(".", 1)
            import importlib
            module = importlib.import_module(module_path)
            CollectorClass = getattr(module, class_name)
            collector = CollectorClass()
            result = _run_async(collector.executar())
            results[name] = result
            logger.info(f"[TASK] {name}: {result.get('total_novos', 0)} novos itens")
        except Exception as exc:
            logger.error(f"[TASK] Falha na coleta {name}: {exc}", exc_info=True)
            results[name] = {"status": "FAILURE", "erro": str(exc)}

    return results


@celery_app.task(
    name="app.tasks.coleta.executar_coleta_completa",
    bind=True,
    max_retries=1,
    default_retry_delay=600,
)
def executar_coleta_completa(self) -> dict:
    """Run all collectors in sequence."""
    logger.info("[TASK] Iniciando coleta completa")
    results = {
        "dou": executar_coleta_dou.apply().get(),
        "agencias": executar_coleta_agencias.apply().get(),
        "tcu": executar_coleta_tcu.apply().get(),
        "legislativo": executar_coleta_legislativo.apply().get(),
    }
    logger.info("[TASK] Coleta completa finalizada")
    return results


@celery_app.task(
    name="app.tasks.coleta.processar_normativo_ia",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    rate_limit="30/m",  # respect Anthropic rate limits
)
def processar_normativo_ia(self, normativo_id: int) -> dict:
    """
    Process a single normativo with Claude AI.
    Rate-limited to 30 per minute to stay within Anthropic API limits.
    """
    logger.info(f"[TASK] Processando normativo {normativo_id} com IA")
    try:
        from app.processors.ia_processor import IAProcessor
        processor = IAProcessor()
        success = _run_async(processor.processar_normativo(normativo_id))
        result = {"normativo_id": normativo_id, "success": success}
        logger.info(f"[TASK] IA processamento normativo {normativo_id}: {'OK' if success else 'FALHA'}")
        return result
    except Exception as exc:
        logger.error(
            f"[TASK] Falha no processamento IA normativo {normativo_id}: {exc}",
            exc_info=True,
        )
        raise self.retry(exc=exc)
