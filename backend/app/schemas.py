from pydantic import BaseModel, PlainSerializer, field_validator
from typing import Optional, List, Annotated
from datetime import datetime, timezone


def _as_utc(dt: datetime) -> datetime:
    """数据库中存的是 naive UTC，序列化时补上时区，避免前端按本地时间解析。"""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


UtcDateTime = Annotated[datetime, PlainSerializer(_as_utc, return_type=datetime)]

# ---- Auth ----
class LoginRequest(BaseModel):
    employee_id: str
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: int
    name: str
    is_admin: bool
    employee_id: str

# ---- User ----
class UserCreate(BaseModel):
    employee_id: str
    name: str
    password: str
    dept: str = ""
    role: str = ""
    is_admin: bool = False
    is_active: bool = True

class UserUpdate(BaseModel):
    name: Optional[str] = None
    dept: Optional[str] = None
    role: Optional[str] = None
    password: Optional[str] = None
    is_admin: Optional[bool] = None
    is_active: Optional[bool] = None

class UserOut(BaseModel):
    id: int
    employee_id: str
    name: str
    dept: str
    role: str
    is_admin: bool
    is_active: bool
    created_at: datetime
    class Config:
        from_attributes = True

# ---- Question ----
class QuestionCreate(BaseModel):
    type: str
    content: str
    options: str = "{}"
    answer: str
    analysis: Optional[str] = ""
    category: Optional[str] = ""

class QuestionUpdate(QuestionCreate):
    pass

class QuestionOut(QuestionCreate):
    id: int
    created_at: datetime
    analysis: Optional[str] = None
    score: Optional[float] = None  # 由调用方在返回时补充（如 get_exam 会补充）
    class Config:
        from_attributes = True

# ---- Exam ----
class ExamCreate(BaseModel):
    title: str
    duration: int = 90
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    pass_score: int = 60
    single_score: int = 10      # 单选题分值
    multiple_score: int = 20    # 多选题分值
    judgment_score: int = 5     # 判断题分值
    retake_limit: int = 0       # 补考次数：0=不限，>0=最多考该次数
    random_mode: bool = False   # 每人随机卷：题数固定、题目随机
    random_rules: List[dict] = []  # 抽题规则：[{category,type,count}]
    question_ids: List[int] = []

class ExamUpdate(BaseModel):
    title: Optional[str] = None
    duration: Optional[int] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    pass_score: Optional[int] = None
    single_score: Optional[int] = None      # 单选题分值
    multiple_score: Optional[int] = None    # 多选题分值
    judgment_score: Optional[int] = None    # 判断题分值
    retake_limit: Optional[int] = None      # 补考次数
    random_mode: Optional[bool] = None     # 每人随机卷
    random_rules: Optional[List[dict]] = None  # 抽题规则
    question_ids: Optional[List[int]] = None

class ExamOut(BaseModel):
    id: int
    title: str
    duration: int
    start_time: Optional[datetime]
    end_time: Optional[datetime]
    pass_score: int
    single_score: int = 10      # 单选题分值
    multiple_score: int = 20    # 多选题分值
    judgment_score: int = 5     # 判断题分值
    total_score: float = 0      # 总分
    random_mode: bool = False   # 每人随机卷
    random_rules: Optional[str] = None  # 抽题规则 JSON
    created_at: datetime
    question_count: int = 0
    participant_count: int = 0
    class Config:
        from_attributes = True

# ---- ExamRecord ----
class ExamRecordCreate(BaseModel):
    exam_id: int
    answers: str  # JSON string

class ExamRecordOut(BaseModel):
    id: int
    exam_id: int
    user_id: int
    answers: str
    score: float
    total_score: float
    submitted_at: datetime
    class Config:
        from_attributes = True

# ---- Statistics ----
class StatsSummary(BaseModel):
    total_users: int
    total_exams: int
    total_records: int
    avg_score: float
    pass_rate: float

# ---- ExamDistribution ----
class DistributionCreate(BaseModel):
    exam_id: int
    user_ids: List[int]

class DistributionOut(BaseModel):
    id: int
    exam_id: int
    exam_title: str
    user_id: int
    user_name: str
    employee_id: str
    invite_code: str
    created_at: datetime
    class Config:
        from_attributes = True

class InviteInfoOut(BaseModel):
    exam_id: int
    exam_title: str
    duration: int
    pass_score: int
    exam_status: str

class InviteLoginRequest(BaseModel):
    invite_code: str
    employee_id: str
    password: str

class InviteLoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: int
    name: str
    is_admin: bool
    exam_id: int

class ExamLoginRequest(BaseModel):
    exam_id: int
    employee_id: str
    password: str

# ========== 专业擂台赛 Schemas ==========

class ArenaSettings(BaseModel):
    """擂台赛规则配置"""
    required_count: int = 5        # 必答题数量
    required_score: int = 10       # 必答每题分值
    required_time: int = 30        # 必答答题时间（秒）
    required_wrong_penalty: bool = False  # 必答答错是否扣分
    rush_count: int = 10           # 抢答题数量
    rush_correct_score: int = 20  # 抢答答对分值
    rush_wrong_penalty: int = 10  # 抢答答错扣分
    rush_answer_time: int = 15     # 抢答答题时间（秒）
    rush_per_person_limit: bool = False  # 每人抢答次数限制
    overtime_count: int = 10      # 加赛题数量
    overtime_score: int = 30      # 加赛每题分值
    overtime_wrong_penalty: int = 15  # 加赛答错扣分
    help_per_round: int = 1        # 每队每轮求助次数
    elimination_count: int = 1     # 淘汰队伍数
    resurrection_rounds: int = 1   # 复活赛轮数
    resurrection_count: int = 5    # 复活赛题目数

class ArenaTeamCreate(BaseModel):
    name: str
    color: str = "#409EFF"

class ArenaTeamUpdate(BaseModel):
    name: Optional[str] = None
    color: Optional[str] = None
    score: Optional[int] = None
    status: Optional[str] = None
    help_used_this_round: Optional[bool] = None

class ArenaTeamOut(BaseModel):
    id: int
    arena_id: int
    name: str
    color: str
    score: int
    status: str
    help_used_this_round: bool = False
    order: int
    created_at: UtcDateTime
    player_count: int = 0

    @field_validator("help_used_this_round", mode="before")
    @classmethod
    def _default_help_used(cls, v):
        # 历史数据的布尔列可能为 NULL，统一按 False 处理
        return bool(v) if v is not None else False

    class Config:
        from_attributes = True

class ArenaCreate(BaseModel):
    title: str
    settings: ArenaSettings = ArenaSettings()
    team_names: List[str] = []  # 初始队伍名称列表
    team_colors: List[str] = []  # 初始队伍颜色列表

class ArenaUpdate(BaseModel):
    title: Optional[str] = None
    status: Optional[str] = None
    settings: Optional[ArenaSettings] = None

class ArenaOut(BaseModel):
    id: int
    title: str
    status: str
    current_round: int
    current_question_index: int
    current_question_type: str
    settings: dict
    invite_code: Optional[str]
    invite_expire: Optional[UtcDateTime]
    winner_team_id: Optional[int]
    created_by: Optional[int]
    created_at: UtcDateTime
    team_count: int = 0
    question_count: int = 0
    class Config:
        from_attributes = True

class ArenaQuestionCreate(BaseModel):
    question_id: int
    q_type: str  # required/rush/analysis/overtime
    order_num: int = 0
    score: int = 10

class ArenaQuestionOut(BaseModel):
    id: int
    arena_id: int
    question_id: int
    q_type: str
    order_num: int
    score: int
    question: Optional[QuestionOut] = None
    class Config:
        from_attributes = True

class ArenaQuestionPublicOut(BaseModel):
    """选手可见的题目（不含答案与解析，防止作弊）"""
    id: int
    arena_id: int
    question_id: int
    q_type: str
    order_num: int
    score: int
    question_type: str = ""
    content: str = ""
    options: str = "{}"

class TeamAnswerSubmit(BaseModel):
    team_id: int
    question_id: int
    answer: str
    time_used: int = 0
    help_used: str = ""

class TeamAnswerJudge(BaseModel):
    """主持人判定结果"""
    is_correct: Optional[bool] = None  # 留空则由服务端按标准答案自动比对
    score: Optional[int] = None  # 留空则按题型自动计算

class TeamAnswerOut(BaseModel):
    id: int
    team_id: int
    question_id: int
    answer: str
    is_correct: Optional[bool]
    time_used: int
    score: int
    help_used: str
    submitted_at: UtcDateTime
    class Config:
        from_attributes = True

class ArenaPlayerJoin(BaseModel):
    team_id: int
    device_id: str
    player_name: str = "选手"

class ArenaPlayerOut(BaseModel):
    id: int
    team_id: int
    device_id: str
    player_name: str
    join_time: UtcDateTime
    last_active: UtcDateTime
    token: Optional[str] = None  # 选手WebSocket令牌
    class Config:
        from_attributes = True

class ArenaLogOut(BaseModel):
    id: int
    arena_id: int
    action: str
    actor_type: str
    actor_id: Optional[int]
    actor_name: str
    detail: str
    timestamp: UtcDateTime
    class Config:
        from_attributes = True

class ArenaAnswerExport(BaseModel):
    """导出答案结构"""
    team_name: str
    team_color: str
    total_score: int
    answers: List[dict]

class ArenaRoundCreate(BaseModel):
    round_num: int
    round_type: str

class ArenaRoundOut(BaseModel):
    id: int
    arena_id: int
    round_num: int
    round_type: str
    status: str
    start_time: Optional[datetime]
    end_time: Optional[datetime]
    class Config:
        from_attributes = True

class ArenaTeamIds(BaseModel):
    team_ids: List[int] = []

class ArenaTeamId(BaseModel):
    team_id: int

class ArenaStandingsTeam(BaseModel):
    id: int
    name: str
    color: str
    score: int
    status: str
    rank: int
    answered_count: int = 0

class ArenaStandingsOut(BaseModel):
    """排名与平局判定"""
    teams: List[ArenaStandingsTeam] = []
    top_score: int = 0
    tied: bool = False           # 是否出现并列第一
    tied_team_ids: List[int] = []
    overtime_needed: bool = False  # 是否需要进入加赛
    overtime_count: int = 0       # 已进行的加赛题数
    max_overtime: int = 10
