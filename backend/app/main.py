from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import os
from fastapi.responses import FileResponse, RedirectResponse
from .database import engine, Base, SessionLocal
from . import models
from .config import APP_VERSION
from .auth import hash_password
from .routers import auth, exams, questions, students, statistics, upload, settings, distributions, arenas, arenas_ws

# 创建所有表
Base.metadata.create_all(bind=engine)

# 迁移：为 exams 表添加 total_score 和 retake_limit 列
from sqlalchemy import text

def _backfill_total_score():
    """回填已有考试的 total_score"""
    db = SessionLocal()
    try:
        from . import crud as _crud, models as _models
        from . import paper as _paper
        all_exams = db.query(_models.Exam).all()
        for exam in all_exams:
            if getattr(exam, "random_mode", False):
                rules = _paper.parse_rules(exam.random_rules)
                exam.total_score = _paper.estimate_total_score(db, exam, rules)
            else:
                exam.total_score = _crud._calc_total_score(exam)
        db.commit()
    finally:
        db.close()

def _add_column(ddl: str) -> None:
    """幂等地补一列。

    每条语句使用独立连接：单条 DDL 失败（如列已存在）会让该连接进入
    aborted 事务状态，若复用同一连接，后续迁移会连环失败并被静默吞掉。
    """
    with engine.connect() as conn:
        try:
            conn.execute(text(ddl))
            conn.commit()
        except Exception:
            conn.rollback()


def _sync_sequences() -> None:
    """把 Postgres 主键序列重置到各表当前的最大 id。

    历史数据从 SQLite 迁移过来时是显式写入 id 的，序列却仍停在 1。
    之后任何 INSERT 都会撞主键唯一约束（新建学员、新增题目、考生交卷
    全部 500）。这里按每张表的实际最大值重置，幂等且可重复执行。

    SQLite 的 rowid 由引擎自行维护，不需要处理。
    """
    if engine.dialect.name != "postgresql":
        return
    with engine.connect() as conn:
        tables = conn.execute(text(
            "SELECT tablename FROM pg_tables WHERE schemaname = 'public'"
        )).scalars().all()
        for table in tables:
            try:
                seq_name = conn.execute(
                    text("SELECT pg_get_serial_sequence(:t, 'id')"),
                    {"t": table},
                ).scalar()
                if not seq_name:
                    continue
                max_id = conn.execute(
                    text(f'SELECT COALESCE(MAX(id), 0) FROM "{table}"')
                ).scalar()
                conn.execute(
                    text("SELECT setval(CAST(:seq AS regclass), :val, true)"),
                    {"seq": seq_name, "val": max_id},
                )
            except Exception:
                conn.rollback()
                continue
        conn.commit()


with engine.connect() as conn:
    try:
        conn.execute(text("ALTER TABLE exams ADD COLUMN total_score FLOAT DEFAULT 0"))
        conn.commit()
    except Exception:
        conn.rollback()

# 随机卷：每人题数相同、题目随机
# 这两列要在 _backfill_total_score 之前补上——那条语句会整行查 exams，
# 模型里已经有这两列了，列不存在会直接报错。
_add_column("ALTER TABLE exams ADD COLUMN random_mode BOOLEAN DEFAULT FALSE")
_add_column("ALTER TABLE exams ADD COLUMN random_rules TEXT DEFAULT '[]'")
# 填空题以前借用 single_score，新增独立分值列时按原单选分值回填，
# 保证已有考试的历史计分口径不变。
_add_column("ALTER TABLE exams ADD COLUMN fill_score INTEGER")
with engine.connect() as conn:
    try:
        conn.execute(text(
            "UPDATE exams SET fill_score = COALESCE(single_score, 10) "
            "WHERE fill_score IS NULL"
        ))
        conn.commit()
    except Exception:
        conn.rollback()

_backfill_total_score()

_add_column("ALTER TABLE exams ADD COLUMN retake_limit INTEGER DEFAULT 0")
_add_column("ALTER TABLE users ADD COLUMN is_active INTEGER DEFAULT 1")
_add_column("ALTER TABLE arenas ADD COLUMN current_question_id INTEGER")
_sync_sequences()

# 布尔列历史上允许为 NULL，序列化时会直接报错，这里回填并收紧约束
with engine.connect() as conn:
    try:
        conn.execute(text(
            "UPDATE arena_teams SET help_used_this_round = FALSE "
            "WHERE help_used_this_round IS NULL"
        ))
        conn.commit()
    except Exception:
        conn.rollback()
    try:
        conn.execute(text(
            "ALTER TABLE arena_teams ALTER COLUMN help_used_this_round "
            "SET DEFAULT FALSE"
        ))
        conn.execute(text(
            "ALTER TABLE arena_teams ALTER COLUMN help_used_this_round SET NOT NULL"
        ))
        conn.commit()
    except Exception:
        conn.rollback()
app = FastAPI(title="医学考试系统 API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(exams.router)
app.include_router(exams.record_router)
app.include_router(questions.router)
app.include_router(students.router)
app.include_router(statistics.router)
app.include_router(upload.router)
app.include_router(settings.router)
app.include_router(distributions.router)
app.include_router(distributions.invite_router)
app.include_router(distributions.exam_login_router)
app.include_router(distributions.exam_student_router)
app.include_router(arenas.router)
app.include_router(arenas_ws.router)

@app.get("/uploads/{filename:path}")
def serve_upload(filename: str):
    """提供 /uploads/images/xxx：先读本地磁盘，读不到再重定向到 Supabase/Blob。

    以前这里只会重定向到 Blob，没配 BLOB_READ_WRITE_TOKEN 时直接 404，
    于是本地库（题库里存的是 /uploads/images/xxx 相对路径）里的题图全军覆没。
    """
    from .storage import blob_url_for, blob_enabled, find_local_image, supabase_enabled

    path = find_local_image(filename)
    if path:
        return FileResponse(path)
    if blob_enabled() or supabase_enabled():
        return RedirectResponse(url=blob_url_for(filename), status_code=302)
    raise HTTPException(status_code=404, detail="文件不存在")

@app.on_event("startup")
def warn_local_database():
    """没配 DATABASE_URL 时后端会静默切到本地 SQLite 题库，提醒一句。

    这不是错误（本地开发确实可能只想用 exam.db），但局域网开考时如果忘了
    载入 .env.local，考生看到的是另一套题，题图也全是本地相对路径，
    排查起来很费时间。
    """
    from .database import DATABASE_URL

    if not DATABASE_URL:
        import sys

        print(
            "[警告] 未设置 DATABASE_URL，正在使用本地 SQLite 题库 "
            "(backend/exam.db)。局域网开考请用 scripts/start-lan.ps1 启动，"
            "或先载入 .env.local。",
            file=sys.stderr,
        )


@app.on_event("startup")
def init_admin():
    """启动时初始化管理员账号"""
    db = SessionLocal()
    try:
        from . import crud, schemas
        if not crud.get_user_by_employee_id(db, "admin"):
            admin = crud.create_user(db, schemas.UserCreate(
                employee_id="admin",
                name="管理员",
                password="admin123",
                dept="管理部",
                role="系统管理员",
                is_admin=True,
            ))
            # 创建示例数据
            _create_sample_data(db, crud, schemas, admin.id)
    finally:
        db.close()

def _create_sample_data(db, crud, schemas, creator_id: int):
    """创建示例考试数据"""
    # 创建示例题目
    sample_questions = [
        # 单选题
        schemas.QuestionCreate(
            type="single",
            content="下列哪项是心脏骤停的典型表现？",
            options='{"A":"意识丧失","B":"面色苍白","C":"四肢抽搐","D":"出汗"}',
            answer="A",
            analysis="心脏骤停最典型的表现是意识丧失，其他选项是伴随症状。",
            category="急救"
        ),
        schemas.QuestionCreate(
            type="single",
            content="高血压的诊断标准是？",
            options='{"A":"收缩压≥140mmHg","B":"收缩压≥130mmHg","C":"收缩压≥120mmHg","D":"收缩压≥110mmHg"}',
            answer="A",
            analysis="根据中国高血压指南，收缩压≥140mmHg可诊断为高血压。",
            category="内科"
        ),
        schemas.QuestionCreate(
            type="single",
            content="糖尿病的典型症状不包括？",
            options='{"A":"多饮","B":"多食","C":"多汗","D":"体重下降"}',
            answer="C",
            analysis="糖尿病典型症状为三多一少：多饮、多食、多尿、体重下降，多汗不是典型症状。",
            category="内科"
        ),
        # 判断题
        schemas.QuestionCreate(
            type="judgment",
            content="心肺复苏时，胸外按压的频率应为100-120次/分。",
            options='{"T":"正确","F":"错误"}',
            answer="T",
            analysis="根据最新心肺复苏指南，胸外按压频率应为100-120次/分。",
            category="急救"
        ),
        schemas.QuestionCreate(
            type="judgment",
            content="阿司匹林可用于儿童退热。",
            options='{"T":"正确","F":"错误"}',
            answer="F",
            analysis="儿童退热应选用对乙酰氨基酚或布洛芬，阿司匹林可能导致瑞氏综合征。",
            category="儿科"
        ),
        # 多选题
        schemas.QuestionCreate(
            type="multiple",
            content="下列哪些是心血管疾病的危险因素？",
            options='{"A":"高血压","B":"糖尿病","C":"吸烟","D":"肥胖"}',
            answer="ABCD",
            analysis="高血压、糖尿病、吸烟、肥胖都是心血管疾病的危险因素。",
            category="内科"
        ),
        schemas.QuestionCreate(
            type="multiple",
            content="心肺复苏的主要步骤包括？",
            options='{"A":"胸外按压","B":"开放气道","C":"人工呼吸","D":"电除颤"}',
            answer="ABC",
            analysis="心肺复苏包括CAB循环：胸外按压、开放气道、人工呼吸，电除颤是后续操作。",
            category="急救"
        ),
    ]

    created_questions = []
    for q in sample_questions:
        question = crud.create_question(db, q)
        created_questions.append(question)

    # 创建示例考试
    from datetime import datetime, timedelta
    now = datetime.now()
    exam = crud.create_exam(db, schemas.ExamCreate(
        title="医学基础知识测试",
        duration=60,
        start_time=now - timedelta(hours=1),
        end_time=now + timedelta(days=7),
        pass_score=60,
        single_score=10,
        fill_score=10,
        multiple_score=20,
        judgment_score=5,
        retake_limit=3,
        question_ids=[q.id for q in created_questions]
    ), creator_id)

@app.get("/")
def root():
    return {"message": "医学考试系统 API 运行中", "version": APP_VERSION}


@app.get("/api/version")
def get_version():
    """当前后端版本号。线上排查时先打这个接口，确认跑的是哪一版。"""
    return {"version": APP_VERSION}
