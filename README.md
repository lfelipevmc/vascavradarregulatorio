# Radar Regulatório

Monitoramento inteligente de normas, resoluções e decisões das agências reguladoras brasileiras, usando Claude AI para resumir e classificar documentos automaticamente.

## Arquitetura

```
┌────────────────────────────────────────────────────────────────┐
│                      Radar Regulatório                         │
│                                                                │
│  ┌──────────────┐   ┌──────────────┐   ┌──────────────────┐  │
│  │  Coletores   │   │  Processador │   │     API REST     │  │
│  │              │   │      IA      │   │    (FastAPI)     │  │
│  │ DOU          │──▶│              │──▶│                  │  │
│  │ ANEEL        │   │ Claude       │   │ /normativos      │  │
│  │ ANTT         │   │ claude-      │   │ /normativos/{id} │  │
│  │ ANAC         │   │ sonnet-4-6   │   │ /normativos/     │  │
│  │ ANATEL       │   │              │   │   stats          │  │
│  │ ANM          │   │ Extrai:      │   │ /health          │  │
│  │ TCU          │   │ • resumo     │   │                  │  │
│  │ Câmara       │   │ • ementa     │   └──────────────────┘  │
│  │ Senado       │   │ • setor      │           │             │
│  │ STJ/STF      │   │ • impacto    │           ▼             │
│  └──────┬───────┘   │ • tags       │   ┌──────────────────┐  │
│         │           └──────────────┘   │   Frontend       │  │
│         ▼                              │   (Next.js 14)   │  │
│  ┌──────────────┐                      │                  │  │
│  │  PostgreSQL  │                      │ Dashboard        │  │
│  │              │                      │ Lista filtrada   │  │
│  │  normativos  │                      │ Detalhe + IA     │  │
│  │  usuarios    │                      └──────────────────┘  │
│  │  alertas     │                                            │
│  │  job_logs    │                                            │
│  └──────────────┘                                            │
│                                                                │
│  ┌──────────────┐   ┌──────────────┐                         │
│  │    Celery    │   │    Redis     │                         │
│  │    Worker    │◀──│   Broker     │                         │
│  │              │   │              │                         │
│  │  Coleta 6h   │   │ Task queue   │                         │
│  │  IA tasks    │   │ Results      │                         │
│  └──────────────┘   └──────────────┘                         │
└────────────────────────────────────────────────────────────────┘
```

## Fontes Monitoradas

| Fonte | Tipo | Setor |
|-------|------|-------|
| DOU (Diário Oficial) | Leis, Decretos, Portarias | Todos |
| ANEEL | Resoluções, Despachos | Energia |
| ANTT | Resoluções, Portarias | Transporte |
| ANAC | Resoluções, RBACs | Aviação |
| ANATEL | Resoluções | Telecomunicações |
| ANM | Portarias, Resoluções | Mineração |
| TCU | Acórdãos | Infraestrutura Geral |
| Câmara dos Deputados | Projetos de Lei | Todos |
| Senado Federal | Projetos de Lei | Todos |
| STJ | Precedentes Judiciais | Todos |
| STF | Precedentes Judiciais | Todos |

## Stack Tecnológico

**Backend:**
- Python 3.11 + FastAPI (API REST)
- SQLAlchemy 2.0 async + Alembic (ORM e migrations)
- PostgreSQL 16 (banco de dados)
- Celery 5 + Redis (filas de tarefas)
- httpx + BeautifulSoup4 + Playwright (coleta de dados)
- Anthropic Python SDK / claude-sonnet-4-6 (IA)

**Frontend:**
- Next.js 14 (App Router)
- TypeScript + Tailwind CSS
- TanStack Query (data fetching)
- Recharts (gráficos)

## Pré-requisitos

- Docker e Docker Compose
- Python 3.11+ (para desenvolvimento local)
- Node.js 20+ (para desenvolvimento do frontend)
- Chave de API da Anthropic

## Configuração

### 1. Variáveis de ambiente

```bash
cp .env.example .env
```

Edite o `.env`:

```env
DATABASE_URL=postgresql://radar:radar@localhost:5432/radar_regulatorio
REDIS_URL=redis://localhost:6379/0
ANTHROPIC_API_KEY=sk-ant-...          # obrigatório para IA
RESEND_API_KEY=re_...                  # opcional, para e-mails de alerta
SECRET_KEY=sua-chave-secreta-aqui
ENVIRONMENT=development
```

### 2. Rodar com Docker Compose

```bash
docker compose up -d
```

Isso sobe:
- `postgres` — banco de dados na porta 5432
- `redis` — broker Redis na porta 6379
- `api` — FastAPI na porta 8000
- `worker` — Celery worker
- `beat` — Celery beat (agendador)
- `frontend` — Next.js na porta 3000

### 3. Rodar as migrations

```bash
docker compose exec api alembic upgrade head
```

### 4. Seed de dados de teste (opcional)

```bash
docker compose exec api python /scripts/seed_test_data.py
```

Ou localmente:
```bash
cd backend
python ../scripts/seed_test_data.py
```

### 5. Acessar

- **Frontend:** http://localhost:3000
- **API Docs:** http://localhost:8000/docs
- **Health check:** http://localhost:8000/health

## Desenvolvimento Local

### Backend

```bash
# Criar virtualenv e instalar dependências
python -m venv venv
source venv/bin/activate  # Linux/Mac
pip install -r backend/requirements.txt

# Subir apenas banco e Redis via Docker
docker compose up -d postgres redis

# Copiar .env
cp .env.example .env
# Editar DATABASE_URL para localhost

# Rodar migrations
cd backend
alembic upgrade head

# Iniciar servidor de desenvolvimento
python main.py
# ou
uvicorn app.api.main:app --reload
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

O frontend fica disponível em http://localhost:3000.

### Celery Worker (desenvolvimento)

```bash
cd backend
celery -A app.tasks.celery_app worker --loglevel=info -Q default,coleta,ia
```

### Celery Beat (agendador)

```bash
cd backend
celery -A app.tasks.celery_app beat --loglevel=info
```

## Executar Coletores Manualmente

Use o script CLI para rodar coletores específicos:

```bash
# Coletar do DOU
python scripts/run_collectors.py --fonte dou

# Coletar da ANEEL
python scripts/run_collectors.py --fonte aneel

# Coletar de todos
python scripts/run_collectors.py --fonte all

# Processar pendentes com IA (limite 50 itens)
python scripts/run_collectors.py --ia-batch --ia-limit 50
```

Fontes disponíveis: `dou`, `aneel`, `antt`, `anac`, `anatel`, `anm`, `tcu`, `camara`, `senado`, `stj_stf`, `all`

## Schedule de Coleta Automática (Celery Beat)

| Horário (BRT) | Tarefa |
|---------------|--------|
| 06:00 | Coleta DOU |
| 07:00 | Coleta agências (ANEEL, ANTT, ANAC, ANATEL, ANM) |
| 08:00 | Coleta TCU |
| 08:30 | Coleta Câmara e Senado |
| 22:00 | Coleta completa (catch-up noturno) |

## Endpoints da API

| Método | Rota | Descrição |
|--------|------|-----------|
| GET | `/health` | Status da API e banco |
| GET | `/api/v1/normativos` | Lista com filtros + paginação |
| GET | `/api/v1/normativos/{id}` | Detalhe do normativo |
| GET | `/api/v1/normativos/stats` | Estatísticas para o dashboard |

### Filtros disponíveis em `/api/v1/normativos`:

- `fonte` — DOU, ANEEL, ANTT, ANAC, ANATEL, ANM, TCU, CAMARA, SENADO, STJ, STF
- `setor` — ENERGIA, TRANSPORTE, AVIACAO, MINERACAO, TELECOMUNICACOES, SANEAMENTO, ESPORTE, GERAL
- `tipo` — LEI, DECRETO, PORTARIA, RESOLUCAO, INSTRUCAO_NORMATIVA, MEDIDA_PROVISORIA, ACORDAO_TCU, PROJETO_LEI, PRECEDENTE_JUDICIAL
- `data_inicio` / `data_fim` — formato YYYY-MM-DD
- `q` — busca textual em título, ementa e resumo_ia
- `page` / `page_size` — paginação

## Como Adicionar um Novo Coletor

1. Crie o arquivo `backend/app/collectors/nova_fonte.py`

2. Implemente a classe herdando de `BaseCollector`:

```python
from app.collectors.base import BaseCollector
from app.models.normativo import FonteNormativo, SetorNormativo, TipoNormativo

class NovaFonteCollector(BaseCollector):
    fonte = FonteNormativo.NOVA_FONTE  # adicionar ao enum

    async def coletar(self) -> list[dict]:
        # Implementar lógica de coleta
        items = []
        # ... fazer requests, parsear HTML/JSON, etc.
        items.append({
            "titulo": "Título do normativo",
            "tipo": TipoNormativo.RESOLUCAO,
            "fonte": self.fonte,
            "setor": SetorNormativo.ENERGIA,
            "url": "https://...",
            "ementa": "Texto da ementa",
            "conteudo_bruto": "Texto completo",
            "data_publicacao": datetime.now(),
        })
        return items
```

3. Adicione o valor ao enum `FonteNormativo` em `backend/app/models/normativo.py`

4. Crie uma migration Alembic para atualizar o tipo enum no PostgreSQL

5. Registre a tarefa em `backend/app/tasks/coleta.py`

6. Adicione o coletor ao script CLI `scripts/run_collectors.py`

## Processamento IA

O processador IA usa o modelo `claude-sonnet-4-6` via Anthropic SDK com **tool_use** para extrair:

- **resumo** — 3-5 frases descrevendo o normativo
- **ementa** — 1 frase sintética
- **setor** — classificação setorial automática
- **impacto** — ALTO/MEDIO/BAIXO com justificativa
- **tags** — 3-8 palavras-chave

O processamento é disparado automaticamente após cada novo normativo ser salvo no banco (via tarefa Celery assíncrona), com rate limiting de 30 chamadas/minuto para respeitar os limites da API da Anthropic.

## Estrutura do Projeto

```
vascavradarregulatorio/
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   ├── main.py           # FastAPI app
│   │   │   └── routes/
│   │   │       ├── normativos.py  # Endpoints de normativos
│   │   │       └── health.py     # Health check
│   │   ├── collectors/           # Coletores de cada fonte
│   │   │   ├── base.py           # BaseCollector abstrato
│   │   │   ├── dou.py
│   │   │   ├── aneel.py
│   │   │   ├── antt.py
│   │   │   ├── anac.py
│   │   │   ├── anatel.py
│   │   │   ├── anm.py
│   │   │   ├── tcu.py
│   │   │   ├── camara.py
│   │   │   ├── senado.py
│   │   │   └── stj_stf.py
│   │   ├── models/
│   │   │   └── normativo.py      # Modelos SQLAlchemy
│   │   ├── processors/
│   │   │   └── ia_processor.py   # Processador Claude IA
│   │   ├── schemas/
│   │   │   └── normativo.py      # Schemas Pydantic
│   │   ├── tasks/
│   │   │   ├── celery_app.py     # Config Celery + beat schedule
│   │   │   └── coleta.py        # Tasks Celery
│   │   ├── config.py             # Pydantic Settings
│   │   └── database.py          # SQLAlchemy engine + session
│   ├── alembic/
│   │   └── versions/
│   │       └── 0001_initial_schema.py
│   ├── main.py                   # Entrypoint uvicorn
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── app/
│   │   │   ├── layout.tsx        # Layout com sidebar
│   │   │   ├── page.tsx          # Dashboard
│   │   │   └── normativos/
│   │   │       ├── page.tsx      # Lista com filtros
│   │   │       └── [id]/
│   │   │           └── page.tsx  # Detalhe
│   │   ├── components/
│   │   │   ├── Sidebar.tsx
│   │   │   └── ui/
│   │   │       ├── Badge.tsx
│   │   │       ├── Card.tsx
│   │   │       ├── SearchBar.tsx
│   │   │       └── Spinner.tsx
│   │   └── lib/
│   │       └── api.ts            # Cliente HTTP tipado
│   └── Dockerfile
├── scripts/
│   ├── seed_test_data.py         # Dados de teste
│   └── run_collectors.py        # CLI de coleta
├── docker-compose.yml
├── pyproject.toml
├── .env.example
└── README.md
```
