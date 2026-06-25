"""
DOU (Diário Oficial da União) collector.
Uses the DOU public JSON index (no auth required):
  https://www.in.gov.br/leiturajornal/data/dou-v4/secao{1,2,3}/{date}/index.json

Fetches sections 1 and 2 and filters for infrastructure-related acts.
"""
import logging
from datetime import date, datetime, timedelta

import httpx

from app.collectors.base import BaseCollector
from app.models.normativo import FonteNormativo, SetorNormativo, TipoNormativo

logger = logging.getLogger(__name__)

DOU_JSON_BASE = "https://www.in.gov.br/leiturajornal/data/dou-v4"

SETOR_KEYWORDS = {
    SetorNormativo.ENERGIA: ["energia", "elétric", "aneel", "petróleo", "gás", "combustível", "geração", "transmissão"],
    SetorNormativo.TRANSPORTE: ["transporte", "rodovia", "ferrovi", "antt", "porto", "aquaviário", "logística"],
    SetorNormativo.AVIACAO: ["aviação", "aeronáut", "anac", "aeroporto"],
    SetorNormativo.MINERACAO: ["mineração", "minério", "anm", "dnpm"],
    SetorNormativo.TELECOMUNICACOES: ["telecomunicações", "anatel", "radiofrequência", "banda larga", "5g"],
    SetorNormativo.SANEAMENTO: ["saneamento", "água", "esgoto", "resíduo", "ana"],
    SetorNormativo.ESPORTE: ["esporte", "desporto", "futebol", "clube", "atleta"],
}

INFRA_FILTER_KEYWORDS = [kw for kws in SETOR_KEYWORDS.values() for kw in kws] + [
    "infraestrutura", "concessão", "regulação", "agência reguladora",
    "licitação", "parceria público", "privatização",
]


def _detectar_setor(texto: str) -> SetorNormativo:
    texto_lower = texto.lower()
    for setor, keywords in SETOR_KEYWORDS.items():
        if any(kw in texto_lower for kw in keywords):
            return setor
    return SetorNormativo.GERAL


def _detectar_tipo(identifica: str) -> TipoNormativo:
    t = identifica.upper()
    if "LEI Nº" in t or t.startswith("LEI "):
        return TipoNormativo.LEI
    if "DECRETO" in t:
        return TipoNormativo.DECRETO
    if "MEDIDA PROVISÓRIA" in t:
        return TipoNormativo.MEDIDA_PROVISORIA
    if "INSTRUÇÃO NORMATIVA" in t:
        return TipoNormativo.INSTRUCAO_NORMATIVA
    if "RESOLUÇÃO" in t:
        return TipoNormativo.RESOLUCAO
    return TipoNormativo.PORTARIA


def _is_relevante(item: dict) -> bool:
    texto = " ".join([
        item.get("identifica", ""),
        item.get("title", ""),
        item.get("ementa", ""),
    ]).lower()
    return any(kw in texto for kw in INFRA_FILTER_KEYWORDS)


class DOUCollector(BaseCollector):
    """Collects normativos from DOU using the public JSON index API."""

    fonte = FonteNormativo.DOU

    async def coletar(self) -> list[dict]:
        today = date.today()
        # DOU doesn't publish on weekends; walk back to find last publication day
        target = today - timedelta(days=1)
        for _ in range(5):
            if target.weekday() < 5:  # Mon-Fri
                break
            target -= timedelta(days=1)

        results = []
        # Fetch sections 1 (executive acts) and 2 (ministerial acts)
        for secao in [1, 2]:
            items = await self._fetch_secao(secao, target)
            results.extend(items)

        logger.info(f"[DOU] {len(results)} atos relevantes coletados de {target}")
        return results

    async def _fetch_secao(self, secao: int, data: date) -> list[dict]:
        url = f"{DOU_JSON_BASE}/secao{secao}/{data.strftime('%Y-%m-%d')}/index.json"
        try:
            async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
                resp = await client.get(url, headers={"Accept": "application/json"})
            if resp.status_code != 200:
                logger.warning(f"[DOU] secao{secao} HTTP {resp.status_code}")
                return []
            data_json = resp.json()
        except Exception as exc:
            logger.warning(f"[DOU] Falha ao buscar secao{secao}: {exc}")
            return []

        content = data_json.get("content", [])
        logger.info(f"[DOU] secao{secao}: {len(content)} atos totais")

        items = []
        for item in content:
            if not _is_relevante(item):
                continue

            identifica = item.get("identifica", "") or item.get("title", "")
            ementa = item.get("ementa", "") or ""
            titulo = f"{identifica} - {ementa[:150]}" if ementa else identifica

            item_url = item.get("urlTitle", "")
            if item_url and not item_url.startswith("http"):
                item_url = f"https://www.in.gov.br{item_url}"

            pub_date = self._parse_date(item.get("pubDate", ""), "%Y-%m-%dT%H:%M:%S")
            tipo = _detectar_tipo(identifica)
            setor = _detectar_setor(f"{identifica} {ementa}")

            items.append({
                "titulo": titulo[:1000],
                "tipo": tipo,
                "fonte": FonteNormativo.DOU,
                "setor": setor,
                "url": item_url,
                "ementa": ementa[:2000],
                "data_publicacao": pub_date or datetime.combine(data, datetime.min.time()),
                "conteudo_bruto": item.get("body", ementa),
                "tags": [f"dou-secao{secao}"],
            })

        logger.info(f"[DOU] secao{secao}: {len(items)} relevantes")
        return items
