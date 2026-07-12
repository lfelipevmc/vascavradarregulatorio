# Radar Regulatório — Relatório de Handover para Desenvolvedores

**Data:** 12/07/2026
**Repositório:** `lfelipevmc/vascavradarregulatorio`
**Branch de desenvolvimento:** `claude/eloquent-turing-n9d9ik`
**Último commit coberto por este relatório:** `48db6d5`

Este documento consolida **tudo** o que foi construído, todos os erros cometidos e corrigidos, e o passo a passo para quem vai integrar este sistema com outro. Leia a Seção 10 (Cronologia de erros) e a Seção 11 (Checklist de armadilhas) antes de escrever qualquer linha de código.

---

## 1. Visão geral

O **Radar Regulatório** monitora diariamente fontes normativas brasileiras relevantes para infraestrutura (DOU, ANEEL, ANTT, ANAC, ANATEL, ANM, TCU, Câmara, Senado, STJ/STF), armazena os atos em PostgreSQL com deduplicação, classifica por setor, e (quando ativado) resume e classifica cada ato com Claude AI. A entrega é um dashboard Next.js + alertas por e-mail (planejado). O objetivo comercial é um SaaS para empresas de infraestrutura, com respaldo jurídico da VCW Advogados.

**URLs de produção (Render, plano free):**

| Serviço | URL |
|---|---|
| API (FastAPI) | `https://radar-api-zefw.onrender.com` — docs interativas em `/docs` |
| Frontend (Next.js) | `https://radar-frontend-y3i5.onrender.com` |
| Health check | `https://radar-api-zefw.onrender.com/health` |

**Stack:**

- Backend: Python 3.11, FastAPI (async), SQLAlchemy 2.0 async + asyncpg, Alembic, APScheduler, httpx + tenacity, BeautifulSoup (legado), Anthropic SDK
- Banco: PostgreSQL (Render) / SQLite+aiosqlite (dev local)
- Frontend: Next.js 14 App Router, TypeScript, Tailwind, axios, React Query (providers.tsx)
- Deploy: Render Blueprint (`render.yaml`), Docker para a API
- Fila (opcional/desativada): Celery + Redis — o plano free do Render não suporta workers; o APScheduler embutido na API substitui o Celery Beat

---

## 2. Arquitetura e fluxo de dados

```
                       ┌─────────────────────────────────────────┐
                       │           radar-api (FastAPI)           │
 Fontes externas ────▶ │  Collectors (httpx) ─▶ BaseCollector    │
 (APIs/JSON dos        │      coletar() ─▶ _salvar_batch()       │
  órgãos públicos)     │           │                             │
                       │           ▼                             │
                       │  PostgreSQL (normativos, job_logs...)   │
                       │           │                             │
                       │  IAProcessor (Claude) [pendente de key] │
                       │           │                             │
                       │  APScheduler (cron diário, in-process)  │
                       └───────────┬─────────────────────────────┘
                                   │ REST /api/v1
                       ┌───────────▼─────────────┐
                       │ radar-frontend (Next.js) │
                       └─────────────────────────┘
```

Fluxo de uma coleta:

1. `POST /api/v1/admin/collect/{fonte}` (manual) ou job do APScheduler (diário) instancia o coletor via `COLLECTOR_MAP`.
2. `BaseCollector.executar()`: cria `JobLog(RUNNING)` → chama `coletar()` da subclasse → `_salvar_batch()` → atualiza `JobLog` com totais/erros → devolve dict-resumo.
3. `_salvar_batch()`: calcula hash SHA-256 de `"{url}|{conteudo}"` para cada item → **um único** `SELECT ... WHERE hash_conteudo IN (...)` para achar duplicatas → adiciona só os novos → **um único** `commit()`. Fallback para inserção individual se houver `IntegrityError` no batch.
4. IA (quando `ANTHROPIC_API_KEY` estiver configurada): `IAProcessor.processar_normativo()` usa tool-use forçado (`tool_choice: any`) com a tool `classificar_normativo` para extrair resumo, ementa, setor, nível de impacto e tags de forma estruturada. Há `processar_lote(limite)` para varrer pendentes (`processado_ia == False`).

---

## 3. Estrutura do repositório

```
├── render.yaml                     # Blueprint Render (API, frontend, redis, postgres)
├── docker-compose.yml              # Dev local
├── backend/
│   ├── Dockerfile                  # Imagem completa (com Playwright)
│   ├── Dockerfile.render           # Imagem leve p/ Render (SEM Playwright, ~300MB a menos)
│   ├── requirements.txt            # Deps completas
│   ├── requirements.render.txt     # Deps sem playwright
│   ├── start.sh                    # Espera DB → alembic upgrade head → uvicorn
│   ├── alembic/
│   │   ├── env.py                  # usa settings.sync_database_url (psycopg2)
│   │   └── versions/
│   │       ├── 0001_initial_schema.py   # 4 tabelas + ENUMs PostgreSQL
│   │       └── 0002_fix_tags_jsonb.py   # ARRAY→JSONB (ver Seção 10, erro #17)
│   └── app/
│       ├── config.py               # Pydantic Settings; normaliza postgres://→postgresql://
│       ├── database.py             # engine async; sem pool_size quando SQLite
│       ├── models/normativo.py     # Normativo, Usuario, Alerta, JobLog + 4 Enums
│       ├── schemas/normativo.py    # Pydantic response models
│       ├── api/
│       │   ├── main.py             # app FastAPI + CORS + APScheduler no startup
│       │   └── routes/
│       │       ├── health.py
│       │       ├── normativos.py   # GET /normativos (7 filtros), /stats, /{id}
│       │       └── admin.py        # POST /admin/collect/{fonte}, GET status, test/senado
│       ├── collectors/
│       │   ├── base.py             # BaseCollector: executar/_salvar_batch/hash/_get retry
│       │   ├── dou.py              # ✅ reescrito p/ JSON index (leiturajornal)
│       │   ├── senado.py           # ✅ FUNCIONA (121 salvos) — API v7 flat
│       │   ├── camara.py           # API dadosabertos v2 por codTema
│       │   ├── stj_stf.py          # APIs REST STJ (SCON) e STF
│       │   ├── anatel.py           # ✅ FUNCIONA (5 salvos)
│       │   ├── aneel.py            # ⚠️ scraping HTML desatualizado → 0 itens
│       │   ├── antt.py             # ⚠️ idem
│       │   ├── anac.py             # ⚠️ idem
│       │   ├── anm.py              # ⚠️ idem
│       │   └── tcu.py              # ⚠️ API Solr retorna 0 → verificar endpoint
│       ├── processors/ia_processor.py  # Claude tool-use estruturado
│       └── tasks/                  # Celery (VESTIGIAL no free tier — ver Seção 14)
├── frontend/
│   ├── package.json                # tailwind/postcss/autoprefixer em devDependencies (!)
│   ├── next.config.js              # SEM output:standalone; ignora erros TS/ESLint no build
│   ├── .node-version               # "20"
│   └── src/
│       ├── lib/api.ts              # cliente axios + tipos TS espelhando schemas
│       ├── app/                    # páginas: dashboard, /normativos, /normativos/[id]
│       └── components/             # Sidebar, Badge, Card, SearchBar, Spinner
└── scripts/
    ├── run_collectors.py           # roda coletores localmente
    └── seed_test_data.py           # dados de teste
```

---

## 4. Modelo de dados

4 tabelas (ver `backend/app/models/normativo.py`):

- **normativos** — o registro central. Campos-chave: `titulo`, `tipo` (ENUM `tipo_normativo`), `fonte` (ENUM `fonte_normativo`), `setor` (ENUM `setor_normativo`), `numero`, `data_publicacao`, `url`, `ementa`, `conteudo_bruto`, `resumo_ia`, `impacto`, `tags` (**JSONB**), `embedding` (JSON, reservado), `hash_conteudo` (SHA-256, **UNIQUE** — é a chave de deduplicação), `processado_ia`.
- **usuarios** — para o SaaS (ainda sem autenticação implementada). `setores_interesse` é **JSONB**.
- **alertas** — N:N usuário↔normativo com `enviado_em` (e-mail ainda não implementado).
- **job_logs** — auditoria de cada execução de coletor (`fonte`, `status` RUNNING/SUCCESS/FAILURE, `total_encontrados`, `total_novos`, `erro`, `executado_em`).

**ENUMs PostgreSQL:** `tipo_normativo`, `fonte_normativo`, `setor_normativo`, `plano_usuario` — criados na migration 0001. Os Enums Python herdam de `str, enum.Enum` e os **valores são os nomes em maiúsculas** (`"SENADO"`, `"ENERGIA"`). Se você adicionar um valor novo a um Enum Python, **precisa de migration** com `ALTER TYPE ... ADD VALUE` — senão o INSERT falha em produção e passa no SQLite.

**Migrations:**
- `0001_initial_schema.py` — schema inicial. **Continha o bug** `tags`/`setores_interesse` como `ARRAY(VARCHAR)`.
- `0002_fix_tags_jsonb.py` — converte para JSONB com `USING to_jsonb(...)`. O modelo usa `JSON` do SQLAlchemy (vira JSONB no postgres e TEXT-json no SQLite) para compatibilidade entre bancos.

`start.sh` roda `alembic upgrade head` a cada boot do container — **migrations são aplicadas automaticamente no deploy**.

---

## 5. O pipeline de coleta (`backend/app/collectors/base.py`)

Contrato para qualquer coletor novo:

```python
class MinhaFonteCollector(BaseCollector):
    fonte = FonteNormativo.MINHA_FONTE   # tem que existir no Enum + ENUM do postgres!

    async def coletar(self) -> list[dict]:
        # devolve lista de dicts com:
        # titulo (obrig.), tipo (TipoNormativo), fonte (FonteNormativo),
        # setor (SetorNormativo), url, numero, data_publicacao (datetime),
        # ementa, conteudo_bruto, tags (list[str])
        ...
```

Regras aprendidas a ferro e fogo (detalhes na Seção 10):

1. **Nunca** salve item a item em sessões separadas — use o `_salvar_batch()` herdado (ele é chamado por `executar()`; você não precisa fazer nada).
2. O hash de deduplicação é `sha256(f"{url}|{conteudo}")`. **A URL faz parte do hash** porque conteúdos vazios/iguais colidiam (582 itens → 1 salvo).
3. Para fontes **lentas ou instáveis**, NÃO use `self._get()` (que tem retry tenacity com backoff de até 30s × 3 tentativas) — crie um `httpx.AsyncClient(timeout=15)` fresco. O retry agressivo multiplicado por N keywords foi a causa dos timeouts de DOU/Câmara/STJ.
4. Prefira **APIs JSON oficiais** a scraping HTML. Todos os coletores baseados em seletores CSS quebraram (ANEEL, ANTT, ANAC, ANM) porque os portais mudam de layout.
5. Erros de save individuais aparecem em `erros_salvar[]` (primeiros 3) na resposta do endpoint admin — essa visibilidade foi o que destravou o debug inteiro. Não remova.
6. `executar()` nunca lança exceção para fora: registra em `JobLog` e devolve dict com `status`/`erro`.

---

## 6. Estado atual de cada coletor (12/07/2026)

| Fonte | Status | Detalhes / próximo passo |
|---|---|---|
| **SENADO** | ✅ Funcionando | 121 matérias salvas (janela 7 dias, sem filtro de keyword). **ATENÇÃO:** a API `dadosabertos/materia/pesquisa/lista` está oficialmente **descontinuada** (metadata da própria API: `DataDesativacaoCompleta: 2026-02-01`, ainda respondendo em 07/2026). Substituto oficial: `https://legis.senado.leg.br/dadosabertos/processo`. **Migrar em breve.** |
| **ANATEL** | ✅ Funcionando | 5 itens salvos. |
| **DOU** | ⚠️ Sem timeout, mas 0 itens | Reescrito para o índice JSON `https://www.in.gov.br/leiturajornal/data/dou-v4/secao{1,2}/{YYYY-MM-DD}/index.json`. Retornou 0 — **verificar** se o padrão de URL/estrutura (`content[]`, `identifica`, `urlTitle`, `pubDate`) ainda é o atual, e se a data-alvo (último dia útil) tinha atos relevantes. Criar um endpoint de diagnóstico igual ao `/admin/test/senado` para inspecionar o JSON bruto. |
| **CAMARA** | ⚠️ Correção aguardando validação | Timeout corrigido em `ca1ae93` (httpx fresco + remoção do N+1 `_buscar_ementa_completa`). API: `https://dadosabertos.camara.leg.br/api/v2/proposicoes?codTema=...` — API oficial estável, deve funcionar. Testar após deploy. |
| **STJ_STF** | ⚠️ Correção aguardando validação | Reduzido para 2 keywords; APIs REST diretas. Os formatos de resposta do SCON/STJ (`documentos[]`) e do STF (`hits.hits[]`) foram **assumidos, não confirmados** — validar com endpoint de diagnóstico. |
| **ANEEL** | ❌ 0 itens | Scraping HTML com seletores desatualizados. Reescrever usando dados abertos (`https://dadosabertos.aneel.gov.br` — CKAN API) ou a Biblioteca Virtual da ANEEL. |
| **ANTT** | ❌ 0 itens | Idem — `https://dados.antt.gov.br` (CKAN). |
| **ANAC** | ❌ 0 itens | Idem — `https://www.anac.gov.br/acesso-a-informacao/dados-abertos` e o sistema de consulta normativa da ANAC. |
| **ANM** | ❌ 0 itens | Idem — `https://dados.gov.br` (conjunto ANM). |
| **TCU** | ❌ 0 itens | A API Solr `pesquisa.apps.tcu.gov.br/rest/acordao/smb` respondeu vazio sem erro. Inspecionar resposta bruta; o TCU também expõe `https://dados.tcu.gov.br` e a API de acórdãos `congresso/api`. |

**Estratégia recomendada para os coletores quebrados:** para cada um, primeiro crie um endpoint de diagnóstico que devolva `status_code`, `content_type` e `body[:1000]` (copie o `/admin/test/senado` em `admin.py`), rode em produção (o IP do Render às vezes é tratado diferente do seu IP local!), e só então escreva o parser contra a estrutura real observada. **Não escreva parser contra documentação — escreva contra a resposta real.** Foi documentação desatualizada que quebrou o parser do Senado.

---

## 7. Deploy no Render — limitações do plano free (todas descobertas na prática)

O `render.yaml` define: `radar-api` (web/docker), `radar-frontend` (web/node), `radar-redis` (redis), `radar-db` (postgres).

**Limitações do free tier que moldaram a arquitetura:**

1. **Não existem background workers** → Celery worker/beat foram removidos do Blueprint. O agendamento é feito por **APScheduler dentro do processo da API** (`main.py::_start_scheduler`, ativado por `ENABLE_SCHEDULER=true`).
2. **`BackgroundTasks` do FastAPI são mortas** após a resposta HTTP → os endpoints admin executam a coleta **sincronamente** e devolvem o resultado completo no corpo da resposta.
3. **Requisições longas são cortadas** (~100s observados) → daí a necessidade de batch insert e de janelas de coleta menores. Se um endpoint retornar body vazio (`Expecting value: line 1 column 1 (char 0)` no `json.tool`), a causa provável é estouro de tempo.
4. **Cold start**: serviços dormem após inatividade; a primeira request demora ~50s.
5. **O hostname gerado tem sufixo aleatório** (`radar-api-zefw`) → não dá para prever a URL no `render.yaml` antes do primeiro deploy. `NEXT_PUBLIC_API_URL` precisou ser corrigida manualmente depois.
6. **Deploy manual**: pushes na branch NÃO disparam deploy automático da configuração atual — é preciso "Manual Deploy" no dashboard para cada serviço após cada push.

**Regras do formato render.yaml (erros de sintaxe que travaram o Blueprint):**
- `fromService` não pode combinar `property` com `envVarKey` — use um ou outro, ou `value:` estático.
- Serviço redis **exige** `ipAllowList` (mesmo vazio: `ipAllowList: []`).
- `nodeVersion` não é campo válido — use env var `NODE_VERSION` (e/ou arquivo `.node-version`).

**Build do frontend no Render:**
- `npm install` roda com NODE_ENV=production e **pula devDependencies** → como `tailwindcss`, `postcss` e `autoprefixer` estão em devDependencies, o buildCommand é `npm install --include=dev && npm run build`.
- `output: "standalone"` no `next.config.js` **quebra `npm start`** no Render — foi removido.
- `next.config.js` está com `typescript.ignoreBuildErrors: true` e `eslint.ignoreDuringBuilds: true` para não bloquear deploy — **remover quando o código estabilizar**.

**Docker da API:** `Dockerfile.render` + `requirements.render.txt` **excluem o Playwright** (economia de ~300MB e minutos de build). Se algum coletor futuro precisar de browser headless, isso não funcionará no free tier — prefira sempre achar a API JSON da fonte.

**Env vars da API em produção:** `DATABASE_URL` (injetada do radar-db; formato `postgres://` — o `config.py` normaliza), `REDIS_URL` (injetada), `SECRET_KEY` (gerada pelo Render), `ENVIRONMENT=production`, `ALLOWED_ORIGINS` (JSON array como string — precisa incluir a URL real do frontend), `ENABLE_SCHEDULER=true`, `ANTHROPIC_API_KEY` (**ainda não configurada**), `RESEND_API_KEY` (**ainda não configurada**).

---

## 8. Endpoints da API

Prefixo: `/api/v1`. Docs interativas: `/docs`.

**Públicos:**
- `GET /health` — status API + banco
- `GET /api/v1/normativos` — filtros: `fonte`, `setor`, `tipo`, `data_inicio`, `data_fim`, `q` (busca ILIKE em título/ementa/resumo), `processado_ia`, paginação `page`/`page_size` (máx 100)
- `GET /api/v1/normativos/stats` — total, novos hoje, contagens por fonte/setor/tipo, processados/pendentes IA
- `GET /api/v1/normativos/{id}` — detalhe completo

**Admin** (header `x-admin-key` = primeiros 32 caracteres da `SECRET_KEY` — ver função `_get_admin_key()` em `admin.py`):
- `POST /api/v1/admin/collect/{fonte}` — roda coletor sincronamente; `fonte` ∈ {dou, aneel, antt, anac, anatel, anm, tcu, camara, senado, stj_stf, all}. Resposta inclui `total_encontrados`, `total_novos`, `erro` e `erros_salvar[]` por fonte.
- `GET /api/v1/admin/collect/status` — últimos 20 `job_logs`
- `GET /api/v1/admin/test/senado` — diagnóstico: devolve resposta bruta da API do Senado (modelo a copiar para outras fontes)

**Rota-armadilha:** `GET /normativos/stats` precisa estar declarada **antes** de `GET /normativos/{id}` no arquivo (senão o FastAPI tenta converter "stats" para int). Já está na ordem certa em `normativos.py` — mantenha assim.

Comandos de teste em produção:

```bash
ADMIN_KEY="<primeiros 32 chars da SECRET_KEY no dashboard do Render>"

# coleta individual
curl -s --max-time 120 -X POST \
  "https://radar-api-zefw.onrender.com/api/v1/admin/collect/senado" \
  -H "x-admin-key: $ADMIN_KEY" | python3 -m json.tool

# todos
for fonte in dou aneel antt anac anatel anm tcu camara senado stj_stf; do
  echo "=== $fonte ===" 
  curl -s --max-time 120 -X POST \
    "https://radar-api-zefw.onrender.com/api/v1/admin/collect/$fonte" \
    -H "x-admin-key: $ADMIN_KEY" | python3 -m json.tool
done

# conferir dados
curl -s "https://radar-api-zefw.onrender.com/api/v1/normativos?limit=5" | python3 -m json.tool
curl -s "https://radar-api-zefw.onrender.com/api/v1/normativos/stats" | python3 -m json.tool
```

> A `SECRET_KEY` atual foi gerada pelo Render e está no dashboard (radar-api → Environment). **Rode a rotação dela antes do lançamento comercial** — ela circulou em terminais/screenshots durante o desenvolvimento. Rotacionar = regenerar no Render; a admin key muda junto (são os primeiros 32 chars).

---

## 9. Frontend

- `src/lib/api.ts` — cliente axios + todos os tipos TS espelhando os schemas Pydantic. `NEXT_PUBLIC_API_URL` define a base (fallback `http://localhost:8000`).
- Páginas: `/` (dashboard com stats), `/normativos` (lista com filtros), `/normativos/[id]` (detalhe).
- **Variáveis `NEXT_PUBLIC_*` são embutidas no build** — mudou a env no Render, precisa **rebuild** do frontend, não só restart.
- CORS: a URL do frontend precisa estar em `ALLOWED_ORIGINS` da API (hoje: `radar-frontend-y3i5.onrender.com` está no default do `config.py` e na env do Render).

---

## 10. Cronologia completa de erros e correções (leitura obrigatória)

Cada item: **sintoma → causa raiz → correção (commit)**.

### Fase 1 — Deploy no Render

1. **Blueprint rejeitado: `fromService cannot refer to property and env var`** → `render.yaml` combinava `property` e `envVarKey` no mesmo `fromService` → usar `value:` estático para `NEXT_PUBLIC_API_URL` (`cba5d38`).
2. **Blueprint rejeitado: `must specify IP allow list`** → serviço redis sem `ipAllowList` → adicionar `ipAllowList: []` (`cba5d38`).
3. **Workers Celery falhando no deploy** → plano free não tem background workers → remover `radar-worker`/`radar-beat` do Blueprint e embutir APScheduler na API com `ENABLE_SCHEDULER=true` (`09d5d36`).
4. **Blueprint rejeitado: `nodeVersion` inválido** → campo não existe no schema do render.yaml → env var `NODE_VERSION: "20"` + arquivo `.node-version` (`442cdd2`).
5. **Frontend build exit 1 sem erro claro** → `output: "standalone"` no `next.config.js` incompatível com `npm start` no Render → removido; adicionados `ignoreBuildErrors`/`ignoreDuringBuilds` (`09d5d36`).
6. **Build: `Cannot find module 'tailwindcss'`** → Render instala com NODE_ENV=production e pula devDependencies → `npm install --include=dev` no buildCommand (`88ed46c`).
7. **Build: `Module not found: Can't resolve '@/lib/api'`** → o `.gitignore` tinha `lib/` **sem âncora**, que casa com `frontend/src/lib/` → arquivo nunca havia sido commitado → corrigir para `/lib/` (raiz apenas) e commitar `api.ts` (`39bc460`). **Lição: padrões de .gitignore sem `/` inicial casam em QUALQUER nível da árvore.**
8. **Frontend com "Failed to fetch"** → `NEXT_PUBLIC_API_URL` apontava para `radar-api.onrender.com`, mas o Render gera sufixo único (`radar-api-zefw`) → corrigir URL real (`71e1e14`) + lembrar de rebuild (item 9 da Seção 7).

### Fase 2 — Coleta silenciosamente quebrada (o debug mais longo)

9. **`POST /admin/collect/all` "iniciava" mas o banco ficava vazio** → `BackgroundTasks` do FastAPI são mortas pelo Render free após a resposta → reescrever endpoint para execução **síncrona** devolvendo resultados completos (`e47ad81`).
10. **Save falhava DEPOIS do commit** → `processar_normativo_ia.delay()` (Celery) lançava exceção com Redis indisponível, estourando `salvar_normativo` após o commit → envolver em try/except; IA vira opcional (`0bfac02`).
11. **SENADO: `total_encontrados: 1, total_novos: 0` com banco vazio, sem nenhum erro visível** → dois problemas empilhados e invisíveis. Técnica que destravou: (a) logar exceções com `exc_info=True` e re-raise (`39dd358`); (b) **devolver os erros no JSON da resposta** (`erros_salvar[]`, `e05a685`); (c) **endpoint de diagnóstico** devolvendo a resposta bruta da API externa (`9e76b9d`). **Sem acesso fácil aos logs do Render free, a resposta HTTP é seu console de debug.**
12. **API Senado devolvia HTTP 400 "Termo de pesquisa no índice inválido"** → o parâmetro `palavraChave` NÃO aceita texto livre (só termos indexados) → remover keyword, buscar **somente por período** (`dataInicioApresentacao`/`dataFimApresentacao`) e filtrar/classificar localmente (`e031d4e`, `26ebdad`).
13. **INSERT falhava: `column "tags" is of type character varying[] but expression is of type json`** → migration 0001 criou `tags`/`setores_interesse` como `ARRAY(VARCHAR)`, mas o modelo SQLAlchemy usa `JSON` → migration 0002 com `ALTER TABLE ... TYPE JSONB USING to_jsonb(...)` (`893ac11`). **Lição: o modelo e a migration foram escritos em momentos diferentes e nunca validados um contra o outro em Postgres real (o dev local rodava SQLite, que aceita tudo). Teste as migrations contra Postgres de verdade.**
14. **582 encontrados, 1 salvo, zero erros** → matérias sem ementa geravam `conteudo_bruto` idêntico (`"Tipo: PL /\nAutor: \nEmenta: "`) → hash igual → dedup descartava tudo como duplicata do primeiro → incluir a **URL** no hash: `sha256(f"{url}|{conteudo}")` (`d8cd3a8`).
15. **Parser do Senado lia campos que não existem** → o código foi escrito contra a estrutura antiga/documentada (`IdentificacaoMateria.SiglaTipoMateria` etc.), mas a API v7 devolve estrutura **flat**: `{Codigo, Sigla, Numero, Ano, Ementa, Autor, Data, UrlDetalheMateria, DescricaoIdentificacao}` → parser reescrito contra a resposta real observada no endpoint de diagnóstico (`46a6294`, `7fe56e6`).
16. **Endpoint estourava o tempo com 582 itens (resposta vazia)** → cada item fazia `SELECT` + `INSERT` + `COMMIT` em sessão própria → reescrever para batch: hashes calculados em memória, **um** `SELECT IN`, **um** `commit` (`09c0de4`).
17. **DOU: `module 'app.collectors.dou' has no attribute 'DouCollector'`** → `COLLECTOR_MAP` do admin usava nomes derivados (`DouCollector`, `AneelCollector`...), mas as classes reais são `DOUCollector`, `ANEELCollector`, `STJSTFCollector`... → corrigir o mapa com os nomes exatos (`2e43dcc`). **Nome de classe não é derivável mecanicamente do nome do módulo neste projeto.**
18. **DOU/CAMARA/STJ_STF: timeout (>120s)** → três causas somadas: scraping HTML de portais lentos com seletores errados; fallback JSON por keyword; e o retry tenacity de `self._get()` (3 tentativas × backoff até 30s) multiplicado por N keywords → reescrever DOU para o índice JSON oficial, remover o N+1 da Câmara (`_buscar_ementa_completa` por proposição), STJ/STF só REST (`12909b1`); httpx fresco com timeout de 15s e menos keywords (`ca1ae93`).
19. **[Encontrado na revisão final] O scheduler diário NUNCA persistiria dados** → `main.py::run_collector` chamava `collector.coletar()` (só baixa, não salva) em vez de `executar()`, **e** derivava nomes de classe errados (mesmo bug do item 17, numa segunda cópia da lógica) → reutilizar `COLLECTOR_MAP` e chamar `executar()` (`48db6d5`). **Lição dupla: (a) o mesmo bug reapareceu porque a lógica foi duplicada — centralize; (b) a coleta agendada nunca tinha sido testada de fato, só a manual.**

---

## 11. Checklist de armadilhas — NÃO repita estes erros

**Integração com APIs públicas brasileiras:**
- [ ] Escreva parsers contra a **resposta real** (endpoint de diagnóstico), nunca contra documentação — Senado v7 provou que a doc mente.
- [ ] Trate HTTP 400 de APIs gov como erro de **contrato** (parâmetro não suportado), não como indisponibilidade.
- [ ] Cheque metadados de descontinuação (`Descontinuacao`, avisos no XSD) — a API do Senado em uso **já passou da data de desligamento anunciada**; migre para `/dadosabertos/processo`.
- [ ] Evite scraping HTML; quando inevitável, isole os seletores e monitore retorno 0 como alarme.
- [ ] O IP do datacenter (Render) pode ser tratado diferente do seu IP local — teste do ambiente de produção.

**Banco de dados:**
- [ ] Valide modelo × migration contra **PostgreSQL real** antes do deploy (SQLite mascara diferenças de tipo — foi assim que ARRAY vs JSON passou).
- [ ] Ao adicionar valor em Enum Python, crie migration `ALTER TYPE ... ADD VALUE`.
- [ ] Insira em **batch** (1 SELECT de dedup + 1 commit); nunca N sessões em loop numa request HTTP.
- [ ] Hash de dedup precisa incluir um componente **garantidamente único por item** (URL/ID da fonte), não só o conteúdo.

**Render free tier:**
- [ ] Nada de background: sem workers, sem `BackgroundTasks` — trabalho pesado ou é síncrono na request (<100s) ou vai para o APScheduler in-process.
- [ ] Resposta vazia + `Expecting value: line 1 column 1` = a plataforma cortou a conexão (tempo), não é bug de JSON.
- [ ] Push não faz deploy — sempre "Manual Deploy" depois; e mudança de `NEXT_PUBLIC_*` exige **rebuild** do frontend.
- [ ] Hostnames ganham sufixo aleatório no primeiro deploy — não hardcode antes de conhecê-los.

**Código:**
- [ ] `COLLECTOR_MAP` em `admin.py` é a **fonte única** de mapeamento fonte→classe. Se criar coletor novo, registre lá (o scheduler importa de lá). Não derive nomes de classe por convenção.
- [ ] Retry com backoff exponencial (tenacity) é veneno dentro de um endpoint síncrono com prazo — para fontes lentas use timeout curto e falhe rápido.
- [ ] Não deixe `except Exception` engolir erro sem devolvê-lo em algum canal observável (resposta HTTP, `JobLog.erro`, `erros_salvar[]`).
- [ ] `.gitignore`: padrões sem `/` inicial casam em qualquer nível. Confirme com `git check-ignore -v <arquivo>`.

---

## 12. Como rodar e testar

**Local (SQLite, sem Docker):**
```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export DATABASE_URL="sqlite:///./radar.db"
alembic upgrade head          # ATENÇÃO: migration 0002 tem SQL específico de Postgres;
                              # para SQLite use create_tables() de app/database.py se falhar
uvicorn app.api.main:app --reload
# noutra aba:
cd frontend && npm install && NEXT_PUBLIC_API_URL=http://localhost:8000 npm run dev
```

**Local (Postgres, igual produção):**
```bash
docker-compose up -d          # sobe postgres/redis
export DATABASE_URL="postgresql://radar:radar@localhost:5432/radar_regulatorio"
cd backend && alembic upgrade head && uvicorn app.api.main:app --reload
```

**Testar coletores sem HTTP:** `python scripts/run_collectors.py` (ou chame `SenadoCollector().executar()` num REPL asyncio).

**Produção:** Seção 8 tem os comandos curl. Fluxo padrão de trabalho usado até aqui: editar → commit → push na branch → **Manual Deploy** no Render (radar-api) → curl de teste → ler `erros_salvar`/`erro` na resposta.

---

## 13. Configuração e credenciais

| Item | Onde está | Observação |
|---|---|---|
| `SECRET_KEY` | Render → radar-api → Environment | Gerada pelo Render. Admin key = primeiros 32 chars. **Rotacionar antes do lançamento** (circulou em terminais durante o debug). |
| `DATABASE_URL` | Injetada pelo Render (radar-db) | Formato `postgres://` — normalização automática no `config.py`. |
| `REDIS_URL` | Injetada (radar-redis) | Hoje sem uso efetivo (Celery desativado). |
| `ANTHROPIC_API_KEY` | **NÃO CONFIGURADA** | Necessária para o `IAProcessor`. Modelo configurado: `claude-sonnet-4-6` (`config.py::ai_model`). |
| `RESEND_API_KEY` | **NÃO CONFIGURADA** | Para os alertas de e-mail (não implementados). |
| `ALLOWED_ORIGINS` | Render env + default no `config.py` | Precisa conter a URL exata do frontend. |
| `ENABLE_SCHEDULER` | `true` no Render | Liga o APScheduler no startup da API. |

---

## 14. Dívida técnica e pendências (em ordem de prioridade)

1. **Validar CAMARA e STJ_STF** após deploy do `ca1ae93`+`48db6d5` (correções ainda não testadas em produção).
2. **Consertar DOU** — diagnosticar o índice JSON real (endpoint de teste) e ajustar o parser.
3. **Reescrever ANEEL/ANTT/ANAC/ANM/TCU** para APIs de dados abertos (CKAN/dados.gov.br) — os atuais fazem scraping HTML morto. Retorno 0 sem erro = parser não casa com a página.
4. **Migrar SENADO** para a API substituta `/dadosabertos/processo` antes do desligamento definitivo da antiga.
5. **Configurar `ANTHROPIC_API_KEY`** e criar um endpoint admin `POST /admin/process-ia` que chame `IAProcessor.processar_lote()` sincronamente (mesmo padrão dos coletores — sem Celery no free tier). Nota: o `IAProcessor` usa o cliente **síncrono** `anthropic.Anthropic` dentro de método async — bloqueia o event loop; trocar por `anthropic.AsyncAnthropic` ao ativar.
6. **Código Celery vestigial** (`app/tasks/`) — mantido para um futuro upgrade de plano. A chamada `processar_normativo_ia.delay()` em `salvar_normativo()` (caminho individual, não o batch) falha silenciosamente sem Redis. O caminho batch **não** dispara IA — de qualquer forma hoje a IA não roda; ao implementar o item 5, remova essas chamadas e processe via lote.
7. **Autenticação/multi-tenancy** para o SaaS (modelo `Usuario` e JWT settings já existem em `config.py`; nada implementado de rotas).
8. **Alertas por e-mail** (modelo `Alerta` pronto; integração Resend pendente).
9. **Reativar checagem de tipos no build do frontend** (remover `ignoreBuildErrors`/`ignoreDuringBuilds`).
10. **Keep-alive/cron externo** para o free tier (cold start pode fazer o APScheduler perder janelas se o serviço estiver dormindo na hora do job — considerar um cron externo chamando `/admin/collect/all` como redundância).
11. **Migration 0002 não roda em SQLite** (SQL Postgres-specific) — dev local em SQLite deve usar `create_tables()`; considerar guardas de dialeto na migration.

---

## 15. Guia de integração com outro sistema

Pontos de acoplamento, do mais desacoplado ao mais invasivo:

**A) Consumir a API REST (recomendado para começar).** `GET /api/v1/normativos` com filtros + `stats`. Sem autenticação hoje (somente os endpoints admin têm chave). Se o outro sistema precisa de dados, este é o caminho: nenhum acoplamento de banco, contrato documentado em `/docs` (OpenAPI).

**B) Compartilhar o banco (leitura).** As tabelas da Seção 4 são estáveis; `normativos.hash_conteudo` é a chave natural para sincronização incremental (junto com `created_at`). Cuidado com os tipos ENUM do Postgres se o outro sistema escreve.

**C) Absorver os coletores como biblioteca.** `app/collectors/` depende de: `app.database.AsyncSessionLocal`, `app.models.normativo`, `app.config.settings`. Para transplantar: leve `base.py` + coletores + modelos + as duas migrations; registre as classes num `COLLECTOR_MAP` central (não derive nomes!); releia a Seção 5 e a Seção 11 inteiras.

**D) Eventos.** Não há hoje fila/webhook de "novo normativo". Se a integração precisar de push: o ponto de inserção é `BaseCollector._salvar_batch()` — logo após o `commit()` bem-sucedido há a lista `new_items` com tudo que entrou. Emita o evento ali (outbox table é a opção segura, dado o histórico do item 10 da Seção 10: **nunca** deixe uma falha de publicação estourar depois do commit).

**Contrato mínimo de um item coletado** (o que qualquer novo produtor de dados precisa fornecer): `titulo`, `tipo` (Enum), `fonte` (Enum), `setor` (Enum, default GERAL), `url` (única por item — participa do hash), `data_publicacao`, `ementa`/`conteudo_bruto`, `tags` (lista). A deduplicação e persistência já são resolvidas pelo `_salvar_batch()`.

---

*Relatório gerado a partir da revisão completa do histórico de desenvolvimento (28 commits, de `7171d66` a `48db6d5`), incluindo todos os erros de deploy e depuração registrados na conversa de desenvolvimento.*
