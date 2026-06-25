"""
AI Processor using Anthropic Claude to summarize and classify regulatory documents.
"""
import json
import logging

import anthropic
from tenacity import retry, stop_after_attempt, wait_exponential

from app.config import settings
from app.database import AsyncSessionLocal
from app.models.normativo import Normativo, SetorNormativo

logger = logging.getLogger(__name__)

# Tool definition for structured extraction
EXTRACTION_TOOL = {
    "name": "classificar_normativo",
    "description": (
        "Classifica e resume um ato normativo ou decisão regulatória brasileira. "
        "Use esta ferramenta para retornar a classificação estruturada."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "resumo": {
                "type": "string",
                "description": (
                    "Resumo do documento em 3 a 5 frases claras, "
                    "explicando o que é, quem é afetado e qual o impacto prático."
                ),
            },
            "ementa": {
                "type": "string",
                "description": (
                    "Ementa sintética em uma única frase descrevendo o objeto do ato normativo."
                ),
            },
            "setor": {
                "type": "string",
                "enum": [s.value for s in SetorNormativo],
                "description": "Setor econômico principal ao qual o normativo se aplica.",
            },
            "nivel_impacto": {
                "type": "string",
                "enum": ["ALTO", "MEDIO", "BAIXO"],
                "description": (
                    "Nível de impacto regulatório: ALTO (muda regras significativas), "
                    "MEDIO (alteração pontual), BAIXO (administrativo/formal)."
                ),
            },
            "descricao_impacto": {
                "type": "string",
                "description": (
                    "Explicação em 1-2 frases do impacto identificado para o setor e agentes regulados."
                ),
            },
            "tags": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Lista de 3 a 8 palavras-chave relevantes em português.",
                "minItems": 3,
                "maxItems": 8,
            },
        },
        "required": ["resumo", "ementa", "setor", "nivel_impacto", "descricao_impacto", "tags"],
    },
}

SYSTEM_PROMPT = """Você é um especialista em direito regulatório brasileiro com profundo conhecimento em:
- Regulação de infraestrutura (energia, transportes, telecomunicações, aviação, mineração, saneamento)
- Legislação federal e atos normativos das agências reguladoras (ANEEL, ANTT, ANAC, ANATEL, ANM)
- Jurisprudência do TCU, STJ e STF sobre contratos de concessão e regulação econômica
- Processo legislativo no Congresso Nacional (Câmara e Senado)

Seu papel é analisar documentos regulatórios e extrair informações precisas e objetivas.
Sempre use a ferramenta classificar_normativo para retornar sua análise em formato estruturado.
Seja preciso, objetivo e use linguagem técnico-jurídica adequada."""


class IAProcessor:
    """Claude AI processor for regulatory documents."""

    def __init__(self) -> None:
        self.client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=2, min=5, max=60),
        reraise=True,
    )
    def _chamar_claude(self, texto: str) -> dict:
        """Call Claude API with retry on rate limit errors."""
        # Truncate if too long (stay within context window)
        max_chars = 40000
        if len(texto) > max_chars:
            texto = texto[:max_chars] + "\n\n[Texto truncado por limite de contexto]"

        message = self.client.messages.create(
            model=settings.ai_model,
            max_tokens=settings.ai_max_tokens,
            system=SYSTEM_PROMPT,
            tools=[EXTRACTION_TOOL],
            tool_choice={"type": "any"},
            messages=[
                {
                    "role": "user",
                    "content": (
                        f"Analise o seguinte ato normativo ou decisão regulatória brasileira "
                        f"e extraia as informações estruturadas:\n\n{texto}"
                    ),
                }
            ],
        )

        # Extract tool use result
        for block in message.content:
            if block.type == "tool_use" and block.name == "classificar_normativo":
                return block.input

        # If no tool use block (unexpected), try to parse text
        text_content = ""
        for block in message.content:
            if hasattr(block, "text"):
                text_content += block.text

        logger.warning("[IAProcessor] Claude não usou tool_use, tentando parsear texto")
        try:
            return json.loads(text_content)
        except json.JSONDecodeError:
            raise ValueError(f"Claude retornou formato inesperado: {text_content[:200]}")

    async def processar_normativo(self, normativo_id: int) -> bool:
        """
        Process a normativo with Claude AI, extracting summary, classification, and tags.
        Updates the normativo in the database.
        Returns True on success, False on failure.
        """
        async with AsyncSessionLocal() as session:
            normativo = await session.get(Normativo, normativo_id)
            if not normativo:
                logger.error(f"[IAProcessor] Normativo {normativo_id} não encontrado")
                return False

            if normativo.processado_ia:
                logger.debug(f"[IAProcessor] Normativo {normativo_id} já processado")
                return True

            # Build context text for Claude
            parts = [f"TÍTULO: {normativo.titulo}"]
            if normativo.ementa:
                parts.append(f"EMENTA: {normativo.ementa}")
            if normativo.conteudo_bruto:
                parts.append(f"CONTEÚDO:\n{normativo.conteudo_bruto}")
            parts.append(f"FONTE: {normativo.fonte.value}")
            parts.append(f"TIPO: {normativo.tipo.value}")
            if normativo.numero:
                parts.append(f"NÚMERO: {normativo.numero}")

            texto = "\n\n".join(parts)

            try:
                resultado = self._chamar_claude(texto)
            except Exception as exc:
                logger.error(
                    f"[IAProcessor] Falha ao processar normativo {normativo_id}: {exc}",
                    exc_info=True,
                )
                return False

            # Update normativo with AI results
            normativo.resumo_ia = resultado.get("resumo", "")
            normativo.ementa = normativo.ementa or resultado.get("ementa", "")

            # Update setor if still GERAL and AI found something better
            ai_setor = resultado.get("setor", "GERAL")
            if normativo.setor == SetorNormativo.GERAL and ai_setor != "GERAL":
                try:
                    normativo.setor = SetorNormativo(ai_setor)
                except ValueError:
                    pass

            nivel = resultado.get("nivel_impacto", "BAIXO")
            descricao = resultado.get("descricao_impacto", "")
            normativo.impacto = f"{nivel}: {descricao}"
            normativo.tags = resultado.get("tags", [])
            normativo.processado_ia = True

            await session.commit()
            logger.info(
                f"[IAProcessor] Normativo {normativo_id} processado: "
                f"setor={normativo.setor.value} impacto={nivel}"
            )
            return True

    async def processar_lote(self, limite: int = 20) -> dict:
        """
        Process a batch of unprocessed normativos.
        Returns summary of processing results.
        """
        from sqlalchemy import select

        async with AsyncSessionLocal() as session:
            stmt = (
                select(Normativo)
                .where(Normativo.processado_ia == False)  # noqa: E712
                .limit(limite)
            )
            result = await session.execute(stmt)
            pendentes = result.scalars().all()

        total = len(pendentes)
        sucesso = 0
        falha = 0

        for normativo in pendentes:
            ok = await self.processar_normativo(normativo.id)
            if ok:
                sucesso += 1
            else:
                falha += 1

        logger.info(f"[IAProcessor] Lote processado: {sucesso}/{total} com sucesso, {falha} falhas")
        return {"total": total, "sucesso": sucesso, "falha": falha}
