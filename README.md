# 秋招复刻：AI 招聘面试智能体

当前界面是企业 HR 出题台：人员列表、面试题配置、岗位资料和题库、题单审阅。发起面试只生成账号、密码和登录地址，候选人打开链接后看到已勾选的题干。

长期背景在 [`docs/context.md`](docs/context.md)。功能一的确认方案在 [`docs/feature-question-generation.md`](docs/feature-question-generation.md)。

请在个人电脑的 WSL 里运行。云环境只负责改仓库，不启动页面、PostgreSQL 或嵌入模型。

## 准备

WSL 需要 Docker，以及本机的 NVIDIA 驱动（RTX 5060 8GB 用于 bge-m3）。

```bash
bash scripts/setup-wsl.sh
```

脚本会启动带 pgvector 的 PostgreSQL 16，创建仓库根目录的 `.venv`，安装后端依赖，复制 `.env.example`，并写入三条虚构电力岗位数据。

然后编辑 `.env`：

```bash
Qwen_API_KEY=你的密钥
QWEN_BASE_URL=https://maas.qianwenaiapi.com/compatible-mode/v1
QWEN_MODEL=qwen3.8-flash
RECRUIT_DATABASE_URL=postgresql+psycopg://recruit:recruit@127.0.0.1:5432/recruit
EMBEDDING_MODEL=BAAI/bge-m3
EMBEDDING_DEVICE=cuda
```

实际默认地址写在 `.env.example`，以该文件为准。没有 `Qwen_API_KEY` 时，出题接口直接报错。

嵌入模型单独安装，避免在没有 GPU 的机器上下载：

```bash
.venv/bin/pip install torch --index-url https://download.pytorch.org/whl/cu128
.venv/bin/pip install -r backend/requirements-embed.txt
cd backend && ../.venv/bin/python -m app.reindex
```

种子数据的向量一开始是空的。`reindex` 用 bge-m3 补上 1024 维向量。显存不够时把 `EMBEDDING_DEVICE` 改成 `cpu`。

## 启动

```bash
cd backend && ../.venv/bin/uvicorn app.main:app --port 8000
```

另一个终端：

```bash
cd frontend && npm run dev
```

打开 `http://127.0.0.1:5173`。侧栏可以切换 HR 和团队负责人。负责人只能看已生成列表。

不使用 Docker 时，自行安装 PostgreSQL 16 和 pgvector，把 `RECRUIT_DATABASE_URL` 指到本机库，再执行 `cd backend && ../.venv/bin/python -m app.seed`。

## 这一版的出题路径

- 上传的长文档按标题和段落切片，去掉过短和重复块，原文、元数据和向量写入 PostgreSQL。
- 出题先用候选人信息抽关键词做召回，再按公司、部门、岗位过滤。未勾选的岗位资料不进入提示词，同一岗位的题库保留。
- 取前 6 段拼进提示词，由 Qwen 返回题干、类别、难度、时长、评估要点和权重、参考答案、引用片段。
- 暂不计算 Recall@5，也不做 BM25、向量双路和重排。

后端单元测试不连接数据库、不下载模型：

```bash
cd backend && ../.venv/bin/pytest
```

更早的文字初试接口还在 `/api/interviews`。新页面不再进入那个房间。
