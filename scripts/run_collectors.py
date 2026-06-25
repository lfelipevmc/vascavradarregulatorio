#!/usr/bin/env python3
"""
CLI to run specific collectors manually.
Usage:
    python scripts/run_collectors.py --fonte dou
    python scripts/run_collectors.py --fonte aneel
    python scripts/run_collectors.py --fonte all
    python scripts/run_collectors.py --ia-batch   # process pending AI items
"""
import argparse
import asyncio
import logging
import sys
import os

# Add backend to sys.path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
)
logger = logging.getLogger("run_collectors")

COLLECTORS = {
    "dou": ("app.collectors.dou", "DOUCollector"),
    "aneel": ("app.collectors.aneel", "ANEELCollector"),
    "antt": ("app.collectors.antt", "ANTTCollector"),
    "anac": ("app.collectors.anac", "ANACCollector"),
    "anatel": ("app.collectors.anatel", "ANATELCollector"),
    "anm": ("app.collectors.anm", "ANMCollector"),
    "tcu": ("app.collectors.tcu", "TCUCollector"),
    "camara": ("app.collectors.camara", "CamaraCollector"),
    "senado": ("app.collectors.senado", "SenadoCollector"),
    "stj_stf": ("app.collectors.stj_stf", "STJSTFCollector"),
}


async def run_collector(fonte: str) -> dict:
    """Run a single collector by name."""
    if fonte not in COLLECTORS:
        logger.error(f"Coletor '{fonte}' não encontrado. Disponíveis: {', '.join(COLLECTORS.keys())}")
        return {"status": "FAILURE", "erro": f"Coletor '{fonte}' não encontrado"}

    module_path, class_name = COLLECTORS[fonte]

    import importlib
    module = importlib.import_module(module_path)
    CollectorClass = getattr(module, class_name)

    logger.info(f"Iniciando coletor: {fonte} ({class_name})")
    collector = CollectorClass()
    result = await collector.executar()

    logger.info(
        f"Coletor {fonte} finalizado: "
        f"status={result.get('status')} "
        f"encontrados={result.get('total_encontrados', 0)} "
        f"novos={result.get('total_novos', 0)}"
    )
    if result.get("erro"):
        logger.error(f"Erro: {result['erro']}")

    return result


async def run_all() -> dict:
    """Run all collectors sequentially."""
    results = {}
    for fonte in COLLECTORS:
        try:
            result = await run_collector(fonte)
            results[fonte] = result
        except Exception as exc:
            logger.error(f"Falha inesperada no coletor {fonte}: {exc}", exc_info=True)
            results[fonte] = {"status": "FAILURE", "erro": str(exc)}
    return results


async def run_ia_batch(limit: int = 20) -> dict:
    """Process pending normativos with Claude AI."""
    from app.processors.ia_processor import IAProcessor
    logger.info(f"Iniciando processamento IA em lote (limite: {limit})")
    processor = IAProcessor()
    result = await processor.processar_lote(limite=limit)
    logger.info(f"Lote IA finalizado: {result}")
    return result


async def main():
    parser = argparse.ArgumentParser(
        description="Radar Regulatório - CLI para execução de coletores",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"""
Fontes disponíveis:
  {', '.join(COLLECTORS.keys())}
  all    - executa todos os coletores

Exemplos:
  python scripts/run_collectors.py --fonte dou
  python scripts/run_collectors.py --fonte aneel
  python scripts/run_collectors.py --fonte all
  python scripts/run_collectors.py --ia-batch --ia-limit 50
        """,
    )
    parser.add_argument(
        "--fonte",
        choices=list(COLLECTORS.keys()) + ["all"],
        help="Coletor a executar (ou 'all' para todos)",
    )
    parser.add_argument(
        "--ia-batch",
        action="store_true",
        help="Processar normativos pendentes com IA",
    )
    parser.add_argument(
        "--ia-limit",
        type=int,
        default=20,
        help="Limite de normativos para processar com IA (default: 20)",
    )

    args = parser.parse_args()

    if not args.fonte and not args.ia_batch:
        parser.print_help()
        sys.exit(1)

    if args.ia_batch:
        result = await run_ia_batch(args.ia_limit)
        print(f"\nResultado IA: {result}")
    elif args.fonte == "all":
        results = await run_all()
        print("\n=== Resumo Final ===")
        for fonte, result in results.items():
            status = result.get("status", "?")
            novos = result.get("total_novos", 0)
            encontrados = result.get("total_encontrados", 0)
            print(f"  {fonte:12s} | {status:8s} | {encontrados:3d} encontrados | {novos:3d} novos")
    else:
        result = await run_collector(args.fonte)
        print(f"\nResultado: {result}")


if __name__ == "__main__":
    asyncio.run(main())
