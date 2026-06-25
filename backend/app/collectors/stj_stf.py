"""
STJ (Superior Tribunal de Justiça) and STF (Supremo Tribunal Federal) collector.
Uses REST APIs — no HTML scraping to avoid timeouts.
"""
import logging
from datetime import datetime

import httpx

from app.collectors.base import BaseCollector
from app.models.normativo import FonteNormativo, SetorNormativo, TipoNormativo

logger = logging.getLogger(__name__)

STJ_API_URL = "https://scon.stj.jus.br/SCON/juri/pesquisar"
STF_API_URL = "https://jurisprudencia.stf.jus.br/api/search/search"

# Limit keywords to avoid timeout (each query = 1 HTTP call)
INFRA_KEYWORDS = [
    "agência reguladora",
    "concessão de serviço público",
    "ANEEL",
    "ANTT",
]

SETOR_MAP = {
    "aneel": SetorNormativo.ENERGIA,
    "energia": SetorNormativo.ENERGIA,
    "antt": SetorNormativo.TRANSPORTE,
    "anac": SetorNormativo.AVIACAO,
    "anatel": SetorNormativo.TELECOMUNICACOES,
    "anm": SetorNormativo.MINERACAO,
    "saneamento": SetorNormativo.SANEAMENTO,
}


def _detectar_setor(texto: str) -> SetorNormativo:
    texto_lower = texto.lower()
    for keyword, setor in SETOR_MAP.items():
        if keyword in texto_lower:
            return setor
    return SetorNormativo.GERAL


class STJSTFCollector(BaseCollector):
    """Collects relevant precedents from STJ and STF via REST APIs."""

    fonte = FonteNormativo.STJ

    async def coletar(self) -> list[dict]:
        results = []

        for keyword in INFRA_KEYWORDS:
            try:
                items = await self._buscar_stj(keyword)
                results.extend(items)
            except Exception as exc:
                logger.warning(f"[STJ] Erro ao buscar '{keyword}': {exc}")

        try:
            stf_items = await self._buscar_stf("agência reguladora infraestrutura")
            results.extend(stf_items)
        except Exception as exc:
            logger.warning(f"[STF] Erro: {exc}")

        # Deduplicate by URL
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
        """Search STJ via REST JSON API."""
        params = {
            "b": "ACOR",
            "p": "true",
            "l": "10",
            "i": "1",
            "operador": "e",
            "q": keyword,
            "tp": "T",
            "outputType": "json",
        }
        try:
            async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
                resp = await client.get(STJ_API_URL, params=params, headers={"Accept": "application/json"})
            if resp.status_code != 200:
                logger.warning(f"[STJ] HTTP {resp.status_code} para '{keyword}'")
                return []
            data = resp.json()
        except Exception as exc:
            logger.warning(f"[STJ] Request falhou para '{keyword}': {exc}")
            return []

        items = []
        documentos = data.get("documentos", []) or data.get("results", []) or []

        for doc in documentos:
            ementa = doc.get("ementa", "") or doc.get("txtEmenta", "") or ""
            titulo = doc.get("orgao", "") + " " + doc.get("numDoc", "")
            setor = _detectar_setor(f"{titulo} {ementa}")
            data_str = doc.get("dtPublicacao", "") or doc.get("data", "")
            data_pub = self._parse_date(data_str, "%d/%m/%Y") or self._parse_date(data_str, "%Y-%m-%d")

            doc_url = doc.get("urlDoc", "") or doc.get("url", "")
            if not doc_url:
                doc_url = f"https://scon.stj.jus.br/SCON/juri/doc.jsp?b=ACOR&p=true&l=10&i=1&q={keyword}"

            if not ementa and not titulo.strip():
                continue

            items.append({
                "titulo": (titulo.strip() or f"STJ - {keyword}")[:1000],
                "tipo": TipoNormativo.PRECEDENTE_JUDICIAL,
                "fonte": FonteNormativo.STJ,
                "setor": setor,
                "url": doc_url,
                "data_publicacao": data_pub or datetime.now(),
                "ementa": ementa[:2000],
                "conteudo_bruto": f"{titulo}\n{ementa}",
            })

        return items

    async def _buscar_stf(self, keyword: str) -> list[dict]:
        """Search STF via REST API."""
        payload = {
            "andSearch": True,
            "pageSize": 10,
            "page": 0,
            "queryString": keyword,
            "sort": "relevance",
        }
        try:
            async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
                resp = await client.post(
                    STF_API_URL,
                    json=payload,
                    headers={"Content-Type": "application/json", "Accept": "application/json"},
                )
            if resp.status_code != 200:
                logger.warning(f"[STF] HTTP {resp.status_code}")
                return []
            data = resp.json()
        except Exception as exc:
            logger.warning(f"[STF] Request falhou: {exc}")
            return []

        items = []
        hits = data.get("hits", {}).get("hits", []) or data.get("results", [])

        for hit in hits:
            source = hit.get("_source", hit)
            titulo = (source.get("classProcessual", "") + " " + source.get("numeroProcesso", "")).strip()
            ementa = source.get("ementa", "")
            relator = source.get("relator", "")
            data_str = source.get("dataPublicacaoDJ", "") or source.get("data", "")
            data_pub = self._parse_date(data_str, "%Y-%m-%d")
            processo_id = source.get("numeroProcesso", "")
            item_url = (
                f"https://portal.stf.jus.br/processos/detalhe.asp?incidente={processo_id}"
                if processo_id else "https://portal.stf.jus.br"
            )
            setor = _detectar_setor(f"{titulo} {ementa}")

            if not ementa and not titulo:
                continue

            items.append({
                "titulo": (titulo or f"STF - {keyword}")[:1000],
                "tipo": TipoNormativo.PRECEDENTE_JUDICIAL,
                "fonte": FonteNormativo.STF,
                "setor": setor,
                "url": item_url,
                "data_publicacao": data_pub or datetime.now(),
                "ementa": ementa[:2000],
                "conteudo_bruto": f"Processo: {titulo}\nRelator: {relator}\nEmenta: {ementa}",
            })

        return items
