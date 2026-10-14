# 秋招复刻：AI 招聘面试智能体

可交互的初试切片：用简历和岗位说明出题，文字作答，按规则追问并生成三阶段记录。

长期背景在 [`docs/context.md`](docs/context.md)。

## 运行

```bash
python3 -m venv .venv
.venv/bin/pip install -r backend/requirements.txt
cd backend && ../.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
```

另一个终端：

```bash
cd frontend
npm install
npm run dev
```

打开 `http://127.0.0.1:5173`。后端测试：`cd backend && ../.venv/bin/pytest`。

可选大模型：同时设置 `LLM_API_KEY`、`LLM_BASE_URL`、`LLM_MODEL`（OpenAI 兼容接口）。没配齐时出题和追问用模板。模型改写追问如果丢掉候选人原话，会退回模板。

## 这一版实际接上的部分

- Vue3 界面：新建场次、查看检索证据、文字面试、初试记录、能力卡点
- FastAPI 保存场次（SQLite）
- LangGraph：出题图是检索再组题；作答图是判定、追问或评分
- 中文检索用字二元组上的 BM25，题目引用命中的原句

## 当前卡点

- 没有大模型密钥，也没有足够内存和 GPU 在本地跑 Qwen
- 没有语音识别，录音上传会返回未配置
- 没有 PostgreSQL / pgvector，没有 Redis / Celery
- 没有钉钉应用凭证和企业租户
- 没有真实候选人数据，页面里的周宁是虚构示例
