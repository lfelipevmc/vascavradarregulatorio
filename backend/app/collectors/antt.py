"""
ANTT (Agência Nacional de Transportes Terrestres) collector.
Scrapes resoluções from https://www.antt.gov.br/resolucoes
"""
import logging
from datetime import datetime

from bs4 import BeautifulSoup

from app.collectors.base import BaseCollector
from app.models.normativo import FonteNormativo, SetorNormativo, TipoNormativo

logger = logging.getLogger(__name__)

ANTT_BASE = "https://www.antt.gov.br"
ANTT_RESOLUCOES_URL = f"{ANTT_BASE}/resolucoes"
ANTT_PORTARIAS_URL = f"{ANTT_BASE}/portarias"
ANTT_API_URL = "https://dadosabertos.antt.gov.br/api/3/action/datastore_search"


def _detectar_tipo_antt(titulo: str) -> TipoNormativo:
    t = titulo.upper()
    if "RESOLUÇÃO" in t:
        return TipoNormativo.RESOLUCAO
    if "PORTARIA" in t:
        return TipoNormativo.PORTARIA
    if "INSTRUÇÃO" in t:
        return TipoNormativo.INSTRUCAO_NORMATIVA
    return TipoNormativo.RESOLUCAO


class ANTTCollector(BaseCollector):
    """Collects regulatory acts from ANTT."""

    fonte = FonteNormativo.ANTT

    async def coletar(self) -> list[dict]:
        results = []

        for url in [ANTT_RESOLUCOES_URL, ANTT_PORTARIAS_URL]:
            try:
                items = await self._coletar_pagina(url)
                results.extend(items)
            except Exception as exc:
                logger.warning(f"[ANTT] Erro ao coletar de {url}: {exc}")

        if not results:
            try:
                items = await self._coletar_api()
                results.extend(items)
            except Exception as exc:
                logger.warning(f"[ANTT] API fallback falhou: {exc}")

        return results

    async def _coletar_pagina(self, url: str) -> list[dict]:
        try:
            resp = await self._get(url)
        except Exception as exc:
            logger.warning(f"[ANTT] Falha no request {url}: {exc}")
            return []

        soup = BeautifulSoup(resp.text, "lxml")
        items = []

        rows = (
            soup.select("table.table tbody tr")
            or soup.select(".results-table tbody tr")
            or soup.select("ul.normativos li")
            or soup.select(".portlet-body .results tr")
        )

        for row in rows:
            try:
                link_el = row.select_one("a[href]")
                if not link_el:
                    continue

                titulo = link_el.get_text(strip=True)
                href = link_el.get("href", "")
                item_url = href if href.startswith("http") else f"{ANTT_BASE}{href}"

                cells = row.select("td")
                data_pub = None
                numero = None

                for i, cell in enumerate(cells):
                    text = cell.get_text(strip=True)
                    parsed = self._parse_date(text)
                    if parsed:
                        data_pub = parsed
                    if i == 0 and text and not parsed:
                        numero = text

                if not titulo:
                    continue

                items.append(
                    {
                        "titulo": titulo[:1000],
                        "tipo": _detectar_tipo_antt(titulo),
                        "numero": numero,
                        "fonte": FonteNormativo.ANTT,
                        "setor": SetorNormativo.TRANSPORTE,
                        "url": item_url,
                        "data_publicacao": data_pub or datetime.now(),
                        "ementa": titulo[:500],
                        "conteudo_bruto": titulo,
                    }
                )
            except Exception as exc:
                logger.debug(f"[ANTT] Erro ao parsear row: {exc}")

        return items

    async def _coletar_api(self) -> list[dict]:
        """Fetch ANTT resolutions from open data API if available."""
        # ANTT Resolucoes dataset
        params = {
            "resource_id": "resolucoes-antt",
            "limit": 50,
        }
        try:
            resp = await self._get(ANTT_API_URL, params=params)
            data = resp.json()
            records = data.get("result", {}).get("records", [])
        except Exception:
            return []

        items = []
        for record in records:
            titulo = record.get("titulo") or record.get("descricao") or "Resolução ANTT"
            data_pub = self._parse_date(record.get("data_publicacao", ""), "%Y-%m-%d")
            items.append(
                {
                    "titulo": titulo[:1000],
                    "tipo": TipoNormativo.RESOLUCAO,
                    "numero": record.get("numero"),
                    "fonte": FonteNormativo.ANTT,
                    "setor": SetorNormativo.TRANSPORTE,
                    "url": record.get("url") or ANTT_BASE,
                    "data_publicacao": data_pub,
                    "ementa": record.get("ementa", "")[:2000],
                    "conteudo_bruto": record.get("ementa", ""),
                }
            )
        return items
