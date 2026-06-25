#!/usr/bin/env python3
"""
Seed test data into the database.
Run from project root: python scripts/seed_test_data.py
"""
import asyncio
import hashlib
import sys
import os

# Add backend to sys.path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from datetime import datetime, timedelta

from sqlalchemy import text

from app.database import AsyncSessionLocal, engine, Base
from app.models.normativo import (
    FonteNormativo,
    Normativo,
    SetorNormativo,
    TipoNormativo,
)


def make_hash(text_content: str) -> str:
    return hashlib.sha256(text_content.encode()).hexdigest()


TEST_NORMATIVOS = [
    {
        "titulo": "Resolução Normativa ANEEL nº 1.000/2024 - Procedimentos de Distribuição de Energia Elétrica",
        "tipo": TipoNormativo.RESOLUCAO,
        "numero": "1.000/2024",
        "data_publicacao": datetime.now() - timedelta(days=2),
        "fonte": FonteNormativo.ANEEL,
        "setor": SetorNormativo.ENERGIA,
        "url": "https://www.aneel.gov.br/resolucoes-normativas",
        "ementa": "Estabelece os Procedimentos de Distribuição de Energia Elétrica no Sistema Elétrico Nacional (PRODIST), Módulo 1 – Introdução, e dá outras providências.",
        "conteudo_bruto": "A DIRETORIA DA AGÊNCIA NACIONAL DE ENERGIA ELÉTRICA - ANEEL, em Reunião de Diretoria realizada em 15 de março de 2024, com fundamento no art. 2o da Lei no 9.427/1996, nos arts. 3o e 4o do Decreto no 2.335/1997, resolveu: Art. 1o Estabelecer os Procedimentos de Distribuição de Energia Elétrica no Sistema Elétrico Nacional (PRODIST), conforme Anexo desta Resolução. Art. 2o Esta Resolução entra em vigor na data de sua publicação.",
        "resumo_ia": "A ANEEL publicou nova resolução normativa que estabelece e atualiza os Procedimentos de Distribuição de Energia Elétrica (PRODIST). O PRODIST é o conjunto de normas que disciplina as atividades técnicas relacionadas ao funcionamento e desempenho dos sistemas de distribuição de energia elétrica. A resolução impacta distribuidoras de energia em todo o Brasil, estabelecendo padrões mínimos de qualidade e segurança no fornecimento.",
        "impacto": "ALTO: Alteração significativa nos procedimentos técnicos de distribuição impacta todas as concessionárias de distribuição de energia elétrica do País, podendo gerar necessidade de investimentos em adequação de infraestrutura.",
        "tags": ["ANEEL", "energia elétrica", "distribuição", "PRODIST", "resolução normativa", "concessão"],
        "processado_ia": True,
    },
    {
        "titulo": "Projeto de Lei 1234/2024 - Marco Legal do Saneamento Básico - Alteração",
        "tipo": TipoNormativo.PROJETO_LEI,
        "numero": "1234/2024",
        "data_publicacao": datetime.now() - timedelta(days=5),
        "fonte": FonteNormativo.CAMARA,
        "setor": SetorNormativo.SANEAMENTO,
        "url": "https://www.camara.leg.br/proposicoes",
        "ementa": "Altera a Lei nº 14.026, de 15 de julho de 2020, que atualiza o marco legal do saneamento básico, para dispor sobre os prazos de universalização dos serviços.",
        "conteudo_bruto": "PROJETO DE LEI Nº 1234, DE 2024. Altera a Lei nº 14.026, de 15 de julho de 2020, que atualiza o marco legal do saneamento básico. A CÂMARA DOS DEPUTADOS decreta: Art. 1o O art. 11-B da Lei nº 14.026, de 15 de julho de 2020, passa a vigorar com a seguinte redação: Art. 11-B Os contratos de prestação dos serviços públicos de saneamento básico deverão prever metas de expansão dos serviços, de melhoria da qualidade...",
        "resumo_ia": "O PL 1234/2024 propõe alterações ao Marco Legal do Saneamento Básico (Lei 14.026/2020), especificamente modificando prazos e metas para universalização dos serviços de água e esgoto. A proposta estende os prazos originalmente previstos para 2033, alegando dificuldades de implementação pelos municípios. O projeto foi apresentado por deputados da base governista e aguarda votação em comissão temática.",
        "impacto": "MEDIO: A mudança nos prazos de universalização pode afetar cronogramas de investimentos das concessionárias privadas que adquiriram concessões com base nas metas originais, podendo gerar renegociações contratuais.",
        "tags": ["saneamento", "Marco Legal", "PL", "universalização", "concessão", "água", "esgoto"],
        "processado_ia": True,
    },
    {
        "titulo": "Acórdão TCU 987/2024 - Plenário - Fiscalização de Concessão de Rodovias Federais",
        "tipo": TipoNormativo.ACORDAO_TCU,
        "numero": "987/2024",
        "data_publicacao": datetime.now() - timedelta(days=10),
        "fonte": FonteNormativo.TCU,
        "setor": SetorNormativo.TRANSPORTE,
        "url": "https://pesquisa.apps.tcu.gov.br",
        "ementa": "Fiscalização em concessões de rodovias federais. Irregularidades na execução de obras de duplicação. Determinação à ANTT para adoção de medidas corretivas.",
        "conteudo_bruto": "ACÓRDÃO No 987/2024 - TCU - PLENÁRIO. TC 012.345/2023-1. Natureza: Representação. Órgão/Entidade: Agência Nacional de Transportes Terrestres - ANTT. Relator: Ministro João Silva. VISTOS, relatados e discutidos estes autos que tratam de representação acerca de irregularidades em contratos de concessão de rodovias federais...",
        "resumo_ia": "O TCU, em fiscalização das concessões de rodovias federais, identificou irregularidades na execução de obras de duplicação por parte de concessionária. O Plenário do TCU determinou à ANTT que adote medidas para cobrar a execução das obras pendentes sob pena de rescisão contratual. O acórdão também determina a apuração de responsabilidades dos gestores envolvidos.",
        "impacto": "ALTO: Decisão do TCU com determinações à ANTT cria obrigações concretas de fiscalização sobre contratos de concessão de rodovias, com risco de rescisão contratual caso as irregularidades não sejam corrigidas.",
        "tags": ["TCU", "ANTT", "rodovias", "concessão", "fiscalização", "obras", "acórdão"],
        "processado_ia": True,
    },
    {
        "titulo": "Resolução ANATEL nº 756/2024 - Espectro de Radiofrequências para Redes 5G",
        "tipo": TipoNormativo.RESOLUCAO,
        "numero": "756/2024",
        "data_publicacao": datetime.now() - timedelta(days=1),
        "fonte": FonteNormativo.ANATEL,
        "setor": SetorNormativo.TELECOMUNICACOES,
        "url": "https://www.anatel.gov.br/legislacao/resolucoes",
        "ementa": "Aprova o Regulamento de Uso do Espectro de Radiofrequências para Redes de 5a Geração (5G) e dá outras providências.",
        "conteudo_bruto": "RESOLUÇÃO No 756, DE 28 DE MAIO DE 2024. Aprova o Regulamento de Uso do Espectro de Radiofrequências para Redes de 5a Geração (5G). O CONSELHO DIRETOR DA AGÊNCIA NACIONAL DE TELECOMUNICAÇÕES, no uso das atribuições que lhe foram conferidas pela Lei no 9.472, de 16 de julho de 1997...",
        "resumo_ia": "A ANATEL aprovou nova regulamentação sobre uso do espectro de radiofrequências para redes 5G no Brasil. A resolução define bandas de frequência, condições de uso compartilhado do espectro e obrigações de cobertura para as operadoras. O texto incorpora recomendações da UIT e experiências internacionais na implantação de redes 5G.",
        "impacto": "ALTO: Nova regulamentação afeta diretamente as quatro grandes operadoras de telecomunicações (Claro, TIM, Vivo e Oi), determinando novos investimentos e prazos de cobertura para as redes 5G.",
        "tags": ["ANATEL", "5G", "espectro", "radiofrequência", "telecomunicações", "resolução", "cobertura"],
        "processado_ia": True,
    },
    {
        "titulo": "Portaria ANM nº 155/2024 - Procedimentos para Outorga de Títulos Minerários",
        "tipo": TipoNormativo.PORTARIA,
        "numero": "155/2024",
        "data_publicacao": datetime.now() - timedelta(days=3),
        "fonte": FonteNormativo.ANM,
        "setor": SetorNormativo.MINERACAO,
        "url": "https://www.gov.br/anm/pt-br/assuntos/legislacao-e-normas/portarias",
        "ementa": "Estabelece procedimentos para outorga de títulos minerários e regula o processo de requerimento de lavra no Sistema de Cadastro Mineiro.",
        "conteudo_bruto": "PORTARIA ANM No 155, DE 20 DE MARÇO DE 2024. Estabelece procedimentos para outorga de títulos minerários. O DIRETOR-GERAL DA AGÊNCIA NACIONAL DE MINERAÇÃO - ANM, no uso das atribuições que lhe conferem o art. 19, inciso II, da Lei no 13.575, de 26 de dezembro de 2017...",
        "resumo_ia": "A ANM publicou portaria que regulamenta os procedimentos para outorga de títulos minerários, incluindo autorizações de pesquisa e concessões de lavra. O texto atualiza o fluxo de requerimentos no Sistema de Cadastro Mineiro (SCM) digital, reduzindo prazos e documentos exigidos. A portaria visa desburocratizar o processo e atrair investimentos para o setor de mineração.",
        "impacto": "MEDIO: Simplificação dos processos de licenciamento mineral pode acelerar novos projetos de mineração, beneficiando empresas do setor mas também podendo gerar pressão por maior celeridade no licenciamento ambiental.",
        "tags": ["ANM", "mineração", "título minerário", "outorga", "SCM", "portaria", "lavra", "pesquisa mineral"],
        "processado_ia": True,
    },
]


async def seed():
    print("Criando tabelas se necessário...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    print(f"Inserindo {len(TEST_NORMATIVOS)} normativos de teste...")

    async with AsyncSessionLocal() as session:
        inserted = 0
        skipped = 0

        for data in TEST_NORMATIVOS:
            conteudo = data.get("conteudo_bruto") or data.get("ementa") or data["titulo"]
            hash_val = make_hash(conteudo)

            # Check if already exists
            from sqlalchemy import select
            result = await session.execute(
                select(Normativo).where(Normativo.hash_conteudo == hash_val)
            )
            existing = result.scalar_one_or_none()

            if existing:
                print(f"  [SKIP] Já existe: {data['titulo'][:60]}...")
                skipped += 1
                continue

            normativo = Normativo(
                titulo=data["titulo"],
                tipo=data["tipo"],
                numero=data.get("numero"),
                data_publicacao=data.get("data_publicacao"),
                fonte=data["fonte"],
                setor=data["setor"],
                url=data.get("url"),
                ementa=data.get("ementa"),
                conteudo_bruto=data.get("conteudo_bruto"),
                resumo_ia=data.get("resumo_ia"),
                impacto=data.get("impacto"),
                tags=data.get("tags"),
                hash_conteudo=hash_val,
                processado_ia=data.get("processado_ia", False),
            )
            session.add(normativo)
            inserted += 1
            print(f"  [OK] {data['titulo'][:70]}...")

        await session.commit()

    print(f"\nSeed concluído: {inserted} inseridos, {skipped} já existiam.")


if __name__ == "__main__":
    asyncio.run(seed())
