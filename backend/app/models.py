from sqlalchemy import Column, Integer, String, Boolean, DateTime, Float, Text, ForeignKey, Table, UniqueConstraint
from sqlalchemy.orm import relationship
from datetime import datetime
from .database import Base

exam_question = Table(
    "exam_question", Base.metadata,
    Column("exam_id", Integer, ForeignKey("exams.id"), primary_key=True),
    Column("question_id", Integer, ForeignKey("questions.id"), primary_key=True),
)

class SystemSetting(Base):
    """系统设置（键值对）。生产环境存数据库，避免依赖只读文件系统。"""
    __tablename__ = "system_settings"
    id = Column(Integer, primary_key=True, index=True)
    key = Column(String, unique=True, index=True)
    value = Column(Text, default="")
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class BackupRecord(Base):
    """数据备份文件（内容存数据库，兼容无持久化磁盘的部署环境）。"""
    __tablename__ = "backup_records"
    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String, unique=True, index=True)
    content = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)

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


class ExamAttempt(Base):
    """考生一次作答会话（进入考试 → 交卷）。

    服务端以此为准核算考试用时：考生进入考试时落一条 started_at，
    交卷时写 submitted_at。这样即使考生清掉浏览器缓存重新登录，
    也无法把考试时间重新算一遍。
    """
    __tablename__ = "exam_attempts"
    id = Column(Integer, primary_key=True, index=True)
    exam_id = Column(Integer, ForeignKey("exams.id"), index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True)
    attempt_no = Column(Integer, default=1)      # 第几次作答（补考时递增）
    started_at = Column(DateTime, default=datetime.utcnow)
    deadline_at = Column(DateTime, nullable=True)  # 截止时间（UTC 无时区）
    draft = Column(Text, default="")            # 服务端保存的作答草稿（超时自动交卷用）
    submitted_at = Column(DateTime, nullable=True)
    __table_args__ = (
        UniqueConstraint("exam_id", "user_id", "attempt_no", name="uq_exam_attempt"),
    )
    exam = relationship("Exam")
    user = relationship("User")

# ========== 专业擂台赛模型 ==========

class Arena(Base):
    """擂台赛主表"""
    __tablename__ = "arenas"
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String)
    status = Column(String, default="pending")  # pending/active/paused/finished
    current_round = Column(Integer, default=0)  # 当前轮次
    current_question_index = Column(Integer, default=-1)  # 当前题目索引
    current_question_id = Column(Integer, nullable=True)  # 当前展示的题目（arena_questions.id）
    current_question_type = Column(String, default="")  # current/required/rush/analysis/overtime
    settings = Column(Text, default="{}")  # JSON规则配置
    invite_code = Column(String, unique=True, index=True)  # 6位邀请码
    invite_expire = Column(DateTime)  # 邀请码过期时间
    winner_team_id = Column(Integer, ForeignKey("arena_teams.id"), nullable=True)
    created_by = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, default=datetime.utcnow)
    teams = relationship("ArenaTeam", back_populates="arena", cascade="all, delete-orphan",
                         foreign_keys="ArenaTeam.arena_id")
    questions = relationship("ArenaQuestion", back_populates="arena", cascade="all, delete-orphan")
    logs = relationship("ArenaLog", back_populates="arena", cascade="all, delete-orphan")

class ArenaTeam(Base):
    """参赛队伍"""
    __tablename__ = "arena_teams"
    id = Column(Integer, primary_key=True, index=True)
    arena_id = Column(Integer, ForeignKey("arenas.id"), index=True)
    name = Column(String)
    color = Column(String, default="#409EFF")  # 队伍颜色
    score = Column(Integer, default=0)
    status = Column(String, default="active")  # active/eliminated/resurrected
    help_used_this_round = Column(Boolean, default=False, nullable=False)  # 本轮求助是否已用
    order = Column(Integer, default=0)  # 显示顺序
    created_at = Column(DateTime, default=datetime.utcnow)
    arena = relationship("Arena", back_populates="teams",
                        foreign_keys=[arena_id])
    players = relationship("ArenaPlayer", back_populates="team", cascade="all, delete-orphan")
    answers = relationship("TeamAnswer", back_populates="team", cascade="all, delete-orphan")

class ArenaQuestion(Base):
    """擂台赛题目关联"""
    __tablename__ = "arena_questions"
    id = Column(Integer, primary_key=True, index=True)
    arena_id = Column(Integer, ForeignKey("arenas.id"), index=True)
    question_id = Column(Integer, ForeignKey("questions.id"), index=True)
    q_type = Column(String)  # required/rush/analysis/overtime
    order_num = Column(Integer, default=0)
    score = Column(Integer, default=10)  # 分值
    created_at = Column(DateTime, default=datetime.utcnow)
    arena = relationship("Arena", back_populates="questions")
    question = relationship("Question")

class TeamAnswer(Base):
    """队伍答题记录"""
    __tablename__ = "team_answers"
    id = Column(Integer, primary_key=True, index=True)
    team_id = Column(Integer, ForeignKey("arena_teams.id"), index=True)
    question_id = Column(Integer, ForeignKey("arena_questions.id"), index=True)
    answer = Column(Text, default="")
    is_correct = Column(Boolean, nullable=True)
    time_used = Column(Integer, default=0)  # 答题用时（秒）
    score = Column(Integer, default=0)  # 得分
    help_used = Column(String, default="")  # 使用的求助类型
    submitted_at = Column(DateTime, default=datetime.utcnow)
    team = relationship("ArenaTeam", back_populates="answers")

class ArenaPlayer(Base):
    """擂台赛选手记录"""
    __tablename__ = "arena_players"
    id = Column(Integer, primary_key=True, index=True)
    team_id = Column(Integer, ForeignKey("arena_teams.id"), index=True)
    device_id = Column(String, index=True)  # 设备ID
    player_name = Column(String, default="选手")
    join_time = Column(DateTime, default=datetime.utcnow)
    last_active = Column(DateTime, default=datetime.utcnow)
    team = relationship("ArenaTeam", back_populates="players")

class ArenaRound(Base):
    """轮次记录"""
    __tablename__ = "arena_rounds"
    id = Column(Integer, primary_key=True, index=True)
    arena_id = Column(Integer, ForeignKey("arenas.id"), index=True)
    round_num = Column(Integer)
    round_type = Column(String)  # required/rush/analysis/overtime
    status = Column(String, default="pending")  # pending/active/finished
    start_time = Column(DateTime, nullable=True)
    end_time = Column(DateTime, nullable=True)

class ArenaLog(Base):
    """操作日志"""
    __tablename__ = "arena_logs"
    id = Column(Integer, primary_key=True, index=True)
    arena_id = Column(Integer, ForeignKey("arenas.id"), index=True)
    action = Column(String)  #抢答/作答/评分/求助等
    actor_type = Column(String)  # team/host/system
    actor_id = Column(Integer, nullable=True)  # 队伍ID或主持人ID
    actor_name = Column(String, default="")
    detail = Column(Text, default="")  # 详细信息JSON
    timestamp = Column(DateTime, default=datetime.utcnow)
    arena = relationship("Arena", back_populates="logs")
