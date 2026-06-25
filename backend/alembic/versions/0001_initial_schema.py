"""Initial schema - create all tables

Revision ID: 0001
Revises:
Create Date: 2025-01-01 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create enum types
    tipo_normativo = postgresql.ENUM(
        "LEI",
        "DECRETO",
        "PORTARIA",
        "RESOLUCAO",
        "INSTRUCAO_NORMATIVA",
        "MEDIDA_PROVISORIA",
        "ACORDAO_TCU",
        "PROJETO_LEI",
        "PRECEDENTE_JUDICIAL",
        name="tipo_normativo",
    )
    tipo_normativo.create(op.get_bind(), checkfirst=True)

    fonte_normativo = postgresql.ENUM(
        "DOU",
        "ANEEL",
        "ANTT",
        "ANAC",
        "ANATEL",
        "ANM",
        "TCU",
        "CAMARA",
        "SENADO",
        "STJ",
        "STF",
        "TRF",
        name="fonte_normativo",
    )
    fonte_normativo.create(op.get_bind(), checkfirst=True)

    setor_normativo = postgresql.ENUM(
        "ENERGIA",
        "TRANSPORTE",
        "AVIACAO",
        "MINERACAO",
        "TELECOMUNICACOES",
        "ESPORTE",
        "SANEAMENTO",
        "GERAL",
        name="setor_normativo",
    )
    setor_normativo.create(op.get_bind(), checkfirst=True)

    plano_usuario = postgresql.ENUM(
        "FREE", "PRO", "ENTERPRISE", name="plano_usuario"
    )
    plano_usuario.create(op.get_bind(), checkfirst=True)

    # Create normativos table
    op.create_table(
        "normativos",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("titulo", sa.String(length=1000), nullable=False),
        sa.Column(
            "tipo",
            postgresql.ENUM(
                "LEI", "DECRETO", "PORTARIA", "RESOLUCAO", "INSTRUCAO_NORMATIVA",
                "MEDIDA_PROVISORIA", "ACORDAO_TCU", "PROJETO_LEI", "PRECEDENTE_JUDICIAL",
                name="tipo_normativo", create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("numero", sa.String(length=100), nullable=True),
        sa.Column("data_publicacao", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "fonte",
            postgresql.ENUM(
                "DOU", "ANEEL", "ANTT", "ANAC", "ANATEL", "ANM",
                "TCU", "CAMARA", "SENADO", "STJ", "STF", "TRF",
                name="fonte_normativo", create_type=False,
            ),
            nullable=False,
        ),
        sa.Column(
            "setor",
            postgresql.ENUM(
                "ENERGIA", "TRANSPORTE", "AVIACAO", "MINERACAO",
                "TELECOMUNICACOES", "ESPORTE", "SANEAMENTO", "GERAL",
                name="setor_normativo", create_type=False,
            ),
            nullable=False,
            server_default="GERAL",
        ),
        sa.Column("url", sa.String(length=2000), nullable=True),
        sa.Column("conteudo_bruto", sa.Text(), nullable=True),
        sa.Column("resumo_ia", sa.Text(), nullable=True),
        sa.Column("ementa", sa.Text(), nullable=True),
        sa.Column("impacto", sa.Text(), nullable=True),
        sa.Column("tags", postgresql.ARRAY(sa.String()), nullable=True),
        sa.Column("embedding", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column("hash_conteudo", sa.String(length=64), nullable=False),
        sa.Column("processado_ia", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("hash_conteudo"),
    )
    op.create_index("ix_normativos_id", "normativos", ["id"])
    op.create_index("ix_normativos_fonte", "normativos", ["fonte"])
    op.create_index("ix_normativos_setor", "normativos", ["setor"])
    op.create_index("ix_normativos_hash_conteudo", "normativos", ["hash_conteudo"])

    # Create usuarios table
    op.create_table(
        "usuarios",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("nome", sa.String(length=255), nullable=False),
        sa.Column("empresa", sa.String(length=255), nullable=True),
        sa.Column("senha_hash", sa.String(length=255), nullable=True),
        sa.Column(
            "plano",
            postgresql.ENUM("FREE", "PRO", "ENTERPRISE", name="plano_usuario", create_type=False),
            nullable=False,
            server_default="FREE",
        ),
        sa.Column("setores_interesse", postgresql.ARRAY(sa.String()), nullable=True),
        sa.Column("ativo", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
    )
    op.create_index("ix_usuarios_id", "usuarios", ["id"])
    op.create_index("ix_usuarios_email", "usuarios", ["email"])

    # Create alertas table
    op.create_table(
        "alertas",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("usuario_id", sa.Integer(), nullable=False),
        sa.Column("normativo_id", sa.Integer(), nullable=False),
        sa.Column("enviado_em", sa.DateTime(timezone=True), nullable=True),
        sa.Column("tipo_alerta", sa.String(length=50), nullable=False, server_default="EMAIL"),
        sa.ForeignKeyConstraint(["normativo_id"], ["normativos.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["usuario_id"], ["usuarios.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_alertas_id", "alertas", ["id"])
    op.create_index("ix_alertas_usuario_id", "alertas", ["usuario_id"])
    op.create_index("ix_alertas_normativo_id", "alertas", ["normativo_id"])

    # Create job_logs table
    op.create_table(
        "job_logs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("fonte", sa.String(length=50), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("total_encontrados", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_novos", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("erro", sa.Text(), nullable=True),
        sa.Column(
            "executado_em",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_job_logs_id", "job_logs", ["id"])
    op.create_index("ix_job_logs_fonte", "job_logs", ["fonte"])


def downgrade() -> None:
    op.drop_table("job_logs")
    op.drop_table("alertas")
    op.drop_table("usuarios")
    op.drop_table("normativos")

    op.execute("DROP TYPE IF EXISTS plano_usuario")
    op.execute("DROP TYPE IF EXISTS setor_normativo")
    op.execute("DROP TYPE IF EXISTS fonte_normativo")
    op.execute("DROP TYPE IF EXISTS tipo_normativo")
