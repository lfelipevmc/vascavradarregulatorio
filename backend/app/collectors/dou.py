"""
DOU (Diário Oficial da União) collector.
Uses the InLabs API: https://inlabs.in.gov.br/
API documentation: https://inlabs.in.gov.br/acesso-api/
"""
import logging
from datetime import date, datetime, timedelta

from bs4 import BeautifulSoup

from app.collectors.base import BaseCollector
from app.config import settings
from app.models.normativo import FonteNormativo, SetorNormativo, TipoNormativo

logger = logging.getLogger(__name__)

INLABS_SEARCH_URL = "https://www.in.gov.br/consulta/-/buscar/dou"
INLABS_API_BASE = "https://inlabs.in.gov.br"

TIPO_MAP = {
    "Lei": TipoNormativo.LEI,
    "Decreto": TipoNormativo.DECRETO,
    "Portaria": TipoNormativo.PORTARIA,
    "Resolução": TipoNormativo.RESOLUCAO,
    "Instrução Normativa": TipoNormativo.INSTRUCAO_NORMATIVA,
    "Medida Provisória": TipoNormativo.MEDIDA_PROVISORIA,
}

SETOR_KEYWORDS = {
    SetorNormativo.ENERGIA: ["energia", "elétric", "ANEEL", "petróleo", "gás", "combustível", "geração", "transmissão"],
    SetorNormativo.TRANSPORTE: ["transporte", "rodovia", "ferrovi", "ANTT", "porto", "aquaviário", "logística"],
    SetorNormativo.AVIACAO: ["aviação", "aeronáut", "ANAC", "aeroporto", "aeronavegab"],
    SetorNormativo.MINERACAO: ["mineração", "minério", "ANM", "DNPM", "extração mineral"],
    SetorNormativo.TELECOMUNICACOES: ["telecomunicações", "ANATEL", "radiofrequência", "banda larga", "5G", "internet"],
    SetorNormativo.SANEAMENTO: ["saneamento", "água", "esgoto", "resíduo", "ANA"],
    SetorNormativo.ESPORTE: ["esporte", "desporto", "futebol", "clube", "atleta", "competição"],
}


def _detectar_setor(texto: str) -> SetorNormativo:
    texto_lower = texto.lower()
    for setor, keywords in SETOR_KEYWORDS.items():
        if any(kw.lower() in texto_lower for kw in keywords):
            return setor
    return SetorNormativo.GERAL


def _detectar_tipo(titulo: str) -> TipoNormativo:
    titulo_upper = titulo.upper()
    if "LEI Nº" in titulo_upper or titulo_upper.startswith("LEI "):
        return TipoNormativo.LEI
    if "DECRETO" in titulo_upper:
        return TipoNormativo.DECRETO
    if "MEDIDA PROVISÓRIA" in titulo_upper or "MP Nº" in titulo_upper:
        return TipoNormativo.MEDIDA_PROVISORIA
    if "INSTRUÇÃO NORMATIVA" in titulo_upper:
        return TipoNormativo.INSTRUCAO_NORMATIVA
    if "RESOLUÇÃO" in titulo_upper:
        return TipoNormativo.RESOLUCAO
    if "PORTARIA" in titulo_upper:
        return TipoNormativo.PORTARIA
    return TipoNormativo.PORTARIA


class DOUCollector(BaseCollector):
    """Collects normativos from Diário Oficial da União via InLabs search API."""

    fonte = FonteNormativo.DOU

    async def coletar(self) -> list[dict]:
        results = []
        today = date.today()
        yesterday = today - timedelta(days=1)

        for keyword in settings.dou_search_keywords[:5]:  # limit to avoid rate limiting
            try:
                items = await self._buscar_por_keyword(keyword, yesterday)
                results.extend(items)
            except Exception as exc:
                logger.warning(f"[DOU] Erro ao buscar keyword '{keyword}': {exc}")

        # Deduplicate by URL within this batch
        seen_urls = set()
        unique = []
        for item in results:
            url = item.get("url", "")
            if url and url not in seen_urls:
                seen_urls.add(url)
                unique.append(item)
            elif not url:
                unique.append(item)

        logger.info(f"[DOU] Total coletado: {len(unique)} itens únicos")
        return unique

    async def _buscar_por_keyword(self, keyword: str, data: date) -> list[dict]:
        """Search DOU via the public search endpoint."""
        data_str = data.strftime("%d-%m-%Y")
        params = {
            "q": keyword,
            "exactDate": data_str,
            "sortType": "0",
            "delta": "20",
            "currentPage": "1",
        }

        try:
            resp = await self._get(INLABS_SEARCH_URL, params=params)
        except Exception as exc:
            logger.warning(f"[DOU] Falha no request para keyword '{keyword}': {exc}")
            return []

        soup = BeautifulSoup(resp.text, "lxml")
        items = []

        # Parse result cards from the DOU search results page
        for card in soup.select(".resultado-card, .search-results-item, article.resultado"):
            try:
                titulo_el = card.select_one("h2, h3, .titulo, .resultado-titulo")
                titulo = titulo_el.get_text(strip=True) if titulo_el else "Sem título"

                link_el = card.select_one("a[href]")
                url = ""
                if link_el:
                    href = link_el.get("href", "")
                    url = href if href.startswith("http") else f"https://www.in.gov.br{href}"

                ementa_el = card.select_one(".resultado-ementa, .ementa, p")
                ementa = ementa_el.get_text(strip=True) if ementa_el else ""

                data_el = card.select_one(".data-publicacao, time, .date")
                data_pub = None
                if data_el:
                    date_text = data_el.get("datetime") or data_el.get_text(strip=True)
                    data_pub = self._parse_date(date_text, "%Y-%m-%d") or self._parse_date(
                        date_text, "%d/%m/%Y"
                    )

                tipo = _detectar_tipo(titulo)
                setor = _detectar_setor(f"{titulo} {ementa}")

                if not titulo or titulo == "Sem título":
                    continue

                items.append(
                    {
                        "titulo": titulo[:1000],
                        "tipo": tipo,
                        "fonte": FonteNormativo.DOU,
                        "setor": setor,
                        "url": url,
                        "ementa": ementa[:2000] if ementa else None,
                        "data_publicacao": data_pub or datetime.combine(data, datetime.min.time()),
                        "conteudo_bruto": ementa,
                    }
                )
            except Exception as exc:
                logger.debug(f"[DOU] Erro ao parsear card: {exc}")

        # Also try JSON endpoint (alternative DOU API approach)
        if not items:
            items = await self._buscar_api_json(keyword, data)

        return items

    async def _buscar_api_json(self, keyword: str, data: date) -> list[dict]:
        """Fallback: try DOU's internal JSON API."""
        data_str = data.strftime("%Y-%m-%d")
        url = f"https://www.in.gov.br/leiturajornal/data/dou-v4/secao1/{data_str}/index.json"

        try:
            resp = await self._get(url)
            data_json = resp.json()
        except Exception:
            return []

        items = []
        keyword_lower = keyword.lower()

        for item in data_json.get("content", []):
            titulo = item.get("title", "")
            identifica = item.get("identifica", "")
            full_text = f"{titulo} {identifica} {item.get('ementa', '')}"

            if keyword_lower not in full_text.lower():
                continue

            tipo = _detectar_tipo(identifica or titulo)
            setor = _detectar_setor(full_text)
            pub_date = self._parse_date(item.get("pubDate", ""), "%Y-%m-%dT%H:%M:%S")

            item_url = item.get("urlTitle", "")
            if item_url and not item_url.startswith("http"):
                item_url = f"https://www.in.gov.br{item_url}"

            items.append(
                {
                    "titulo": (identifica or titulo)[:1000],
                    "tipo": tipo,
                    "fonte": FonteNormativo.DOU,
                    "setor": setor,
                    "url": item_url,
                    "ementa": item.get("ementa", "")[:2000],
                    "data_publicacao": pub_date or datetime.combine(data, datetime.min.time()),
                    "conteudo_bruto": item.get("body", ""),
                }
            )

        return items
