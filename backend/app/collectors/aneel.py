"""
ANEEL (Agência Nacional de Energia Elétrica) collector.
Scrapes resoluções e despachos from https://www.aneel.gov.br/normas-e-atos-regulativos
"""
import logging
from datetime import datetime

from bs4 import BeautifulSoup

from app.collectors.base import BaseCollector
from app.models.normativo import FonteNormativo, SetorNormativo, TipoNormativo

logger = logging.getLogger(__name__)

ANEEL_BASE = "https://www.aneel.gov.br"
ANEEL_NORMAS_URL = f"{ANEEL_BASE}/normas-e-atos-regulativos"
ANEEL_RESOLUCOES_URL = f"{ANEEL_BASE}/resolucoes-normativas"
ANEEL_DESPACHOS_URL = f"{ANEEL_BASE}/despachos"


def _detectar_tipo_aneel(titulo: str) -> TipoNormativo:
    t = titulo.upper()
    if "RESOLUÇÃO NORMATIVA" in t or "REN" in t:
        return TipoNormativo.RESOLUCAO
    if "RESOLUÇÃO AUTORIZATIVA" in t or "REA" in t:
        return TipoNormativo.RESOLUCAO
    if "PORTARIA" in t:
        return TipoNormativo.PORTARIA
    if "INSTRUÇÃO NORMATIVA" in t:
        return TipoNormativo.INSTRUCAO_NORMATIVA
    if "DESPACHO" in t:
        return TipoNormativo.PORTARIA
    return TipoNormativo.RESOLUCAO


class ANEELCollector(BaseCollector):
    """Collects regulatory acts from ANEEL."""

    fonte = FonteNormativo.ANEEL

    async def coletar(self) -> list[dict]:
        results = []

        for url in [ANEEL_NORMAS_URL, ANEEL_RESOLUCOES_URL]:
            try:
                items = await self._coletar_pagina(url)
                results.extend(items)
            except Exception as exc:
                logger.warning(f"[ANEEL] Erro ao coletar de {url}: {exc}")

        return results

    async def _coletar_pagina(self, url: str) -> list[dict]:
        try:
            resp = await self._get(url)
        except Exception as exc:
            logger.warning(f"[ANEEL] Falha no request {url}: {exc}")
            return []

        soup = BeautifulSoup(resp.text, "lxml")
        items = []

        # ANEEL uses various table/list layouts; try multiple selectors
        rows = (
            soup.select("table.table tbody tr")
            or soup.select(".list-group .list-group-item")
            or soup.select("article.normativo")
            or soup.select(".portlet-body table tr")
        )

        for row in rows:
            try:
                cells = row.select("td")
                if len(cells) >= 2:
                    # Table layout: number | date | title | link
                    titulo_cell = cells[-2] if len(cells) > 2 else cells[0]
                    titulo = titulo_cell.get_text(strip=True)

                    link_el = row.select_one("a[href]")
                    item_url = ""
                    if link_el:
                        href = link_el.get("href", "")
                        item_url = href if href.startswith("http") else f"{ANEEL_BASE}{href}"

                    # Try to find date
                    data_pub = None
                    for cell in cells:
                        text = cell.get_text(strip=True)
                        parsed = self._parse_date(text)
                        if parsed:
                            data_pub = parsed
                            break

                    numero = cells[0].get_text(strip=True) if cells else None

                else:
                    # List layout
                    link_el = row.select_one("a")
                    if not link_el:
                        continue
                    titulo = link_el.get_text(strip=True)
                    href = link_el.get("href", "")
                    item_url = href if href.startswith("http") else f"{ANEEL_BASE}{href}"
                    data_pub = None
                    numero = None

                if not titulo:
                    continue

                tipo = _detectar_tipo_aneel(titulo)

                items.append(
                    {
                        "titulo": titulo[:1000],
                        "tipo": tipo,
                        "numero": numero,
                        "fonte": FonteNormativo.ANEEL,
                        "setor": SetorNormativo.ENERGIA,
                        "url": item_url,
                        "data_publicacao": data_pub or datetime.now(),
                        "conteudo_bruto": titulo,
                        "ementa": titulo[:500],
                    }
                )
            except Exception as exc:
                logger.debug(f"[ANEEL] Erro ao parsear row: {exc}")

        # If table parsing yielded nothing, try fetching via ANEEL's search API
        if not items:
            items = await self._coletar_api()

        return items

    async def _coletar_api(self) -> list[dict]:
        """Try ANEEL's open data API for resoluções."""
        api_url = "https://dadosabertos.aneel.gov.br/api/3/action/datastore_search"
        params = {
            "resource_id": "b1bd71e7-d0ad-4214-9053-cbd58e9564a7",
            "limit": 50,
            "sort": "DatPublicacaoDOU desc",
        }

        try:
            resp = await self._get(api_url, params=params)
            data = resp.json()
        except Exception as exc:
            logger.debug(f"[ANEEL] API fallback falhou: {exc}")
            return []

        items = []
        records = data.get("result", {}).get("records", [])

        for record in records:
            titulo = (
                record.get("DscTipoDocumento", "")
                + " "
                + record.get("NomDispositivo", "")
                + " - "
                + record.get("DscEmenta", "")[:200]
            ).strip()

            data_pub = self._parse_date(record.get("DatPublicacaoDOU", ""), "%Y-%m-%dT%H:%M:%S")

            items.append(
                {
                    "titulo": titulo[:1000] or "Resolução ANEEL",
                    "tipo": TipoNormativo.RESOLUCAO,
                    "numero": record.get("NomDispositivo"),
                    "fonte": FonteNormativo.ANEEL,
                    "setor": SetorNormativo.ENERGIA,
                    "url": record.get("UrlDocumento") or ANEEL_BASE,
                    "data_publicacao": data_pub,
                    "ementa": record.get("DscEmenta", "")[:2000],
                    "conteudo_bruto": record.get("DscEmenta", ""),
                }
            )

        return items
