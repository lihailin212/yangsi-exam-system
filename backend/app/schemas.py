from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

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
    analysis: str = ""
    category: str = ""

class QuestionUpdate(QuestionCreate):
    pass

class QuestionOut(QuestionCreate):
    id: int
    created_at: datetime
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
