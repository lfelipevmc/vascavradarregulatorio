"""
TCU (Tribunal de Contas da União) collector.
Uses TCU's jurisprudência search API: https://pesquisa.apps.tcu.gov.br/
"""
import logging
from datetime import datetime

from app.collectors.base import BaseCollector
from app.models.normativo import FonteNormativo, SetorNormativo, TipoNormativo

logger = logging.getLogger(__name__)

TCU_SEARCH_API = "https://pesquisa.apps.tcu.gov.br/rest/acordao/smb/dsa"
TCU_SOLR_API = "https://pesquisa.apps.tcu.gov.br/rest/acordao/smb"
TCU_BASE_URL = "https://pesquisa.apps.tcu.gov.br"

INFRA_KEYWORDS = [
    "infraestrutura",
    "concessão",
    "energia elétrica",
    "telecomunicações",
    "aeroporto",
    "ferrovia",
    "rodovia",
    "porto",
    "saneamento",
    "mineração",
    "petróleo",
    "licitação",
    "regulação",
]

SETOR_MAP = {
    "energia": SetorNormativo.ENERGIA,
    "elétric": SetorNormativo.ENERGIA,
    "petróleo": SetorNormativo.ENERGIA,
    "gás": SetorNormativo.ENERGIA,
    "telecom": SetorNormativo.TELECOMUNICACOES,
    "anatel": SetorNormativo.TELECOMUNICACOES,
    "aeroporto": SetorNormativo.AVIACAO,
    "aviação": SetorNormativo.AVIACAO,
    "anac": SetorNormativo.AVIACAO,
    "ferrovia": SetorNormativo.TRANSPORTE,
    "rodovia": SetorNormativo.TRANSPORTE,
    "porto": SetorNormativo.TRANSPORTE,
    "antt": SetorNormativo.TRANSPORTE,
    "mineração": SetorNormativo.MINERACAO,
    "anm": SetorNormativo.MINERACAO,
    "saneamento": SetorNormativo.SANEAMENTO,
}


def _detectar_setor_tcu(texto: str) -> SetorNormativo:
    texto_lower = texto.lower()
    for keyword, setor in SETOR_MAP.items():
        if keyword in texto_lower:
            return setor
    return SetorNormativo.GERAL


class TCUCollector(BaseCollector):
    """Collects TCU acórdãos related to infrastructure regulation."""

    fonte = FonteNormativo.TCU

    async def coletar(self) -> list[dict]:
        results = []

        for keyword in INFRA_KEYWORDS[:6]:  # limit API calls
            try:
                items = await self._buscar_acordaos(keyword)
                results.extend(items)
            except Exception as exc:
                logger.warning(f"[TCU] Erro ao buscar '{keyword}': {exc}")

        # Deduplicate by URL
        seen = set()
        unique = []
        for item in results:
            key = item.get("url") or item.get("titulo", "")[:100]
            if key not in seen:
                seen.add(key)
                unique.append(item)

        logger.info(f"[TCU] Total coletado: {len(unique)} acórdãos únicos")
        return unique

    async def _buscar_acordaos(self, keyword: str) -> list[dict]:
        """Search TCU jurisprudence using the Solr-based API."""
        # TCU uses a Solr REST API
        params = {
            "q": keyword,
            "facet": "false",
            "start": 0,
            "rows": 20,
            "sort": "dataAcordao desc",
            "fl": "id,colegiado,numero,anoPlenario,ementa,relator,dataAcordao,processo,tipoProcesso",
        }

        try:
            resp = await self._get(TCU_SOLR_API, params=params)
            data = resp.json()
        except Exception as exc:
            logger.debug(f"[TCU] Solr API falhou para '{keyword}': {exc}")
            return await self._buscar_api_alternativa(keyword)

        items = []
        docs = data.get("response", {}).get("docs", []) or data.get("docs", []) or []

        for doc in docs:
            numero = doc.get("numero") or doc.get("numeroacordao", "")
            ano = doc.get("anoPlenario") or doc.get("anoAcordao", "")
            colegiado = doc.get("colegiado", "Plenário")
            titulo = f"Acórdão TCU {numero}/{ano} - {colegiado}"

            ementa = doc.get("ementa", "")
            processo = doc.get("processo", "")
            relator = doc.get("relator", "")

            doc_id = doc.get("id") or doc.get("chaveAcordao", "")
            item_url = f"{TCU_BASE_URL}/#/documento/acordao-completo/{doc_id}" if doc_id else TCU_BASE_URL

            data_str = doc.get("dataAcordao", "")
            data_pub = self._parse_date(data_str, "%Y-%m-%dT%H:%M:%SZ") or self._parse_date(
                data_str, "%d/%m/%Y"
            )

            setor = _detectar_setor_tcu(f"{titulo} {ementa}")
            conteudo = f"Processo: {processo}\nRelator: {relator}\nEmenta: {ementa}"

            items.append(
                {
                    "titulo": titulo[:1000],
                    "tipo": TipoNormativo.ACORDAO_TCU,
                    "numero": f"{numero}/{ano}",
                    "fonte": FonteNormativo.TCU,
                    "setor": setor,
                    "url": item_url,
                    "data_publicacao": data_pub or datetime.now(),
                    "ementa": ementa[:2000],
                    "conteudo_bruto": conteudo,
                }
            )

        return items

    async def _buscar_api_alternativa(self, keyword: str) -> list[dict]:
        """Alternative TCU API endpoint."""
        url = "https://pesquisa.apps.tcu.gov.br/rest/acordao/smb/dsa"
        payload = {
            "pesquisa": keyword,
            "colegiado": "",
            "dataInicio": "",
            "dataFim": "",
            "paginacao": {"pagina": 1, "tamanhoPagina": 20},
            "ordenacao": "dataAcordao",
        }

        try:
            resp = await self._post(url, json=payload)
            data = resp.json()
        except Exception as exc:
            logger.debug(f"[TCU] API alternativa falhou: {exc}")
            return []

        items = []
        acordaos = data.get("dados", []) or data.get("acordaos", []) or data.get("results", [])

        for doc in acordaos:
            numero = doc.get("numero", "") or doc.get("numeroacordao", "")
            ano = doc.get("ano", "") or doc.get("anoAcordao", "")
            titulo = f"Acórdão TCU {numero}/{ano}"
            ementa = doc.get("ementa", "")
            setor = _detectar_setor_tcu(f"{titulo} {ementa}")
            data_str = doc.get("dataAcordao", "") or doc.get("data", "")
            data_pub = self._parse_date(data_str, "%d/%m/%Y")

            items.append(
                {
                    "titulo": titulo[:1000],
                    "tipo": TipoNormativo.ACORDAO_TCU,
                    "numero": f"{numero}/{ano}",
                    "fonte": FonteNormativo.TCU,
                    "setor": setor,
                    "url": TCU_BASE_URL,
                    "data_publicacao": data_pub or datetime.now(),
                    "ementa": ementa[:2000],
                    "conteudo_bruto": ementa,
                }
            )

        return items
