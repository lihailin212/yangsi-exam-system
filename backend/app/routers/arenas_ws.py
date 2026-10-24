"""擂台赛 WebSocket 路由

连接方式：
    主持人：/ws/arenas/{arena_id}?role=host&token=<管理员登录令牌>
    选手：  /ws/arenas/{arena_id}?role=player&token=<加入擂台赛后下发的选手令牌>

选手身份完全由令牌推导（队伍ID取自令牌），忽略客户端上报的 team_id，避免越权代答。
"""
import json
from typing import Dict, Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, Query
from sqlalchemy.orm import Session

from ..database import get_db
from .. import crud, schemas, models
from ..auth import decode_token, decode_arena_player_token

router = APIRouter(prefix="/ws/arenas", tags=["擂台赛WebSocket"])


class ConnectionInfo:
    """单个连接的元信息"""

    def __init__(self, role: str, team_id: int = None, user_id: int = None,
                 user_name: str = ""):
        self.role = role              # host / player
        self.team_id = team_id
        self.user_id = user_id
        self.user_name = user_name


class ConnectionManager:
    """连接管理器：按擂台赛分组，并记录每个连接的角色与队伍"""

    def __init__(self):
        # arena_id -> {websocket: ConnectionInfo}
        self.connections: Dict[int, Dict[WebSocket, ConnectionInfo]] = {}
        # arena_id -> {"question_id": int, "winner_team_id": int, "timestamp": float}
        self.rush_state: Dict[int, dict] = {}
        # arena_id -> set(team_id) 已使用过抢答机会的队伍（当前题）
        self.rush_used_teams: Dict[int, set] = {}
        # arena_id -> {"duration": int, "started_at": float} 计时器状态（用于断线重连恢复）
        self.timer_state: Dict[int, dict] = {}

    async def connect(self, arena_id: int, websocket: WebSocket, info: ConnectionInfo):
        await websocket.accept()
        self.connections.setdefault(arena_id, {})[websocket] = info

    def disconnect(self, arena_id: int, websocket: WebSocket):
        arena_conns = self.connections.get(arena_id)
        if not arena_conns:
            return
        arena_conns.pop(websocket, None)
        if not arena_conns:
            self.connections.pop(arena_id, None)
            self.rush_state.pop(arena_id, None)
            self.rush_used_teams.pop(arena_id, None)
            self.timer_state.pop(arena_id, None)

    def start_timer(self, arena_id: int, duration: int):
        """主持人开启计时，记录起始时间以便断线重连后恢复剩余时间"""
        self.timer_state[arena_id] = {
            "duration": duration,
            "started_at": _now_ts(),
        }

    def stop_timer(self, arena_id: int):
        self.timer_state.pop(arena_id, None)

    def timer_snapshot(self, arena_id: int) -> Optional[dict]:
        """返回计时器快照：剩余秒数（已结束则为 None）"""
        state = self.timer_state.get(arena_id)
        if not state:
            return None
        elapsed = _now_ts() - state["started_at"]
        remaining = state["duration"] - elapsed
        if remaining <= 0:
            return None
        return {"duration": state["duration"], "remaining": remaining}

    async def _send(self, websocket: WebSocket, message: dict):
        try:
            await websocket.send_json(message)
            return True
        except Exception:
            return False

    async def broadcast(self, arena_id: int, message: dict, exclude: WebSocket = None):
        """向该擂台赛的所有连接广播"""
        arena_conns = self.connections.get(arena_id, {})
        dead = []
        for ws, info in list(arena_conns.items()):
            if ws is exclude:
                continue
            if not await self._send(ws, message):
                dead.append(ws)
        for ws in dead:
            self.disconnect(arena_id, ws)

    async def send_to_team(self, arena_id: int, team_id: int, message: dict):
        """只向指定队伍的选手连接发送（不广播给其他队伍或主持人）"""
        arena_conns = self.connections.get(arena_id, {})
        dead = []
        for ws, info in list(arena_conns.items()):
            if info.role != "player" or info.team_id != team_id:
                continue
            if not await self._send(ws, message):
                dead.append(ws)
        for ws in dead:
            self.disconnect(arena_id, ws)

    async def send_to_hosts(self, arena_id: int, message: dict):
        """只向主持人连接发送"""
        arena_conns = self.connections.get(arena_id, {})
        dead = []
        for ws, info in list(arena_conns.items()):
            if info.role != "host":
                continue
            if not await self._send(ws, message):
                dead.append(ws)
        for ws in dead:
            self.disconnect(arena_id, ws)

    def is_host(self, arena_id: int, websocket: WebSocket) -> bool:
        info = self.connections.get(arena_id, {}).get(websocket)
        return bool(info and info.role == "host")

    # ---- 抢答仲裁 ----

    def begin_rush(self, arena_id: int, question_id: int):
        """主持人开启抢答，清空上一题的抢答状态"""
        self.rush_state[arena_id] = {
            "question_id": question_id,
            "winner_team_id": None,
            "timestamp": None,
        }
        self.rush_used_teams[arena_id] = set()

    def claim_rush(self, arena_id: int, question_id: int, team_id: int) -> dict:
        """抢答仲裁：同一题只有第一支队伍能抢到答题权

        返回 {'result': 'won'|'lost'|'used_up'|'closed', 'winner_team_id': int|None}
        """
        state = self.rush_state.get(arena_id)
        if not state or state.get("question_id") != question_id:
            return {"result": "closed", "winner_team_id": None}
        used = self.rush_used_teams.setdefault(arena_id, set())
        if state.get("winner_team_id") is not None:
            return {"result": "lost", "winner_team_id": state["winner_team_id"]}
        if team_id in used:
            return {"result": "used_up", "winner_team_id": state.get("winner_team_id")}
        used.add(team_id)
        state["winner_team_id"] = team_id
        state["timestamp"] = _now_ts()
        return {"result": "won", "winner_team_id": team_id}


def _now_ts() -> float:
    import time
    return time.time()


manager = ConnectionManager()


def _public_question(db: Session, arena_question) -> dict:
    """构造选手可见的题目信息（不含答案与解析）"""
    origin = arena_question.question
    return {
        "id": arena_question.id,             # arena_questions.id，全流程统一使用
        "question_id": arena_question.question_id,
        "q_type": arena_question.q_type,
        "order_num": arena_question.order_num,
        "score": arena_question.score,
        "question_type": origin.type if origin else "",
        "content": origin.content if origin else "",
        "options": origin.options if origin else "{}",
    }


def _team_snapshot(db: Session, arena_id: int) -> list:
    teams = crud.get_arena_teams(db, arena_id)
    return [
        {"id": t.id, "name": t.name, "score": t.score or 0, "color": t.color,
         "status": t.status}
        for t in teams
    ]


def _current_question_payload(db: Session, arena) -> Optional[dict]:
    """返回当前展示题目的公开信息（供断线重连恢复现场）"""
    question_id = getattr(arena, "current_question_id", None)
    if not question_id:
        return None
    arena_question = crud.get_arena_question(db, question_id)
    if not arena_question or arena_question.arena_id != arena.id:
        return None
    return _public_question(db, arena_question)


def _team_answer_state(db: Session, team_id: Optional[int], question_id: Optional[int]) -> Optional[dict]:
    """返回该队伍在当前题目的作答状态（用于重连后恢复已提交/已判定）"""
    if not team_id or not question_id:
        return None
    answer = db.query(models.TeamAnswer).filter(
        models.TeamAnswer.team_id == team_id,
        models.TeamAnswer.question_id == question_id,
    ).first()
    if not answer:
        return None
    return {
        "answer_id": answer.id,
        "question_id": answer.question_id,
        "answer": answer.answer,
        "is_correct": answer.is_correct,
        "score": answer.score,
        "time_used": answer.time_used,
    }


def _pending_answers_payload(db: Session, arena_id: int, question_id: Optional[int]) -> list:
    """主持人断线重连后恢复待判定列表"""
    if not question_id:
        return []
    teams = {t.id: t for t in crud.get_arena_teams(db, arena_id)}
    payload = []
    for ans in crud.get_pending_answers(db, arena_id, question_id):
        team = teams.get(ans.team_id)
        payload.append({
            "answer_id": ans.id,
            "team_id": ans.team_id,
            "team_name": team.name if team else "",
            "team_color": team.color if team else "",
            "question_id": ans.question_id,
            "answer": ans.answer,
            "time_used": ans.time_used,
            "is_correct": None,
            "score": 0,
            "timeout": False,
        })
    return payload


@router.websocket("/{arena_id}")
async def arena_websocket(
    websocket: WebSocket,
    arena_id: int,
    role: str = Query("player"),
    token: str = Query(""),
    db: Session = Depends(get_db),
):
    """擂台赛WebSocket连接"""
    arena = crud.get_arena(db, arena_id)
    if not arena:
        await websocket.close(code=4004, reason="擂台赛不存在")
        return

    info = None
    if role == "host":
        payload = decode_token(token) if token else None
        if not payload or payload.get("type") == "arena_player":
            await websocket.close(code=4001, reason="主持人令牌无效")
            return
        from .. import models
        user = db.query(models.User).filter(
            models.User.id == int(payload.get("sub"))
        ).first()
        if not user or not user.is_admin:
            await websocket.close(code=4003, reason="需要管理员权限")
            return
        info = ConnectionInfo(role="host", user_id=user.id, user_name=user.name)
    else:
        payload = decode_arena_player_token(token) if token else None
        if not payload:
            await websocket.close(code=4001, reason="选手令牌无效")
            return
        if int(payload.get("arena_id")) != arena_id:
            await websocket.close(code=4001, reason="选手令牌与擂台赛不匹配")
            return
        info = ConnectionInfo(role="player", team_id=int(payload.get("team_id")))

    await manager.connect(arena_id, websocket, info)

    try:
        await websocket.send_json({
            "type": "connected",
            "payload": {"role": info.role, "team_id": info.team_id,
                        "arena_id": arena_id},
        })
        while True:
            data = await websocket.receive_json()
            msg_type = data.get("type")
            payload = data.get("payload", {}) or {}

            if msg_type == "ping":
                await websocket.send_json({"type": "pong", "payload": {}})

            elif msg_type == "sync_state":
                # 重新读取，保证断线重连拿到的是最新状态
                fresh_arena = crud.get_arena(db, arena_id) or arena
                arena = fresh_arena
                current_question = _current_question_payload(db, arena)
                await websocket.send_json({
                    "type": "state_sync",
                    "payload": {
                        "arena_status": arena.status,
                        "current_round": arena.current_round,
                        "current_question_index": arena.current_question_index,
                        "current_question_type": arena.current_question_type,
                        "settings": crud.get_arena_settings(arena),
                        "teams": _team_snapshot(db, arena_id),
                        "my_team_id": info.team_id,
                        # —— 断线重连恢复现场 ——
                        "current_question": current_question,
                        "my_answer_state": _team_answer_state(
                            db, info.team_id,
                            current_question.get("id") if current_question else None,
                        ),
                        "timer": manager.timer_snapshot(arena_id),
                        "rush_winner_team_id": (manager.rush_state.get(arena_id) or {}).get("winner_team_id"),
                        "pending_answers": _pending_answers_payload(
                            db, arena_id,
                            current_question.get("id") if current_question else None,
                        ) if info.role == "host" else [],
                    },
                })

            elif msg_type == "answer_submit":
                await _handle_answer_submit(websocket, arena_id, info, payload, db)

            elif msg_type == "rush_answer":
                await _handle_rush_answer(websocket, arena_id, info, payload, db)

            elif msg_type == "help_request":
                await _handle_help_request(websocket, arena_id, info, payload, db)

            elif msg_type == "host_control":
                if not manager.is_host(arena_id, websocket):
                    await websocket.send_json({
                        "type": "error",
                        "payload": {"message": "只有主持人可以执行控制指令"},
                    })
                    continue
                await _handle_host_control(websocket, arena_id, payload, db)

    except WebSocketDisconnect:
        manager.disconnect(arena_id, websocket)
        await _handle_host_left(arena_id, db)
    except Exception as e:  # pragma: no cover - 防御性兜底
        print(f"WebSocket error: {e}")
        manager.disconnect(arena_id, websocket)
        await _handle_host_left(arena_id, db)


async def _handle_host_left(arena_id: int, db: Session):
    """主持人断线：自动暂停比赛，选手端显示“等待主持人”"""
    arena_conns = manager.connections.get(arena_id, {})
    if any(info.role == "host" for info in arena_conns.values()):
        return
    if not arena_conns:
        return
    arena = crud.get_arena(db, arena_id)
    if arena and arena.status == "active":
        arena.status = "paused"
        db.commit()
        await manager.broadcast(arena_id, {
            "type": "host_disconnected",
            "payload": {"message": "主持人已断开，比赛自动暂停"},
        })


async def _handle_answer_submit(websocket: WebSocket, arena_id: int, info: ConnectionInfo,
                                payload: dict, db: Session):
    """选手提交答案：只记录，不判分"""
    if info.role != "player" or not info.team_id:
        await websocket.send_json({"type": "error", "payload": {"message": "选手身份无效"}})
        return
    question_id = payload.get("question_id")
    answer_text = payload.get("answer", "")
    time_used = int(payload.get("time_used", 0) or 0)
    help_used = payload.get("help_used", "") or ""

    answer_record = crud.submit_team_answer(db, schemas.TeamAnswerSubmit(
        team_id=info.team_id,
        question_id=question_id,
        answer=answer_text,
        time_used=time_used,
        help_used=help_used,
    ))
    if not answer_record:
        await websocket.send_json({
            "type": "error",
            "payload": {"message": "提交失败：题目不存在或不属于本擂台赛"},
        })
        return

    team = crud.get_arena_team(db, info.team_id)

    # 超时未答：服务端直接判错并结算扣分（主持人可再手动修改）
    is_timeout = bool(payload.get("timeout"))
    if is_timeout:
        judged = crud.judge_answer(db, answer_record.id, False, None)
        if judged:
            answer_record = judged

    crud.log_arena_action(
        db, arena_id, "作答", actor_type="team", actor_id=info.team_id,
        actor_name=team.name if team else "",
        detail=json.dumps({"question_id": question_id, "answer": answer_text,
                           "answer_id": answer_record.id,
                           "timeout": is_timeout}, ensure_ascii=False),
    )

    # 回执只发给提交者本人
    await manager.send_to_team(arena_id, info.team_id, {
        "type": "answer_received",
        "payload": {"question_id": question_id, "answer_id": answer_record.id,
                    "timeout": is_timeout},
    })
    if is_timeout:
        await manager.send_to_team(arena_id, info.team_id, {
            "type": "judge_result",
            "payload": {
                "answer_id": answer_record.id,
                "question_id": question_id,
                "is_correct": False,
                "score": answer_record.score,
                "team_score": team.score if team else 0,
            },
        })
    # 主持人收到待判定的提交（包含答案内容，主持人需要看到）
    await manager.send_to_hosts(arena_id, {
        "type": "answer_submitted",
        "payload": {
            "answer_id": answer_record.id,
            "team_id": info.team_id,
            "team_name": team.name if team else "",
            "team_color": team.color if team else "",
            "question_id": question_id,
            "answer": answer_text,
            "time_used": time_used,
            "is_correct": False if is_timeout else None,
            "score": answer_record.score if is_timeout else 0,
            "timeout": is_timeout,
        },
    })


async def _handle_rush_answer(websocket: WebSocket, arena_id: int, info: ConnectionInfo,
                              payload: dict, db: Session):
    """队伍抢答：同一题只有第一支抢到的队伍获得答题权"""
    if info.role != "player" or not info.team_id:
        await websocket.send_json({"type": "error", "payload": {"message": "选手身份无效"}})
        return
    question_id = payload.get("question_id")
    team_id = info.team_id
    team = crud.get_arena_team(db, team_id)

    claim = manager.claim_rush(arena_id, question_id, team_id)
    if claim["result"] == "won":
        timestamp = _now_ts()
        await manager.broadcast(arena_id, {
            "type": "rush_success",
            "payload": {
                "team_id": team_id,
                "team_name": team.name if team else "",
                "team_color": team.color if team else "",
                "question_id": question_id,
                "timestamp": timestamp,
            },
        })
    elif claim["result"] == "lost":
        await manager.send_to_team(arena_id, team_id, {
            "type": "rush_lost",
            "payload": {"winner_team_id": claim["winner_team_id"],
                        "question_id": question_id},
        })
    elif claim["result"] == "used_up":
        await manager.send_to_team(arena_id, team_id, {
            "type": "rush_already",
            "payload": {"question_id": question_id},
        })
    else:
        await manager.send_to_team(arena_id, team_id, {
            "type": "rush_closed",
            "payload": {"question_id": question_id},
        })


async def _handle_help_request(websocket: WebSocket, arena_id: int, info: ConnectionInfo,
                               payload: dict, db: Session):
    """求助：服务端计算需要排除的错误选项，只发给请求的队伍"""
    if info.role != "player" or not info.team_id:
        await websocket.send_json({"type": "error", "payload": {"message": "选手身份无效"}})
        return
    help_type = payload.get("help_type")
    question_id = payload.get("question_id")
    team = crud.get_arena_team(db, info.team_id)
    if not team:
        return
    if team.help_used_this_round:
        await manager.send_to_team(arena_id, info.team_id, {
            "type": "help_result",
            "payload": {"help_type": help_type, "question_id": question_id,
                        "success": False, "message": "本轮求助次数已用完"},
        })
        return

    arena_question = crud.get_arena_question(db, question_id) if question_id else None
    if arena_question and arena_question.q_type == "analysis":
        await manager.send_to_team(arena_id, info.team_id, {
            "type": "help_result",
            "payload": {"help_type": help_type, "question_id": question_id,
                        "success": False, "message": "综合分析题不可求助"},
        })
        return

    team.help_used_this_round = True
    db.commit()

    excluded = []
    if help_type == "eliminate" and arena_question:
        excluded = crud.get_help_excluded_options(db, arena_question, 2)

    crud.log_arena_action(
        db, arena_id, f"求助_{help_type}", actor_type="team", actor_id=info.team_id,
        actor_name=team.name,
        detail=json.dumps({"help_type": help_type, "question_id": question_id},
                          ensure_ascii=False),
    )
    await manager.send_to_team(arena_id, info.team_id, {
        "type": "help_result",
        "payload": {
            "help_type": help_type,
            "question_id": question_id,
            "success": True,
            "excluded_options": excluded,
            "extra_time": 60 if help_type == "team_help" else 0,
        },
    })
    await manager.send_to_hosts(arena_id, {
        "type": "help_used",
        "payload": {"team_id": info.team_id, "team_name": team.name,
                    "help_type": help_type, "question_id": question_id},
    })


async def _broadcast_judgement(manager, db: Session, arena_id: int, answer):
    """把一次判定的结果推送给相关队伍、主持人，并同步排行榜"""
    team = crud.get_arena_team(db, answer.team_id)
    # 判定结果只发给该队选手
    await manager.send_to_team(arena_id, answer.team_id, {
        "type": "judge_result",
        "payload": {
            "answer_id": answer.id,
            "question_id": answer.question_id,
            "is_correct": answer.is_correct,
            "score": answer.score,
            "team_score": team.score if team else 0,
        },
    })
    await manager.send_to_hosts(arena_id, {
        "type": "answer_judged",
        "payload": {
            "answer_id": answer.id,
            "team_id": answer.team_id,
            "team_name": team.name if team else "",
            "is_correct": answer.is_correct,
            "score": answer.score,
            "team_score": team.score if team else 0,
        },
    })
    await manager.broadcast(arena_id, {
        "type": "scores_updated",
        "payload": {"teams": _team_snapshot(db, arena_id)},
    })
    crud.log_arena_action(
        db, arena_id, "评分", actor_type="host",
        actor_id=answer.team_id, actor_name=team.name if team else "",
        detail=json.dumps({"answer_id": answer.id, "is_correct": answer.is_correct,
                           "score": answer.score}, ensure_ascii=False),
    )


async def _handle_host_control(websocket: WebSocket, arena_id: int, payload: dict, db: Session):
    """主持人控制指令"""
    action = payload.get("action")

    if action == "pause":
        arena = crud.get_arena(db, arena_id)
        if arena:
            arena.status = "paused"
            db.commit()
        await manager.broadcast(arena_id, {"type": "game_paused", "payload": {"message": "比赛已暂停"}})
        crud.log_arena_action(db, arena_id, "暂停比赛", actor_type="host", actor_name="主持人")

    elif action == "resume":
        arena = crud.get_arena(db, arena_id)
        if arena:
            arena.status = "active"
            db.commit()
        await manager.broadcast(arena_id, {"type": "game_resumed", "payload": {"message": "比赛继续"}})
        crud.log_arena_action(db, arena_id, "继续比赛", actor_type="host", actor_name="主持人")

    elif action == "start":
        arena = crud.get_arena(db, arena_id)
        if arena:
            arena.status = "active"
            db.commit()
        await manager.broadcast(arena_id, {"type": "game_started", "payload": {}})
        crud.log_arena_action(db, arena_id, "比赛开始", actor_type="host", actor_name="主持人")

    elif action == "finish":
        arena = crud.get_arena(db, arena_id)
        standings = crud.get_arena_standings(db, arena_id)
        winner_id = None
        if arena:
            arena.status = "finished"
            active = [t for t in standings.teams if t.status != "eliminated"]
            if active and len([t for t in active if t.score == standings.top_score]) == 1:
                winner_id = active[0].id
                arena.winner_team_id = winner_id
            db.commit()
        await manager.broadcast(arena_id, {
            "type": "game_finished",
            "payload": {"teams": _team_snapshot(db, arena_id),
                        "winner_team_id": winner_id},
        })
        crud.log_arena_action(db, arena_id, "比赛结束", actor_type="host", actor_name="主持人")

    elif action == "show_question":
        question_id = payload.get("question_id")
        arena_question = crud.get_arena_question(db, question_id) if question_id else None
        if not arena_question:
            return
        arena = crud.get_arena(db, arena_id)
        if arena:
            arena.current_question_index = arena_question.order_num
            arena.current_question_id = arena_question.id
            arena.current_question_type = arena_question.q_type
            db.commit()
        await manager.broadcast(arena_id, {
            "type": "question_shown",
            "payload": {"question_id": arena_question.id,
                        "question": _public_question(db, arena_question)},
        })
        crud.log_arena_action(db, arena_id, "显示题目", actor_type="host",
                              detail=json.dumps({"question_id": arena_question.id}))

    elif action == "start_rush":
        question_id = payload.get("question_id")
        manager.begin_rush(arena_id, question_id)
        await manager.broadcast(arena_id, {
            "type": "rush_started",
            "payload": {"question_id": question_id, "timestamp": _now_ts()},
        })
        crud.log_arena_action(db, arena_id, "开始抢答", actor_type="host",
                              detail=json.dumps({"question_id": question_id}))

    elif action == "start_timer":
        duration = int(payload.get("duration", 15) or 15)
        manager.start_timer(arena_id, duration)
        await manager.broadcast(arena_id, {"type": "timer_started", "payload": {"duration": duration}})

    elif action == "stop_timer":
        manager.stop_timer(arena_id)
        await manager.broadcast(arena_id, {"type": "timer_stopped", "payload": {}})

    elif action == "score_update":
        await manager.broadcast(arena_id, {
            "type": "scores_updated",
            "payload": {"teams": _team_snapshot(db, arena_id)},
        })

    elif action == "judge_answer":
        answer_id = payload.get("answer_id")
        is_correct = payload.get("is_correct")
        score = payload.get("score")
        if answer_id is None:
            return
        if is_correct is None:
            # 主持人未指定对错时按标准答案自动比对
            answer, verdict = crud.auto_judge_team_answer(db, answer_id)
            if answer is None:
                return
            if verdict is None:
                await manager.send_to_hosts(arena_id, {
                    "type": "auto_judge_skipped",
                    "payload": {
                        "answer_id": answer_id,
                        "message": "该题为主观题或缺少标准答案，需人工评分",
                    },
                })
                return
        else:
            answer = crud.judge_answer(db, answer_id, is_correct, score)
        if not answer:
            return
        await _broadcast_judgement(manager, db, arena_id, answer)

    elif action == "auto_judge_answer":
        # 自动判定单条作答（客观题按标准答案比对，主观题/无标准答案保持待判定）
        answer_id = payload.get("answer_id")
        if answer_id is None:
            return
        answer, verdict = crud.auto_judge_team_answer(db, answer_id)
        if answer is None:
            return
        if verdict is None:
            await manager.send_to_hosts(arena_id, {
                "type": "auto_judge_skipped",
                "payload": {
                    "answer_id": answer_id,
                    "message": "该题为主观题或缺少标准答案，需人工评分",
                },
            })
            return
        await _broadcast_judgement(manager, db, arena_id, answer)

    elif action == "auto_judge_all":
        # 一键自动判定当前题下所有待判定的作答
        question_id = payload.get("question_id")
        if question_id is None:
            return
        judged, skipped = crud.auto_judge_pending(db, arena_id, question_id)
        for answer in judged:
            await _broadcast_judgement(manager, db, arena_id, answer)
        await manager.broadcast(arena_id, {
            "type": "scores_updated",
            "payload": {"teams": _team_snapshot(db, arena_id)},
        })
        await manager.send_to_hosts(arena_id, {
            "type": "auto_judge_done",
            "payload": {
                "question_id": question_id,
                "judged_count": len(judged),
                "skipped": skipped,
            },
        })

    elif action == "eliminate":
        team = crud.get_arena_team(db, answer.team_id)
        # 判定结果只发给该队选手
        await manager.send_to_team(arena_id, answer.team_id, {
            "type": "judge_result",
            "payload": {
                "answer_id": answer.id,
                "question_id": answer.question_id,
                "is_correct": answer.is_correct,
                "score": answer.score,
                "team_score": team.score if team else 0,
            },
        })
        await manager.send_to_hosts(arena_id, {
            "type": "answer_judged",
            "payload": {
                "answer_id": answer.id,
                "team_id": answer.team_id,
                "team_name": team.name if team else "",
                "is_correct": answer.is_correct,
                "score": answer.score,
                "team_score": team.score if team else 0,
            },
        })
        await manager.broadcast(arena_id, {
            "type": "scores_updated",
            "payload": {"teams": _team_snapshot(db, arena_id)},
        })
        crud.log_arena_action(
            db, arena_id, "评分", actor_type="host",
            actor_id=answer.team_id, actor_name=team.name if team else "",
            detail=json.dumps({"answer_id": answer.id, "is_correct": answer.is_correct,
                               "score": answer.score}, ensure_ascii=False),
        )

    elif action == "eliminate":
        team_ids = payload.get("team_ids") or []
        crud.eliminate_teams(db, arena_id, team_ids)
        await manager.broadcast(arena_id, {
            "type": "teams_updated",
            "payload": {"teams": _team_snapshot(db, arena_id)},
        })
        crud.log_arena_action(db, arena_id, "淘汰队伍", actor_type="host",
                              detail=json.dumps({"team_ids": team_ids}, ensure_ascii=False))

    elif action == "resurrect":
        team_id = payload.get("team_id")
        if team_id:
            crud.resurrect_team(db, team_id)
            await manager.broadcast(arena_id, {
                "type": "teams_updated",
                "payload": {"teams": _team_snapshot(db, arena_id)},
            })
            crud.log_arena_action(db, arena_id, "复活队伍", actor_type="host",
                                  detail=json.dumps({"team_id": team_id}))

    elif action == "reset_help":
        crud.reset_team_help_status(db, arena_id)
        await manager.broadcast(arena_id, {"type": "help_reset", "payload": {}})

    elif action == "next_round":
        arena = crud.get_arena(db, arena_id)
        if arena:
            arena.current_round = (arena.current_round or 0) + 1
            db.commit()
            crud.reset_team_help_status(db, arena_id)
        await manager.broadcast(arena_id, {
            "type": "round_changed",
            "payload": {"current_round": arena.current_round if arena else 0},
        })

    elif action == "overtime":
        arena = crud.get_arena(db, arena_id)
        if arena:
            arena.current_question_type = "overtime"
            db.commit()
        await manager.broadcast(arena_id, {"type": "overtime_started", "payload": {}})
        crud.log_arena_action(db, arena_id, "进入加赛", actor_type="host", actor_name="主持人")

    elif action == "sync_state":
        await manager.broadcast(arena_id, {
            "type": "scores_updated",
            "payload": {"teams": _team_snapshot(db, arena_id)},
        })
