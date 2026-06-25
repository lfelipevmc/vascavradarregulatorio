from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, field_validator

from app.models.normativo import FonteNormativo, PlanoUsuario, SetorNormativo, TipoNormativo


class NormativoCreate(BaseModel):
    titulo: str
    tipo: TipoNormativo
    numero: str | None = None
    data_publicacao: datetime | None = None
    fonte: FonteNormativo
    setor: SetorNormativo = SetorNormativo.GERAL
    url: str | None = None
    conteudo_bruto: str | None = None
    ementa: str | None = None
    tags: list[str] | None = None
    hash_conteudo: str


class NormativoListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    titulo: str
    tipo: TipoNormativo
    numero: str | None
    data_publicacao: datetime | None
    fonte: FonteNormativo
    setor: SetorNormativo
    url: str | None
    ementa: str | None
    resumo_ia: str | None
    impacto: str | None
    tags: list[str] | None
    processado_ia: bool
    created_at: datetime


class NormativoDetail(NormativoListItem):
    conteudo_bruto: str | None
    embedding: dict | None
    updated_at: datetime
    alertas: list["AlertaResponse"] = []


class NormativoStats(BaseModel):
    total: int
    novos_hoje: int
    por_fonte: dict[str, int]
    por_setor: dict[str, int]
    por_tipo: dict[str, int]
    processados_ia: int
    pendentes_ia: int


class UsuarioCreate(BaseModel):
    email: EmailStr
    nome: str
    empresa: str | None = None
    senha: str
    plano: PlanoUsuario = PlanoUsuario.FREE
    setores_interesse: list[str] | None = None

    @field_validator("senha")
    @classmethod
    def senha_minima(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Senha deve ter pelo menos 8 caracteres")
        return v


class UsuarioResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    nome: str
    empresa: str | None
    plano: PlanoUsuario
    setores_interesse: list[str] | None
    ativo: bool
    created_at: datetime


class AlertaCreate(BaseModel):
    usuario_id: int
    normativo_id: int
    tipo_alerta: str = "EMAIL"


class AlertaResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    usuario_id: int
    normativo_id: int
    enviado_em: datetime | None
    tipo_alerta: str


class JobLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    fonte: str
    status: str
    total_encontrados: int
    total_novos: int
    erro: str | None
    executado_em: datetime


class PaginatedResponse(BaseModel):
    items: list[NormativoListItem]
    total: int
    page: int
    page_size: int
    pages: int
