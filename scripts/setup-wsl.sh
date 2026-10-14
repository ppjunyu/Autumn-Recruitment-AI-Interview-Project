#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

if ! command -v docker >/dev/null 2>&1; then
  echo "WSL 里还没有 Docker。请先安装 Docker，或自行安装 PostgreSQL 16 和 pgvector。"
  exit 1
fi

docker compose up -d postgres
python3 -m venv .venv
.venv/bin/pip install -U pip
.venv/bin/pip install -r backend/requirements.txt
if [[ ! -f .env ]]; then
  cp .env.example .env
  echo "已创建 .env。请把 Qwen_API_KEY 填进去。"
fi
set -a
source .env
set +a
cd backend
../.venv/bin/python -m app.seed
cd ../frontend
npm install
echo "数据库和虚拟环境已准备。嵌入模型请在本机执行："
echo "  .venv/bin/pip install torch --index-url https://download.pytorch.org/whl/cu128"
echo "  .venv/bin/pip install -r backend/requirements-embed.txt"
echo "  cd backend && ../.venv/bin/python -m app.reindex"
echo "启动：cd backend && ../.venv/bin/uvicorn app.main:app --port 8000"
echo "另开终端：cd frontend && npm run dev"
