import hashlib
import logging
from abc import ABC, abstractmethod
from datetime import datetime

import httpx
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from tenacity import RetryError, retry, stop_after_attempt, wait_exponential

from app.database import AsyncSessionLocal
from app.models.normativo import FonteNormativo, JobLog, Normativo

logger = logging.getLogger(__name__)


class BaseCollector(ABC):
    """Abstract base class for all regulatory source collectors."""

    fonte: FonteNormativo
    timeout: int = 30

    def __init__(self) -> None:
        self.http_client = httpx.AsyncClient(
            timeout=self.timeout,
            follow_redirects=True,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (compatible; RadarRegulatorio/1.0; "
                    "+https://radar.vascav.com.br/bot)"
                )
            },
        )

    @abstractmethod
    async def coletar(self) -> list[dict]:
        """
        Collect normatives from the source.
        Returns a list of dicts with at minimum:
          titulo, tipo, fonte, conteudo_bruto or ementa, url
        """
        ...

    async def executar(self) -> dict:
        """
        Main entry point: collect, deduplicate, save, and trigger AI processing.
        Returns a summary dict with total_encontrados, total_novos, errors.
        """
        job_log_id: int | None = None
        total_encontrados = 0
        total_novos = 0
        erro: str | None = None

        async with AsyncSessionLocal() as session:
            job = JobLog(
                fonte=self.fonte.value,
                status="RUNNING",
                total_encontrados=0,
                total_novos=0,
            )
            session.add(job)
            await session.commit()
            await session.refresh(job)
            job_log_id = job.id

        erros_salvar: list[str] = []
        try:
            items = await self.coletar()
            total_encontrados = len(items)
            logger.info(f"[{self.fonte.value}] Coletados {total_encontrados} itens")

            total_novos = await self._salvar_batch(items, erros_salvar)
            status = "SUCCESS"
        except RetryError as exc:
            erro = f"Erro após múltiplas tentativas: {exc}"
            status = "FAILURE"
            logger.error(f"[{self.fonte.value}] {erro}")
        except Exception as exc:
            erro = str(exc)
            status = "FAILURE"
            logger.error(f"[{self.fonte.value}] Falha na coleta: {exc}", exc_info=True)
        finally:
            await self.http_client.aclose()

        async with AsyncSessionLocal() as session:
            job = await session.get(JobLog, job_log_id)
            if job:
                job.status = status
                job.total_encontrados = total_encontrados
                job.total_novos = total_novos
                job.erro = erro
                await session.commit()

        return {
            "fonte": self.fonte.value,
            "status": status,
            "total_encontrados": total_encontrados,
            "total_novos": total_novos,
            "erro": erro,
            "erros_salvar": erros_salvar,
        }

    async def _salvar_batch(self, items: list[dict], erros_salvar: list[str]) -> int:
        """Batch-save all items in a single DB session for performance."""
        if not items:
            return 0

        # Compute hashes for all items
        for data in items:
            url_part = data.get("url") or ""
            content_part = data.get("conteudo_bruto") or data.get("ementa") or data.get("titulo") or ""
            data["hash_conteudo"] = self._hash_conteudo(f"{url_part}|{content_part}")

        total_novos = 0
        async with AsyncSessionLocal() as session:
            # Fetch existing hashes in one query
            all_hashes = [d["hash_conteudo"] for d in items]
            existing_result = await session.execute(
                select(Normativo.hash_conteudo).where(Normativo.hash_conteudo.in_(all_hashes))
            )
            existing_hashes = {row[0] for row in existing_result.all()}

            new_items = [d for d in items if d["hash_conteudo"] not in existing_hashes]
            logger.info(f"[{self.fonte.value}] {len(new_items)} novos de {len(items)} (já existiam: {len(existing_hashes)})")

            for data in new_items:
                try:
                    normativo = Normativo(
                        titulo=data.get("titulo", "Sem título")[:1000],
                        tipo=data["tipo"],
                        numero=data.get("numero"),
                        data_publicacao=data.get("data_publicacao"),
                        fonte=data.get("fonte", self.fonte),
                        setor=data.get("setor", "GERAL"),
                        url=data.get("url"),
                        conteudo_bruto=data.get("conteudo_bruto"),
                        ementa=data.get("ementa"),
                        tags=data.get("tags"),
                        hash_conteudo=data["hash_conteudo"],
                        processado_ia=False,
                    )
                    session.add(normativo)
                    total_novos += 1
                except Exception as exc:
                    msg = f"{type(exc).__name__}: {exc}"
                    logger.warning(f"[{self.fonte.value}] Erro ao preparar normativo: {msg}")
                    if len(erros_salvar) < 3:
                        erros_salvar.append(msg)

            try:
                await session.commit()
                logger.info(f"[{self.fonte.value}] Batch commit: {total_novos} novos salvos")
            except IntegrityError:
                await session.rollback()
                logger.warning(f"[{self.fonte.value}] IntegrityError no batch — tentando individualmente")
                total_novos = await self._salvar_individualmente(new_items, erros_salvar)
            except Exception as exc:
                await session.rollback()
                msg = f"{type(exc).__name__}: {exc}"
                logger.error(f"[{self.fonte.value}] Erro no batch commit: {msg}", exc_info=True)
                if len(erros_salvar) < 3:
                    erros_salvar.append(msg)

        return total_novos

    async def _salvar_individualmente(self, items: list[dict], erros_salvar: list[str]) -> int:
        """Fallback: save items one by one when batch fails."""
        total_novos = 0
        for data in items:
            try:
                saved = await self.salvar_normativo(data)
                if saved:
                    total_novos += 1
            except Exception as exc:
                msg = f"{type(exc).__name__}: {exc}"
                logger.warning(f"[{self.fonte.value}] Erro ao salvar: {msg}")
                if len(erros_salvar) < 3:
                    erros_salvar.append(msg)
        return total_novos

    async def salvar_normativo(self, data: dict) -> bool:
        """
        Save a normativo to DB, deduplicating by hash.
        Returns True if it was a new record, False if duplicate.
        Triggers AI processing task for new records.
        """
        # Always include URL to ensure uniqueness even when content is identical
        url_part = data.get("url") or ""
        content_part = data.get("conteudo_bruto") or data.get("ementa") or data.get("titulo") or ""
        texto_para_hash = f"{url_part}|{content_part}"
        hash_val = self._hash_conteudo(texto_para_hash)
        data["hash_conteudo"] = hash_val

        async with AsyncSessionLocal() as session:
            stmt = select(Normativo).where(Normativo.hash_conteudo == hash_val)
            result = await session.execute(stmt)
            existing = result.scalar_one_or_none()

            if existing:
                logger.debug(f"[{self.fonte.value}] Normativo já existe: hash={hash_val[:8]}")
                return False

            normativo = Normativo(
                titulo=data.get("titulo", "Sem título")[:1000],
                tipo=data["tipo"],
                numero=data.get("numero"),
                data_publicacao=data.get("data_publicacao"),
                fonte=data.get("fonte", self.fonte),
                setor=data.get("setor", "GERAL"),
                url=data.get("url"),
                conteudo_bruto=data.get("conteudo_bruto"),
                ementa=data.get("ementa"),
                tags=data.get("tags"),
                hash_conteudo=hash_val,
                processado_ia=False,
            )

            try:
                session.add(normativo)
                await session.commit()
                await session.refresh(normativo)
                logger.info(
                    f"[{self.fonte.value}] Novo normativo salvo: id={normativo.id} "
                    f"titulo={normativo.titulo[:60]}"
                )
                # Trigger async AI processing (optional — requires Celery/Redis)
                try:
                    from app.tasks.coleta import processar_normativo_ia
                    processar_normativo_ia.delay(normativo.id)
                except Exception as celery_exc:
                    logger.debug(f"[{self.fonte.value}] Celery indisponível, IA ignorada: {celery_exc}")
                return True
            except IntegrityError:
                await session.rollback()
                logger.debug(f"[{self.fonte.value}] Race condition - hash já existe: {hash_val[:8]}")
                return False
            except Exception as exc:
                await session.rollback()
                logger.error(f"[{self.fonte.value}] ERRO AO INSERIR normativo: {type(exc).__name__}: {exc}", exc_info=True)
                raise

    @staticmethod
    def _hash_conteudo(texto: str) -> str:
        """Compute SHA-256 hash of the content for deduplication."""
        return hashlib.sha256(texto.encode("utf-8", errors="replace")).hexdigest()

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        reraise=True,
    )
    async def _get(self, url: str, **kwargs) -> httpx.Response:
        """HTTP GET with retry logic."""
        response = await self.http_client.get(url, **kwargs)
        response.raise_for_status()
        return response

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        reraise=True,
    )
    async def _post(self, url: str, **kwargs) -> httpx.Response:
        """HTTP POST with retry logic."""
        response = await self.http_client.post(url, **kwargs)
        response.raise_for_status()
        return response

    def _parse_date(self, date_str: str, fmt: str = "%d/%m/%Y") -> datetime | None:
        """Parse date string to datetime, returning None on failure."""
        if not date_str:
            return None
        try:
            return datetime.strptime(date_str.strip(), fmt)
        except ValueError:
            try:
                return datetime.fromisoformat(date_str.strip())
            except ValueError:
                logger.debug(f"Could not parse date: {date_str!r}")
                return None
