"""
ANAC (Agência Nacional de Aviação Civil) collector.
Scrapes resoluções e regulamentos from https://www.anac.gov.br
"""
import logging
from datetime import datetime

from bs4 import BeautifulSoup

from app.collectors.base import BaseCollector
from app.models.normativo import FonteNormativo, SetorNormativo, TipoNormativo

logger = logging.getLogger(__name__)

ANAC_BASE = "https://www.anac.gov.br"
ANAC_RESOLUCOES_URL = f"{ANAC_BASE}/assuntos/legislacao/resolucao"
ANAC_RBAC_URL = f"{ANAC_BASE}/assuntos/legislacao/regulamento-brasileiro-da-aviacao-civil-rbac"
ANAC_PORTARIAS_URL = f"{ANAC_BASE}/assuntos/legislacao/portaria"


def _detectar_tipo_anac(titulo: str) -> TipoNormativo:
    t = titulo.upper()
    if "RESOLUÇÃO" in t:
        return TipoNormativo.RESOLUCAO
    if "PORTARIA" in t:
        return TipoNormativo.PORTARIA
    if "INSTRUÇÃO" in t:
        return TipoNormativo.INSTRUCAO_NORMATIVA
    if "RBAC" in t or "REGULAMENTO" in t:
        return TipoNormativo.RESOLUCAO
    return TipoNormativo.RESOLUCAO


class ANACCollector(BaseCollector):
    """Collects regulatory acts from ANAC."""

    fonte = FonteNormativo.ANAC

    async def coletar(self) -> list[dict]:
        results = []

        for url in [ANAC_RESOLUCOES_URL, ANAC_PORTARIAS_URL]:
            try:
                items = await self._coletar_pagina(url)
                results.extend(items)
            except Exception as exc:
                logger.warning(f"[ANAC] Erro ao coletar de {url}: {exc}")

        # Try ANAC open data
        try:
            items = await self._coletar_dados_abertos()
            results.extend(items)
        except Exception as exc:
            logger.debug(f"[ANAC] Dados abertos falhou: {exc}")

        return results

    async def _coletar_pagina(self, url: str) -> list[dict]:
        try:
            resp = await self._get(url)
        except Exception as exc:
            logger.warning(f"[ANAC] Falha no request {url}: {exc}")
            return []

        soup = BeautifulSoup(resp.text, "lxml")
        items = []

        rows = (
            soup.select("table tbody tr")
            or soup.select(".tileItem")
            or soup.select(".listing tbody tr")
            or soup.select("article.ato-normativo")
        )

        for row in rows:
            try:
                link_el = row.select_one("a[href]")
                if not link_el:
                    continue

                titulo = link_el.get_text(strip=True)
                href = link_el.get("href", "")
                item_url = href if href.startswith("http") else f"{ANAC_BASE}{href}"

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
                        "tipo": _detectar_tipo_anac(titulo),
                        "numero": numero,
                        "fonte": FonteNormativo.ANAC,
                        "setor": SetorNormativo.AVIACAO,
                        "url": item_url,
                        "data_publicacao": data_pub or datetime.now(),
                        "ementa": titulo[:500],
                        "conteudo_bruto": titulo,
                    }
                )
            except Exception as exc:
                logger.debug(f"[ANAC] Erro ao parsear row: {exc}")

        return items

    async def _coletar_dados_abertos(self) -> list[dict]:
        """Fetch from ANAC's open data API."""
        url = "https://dados.anac.gov.br/api/3/action/datastore_search"
        params = {
            "resource_id": "normas-anac",
            "limit": 30,
        }
        try:
            resp = await self._get(url, params=params)
            data = resp.json()
            records = data.get("result", {}).get("records", [])
        except Exception:
            return []

        items = []
        for record in records:
            titulo = record.get("titulo") or record.get("descricao") or "Ato ANAC"
            data_pub = self._parse_date(record.get("data_publicacao", ""), "%Y-%m-%d")
            items.append(
                {
                    "titulo": titulo[:1000],
                    "tipo": _detectar_tipo_anac(titulo),
                    "numero": record.get("numero"),
                    "fonte": FonteNormativo.ANAC,
                    "setor": SetorNormativo.AVIACAO,
                    "url": record.get("url") or ANAC_BASE,
                    "data_publicacao": data_pub,
                    "ementa": record.get("ementa", "")[:2000],
                    "conteudo_bruto": record.get("ementa", ""),
                }
            )
        return items
