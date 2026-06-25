"""
STJ (Superior Tribunal de Justiça) and STF (Supremo Tribunal Federal) collector.
Scrapes jurisprudência related to infrastructure regulation.
"""
import logging
from datetime import datetime

from bs4 import BeautifulSoup

from app.collectors.base import BaseCollector
from app.models.normativo import FonteNormativo, SetorNormativo, TipoNormativo

logger = logging.getLogger(__name__)

STJ_PESQUISA_URL = "https://scon.stj.jus.br/SCON/pesquisar.jsp"
STJ_API_URL = "https://scon.stj.jus.br/SCON/juri/pesquisar"
STF_PESQUISA_URL = "https://portal.stf.jus.br/jurisprudencia/pesquisarJurisprudencia.asp"
STF_API_URL = "https://jurisprudencia.stf.jus.br/api/search/search"

INFRA_KEYWORDS = [
    "agência reguladora",
    "concessão de serviço público",
    "ANEEL",
    "ANTT",
    "ANATEL",
    "ANAC",
    "ANM",
    "regulação econômica",
    "tarifa",
]

SETOR_MAP = {
    "aneel": SetorNormativo.ENERGIA,
    "energia": SetorNormativo.ENERGIA,
    "antt": SetorNormativo.TRANSPORTE,
    "transport": SetorNormativo.TRANSPORTE,
    "anac": SetorNormativo.AVIACAO,
    "aviação": SetorNormativo.AVIACAO,
    "anatel": SetorNormativo.TELECOMUNICACOES,
    "telecom": SetorNormativo.TELECOMUNICACOES,
    "anm": SetorNormativo.MINERACAO,
    "mineração": SetorNormativo.MINERACAO,
    "saneamento": SetorNormativo.SANEAMENTO,
}


def _detectar_setor(texto: str) -> SetorNormativo:
    texto_lower = texto.lower()
    for keyword, setor in SETOR_MAP.items():
        if keyword in texto_lower:
            return setor
    return SetorNormativo.GERAL


class STJSTFCollector(BaseCollector):
    """Collects relevant precedents from STJ and STF."""

    fonte = FonteNormativo.STJ  # will be overridden per item

    async def coletar(self) -> list[dict]:
        results = []

        # Collect from STJ
        for keyword in INFRA_KEYWORDS[:4]:
            try:
                items = await self._buscar_stj(keyword)
                results.extend(items)
            except Exception as exc:
                logger.warning(f"[STJ] Erro ao buscar '{keyword}': {exc}")

        # Collect from STF
        for keyword in INFRA_KEYWORDS[:4]:
            try:
                items = await self._buscar_stf(keyword)
                results.extend(items)
            except Exception as exc:
                logger.warning(f"[STF] Erro ao buscar '{keyword}': {exc}")

        # Deduplicate
        seen = set()
        unique = []
        for item in results:
            key = item.get("url", "") or item.get("titulo", "")[:80]
            if key not in seen:
                seen.add(key)
                unique.append(item)

        logger.info(f"[STJ/STF] Total coletado: {len(unique)} precedentes")
        return unique

    async def _buscar_stj(self, keyword: str) -> list[dict]:
        """Search STJ jurisprudência."""
        params = {
            "b": "ACOR",
            "thesaurus": "JURIDICO",
            "p": "true",
            "l": "10",
            "i": "1",
            "operador": "e",
            "q": keyword,
            "tp": "T",
        }

        try:
            resp = await self._get(STJ_PESQUISA_URL, params=params)
        except Exception as exc:
            logger.debug(f"[STJ] Request falhou para '{keyword}': {exc}")
            return []

        soup = BeautifulSoup(resp.text, "lxml")
        items = []

        for resultado in soup.select(".resultado, .resultSearch, .jurisprudencia-item"):
            try:
                titulo_el = resultado.select_one(".tituloDocumento, h3, .ementa-titulo")
                titulo = titulo_el.get_text(strip=True) if titulo_el else ""

                ementa_el = resultado.select_one(".ementa, .ementaDocumento, p")
                ementa = ementa_el.get_text(strip=True) if ementa_el else ""

                link_el = resultado.select_one("a[href]")
                item_url = ""
                if link_el:
                    href = link_el.get("href", "")
                    item_url = href if href.startswith("http") else f"https://scon.stj.jus.br{href}"

                date_el = resultado.select_one(".dataDoc, .date, time")
                data_pub = None
                if date_el:
                    data_pub = self._parse_date(date_el.get_text(strip=True))

                if not titulo and not ementa:
                    continue

                full_text = f"{titulo} {ementa}"
                setor = _detectar_setor(full_text)

                items.append(
                    {
                        "titulo": (titulo or f"STJ - {keyword}")[:1000],
                        "tipo": TipoNormativo.PRECEDENTE_JUDICIAL,
                        "fonte": FonteNormativo.STJ,
                        "setor": setor,
                        "url": item_url or STJ_PESQUISA_URL,
                        "data_publicacao": data_pub or datetime.now(),
                        "ementa": ementa[:2000],
                        "conteudo_bruto": full_text,
                    }
                )
            except Exception as exc:
                logger.debug(f"[STJ] Erro ao parsear resultado: {exc}")

        return items

    async def _buscar_stf(self, keyword: str) -> list[dict]:
        """Search STF jurisprudência via API."""
        payload = {
            "andSearch": True,
            "pageSize": 10,
            "page": 0,
            "queryString": keyword,
            "sort": "relevance",
            "classe": "",
            "ministro": "",
            "origem": "",
        }

        try:
            resp = await self._post(
                STF_API_URL,
                json=payload,
                headers={"Content-Type": "application/json", "Accept": "application/json"},
            )
            data = resp.json()
        except Exception as exc:
            logger.debug(f"[STF] API falhou para '{keyword}': {exc}")
            # Fallback to HTML scraping
            return await self._buscar_stf_html(keyword)

        items = []
        hits = data.get("hits", {}).get("hits", []) or data.get("results", [])

        for hit in hits:
            source = hit.get("_source", hit)
            titulo = source.get("classProcessual", "") + " " + source.get("numeroProcesso", "")
            ementa = source.get("ementa", "")
            relator = source.get("relator", "")
            data_str = source.get("dataPublicacaoDJ", "") or source.get("data", "")
            data_pub = self._parse_date(data_str, "%Y-%m-%d")

            processo_id = source.get("numeroProcesso", "")
            item_url = (
                f"https://portal.stf.jus.br/processos/detalhe.asp?incidente={processo_id}"
                if processo_id
                else "https://portal.stf.jus.br"
            )

            full_text = f"{titulo} {ementa}"
            setor = _detectar_setor(full_text)

            conteudo = f"Processo: {titulo}\nRelator: {relator}\nEmenta: {ementa}"

            items.append(
                {
                    "titulo": (titulo.strip() or f"STF - {keyword}")[:1000],
                    "tipo": TipoNormativo.PRECEDENTE_JUDICIAL,
                    "fonte": FonteNormativo.STF,
                    "setor": setor,
                    "url": item_url,
                    "data_publicacao": data_pub or datetime.now(),
                    "ementa": ementa[:2000],
                    "conteudo_bruto": conteudo,
                }
            )

        return items

    async def _buscar_stf_html(self, keyword: str) -> list[dict]:
        """Fallback HTML scraping for STF."""
        params = {
            "andSearch": "true",
            "queryString": keyword,
        }
        try:
            resp = await self._get(STF_PESQUISA_URL, params=params)
        except Exception:
            return []

        soup = BeautifulSoup(resp.text, "lxml")
        items = []

        for resultado in soup.select(".resultado-item, .jurisprudencia-card, tr.resultado"):
            try:
                link_el = resultado.select_one("a[href]")
                if not link_el:
                    continue
                titulo = link_el.get_text(strip=True)
                href = link_el.get("href", "")
                item_url = href if href.startswith("http") else f"https://portal.stf.jus.br{href}"

                ementa_el = resultado.select_one(".ementa, p")
                ementa = ementa_el.get_text(strip=True) if ementa_el else ""

                setor = _detectar_setor(f"{titulo} {ementa}")

                items.append(
                    {
                        "titulo": titulo[:1000],
                        "tipo": TipoNormativo.PRECEDENTE_JUDICIAL,
                        "fonte": FonteNormativo.STF,
                        "setor": setor,
                        "url": item_url,
                        "data_publicacao": datetime.now(),
                        "ementa": ementa[:2000],
                        "conteudo_bruto": f"{titulo} {ementa}",
                    }
                )
            except Exception as exc:
                logger.debug(f"[STF] Erro ao parsear resultado: {exc}")

        return items
