from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os
from .database import engine, Base, SessionLocal
from . import models
from .auth import hash_password
from .routers import auth, exams, questions, students, statistics, upload, settings, distributions

# 创建所有表
Base.metadata.create_all(bind=engine)

# 迁移：为 exams 表添加 total_score 和 retake_limit 列
from sqlalchemy import text

def _backfill_total_score():
    """回填已有考试的 total_score"""
    db = SessionLocal()
    try:
        from . import crud as _crud, models as _models
        all_exams = db.query(_models.Exam).all()
        for exam in all_exams:
            exam.total_score = _crud._calc_total_score(exam)
        db.commit()
    finally:
        db.close()

with engine.connect() as conn:
    try:
        conn.execute(text("ALTER TABLE exams ADD COLUMN total_score FLOAT DEFAULT 0"))
        conn.commit()
        _backfill_total_score()
    except Exception:
        pass
    try:
        conn.execute(text("ALTER TABLE exams ADD COLUMN retake_limit INTEGER DEFAULT 0"))
        conn.commit()
    except Exception:
        pass
    try:
        conn.execute(text("ALTER TABLE users ADD COLUMN is_active INTEGER DEFAULT 1"))
        conn.commit()
    except Exception:
        pass

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

# Railway 持久化磁盘路径（生产环境）
_DATA_DIR = os.environ.get("RAILWAY_VOLUME_MOUNT_PATH", os.path.join(os.path.dirname(__file__), ".."))
_UPLOADS_DIR = os.path.join(_DATA_DIR, "uploads")
os.makedirs(os.path.join(_UPLOADS_DIR, "images"), exist_ok=True)
app.mount("/uploads", StaticFiles(directory=_UPLOADS_DIR), name="uploads")

@app.on_event("startup")
def init_admin():
    """启动时初始化管理员账号"""
    db = SessionLocal()
    try:
        from . import crud, schemas
        if not crud.get_user_by_employee_id(db, "admin"):
            crud.create_user(db, schemas.UserCreate(
                employee_id="admin",
                name="管理员",
                password="admin123",
                dept="管理部",
                role="系统管理员",
                is_admin=True,
            ))
            # 创建示例数据
            _create_sample_data(db, crud, schemas)
    finally:
        db.close()

def _create_sample_data(db, crud, schemas):
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
        multiple_score=20,
        judgment_score=5,
        retake_limit=3,
        question_ids=[q.id for q in created_questions]
    ))

@app.get("/")
def root():
    return {"message": "医学考试系统 API 运行中"}
