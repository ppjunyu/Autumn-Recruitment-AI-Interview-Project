"""写入两三条虚构电力岗位数据。在 WSL 里执行：python -m app.seed"""

from sqlalchemy import select

from app.chunking import chunk_document
from app.envfile import load_env_file
from app.recruit_db import init_recruit_db
from app.recruit_models import Candidate, Job, KnowledgeChunk, KnowledgeDocument

MATERIALS = {
    "billing": """# 电费核算规则

电费按抄表读数和阶梯单价计算。异常标记包括缺失读数、负电量和单价缺失。对账文件要和财务系统的应收字段一一对应。

# 欠费提醒

工单状态分为待提醒、已发送、已回访。失败重试必须带业务单号，避免同一户号被重复提醒。
""",
    "bank": """# 沟通协作

请讲一次你和业务人员对规则理解不一致的经历。说明你如何确认口径，以及最后怎么验收。

# 故障处理

请讲一次线上重复执行或数据不一致的问题。说明现象、原因和你做的去重或校验。
""",
}


def seed(session) -> None:
    if session.scalar(select(Job.id).limit(1)):
        return
    billing = Job(
        id="job-billing",
        company="山东鲁软",
        department="营销部",
        title="电费核算后端开发",
        jd_code="JD-YX-001",
        responsibilities="参与电费核算、欠费提醒和工单查询接口，与财务系统对账。",
        requirements="熟悉 Python 或 Java，能讲清计价和异常标记规则。",
        preferred="有过幂等或对账经历。",
        is_management=False,
    )
    dispatch = Job(
        id="job-dispatch",
        company="北京南瑞",
        department="调度部",
        title="调度自动化开发",
        jd_code="JD-DD-014",
        responsibilities="维护告警接入和值班查询接口，整理故障复盘记录。",
        requirements="了解时序数据或消息队列，能把告警误报的处理过程讲清楚。",
        preferred="有过现场值班或监控平台经历。",
        is_management=False,
    )
    session.add_all([billing, dispatch])
    session.add_all(
        [
            Candidate(
                id="cand-zhou",
                job_id=billing.id,
                name="周宁",
                company=billing.company,
                department=billing.department,
                position=billing.title,
                jd_code=billing.jd_code,
                resume_text="负责电费核算接口。输入是抄表读数和计价规则，输出是应收金额和异常标记。做过财务对账字段映射。欠费提醒上线后出现重复提醒，后来用业务单号做了去重。",
                screening_status="passed",
            ),
            Candidate(
                id="cand-li",
                job_id=dispatch.id,
                name="李衡",
                company=dispatch.company,
                department=dispatch.department,
                position=dispatch.title,
                jd_code=dispatch.jd_code,
                resume_text="做过告警接入。把遥测抖动造成的误报先做了时间窗合并，再推给值班查询。写过一次开关拒动的复盘，记录了报文时间和处理人。",
                screening_status="passed",
            ),
            Candidate(
                id="cand-zhao",
                job_id=billing.id,
                name="赵敏",
                company=billing.company,
                department=billing.department,
                position=billing.title,
                jd_code=billing.jd_code,
                resume_text="参与过账单查询页面的接口联调，负责把异常标记展示给营业厅。没有独立设计过计价规则。",
                screening_status="passed",
            ),
        ]
    )
    _add_doc(session, billing, "position_material", "电费核算规则.txt", "本岗位", MATERIALS["billing"])
    _add_doc(session, billing, "question_bank", "营销初试题库.txt", "岗位模板", MATERIALS["bank"])
    session.commit()


def _add_doc(session, job: Job, kind: str, filename: str, label: str, text: str) -> None:
    document = KnowledgeDocument(
        id=f"doc-{job.id}-{kind}",
        kind=kind,
        company=job.company,
        department=job.department,
        position=job.title,
        filename=filename,
        source_label=label,
    )
    session.add(document)
    for index, piece in enumerate(chunk_document(text)):
        session.add(
            KnowledgeChunk(
                id=f"chunk-{document.id}-{index}",
                document_id=document.id,
                heading=piece["heading"],
                text=piece["text"],
                content_hash=piece["content_hash"],
                embedding=None,
                meta={"filename": filename, "heading": piece["heading"], "embedded": False},
                company=job.company,
                department=job.department,
                position=job.title,
                kind=kind,
            )
        )


def main() -> None:
    load_env_file()
    init_recruit_db()
    from app.recruit_db import SessionLocal

    if SessionLocal is None:
        raise SystemExit("请先设置 RECRUIT_DATABASE_URL 并启动 PostgreSQL")
    session = SessionLocal()
    seed(session)
    session.close()
    print("虚构数据已写入。向量仍为空，在本机执行 python -m app.reindex 后才会用 bge-m3 补嵌入。")


if __name__ == "__main__":
    main()
