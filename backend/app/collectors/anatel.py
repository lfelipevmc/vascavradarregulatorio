"""
ANATEL (Agência Nacional de Telecomunicações) collector.
Uses ANATEL's open data portal and website.
"""
import logging
from datetime import datetime

from bs4 import BeautifulSoup

from app.collectors.base import BaseCollector
from app.models.normativo import FonteNormativo, SetorNormativo, TipoNormativo

logger = logging.getLogger(__name__)

ANATEL_BASE = "https://www.anatel.gov.br"
ANATEL_NORMAS_URL = f"{ANATEL_BASE}/legislacao/normas-e-regulamentos"
ANATEL_RESOLUCOES_URL = f"{ANATEL_BASE}/legislacao/resolucoes"
ANATEL_API_URL = "https://sistemas.anatel.gov.br/sacp/contribuicoes/api/pesquisar-ato"


def _detectar_tipo_anatel(titulo: str) -> TipoNormativo:
    t = titulo.upper()
    if "RESOLUÇÃO" in t:
        return TipoNormativo.RESOLUCAO
    if "PORTARIA" in t:
        return TipoNormativo.PORTARIA
    if "INSTRUÇÃO" in t:
        return TipoNormativo.INSTRUCAO_NORMATIVA
    if "LEI" in t:
        return TipoNormativo.LEI
    return TipoNormativo.RESOLUCAO


class ANATELCollector(BaseCollector):
    """Collects regulatory acts from ANATEL."""

    fonte = FonteNormativo.ANATEL

    async def coletar(self) -> list[dict]:
        results = []

        # Try ANATEL's SEI/SACP system API
        try:
            items = await self._coletar_sacp()
            results.extend(items)
        except Exception as exc:
            logger.warning(f"[ANATEL] SACP API falhou: {exc}")

        if not results:
            for url in [ANATEL_NORMAS_URL, ANATEL_RESOLUCOES_URL]:
                try:
                    items = await self._coletar_pagina(url)
                    results.extend(items)
                except Exception as exc:
                    logger.warning(f"[ANATEL] Erro ao coletar de {url}: {exc}")

        return results

    async def _coletar_sacp(self) -> list[dict]:
        """Collect from ANATEL's SACP regulatory acts system."""
        payload = {
            "pageSize": 30,
            "page": 1,
            "tipoAto": "",
            "statusAto": "VIGENTE",
        }
        try:
            resp = await self._post(ANATEL_API_URL, json=payload)
            data = resp.json()
        except Exception as exc:
            logger.debug(f"[ANATEL] SACP falhou: {exc}")
            return []

        items = []
        records = data.get("content", []) or data.get("data", []) or []

        for record in records:
            titulo = (
                record.get("tipoAto", "")
                + " "
                + str(record.get("numero", ""))
                + " - "
                + record.get("ementa", "")[:200]
            ).strip()

            data_pub = self._parse_date(record.get("dataPublicacao", ""), "%Y-%m-%d")

            items.append(
                {
                    "titulo": titulo[:1000] or "Ato ANATEL",
                    "tipo": _detectar_tipo_anatel(titulo),
                    "numero": str(record.get("numero", "")),
                    "fonte": FonteNormativo.ANATEL,
                    "setor": SetorNormativo.TELECOMUNICACOES,
                    "url": record.get("url") or record.get("linkAto") or ANATEL_BASE,
                    "data_publicacao": data_pub,
                    "ementa": record.get("ementa", "")[:2000],
                    "conteudo_bruto": record.get("ementa", ""),
                }
            )

        return items

    async def _coletar_pagina(self, url: str) -> list[dict]:
        try:
            resp = await self._get(url)
        except Exception as exc:
            logger.warning(f"[ANATEL] Falha no request {url}: {exc}")
            return []

        soup = BeautifulSoup(resp.text, "lxml")
        items = []

        rows = (
            soup.select("table tbody tr")
            or soup.select(".views-row")
            or soup.select(".field-items .field-item")
        )

        for row in rows:
            try:
                link_el = row.select_one("a[href]")
                if not link_el:
                    continue

                titulo = link_el.get_text(strip=True)
                href = link_el.get("href", "")
                item_url = href if href.startswith("http") else f"{ANATEL_BASE}{href}"

                cells = row.select("td")
                data_pub = None
                for cell in cells:
                    text = cell.get_text(strip=True)
                    parsed = self._parse_date(text)
                    if parsed:
                        data_pub = parsed
                        break

                if not titulo:
                    continue

                items.append(
                    {
                        "titulo": titulo[:1000],
                        "tipo": _detectar_tipo_anatel(titulo),
                        "fonte": FonteNormativo.ANATEL,
                        "setor": SetorNormativo.TELECOMUNICACOES,
                        "url": item_url,
                        "data_publicacao": data_pub or datetime.now(),
                        "ementa": titulo[:500],
                        "conteudo_bruto": titulo,
                    }
                )
            except Exception as exc:
                logger.debug(f"[ANATEL] Erro ao parsear row: {exc}")

        return items
