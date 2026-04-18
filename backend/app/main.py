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
    allow_origins=[
        "https://yangsi-exam.vercel.app",
        "https://yangsi-exam-system.vercel.app",
        "http://localhost:5173",
        "http://localhost:5174",
    ],
    allow_credentials=True,
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
    finally:
        db.close()

@app.get("/")
def root():
    return {"message": "医学考试系统 API 运行中"}
