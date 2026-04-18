from sqlalchemy import Column, Integer, String, Boolean, DateTime, Float, Text, ForeignKey, Table
from sqlalchemy.orm import relationship
from datetime import datetime
from .database import Base

exam_question = Table(
    "exam_question", Base.metadata,
    Column("exam_id", Integer, ForeignKey("exams.id"), primary_key=True),
    Column("question_id", Integer, ForeignKey("questions.id"), primary_key=True),
)

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(String, unique=True, index=True)  # 工号
    name = Column(String)
    password_hash = Column(String)
    dept = Column(String, default="")
    role = Column(String, default="")
    is_admin = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)  # 账号是否启用
    created_at = Column(DateTime, default=datetime.utcnow)
    records = relationship("ExamRecord", back_populates="user")

class Exam(Base):
    __tablename__ = "exams"
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String)
    duration = Column(Integer, default=90)  # 分钟
    start_time = Column(DateTime, nullable=True)
    end_time = Column(DateTime, nullable=True)
    pass_score = Column(Integer, default=60)
    single_score = Column(Integer, default=10)      # 单选题分值
    multiple_score = Column(Integer, default=20)    # 多选题分值
    judgment_score = Column(Integer, default=5)     # 判断题分值
    retake_limit = Column(Integer, default=0)       # 补考次数：0=不限，>0=最多考该次数
    total_score = Column(Float, default=0)           # 存储总分（创建/更新时计算）
    created_by = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, default=datetime.utcnow)
    questions = relationship("Question", secondary=exam_question, back_populates="exams")
    records = relationship("ExamRecord", back_populates="exam")

class Question(Base):
    __tablename__ = "questions"
    id = Column(Integer, primary_key=True, index=True)
    type = Column(String)       # single / multiple / judgment
    content = Column(Text)      # 富文本 HTML
    options = Column(Text)      # JSON: {"A":"...","B":"..."}
    answer = Column(String)     # 单选/判断: "A" / "正确"; 多选: "A,B"
    analysis = Column(Text, default="")
    category = Column(String, default="")
    created_at = Column(DateTime, default=datetime.utcnow)
    exams = relationship("Exam", secondary=exam_question, back_populates="questions")

class ExamRecord(Base):
    __tablename__ = "exam_records"
    id = Column(Integer, primary_key=True, index=True)
    exam_id = Column(Integer, ForeignKey("exams.id"))
    user_id = Column(Integer, ForeignKey("users.id"))
    answers = Column(Text)      # JSON: {"question_id": "answer"}
    score = Column(Float, default=0)
    total_score = Column(Float, default=0)
    submitted_at = Column(DateTime, default=datetime.utcnow)
    exam = relationship("Exam", back_populates="records")
    user = relationship("User", back_populates="records")

class ExamDistribution(Base):
    __tablename__ = "exam_distributions"
    id = Column(Integer, primary_key=True, index=True)
    exam_id = Column(Integer, ForeignKey("exams.id"), index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True)
    invite_code = Column(String, unique=True, index=True)  # 6位随机码
    created_at = Column(DateTime, default=datetime.utcnow)
    exam = relationship("Exam")
    user = relationship("User")
