"""时间口径统一。

两套时间不能混用：

- 考试时间窗（``exam.start_time`` / ``exam.end_time``）由管理端按本地墙钟
  时间录入，比较时也必须用同一口径，否则整体会差一个时区。
- 考试过程计时（``started_at`` 等）只做差值运算，统一用 UTC 无时区时间。
"""
from datetime import datetime, timedelta, timezone

# 考试所在地时区（北京时间）。写死而不是取服务器本地时区，
# 这样局域网开考和云端部署的口径完全一致。
APP_UTC_OFFSET = timedelta(hours=8)

# 交卷宽限：客户端到点会自动提交，留一点网络延迟余量，
# 超过这个余量还没交卷才判定超时，避免"差几秒被判无效"误伤考生。
# 草稿保存、超时结算、次数校验都按这一个余量判断，三处口径必须一致。
SUBMIT_GRACE_SECONDS = 60


def app_now() -> datetime:
    """本地墙钟时间（北京时间），与录入的时间窗同口径。"""
    return (datetime.now(timezone.utc)
            .astimezone(timezone(APP_UTC_OFFSET))
            .replace(tzinfo=None))


def utc_now() -> datetime:
    """UTC 无时区时间，用于时长差值运算。"""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def to_epoch_ms(dt: datetime) -> int:
    """把 UTC 无时区时间转成毫秒时间戳，供前端做倒计时。"""
    return int(dt.replace(tzinfo=timezone.utc).timestamp() * 1000)


def app_to_utc(dt: datetime) -> datetime:
    """本地墙钟时间（北京时间）→ UTC 无时区时间。"""
    return dt - APP_UTC_OFFSET


def utc_to_app(dt: datetime) -> datetime:
    """UTC 无时区时间 → 本地墙钟时间（北京时间）。"""
    return dt + APP_UTC_OFFSET


def epoch_seconds() -> int:
    """当前时刻的整数秒时间戳（JWT 的 ``iat`` 必须是整数）。"""
    return int(datetime.now(timezone.utc).timestamp())
