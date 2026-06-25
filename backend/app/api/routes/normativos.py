import math
from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import String, case, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.normativo import FonteNormativo, Normativo, SetorNormativo, TipoNormativo
from app.schemas.normativo import NormativoDetail, NormativoListItem, NormativoStats, PaginatedResponse

router = APIRouter()


@router.get("/normativos/stats", response_model=NormativoStats)
async def get_stats(db: AsyncSession = Depends(get_db)) -> NormativoStats:
    """Dashboard statistics: counts by fonte, setor, tipo, and new today."""
    today_start = datetime.combine(date.today(), datetime.min.time())

    # Total count
    total_result = await db.execute(select(func.count(Normativo.id)))
    total = total_result.scalar_one()

    # New today
    novos_result = await db.execute(
        select(func.count(Normativo.id)).where(Normativo.created_at >= today_start)
    )
    novos_hoje = novos_result.scalar_one()

    # By fonte
    fonte_result = await db.execute(
        select(cast(Normativo.fonte, String), func.count(Normativo.id))
        .group_by(Normativo.fonte)
        .order_by(func.count(Normativo.id).desc())
    )
    por_fonte = {row[0]: row[1] for row in fonte_result.all()}

    # By setor
    setor_result = await db.execute(
        select(cast(Normativo.setor, String), func.count(Normativo.id))
        .group_by(Normativo.setor)
        .order_by(func.count(Normativo.id).desc())
    )
    por_setor = {row[0]: row[1] for row in setor_result.all()}

    # By tipo
    tipo_result = await db.execute(
        select(cast(Normativo.tipo, String), func.count(Normativo.id))
        .group_by(Normativo.tipo)
        .order_by(func.count(Normativo.id).desc())
    )
    por_tipo = {row[0]: row[1] for row in tipo_result.all()}

    # AI processing stats
    ia_result = await db.execute(
        select(
            func.count(case((Normativo.processado_ia == True, 1))),  # noqa: E712
            func.count(case((Normativo.processado_ia == False, 1))),  # noqa: E712
        )
    )
    ia_row = ia_result.one()

    return NormativoStats(
        total=total,
        novos_hoje=novos_hoje,
        por_fonte=por_fonte,
        por_setor=por_setor,
        por_tipo=por_tipo,
        processados_ia=ia_row[0],
        pendentes_ia=ia_row[1],
    )


@router.get("/normativos", response_model=PaginatedResponse)
async def list_normativos(
    fonte: FonteNormativo | None = Query(None, description="Filtrar por fonte"),
    setor: SetorNormativo | None = Query(None, description="Filtrar por setor"),
    tipo: TipoNormativo | None = Query(None, description="Filtrar por tipo"),
    data_inicio: date | None = Query(None, description="Data de publicação início (YYYY-MM-DD)"),
    data_fim: date | None = Query(None, description="Data de publicação fim (YYYY-MM-DD)"),
    q: str | None = Query(None, description="Busca em título, ementa e resumo"),
    processado_ia: bool | None = Query(None, description="Filtrar por processamento IA"),
    page: int = Query(1, ge=1, description="Número da página"),
    page_size: int = Query(20, ge=1, le=100, description="Itens por página"),
    db: AsyncSession = Depends(get_db),
) -> PaginatedResponse:
    """List normativos with filters and pagination."""
    stmt = select(Normativo)

    if fonte:
        stmt = stmt.where(Normativo.fonte == fonte)
    if setor:
        stmt = stmt.where(Normativo.setor == setor)
    if tipo:
        stmt = stmt.where(Normativo.tipo == tipo)
    if data_inicio:
        stmt = stmt.where(Normativo.data_publicacao >= datetime.combine(data_inicio, datetime.min.time()))
    if data_fim:
        stmt = stmt.where(
            Normativo.data_publicacao <= datetime.combine(data_fim, datetime.max.time())
        )
    if processado_ia is not None:
        stmt = stmt.where(Normativo.processado_ia == processado_ia)
    if q:
        search_term = f"%{q}%"
        stmt = stmt.where(
            Normativo.titulo.ilike(search_term)
            | Normativo.ementa.ilike(search_term)
            | Normativo.resumo_ia.ilike(search_term)
        )

    # Count total for pagination
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total_result = await db.execute(count_stmt)
    total = total_result.scalar_one()

    # Apply ordering and pagination
    stmt = (
        stmt.order_by(Normativo.data_publicacao.desc(), Normativo.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )

    result = await db.execute(stmt)
    normativos = result.scalars().all()

    return PaginatedResponse(
        items=[NormativoListItem.model_validate(n) for n in normativos],
        total=total,
        page=page,
        page_size=page_size,
        pages=math.ceil(total / page_size) if total > 0 else 0,
    )


@router.get("/normativos/{normativo_id}", response_model=NormativoDetail)
async def get_normativo(normativo_id: int, db: AsyncSession = Depends(get_db)) -> NormativoDetail:
    """Get a single normativo by ID with full detail."""
    normativo = await db.get(Normativo, normativo_id)
    if not normativo:
        raise HTTPException(status_code=404, detail=f"Normativo {normativo_id} não encontrado")

    return NormativoDetail.model_validate(normativo)
