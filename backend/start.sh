#!/bin/bash
set -e

echo "==> Aguardando banco de dados..."
python3 -c "
import time, psycopg2, os
url = os.environ.get('DATABASE_URL', '')
if not url or 'sqlite' in url:
    print('Banco SQLite ou sem DATABASE_URL — pulando espera.')
    exit(0)
# Render usa postgres:// — normalizar
url = url.replace('postgres://', 'postgresql://', 1)
for i in range(30):
    try:
        psycopg2.connect(url)
        print('Banco disponível.')
        exit(0)
    except Exception as e:
        print(f'Tentativa {i+1}/30: {e}')
        time.sleep(2)
print('Banco não respondeu após 60s — abortando.')
exit(1)
"

echo "==> Executando migrations (alembic upgrade head)..."
alembic upgrade head

echo "==> Iniciando API (uvicorn)..."
exec uvicorn app.api.main:app --host 0.0.0.0 --port "${PORT:-8000}"
