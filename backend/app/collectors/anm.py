"""
ANM (Agência Nacional de Mineração) collector.
Scrapes portarias e resoluções from https://www.gov.br/anm/
"""
import logging
from datetime import datetime

from bs4 import BeautifulSoup

from app.collectors.base import BaseCollector
from app.models.normativo import FonteNormativo, SetorNormativo, TipoNormativo

logger = logging.getLogger(__name__)

ANM_BASE = "https://www.gov.br/anm/pt-br"
ANM_NORMAS_URL = f"{ANM_BASE}/assuntos/legislacao-e-normas"
ANM_PORTARIAS_URL = f"{ANM_BASE}/assuntos/legislacao-e-normas/portarias"
ANM_RESOLUCOES_URL = f"{ANM_BASE}/assuntos/legislacao-e-normas/resolucoes"
ANM_API_URL = "https://www.gov.br/anm/pt-br/assuntos/legislacao-e-normas/@@search"


def _detectar_tipo_anm(titulo: str) -> TipoNormativo:
    t = titulo.upper()
    if "RESOLUÇÃO" in t:
        return TipoNormativo.RESOLUCAO
    if "PORTARIA" in t:
        return TipoNormativo.PORTARIA
    if "INSTRUÇÃO NORMATIVA" in t:
        return TipoNormativo.INSTRUCAO_NORMATIVA
    return TipoNormativo.PORTARIA


class ANMCollector(BaseCollector):
    """Collects regulatory acts from ANM (mining agency)."""

    fonte = FonteNormativo.ANM

    async def coletar(self) -> list[dict]:
        results = []

        for url in [ANM_PORTARIAS_URL, ANM_RESOLUCOES_URL]:
            try:
                items = await self._coletar_pagina(url)
                results.extend(items)
            except Exception as exc:
                logger.warning(f"[ANM] Erro ao coletar de {url}: {exc}")

        if not results:
            try:
                items = await self._coletar_search_api()
                results.extend(items)
            except Exception as exc:
                logger.debug(f"[ANM] Search API falhou: {exc}")

        return results

    async def _coletar_pagina(self, url: str) -> list[dict]:
        try:
            resp = await self._get(url)
        except Exception as exc:
            logger.warning(f"[ANM] Falha no request {url}: {exc}")
            return []

        soup = BeautifulSoup(resp.text, "lxml")
        items = []

        # gov.br uses Plone CMS - look for listing items
        rows = (
            soup.select(".listing tr")
            or soup.select("article.tileItem")
            or soup.select(".summary")
            or soup.select("table.listing tbody tr")
        )

        for row in rows:
            try:
                link_el = row.select_one("a[href]")
                if not link_el:
                    continue

                titulo = link_el.get_text(strip=True)
                href = link_el.get("href", "")
                item_url = href if href.startswith("http") else f"{ANM_BASE}{href}"

                # Look for date in the row
                data_pub = None
                date_el = row.select_one(".listing-date, .documentModified, time")
                if date_el:
                    date_text = date_el.get("datetime") or date_el.get_text(strip=True)
                    data_pub = self._parse_date(date_text, "%Y-%m-%dT%H:%M:%S") or self._parse_date(
                        date_text, "%d/%m/%Y"
                    )

                desc_el = row.select_one(".description, .tileBody p")
                ementa = desc_el.get_text(strip=True) if desc_el else titulo[:300]

                if not titulo:
                    continue

                items.append(
                    {
                        "titulo": titulo[:1000],
                        "tipo": _detectar_tipo_anm(titulo),
                        "fonte": FonteNormativo.ANM,
                        "setor": SetorNormativo.MINERACAO,
                        "url": item_url,
                        "data_publicacao": data_pub or datetime.now(),
                        "ementa": ementa[:2000],
                        "conteudo_bruto": ementa,
                    }
                )
            except Exception as exc:
                logger.debug(f"[ANM] Erro ao parsear row: {exc}")

        return items

    async def _coletar_search_api(self) -> list[dict]:
        """Use Plone's @search endpoint for gov.br ANM."""
        url = "https://www.gov.br/anm/pt-br/@search"
        params = {
            "portal_type": "Document",
            "path": "/anm/pt-br/assuntos/legislacao-e-normas",
            "b_size": 30,
            "sort_on": "modified",
            "sort_order": "descending",
        }
        try:
            resp = await self._get(url, params=params)
            data = resp.json()
        except Exception:
            return []

        items = []
        for item in data.get("items", []):
            titulo = item.get("title", "Ato ANM")
            data_pub = self._parse_date(item.get("modified", ""), "%Y-%m-%dT%H:%M:%S%z")
            items.append(
                {
                    "titulo": titulo[:1000],
                    "tipo": _detectar_tipo_anm(titulo),
                    "fonte": FonteNormativo.ANM,
                    "setor": SetorNormativo.MINERACAO,
                    "url": item.get("@id") or ANM_BASE,
                    "data_publicacao": data_pub,
                    "ementa": item.get("description", "")[:2000],
                    "conteudo_bruto": item.get("description", ""),
                }
            )
        return items
