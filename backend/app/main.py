import re
import time

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import os
import secrets
import sys
from fastapi.responses import FileResponse, RedirectResponse
from .database import engine, Base, SessionLocal
from . import models
from .config import APP_VERSION, ADMIN_INITIAL_PASSWORD
from .auth import verify_password
from .routers import (auth, exams, questions, students, statistics, upload,
                      settings, distributions, arenas, arenas_ws, billing, organizations,
                      images, past_papers, wrong_questions)

class _Phase:
    """打印启动各阶段耗时。

    后端连的是远端库，建表/补列/校序列都要走网络。以前这些加起来要一分多钟，
    这段时间端口还没绑上，前端点登录只会拿到"网络异常"。
    打印出来才好知道到底卡在哪一步。
    """

    def __init__(self, name):
        self.name = name

    def __enter__(self):
        self._t = time.time()
        return self

    def __exit__(self, *exc):
        print(f"[启动] {self.name} 用时 {time.time() - self._t:.1f}s", file=sys.stderr)
        return False


# 创建所有表
with _Phase("建表 create_all"):
    Base.metadata.create_all(bind=engine)

# 默认机构套餐：导入时就写好（startup 事件里还会再兜一次），
# 这样任何入口（脚本、测试、首次部署）都能直接看到套餐。
try:
    from . import billing as _billing
    _db = SessionLocal()
    try:
        with _Phase("默认套餐"):
            _billing.ensure_default_plans(_db)
    finally:
        _db.close()
except Exception as _e:  # 数据库暂时连不上不影响启动
    print(f"[billing] 初始化默认套餐跳过: {_e}", file=sys.stderr)

# 迁移：为 exams 表添加 total_score 和 retake_limit 列
from sqlalchemy import text

def _backfill_total_score():
    """回填已有考试的 total_score"""
    db = SessionLocal()
    try:
        _phase = _Phase("回填总分")
        from . import crud as _crud, models as _models
        from . import paper as _paper
        # 只有还没算出总分的考试才需要补。题目/考试改动时 CRUD 里本来就会
        # 重算，启动时全量重算一遍纯属浪费（每场考试都要再查一次题目）。
        all_exams = db.query(_models.Exam).filter(
            (_models.Exam.total_score == 0) | (_models.Exam.total_score.is_(None))
        ).all()
        if not all_exams:
            return
        for exam in all_exams:
            if getattr(exam, "random_mode", False):
                rules = _paper.parse_rules(exam.random_rules)
                exam.total_score = _paper.estimate_total_score(db, exam, rules)
            else:
                exam.total_score = _crud._calc_total_score(exam)
        db.commit()
        _phase.__exit__()
    finally:
        db.close()

_ADD_COLUMN_RE = re.compile(r"ALTER TABLE\s+(\w+)\s+ADD COLUMN\s+(\w+)", re.I)

# 所有补列共用一条连接 + 一次列清单查询。
#
# 以前每条 DDL 各开一条连接。数据库在远端（Neon），建一次连接要 1~10 秒，
# 一共十来条补列语句，光迁移就把启动拖到五十多秒——这段时间后端端口还没绑上，
# 前端点登录只会拿到"网络异常"。现在全部共用一条连接、只查一次列清单，
# 已经存在的列连 ALTER 都不用发。
_ddl_conn = None
_ddl_existing = None


def _get_ddl_conn():
    global _ddl_conn
    if _ddl_conn is None or _ddl_conn.closed:
        _ddl_conn = engine.connect()
    return _ddl_conn


def _existing_columns(conn) -> set:
    """一次查完所有已存在的 (表, 列)。"""
    global _ddl_existing
    if _ddl_existing is not None:
        return _ddl_existing
    try:
        rows = conn.execute(text(
            "SELECT table_name, column_name FROM information_schema.columns "
            "WHERE table_schema = 'public'"
        )).fetchall()
        _ddl_existing = {(r[0], r[1]) for r in rows}
    except Exception:
        _ddl_existing = set()
    return _ddl_existing


def _add_column(ddl: str) -> None:
    """幂等地补一列。

    所有补列共用一条连接，先查 information_schema，列已经在就直接跳过
    （大多数情况下一条 ALTER 都不用发）。单条 DDL 失败用 SAVEPOINT 回滚，
    不影响后续语句。
    """
    try:
        conn = _get_ddl_conn()
    except Exception:
        return
    try:
        m = _ADD_COLUMN_RE.search(ddl)
        if m:
            table, column = m.group(1), m.group(2)
            if (table, column) in _existing_columns(conn):
                if conn.in_transaction():
                    conn.rollback()   # information_schema 查询开了隐式事务
                return
        # 上面的查询会开一个隐式事务，conn.begin() 遇到它会直接抛
        # "This connection has already initialized a SQLAlchemy Transaction()"。
        # 异常被吞掉之后，这一条 ALTER 就没执行——补列于是隔一条失败一条，
        # 缺的列要等下次发版才补上。先把事务收掉再开新的。
        if conn.in_transaction():
            conn.rollback()
        trans = conn.begin()
        try:
            with conn.begin_nested():
                conn.execute(text(ddl))
        except Exception:
            pass
        trans.commit()
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass


def _sync_sequences() -> None:
    """把 Postgres 主键序列重置到各表当前的最大 id。

    历史数据从 SQLite 迁移过来时是显式写入 id 的，序列却仍停在 1。
    之后任何 INSERT 都会撞主键唯一约束（新建学员、新增题目、考生交卷
    全部 500）。这里按每张表的实际最大值重置，幂等且可重复执行。

    SQLite 的 rowid 由引擎自行维护，不需要处理。
    """
    if engine.dialect.name != "postgresql":
        return
    # 原来是一张表一条 SELECT、再一条 setval：22 张表就是 66 次网络往返，
    # 在 Neon 上光这一段就要 20 多秒。现在用一个 DO 块一次算完，
    # 整条语句只跑一趟。
    with _Phase("校准序列"), engine.connect() as conn:
        try:
            conn.execute(text("""
                DO $$
                DECLARE r record;
                BEGIN
                  FOR r IN
                    SELECT s.oid AS seq_oid, t.relname AS tbl
                    FROM pg_class s
                    JOIN pg_namespace n ON n.oid = s.relnamespace
                    JOIN pg_depend d ON d.objid = s.oid
                        AND d.classid = 'pg_class'::regclass
                        AND d.deptype IN ('a', 'i')
                    JOIN pg_class t ON t.oid = d.refobjid
                    JOIN pg_namespace tn ON tn.oid = t.relnamespace
                    WHERE s.relkind = 'S'
                      AND n.nspname = 'public'
                      AND tn.nspname = 'public'
                  LOOP
                    EXECUTE format(
                      'SELECT setval(%L, GREATEST((SELECT COALESCE(MAX(id), 0) FROM %I), 1), true)',
                      r.seq_oid::regclass::text, r.tbl);
                  END LOOP;
                END $$;
            """))
            conn.commit()
        except Exception:
            conn.rollback()


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

# 新列必须先补上：_backfill_total_score() 会 SELECT exams 全表，
# 模型里声明了新列而旧表还没有时，直接报 "no such column"。
_add_column("ALTER TABLE questions ADD COLUMN paper_id INTEGER REFERENCES question_papers(id)")
_add_column("ALTER TABLE exams ADD COLUMN kind VARCHAR(20) DEFAULT 'normal'")
_add_column("ALTER TABLE exams ADD COLUMN paper_id INTEGER REFERENCES question_papers(id)")

_backfill_total_score()

_add_column("ALTER TABLE exams ADD COLUMN retake_limit INTEGER DEFAULT 0")
_add_column("ALTER TABLE users ADD COLUMN is_active INTEGER DEFAULT 1")
# 初始密码没改过的账号：登录后强制改密码，改完之前其他接口一律拒绝
_add_column("ALTER TABLE users ADD COLUMN must_change_password BOOLEAN DEFAULT FALSE")
_add_column("ALTER TABLE arenas ADD COLUMN current_question_id INTEGER")

# ---- 收费改造：手机号注册 + 机构（付费单位） ----
_add_column("ALTER TABLE users ADD COLUMN phone VARCHAR(20)")
_add_column("ALTER TABLE users ADD COLUMN organization_id INTEGER REFERENCES organizations(id)")
_add_column("ALTER TABLE users ADD COLUMN org_role VARCHAR(20) DEFAULT ''")
_add_column("ALTER TABLE users ADD COLUMN trial_expires_at TIMESTAMP")
_add_column("ALTER TABLE users ADD COLUMN registered_via VARCHAR(20) DEFAULT 'admin'")



def _add_index(ddl: str) -> None:
    """幂等地建索引。Postgres 与 SQLite 都支持 CREATE INDEX IF NOT EXISTS。"""
    with engine.connect() as conn:
        try:
            conn.execute(text(ddl))
            conn.commit()
        except Exception:
            conn.rollback()


# 手机号唯一（Postgres 里 NULL 不参与唯一约束，存量工号账号不受影响）
_add_index("CREATE UNIQUE INDEX IF NOT EXISTS ix_users_phone ON users (phone)")
_add_index("CREATE INDEX IF NOT EXISTS ix_users_organization ON users (organization_id)")
_add_index("CREATE INDEX IF NOT EXISTS ix_questions_paper ON questions (paper_id)")
_add_index("CREATE INDEX IF NOT EXISTS ix_exams_kind ON exams (kind)")
_add_index("CREATE INDEX IF NOT EXISTS ix_exams_paper ON exams (paper_id)")
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
app.include_router(billing.router)
app.include_router(billing.admin_router)
app.include_router(organizations.router)
app.include_router(images.router)
app.include_router(past_papers.router)
app.include_router(wrong_questions.router)

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


# 老版本写死的默认密码。现在只用来识别"还停在默认密码"的历史账号，
# 新建账号一律走环境变量或随机生成。
LEGACY_DEFAULT_PASSWORD = "admin123"


def _generate_initial_password(length: int = 16) -> str:
    """生成一次性初始密码。

    字符集去掉容易混淆的 O/0、l/1/I，避免手抄时输错。
    """
    alphabet = "abcdefghijkmnopqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789!@#$%^&*-_=+"
    return "".join(secrets.choice(alphabet) for _ in range(length))


@app.on_event("startup")
def init_billing_defaults():
    """首次启动写入默认机构套餐。管理员可以随时改价、改名、改席位。"""
    from . import billing as billing_lib
    db = SessionLocal()
    try:
        billing_lib.ensure_default_plans(db)
    except Exception as e:
        print(f"[billing] 初始化默认套餐失败: {e}", file=sys.stderr)
    finally:
        db.close()


@app.on_event("startup")
def init_admin():
    """启动时初始化管理员账号。

    初始密码有两个来源：
      1. 环境变量 ADMIN_INITIAL_PASSWORD —— 部署时自己定；
      2. 没配就随机生成一个，打印在启动日志里。
    两种情况都只用来第一次登录，登录后必须改密码（must_change_password），
    改完之前其他接口一律拒绝。
    """
    db = SessionLocal()
    try:
        from . import crud, schemas
        admin = crud.get_user_by_employee_id(db, "admin")
        if admin is None:
            initial = ADMIN_INITIAL_PASSWORD or _generate_initial_password()
            admin = crud.create_user(db, schemas.UserCreate(
                employee_id="admin",
                name="管理员",
                password=initial,
                dept="管理部",
                role="系统管理员",
                is_admin=True,
            ))
            admin.must_change_password = True
            db.commit()
            db.refresh(admin)
            print("=" * 60, file=sys.stderr)
            print("[init] 已创建管理员账号 admin", file=sys.stderr)
            print("[init] 初始密码：%s" % initial, file=sys.stderr)
            print("[init] 该密码只能用于第一次登录，登录后必须立即修改。", file=sys.stderr)
            print("=" * 60, file=sys.stderr)
            # 创建示例数据
            _create_sample_data(db, crud, schemas, admin.id)
        elif ADMIN_INITIAL_PASSWORD:
            print("[init] 管理员账号已存在，忽略 ADMIN_INITIAL_PASSWORD"
                  "（不会重置线上已有密码）", file=sys.stderr)
        if (not admin.must_change_password
                and verify_password(LEGACY_DEFAULT_PASSWORD, admin.password_hash)):
            # 历史遗留：还在用写死的 admin123，标记成必须改密码
            admin.must_change_password = True
            db.commit()
            print("[init] 检测到管理员仍在使用默认密码 admin123，"
                  "下次登录后必须修改密码", file=sys.stderr)
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
