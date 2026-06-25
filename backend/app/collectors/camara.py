"""
Câmara dos Deputados collector.
Uses the official API: https://dadosabertos.camara.leg.br/api/v2/proposicoes
"""
import logging
from datetime import date, datetime, timedelta

from app.collectors.base import BaseCollector
from app.models.normativo import FonteNormativo, SetorNormativo, TipoNormativo

logger = logging.getLogger(__name__)

CAMARA_API_BASE = "https://dadosabertos.camara.leg.br/api/v2"
CAMARA_PROPOSICOES_URL = f"{CAMARA_API_BASE}/proposicoes"

# Infrastructure-related theme codes in Câmara's taxonomy
# These tema IDs correspond to infrastructure topics
TEMAS_INFRAESTRUTURA = [
    "46",   # Energia
    "47",   # Minas e Recursos Minerais
    "40",   # Comunicações
    "42",   # Transportes e Trânsito
    "50",   # Meio Ambiente e Desenvolvimento Sustentável
    "48",   # Petróleo e Gás
    "55",   # Aviação Civil e Aeronáutica
]

SETOR_POR_TEMA = {
    "46": SetorNormativo.ENERGIA,
    "47": SetorNormativo.MINERACAO,
    "40": SetorNormativo.TELECOMUNICACOES,
    "42": SetorNormativo.TRANSPORTE,
    "48": SetorNormativo.ENERGIA,
    "55": SetorNormativo.AVIACAO,
    "50": SetorNormativo.SANEAMENTO,
}

TIPO_MAP = {
    "PL": TipoNormativo.PROJETO_LEI,
    "PLP": TipoNormativo.PROJETO_LEI,
    "PEC": TipoNormativo.PROJETO_LEI,
    "MPV": TipoNormativo.MEDIDA_PROVISORIA,
    "PDL": TipoNormativo.PROJETO_LEI,
    "PRC": TipoNormativo.PROJETO_LEI,
    "REQ": TipoNormativo.PROJETO_LEI,
}


class CamaraCollector(BaseCollector):
    """Collects bills and propositions from Câmara dos Deputados."""

    fonte = FonteNormativo.CAMARA

    async def coletar(self) -> list[dict]:
        results = []
        today = date.today()
        last_week = today - timedelta(days=7)

        for tema_id in TEMAS_INFRAESTRUTURA:
            try:
                items = await self._buscar_proposicoes(tema_id, last_week, today)
                results.extend(items)
            except Exception as exc:
                logger.warning(f"[CAMARA] Erro ao buscar tema {tema_id}: {exc}")

        logger.info(f"[CAMARA] Total coletado: {len(results)} proposições")
        return results

    async def _buscar_proposicoes(
        self, tema_id: str, data_inicio: date, data_fim: date
    ) -> list[dict]:
        params = {
            "codTema": tema_id,
            "dataApresentacaoInicio": data_inicio.strftime("%Y-%m-%d"),
            "dataApresentacaoFim": data_fim.strftime("%Y-%m-%d"),
            "itens": 50,
            "pagina": 1,
            "ordem": "DESC",
            "ordenarPor": "id",
        }

        try:
            resp = await self._get(CAMARA_PROPOSICOES_URL, params=params)
            data = resp.json()
        except Exception as exc:
            logger.warning(f"[CAMARA] Falha na request para tema {tema_id}: {exc}")
            return []

        items = []
        proposicoes = data.get("dados", [])

        for prop in proposicoes:
            tipo_sigla = prop.get("siglaTipo", "PL")
            numero = str(prop.get("numero", ""))
            ano = str(prop.get("ano", ""))
            ementa = prop.get("ementa", "")
            titulo = f"{tipo_sigla} {numero}/{ano} - {ementa[:200]}"

            prop_id = prop.get("id")
            item_url = (
                f"https://www.camara.leg.br/proposicoesWeb/fichadetramitacao?idProposicao={prop_id}"
                if prop_id
                else "https://www.camara.leg.br"
            )

            data_str = prop.get("dataApresentacao", "")
            data_pub = self._parse_date(data_str, "%Y-%m-%dT%H:%M:%S") or self._parse_date(
                data_str, "%Y-%m-%d"
            )

            tipo = TIPO_MAP.get(tipo_sigla, TipoNormativo.PROJETO_LEI)
            setor = SETOR_POR_TEMA.get(tema_id, SetorNormativo.GERAL)

            items.append(
                {
                    "titulo": titulo[:1000],
                    "tipo": tipo,
                    "numero": f"{numero}/{ano}",
                    "fonte": FonteNormativo.CAMARA,
                    "setor": setor,
                    "url": item_url,
                    "data_publicacao": data_pub or datetime.now(),
                    "ementa": ementa[:2000],
                    "conteudo_bruto": ementa,
                    "tags": [tipo_sigla, f"tema_{tema_id}"],
                }
            )

        return items

    async def _buscar_ementa_completa(self, prop_id: int) -> str:
        """Fetch complete ementa from the proposição detail endpoint."""
        url = f"{CAMARA_PROPOSICOES_URL}/{prop_id}"
        try:
            resp = await self._get(url)
            data = resp.json()
            return data.get("dados", {}).get("ementa", "")
        except Exception:
            return ""
