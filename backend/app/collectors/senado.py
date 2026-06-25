"""
Senado Federal collector.
Uses the official API: https://legis.senado.leg.br/dadosabertos/materia/pesquisa/lista

NOTE: The API does NOT support free-text palavraChave for general terms.
We fetch all materias by date range (last 30 days) without keyword filtering.
All bills are saved; sector classification is done locally.
"""
import logging
from datetime import date, datetime, timedelta

from app.collectors.base import BaseCollector
from app.models.normativo import FonteNormativo, SetorNormativo, TipoNormativo

logger = logging.getLogger(__name__)

SENADO_API_BASE = "https://legis.senado.leg.br/dadosabertos"
SENADO_MATERIAS_URL = f"{SENADO_API_BASE}/materia/pesquisa/lista"

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
    SetorNormativo.ENERGIA: ["energia", "elétric", "eletric", "petróleo", "petroleo", "gás", "gas", "combustível", "combustivel", "aneel"],
    SetorNormativo.TRANSPORTE: ["transport", "rodovia", "ferrovi", "porto", "antt", "dnit"],
    SetorNormativo.AVIACAO: ["aviação", "aviacao", "aeronáut", "aeronaut", "aeroporto", "anac"],
    SetorNormativo.MINERACAO: ["mineração", "mineracao", "minério", "minerio", "anm"],
    SetorNormativo.TELECOMUNICACOES: ["telecom", "anatel", "internet", "banda larga", "5g"],
    SetorNormativo.SANEAMENTO: ["saneamento", "água", "agua", "esgoto"],
    SetorNormativo.ESPORTE: ["esporte", "desporto", "futebol", "olímpico", "olimpico"],
}


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
        today = date.today()
        last_7_days = today - timedelta(days=7)

        all_materias = await self._buscar_por_periodo(last_7_days, today)
        logger.info(f"[SENADO] Total de matérias no período: {len(all_materias)}")
        return all_materias

    async def _buscar_por_periodo(self, data_inicio: date, data_fim: date) -> list[dict]:
        """Fetch all materias in a date range without keyword filter."""
        import httpx

        params = {
            "dataInicioApresentacao": data_inicio.strftime("%Y%m%d"),
            "dataFimApresentacao": data_fim.strftime("%Y%m%d"),
            "v": "7",
        }

        # Use a fresh client — the shared self.http_client may behave differently
        # with the deprecated Senado endpoint.
        try:
            async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
                resp = await client.get(
                    SENADO_MATERIAS_URL,
                    params=params,
                    headers={"Accept": "application/json", "User-Agent": "RadarRegulatorio/1.0"},
                )
        except Exception as exc:
            logger.error(f"[SENADO] Falha na request HTTP: {exc}")
            return []

        logger.info(f"[SENADO] HTTP {resp.status_code} - {resp.headers.get('content-type', '?')}")

        if resp.status_code != 200:
            logger.error(f"[SENADO] Erro HTTP {resp.status_code}: {resp.text[:300]}")
            return []

        try:
            data = resp.json()
        except Exception as exc:
            logger.error(f"[SENADO] JSON parse error: {exc} - body[:200]: {resp.text[:200]}")
            return []

        materias_wrapper = data.get("PesquisaBasicaMateria", {})
        materias = materias_wrapper.get("Materias", {}).get("Materia", [])

        if not materias:
            logger.info("[SENADO] Nenhuma matéria encontrada no período")
            return []

        if isinstance(materias, dict):
            materias = [materias]

        logger.info(f"[SENADO] {len(materias)} matérias brutas recebidas da API")

        items = []
        for materia in materias:
            item = self._parse_materia(materia)
            if item:
                items.append(item)

        return items

    def _parse_materia(self, materia: dict) -> dict | None:
        """Parse a materia using API v7 flat structure:
        {Codigo, Sigla, Numero, Ano, Ementa, Autor, Data, UrlDetalheMateria, ...}
        """
        try:
            tipo_sigla = materia.get("Sigla", "PL")
            numero = str(materia.get("Numero", "")).lstrip("0") or "0"
            ano = str(materia.get("Ano", ""))
            ementa = materia.get("Ementa", "") or ""
            autor = materia.get("Autor", "") or ""
            materia_id = materia.get("Codigo", "")
            item_url = (
                materia.get("UrlDetalheMateria")
                or (f"https://www25.senado.leg.br/web/atividade/materias/-/materia/{materia_id}" if materia_id else "https://www.senado.leg.br")
            )

            data_str = materia.get("Data", "")
            data_pub = self._parse_date(data_str, "%Y-%m-%d") or self._parse_date(data_str, "%d/%m/%Y")

            # DescricaoIdentificacao already has "PDL 876/2025" format
            descricao = materia.get("DescricaoIdentificacao", f"{tipo_sigla} {numero}/{ano}")
            titulo = f"{descricao} - {ementa[:200]}" if ementa else descricao

            tipo = TIPO_MAP_SENADO.get(tipo_sigla, TipoNormativo.PROJETO_LEI)
            setor = _detectar_setor_senado(ementa)
            conteudo = f"Tipo: {descricao}\nAutor: {autor}\nEmenta: {ementa}"

            return {
                "titulo": titulo[:1000],
                "tipo": tipo,
                "numero": f"{numero}/{ano}",
                "fonte": FonteNormativo.SENADO,
                "setor": setor,
                "url": item_url,
                "data_publicacao": data_pub or datetime.now(),
                "ementa": ementa[:2000],
                "conteudo_bruto": conteudo,
                "tags": [tipo_sigla],
            }
        except Exception as exc:
            logger.warning(f"[SENADO] Erro ao parsear matéria: {exc}")
            return None
