import enum
from datetime import datetime

from sqlalchemy import (
    JSON,
    ARRAY,
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class TipoNormativo(str, enum.Enum):
    LEI = "LEI"
    DECRETO = "DECRETO"
    PORTARIA = "PORTARIA"
    RESOLUCAO = "RESOLUCAO"
    INSTRUCAO_NORMATIVA = "INSTRUCAO_NORMATIVA"
    MEDIDA_PROVISORIA = "MEDIDA_PROVISORIA"
    ACORDAO_TCU = "ACORDAO_TCU"
    PROJETO_LEI = "PROJETO_LEI"
    PRECEDENTE_JUDICIAL = "PRECEDENTE_JUDICIAL"


class FonteNormativo(str, enum.Enum):
    DOU = "DOU"
    ANEEL = "ANEEL"
    ANTT = "ANTT"
    ANAC = "ANAC"
    ANATEL = "ANATEL"
    ANM = "ANM"
    TCU = "TCU"
    CAMARA = "CAMARA"
    SENADO = "SENADO"
    STJ = "STJ"
    STF = "STF"
    TRF = "TRF"


class SetorNormativo(str, enum.Enum):
    ENERGIA = "ENERGIA"
    TRANSPORTE = "TRANSPORTE"
    AVIACAO = "AVIACAO"
    MINERACAO = "MINERACAO"
    TELECOMUNICACOES = "TELECOMUNICACOES"
    ESPORTE = "ESPORTE"
    SANEAMENTO = "SANEAMENTO"
    GERAL = "GERAL"


class PlanoUsuario(str, enum.Enum):
    FREE = "FREE"
    PRO = "PRO"
    ENTERPRISE = "ENTERPRISE"


class Normativo(Base):
    __tablename__ = "normativos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    titulo: Mapped[str] = mapped_column(String(1000), nullable=False)
    tipo: Mapped[TipoNormativo] = mapped_column(
        Enum(TipoNormativo, name="tipo_normativo"), nullable=False
    )
    numero: Mapped[str | None] = mapped_column(String(100), nullable=True)
    data_publicacao: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    fonte: Mapped[FonteNormativo] = mapped_column(
        Enum(FonteNormativo, name="fonte_normativo"), nullable=False, index=True
    )
    setor: Mapped[SetorNormativo] = mapped_column(
        Enum(SetorNormativo, name="setor_normativo"),
        nullable=False,
        default=SetorNormativo.GERAL,
        index=True,
    )
    url: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    conteudo_bruto: Mapped[str | None] = mapped_column(Text, nullable=True)
    resumo_ia: Mapped[str | None] = mapped_column(Text, nullable=True)
    ementa: Mapped[str | None] = mapped_column(Text, nullable=True)
    impacto: Mapped[str | None] = mapped_column(Text, nullable=True)
    tags: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)
    embedding: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    hash_conteudo: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    processado_ia: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    alertas: Mapped[list["Alerta"]] = relationship("Alerta", back_populates="normativo")

    def __repr__(self) -> str:
        return f"<Normativo id={self.id} fonte={self.fonte} tipo={self.tipo}>"


class Usuario(Base):
    __tablename__ = "usuarios"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    nome: Mapped[str] = mapped_column(String(255), nullable=False)
    empresa: Mapped[str | None] = mapped_column(String(255), nullable=True)
    senha_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    plano: Mapped[PlanoUsuario] = mapped_column(
        Enum(PlanoUsuario, name="plano_usuario"),
        nullable=False,
        default=PlanoUsuario.FREE,
    )
    setores_interesse: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)
    ativo: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    alertas: Mapped[list["Alerta"]] = relationship("Alerta", back_populates="usuario")

    def __repr__(self) -> str:
        return f"<Usuario id={self.id} email={self.email}>"


class Alerta(Base):
    __tablename__ = "alertas"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    usuario_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False, index=True
    )
    normativo_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("normativos.id", ondelete="CASCADE"), nullable=False, index=True
    )
    enviado_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    tipo_alerta: Mapped[str] = mapped_column(String(50), nullable=False, default="EMAIL")

    usuario: Mapped["Usuario"] = relationship("Usuario", back_populates="alertas")
    normativo: Mapped["Normativo"] = relationship("Normativo", back_populates="alertas")

    def __repr__(self) -> str:
        return f"<Alerta id={self.id} usuario={self.usuario_id} normativo={self.normativo_id}>"


class JobLog(Base):
    __tablename__ = "job_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    fonte: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False)  # SUCCESS, FAILURE, RUNNING
    total_encontrados: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_novos: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    erro: Mapped[str | None] = mapped_column(Text, nullable=True)
    executado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    def __repr__(self) -> str:
        return f"<JobLog id={self.id} fonte={self.fonte} status={self.status}>"
