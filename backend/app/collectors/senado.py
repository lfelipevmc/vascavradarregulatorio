"""
Senado Federal collector.
Uses the official API: https://legis.senado.leg.br/dadosabertos/materia/pesquisa/lista
"""
import logging
from datetime import date, datetime, timedelta

from app.collectors.base import BaseCollector
from app.models.normativo import FonteNormativo, SetorNormativo, TipoNormativo

logger = logging.getLogger(__name__)

SENADO_API_BASE = "https://legis.senado.leg.br/dadosabertos"
SENADO_MATERIAS_URL = f"{SENADO_API_BASE}/materia/pesquisa/lista"
SENADO_MATERIA_DETAIL = f"{SENADO_API_BASE}/materia"

TIPO_MAP_SENADO = {
    "PL": TipoNormativo.PROJETO_LEI,
    "PLS": TipoNormativo.PROJETO_LEI,
    "PLC": TipoNormativo.PROJETO_LEI,
    "PEC": TipoNormativo.PROJETO_LEI,
    "MPV": TipoNormativo.MEDIDA_PROVISORIA,
    "PDL": TipoNormativo.PROJETO_LEI,
    "SCD": TipoNormativo.PROJETO_LEI,
    "SUG": TipoNormativo.PROJETO_LEI,
}

KEYWORDS_SETOR = {
    SetorNormativo.ENERGIA: ["energia", "elétric", "petróleo", "gás", "combustível", "ANEEL"],
    SetorNormativo.TRANSPORTE: ["transport", "rodovia", "ferrovi", "porto", "ANTT"],
    SetorNormativo.AVIACAO: ["aviação", "aeronáut", "aeroporto", "ANAC"],
    SetorNormativo.MINERACAO: ["mineração", "minério", "ANM"],
    SetorNormativo.TELECOMUNICACOES: ["telecom", "ANATEL", "internet", "banda larga"],
    SetorNormativo.SANEAMENTO: ["saneamento", "água", "esgoto"],
    SetorNormativo.ESPORTE: ["esporte", "desporto", "futebol"],
}

INFRA_KEYWORDS_SEARCH = [
    "infraestrutura",
    "energia elétrica",
    "telecomunicações",
    "mineração",
    "aviação civil",
    "saneamento básico",
    "transporte",
]


def _detectar_setor_senado(texto: str) -> SetorNormativo:
    texto_lower = texto.lower()
    for setor, keywords in KEYWORDS_SETOR.items():
        if any(kw.lower() in texto_lower for kw in keywords):
            return setor
    return SetorNormativo.GERAL


class SenadoCollector(BaseCollector):
    """Collects bills from Senado Federal."""

    fonte = FonteNormativo.SENADO

    async def coletar(self) -> list[dict]:
        results = []
        today = date.today()
        last_week = today - timedelta(days=7)

        for keyword in INFRA_KEYWORDS_SEARCH:
            try:
                items = await self._buscar_materias(keyword, last_week, today)
                results.extend(items)
            except Exception as exc:
                logger.warning(f"[SENADO] Erro ao buscar '{keyword}': {exc}")

        # Deduplicate by Senado materia URL
        seen = set()
        unique = []
        for item in results:
            key = item.get("url", "") or item.get("titulo", "")[:80]
            if key not in seen:
                seen.add(key)
                unique.append(item)

        logger.info(f"[SENADO] Total coletado: {len(unique)} matérias únicas")
        return unique

    async def _buscar_materias(
        self, keyword: str, data_inicio: date, data_fim: date
    ) -> list[dict]:
        params = {
            "palavraChave": keyword,
            "dataInicioApresentacao": data_inicio.strftime("%Y%m%d"),
            "dataFimApresentacao": data_fim.strftime("%Y%m%d"),
            "v": "7",
        }

        resp = await self._get(
            SENADO_MATERIAS_URL,
            params=params,
            headers={"Accept": "application/json"},
        )
        logger.info(f"[SENADO] HTTP {resp.status_code} para '{keyword}' - Content-Type: {resp.headers.get('content-type','?')}")
        try:
            data = resp.json()
        except Exception as exc:
            logger.error(f"[SENADO] JSON parse error para '{keyword}': {exc} - body[:200]: {resp.text[:200]}")
            return []

        items = []
        # Senado API returns nested structure
        materias_wrapper = data.get("PesquisaBasicaMateria", {})
        materias = materias_wrapper.get("Materias", {}).get("Materia", [])

        if isinstance(materias, dict):  # single result is not wrapped in list
            materias = [materias]

        for materia in materias:
            identificacao = materia.get("IdentificacaoMateria", {})
            tipo_sigla = identificacao.get("SiglaSubtipoMateria") or identificacao.get(
                "SiglaTipoMateria", "PL"
            )
            numero = str(identificacao.get("NumeroMateria", ""))
            ano = str(identificacao.get("AnoMateria", ""))
            ementa = materia.get("EmentaMateria", "")
            materia_id = identificacao.get("CodigoMateria")

            titulo = f"{tipo_sigla} {numero}/{ano} - {ementa[:200]}"

            item_url = (
                f"https://www25.senado.leg.br/web/atividade/materias/-/materia/{materia_id}"
                if materia_id
                else "https://www.senado.leg.br"
            )

            data_str = materia.get("DataApresentacao", "")
            data_pub = self._parse_date(data_str, "%Y-%m-%d") or self._parse_date(
                data_str, "%d/%m/%Y"
            )

            tipo = TIPO_MAP_SENADO.get(tipo_sigla, TipoNormativo.PROJETO_LEI)
            setor = _detectar_setor_senado(f"{ementa} {keyword}")

            # Get author info if available
            autor = ""
            autoria = materia.get("AutoriaMateria", {})
            if isinstance(autoria, dict):
                autor = autoria.get("NomeAutor", "")

            conteudo = f"Tipo: {tipo_sigla} {numero}/{ano}\nAutor: {autor}\nEmenta: {ementa}"

            items.append(
                {
                    "titulo": titulo[:1000],
                    "tipo": tipo,
                    "numero": f"{numero}/{ano}",
                    "fonte": FonteNormativo.SENADO,
                    "setor": setor,
                    "url": item_url,
                    "data_publicacao": data_pub or datetime.now(),
                    "ementa": ementa[:2000],
                    "conteudo_bruto": conteudo,
                    "tags": [tipo_sigla, keyword],
                }
            )

        return items
