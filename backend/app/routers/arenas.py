import json
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from typing import List
from urllib.parse import quote
from ..database import get_db
from .. import crud, schemas
from ..auth import get_current_user, create_arena_player_token

router = APIRouter(prefix="/api/arenas", tags=["擂台赛"])

def _parse_settings(settings_str: str) -> dict:
    """解析settings JSON字符串"""
    if not settings_str:
        return {}
    try:
        return json.loads(settings_str)
    except (json.JSONDecodeError, TypeError):
        return {}

def _arena_to_out(arena) -> schemas.ArenaOut:
    """转换Arena模型为输出Schema"""
    return schemas.ArenaOut(
        id=arena.id,
        title=arena.title,
        status=arena.status,
        current_round=arena.current_round,
        current_question_index=arena.current_question_index,
        current_question_type=arena.current_question_type,
        settings=_parse_settings(arena.settings),
        invite_code=arena.invite_code,
        invite_expire=arena.invite_expire,
        winner_team_id=arena.winner_team_id,
        created_by=arena.created_by,
        created_at=arena.created_at,
        team_count=len(arena.teams or []),
        question_count=len(arena.questions or []),
    )

@router.post("/", response_model=schemas.ArenaOut)
def create_arena(arena_in: schemas.ArenaCreate, db: Session = Depends(get_db), user=Depends(get_current_user)):
    """创建擂台赛"""
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="需要管理员权限")
    arena = crud.create_arena(db, arena_in, user.id)
    return _arena_to_out(arena)

@router.get("/", response_model=List[schemas.ArenaOut])
def list_arenas(skip: int = 0, limit: int = 100, status: str = "", db: Session = Depends(get_db)):
    """获取擂台赛列表"""
    arenas, _ = crud.get_arenas(db, skip, limit, status)
    return [_arena_to_out(a) for a in arenas]

@router.get("/{arena_id}", response_model=schemas.ArenaOut)
def get_arena(arena_id: int, db: Session = Depends(get_db)):
    """获取擂台赛详情"""
    arena = crud.get_arena(db, arena_id)
    if not arena:
        raise HTTPException(status_code=404, detail="擂台赛不存在")
    return _arena_to_out(arena)

@router.put("/{arena_id}", response_model=schemas.ArenaOut)
def update_arena(arena_id: int, arena_in: schemas.ArenaUpdate, db: Session = Depends(get_db), user=Depends(get_current_user)):
    """更新擂台赛"""
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="需要管理员权限")
    arena = crud.update_arena(db, arena_id, arena_in)
    if not arena:
        raise HTTPException(status_code=404, detail="擂台赛不存在")
    return _arena_to_out(arena)

@router.delete("/{arena_id}")
def delete_arena(arena_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    """删除擂台赛"""
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="需要管理员权限")
    result = crud.delete_arena(db, arena_id)
    if not result:
        raise HTTPException(status_code=404, detail="擂台赛不存在")
    return {"message": "删除成功"}

@router.get("/invite/{code}", response_model=schemas.ArenaOut)
def get_arena_by_invite(code: str, db: Session = Depends(get_db)):
    """通过邀请码获取擂台赛"""
    arena = crud.get_arena_by_invite_code(db, code)
    if not arena:
        raise HTTPException(status_code=404, detail="邀请码无效或已过期")
    return _arena_to_out(arena)

@router.post("/{arena_id}/refresh-invite", response_model=schemas.ArenaOut)
def refresh_invite(arena_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    """刷新邀请码（重置15分钟有效期）"""
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="需要管理员权限")
    arena = crud.refresh_arena_invite(db, arena_id)
    if not arena:
        raise HTTPException(status_code=404, detail="擂台赛不存在")
    return _arena_to_out(arena)

# ===== 队伍管理 =====

@router.post("/{arena_id}/teams", response_model=schemas.ArenaTeamOut)
def add_team(arena_id: int, team_in: schemas.ArenaTeamCreate, db: Session = Depends(get_db), user=Depends(get_current_user)):
    """添加队伍"""
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="需要管理员权限")
    team = crud.add_team_to_arena(db, arena_id, team_in)
    if not team:
        raise HTTPException(status_code=404, detail="擂台赛不存在")
    return schemas.ArenaTeamOut(
        id=team.id,
        arena_id=team.arena_id,
        name=team.name,
        color=team.color,
        score=team.score,
        status=team.status,
        help_used_this_round=team.help_used_this_round,
        order=team.order,
        created_at=team.created_at,
        player_count=len(team.players or []),
    )

@router.get("/{arena_id}/teams", response_model=List[schemas.ArenaTeamOut])
def list_teams(arena_id: int, db: Session = Depends(get_db)):
    """获取队伍列表"""
    teams = crud.get_arena_teams(db, arena_id)
    return [
        schemas.ArenaTeamOut(
            id=t.id,
            arena_id=t.arena_id,
            name=t.name,
            color=t.color,
            score=t.score,
            status=t.status,
            help_used_this_round=t.help_used_this_round,
            order=t.order,
            created_at=t.created_at,
            player_count=len(t.players) if t.players else 0,
        ) for t in teams
    ]

@router.put("/teams/{team_id}", response_model=schemas.ArenaTeamOut)
def update_team(team_id: int, team_in: schemas.ArenaTeamUpdate, db: Session = Depends(get_db), user=Depends(get_current_user)):
    """更新队伍"""
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="需要管理员权限")
    team = crud.update_arena_team(db, team_id, team_in)
    if not team:
        raise HTTPException(status_code=404, detail="队伍不存在")
    return schemas.ArenaTeamOut(
        id=team.id,
        arena_id=team.arena_id,
        name=team.name,
        color=team.color,
        score=team.score,
        status=team.status,
        help_used_this_round=team.help_used_this_round,
        order=team.order,
        created_at=team.created_at,
        player_count=len(team.players or []),
    )

@router.delete("/teams/{team_id}")
def delete_team(team_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    """删除队伍"""
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="需要管理员权限")
    team = crud.get_arena_team(db, team_id)
    if not team:
        raise HTTPException(status_code=404, detail="队伍不存在")
    db.delete(team)
    db.commit()
    return {"message": "删除成功"}

# ===== 题目管理 =====

@router.post("/{arena_id}/questions", response_model=List[schemas.ArenaQuestionOut])
def add_questions(arena_id: int, questions: List[schemas.ArenaQuestionCreate], db: Session = Depends(get_db), user=Depends(get_current_user)):
    """添加题目到擂台赛"""
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="需要管理员权限")
    result = crud.add_questions_to_arena(db, arena_id, questions)
    return [
        schemas.ArenaQuestionOut(
            id=q.id,
            arena_id=q.arena_id,
            question_id=q.question_id,
            q_type=q.q_type,
            order_num=q.order_num,
            score=q.score,
            question=schemas.QuestionOut(
                id=q.question.id,
                type=q.question.type,
                content=q.question.content,
                options=q.question.options,
                answer=q.question.answer,
                analysis=q.question.analysis or "",
                category=q.question.category or "",
                created_at=q.question.created_at,
            ) if q.question else None,
        ) for q in result
    ]

@router.get("/{arena_id}/questions", response_model=List[schemas.ArenaQuestionOut])
def list_questions(arena_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    """获取擂台赛题目列表（含答案，仅主持人/管理员）"""
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="需要管理员权限")
    questions = crud.get_arena_questions(db, arena_id)
    return [
        schemas.ArenaQuestionOut(
            id=q.id,
            arena_id=q.arena_id,
            question_id=q.question_id,
            q_type=q.q_type,
            order_num=q.order_num,
            score=q.score,
            question=schemas.QuestionOut(
                id=q.question.id,
                type=q.question.type,
                content=q.question.content,
                options=q.question.options,
                answer=q.question.answer,
                analysis=q.question.analysis or "",
                category=q.question.category or "",
                created_at=q.question.created_at,
            ) if q.question else None,
        ) for q in questions
    ]

@router.get("/{arena_id}/questions/public", response_model=List[schemas.ArenaQuestionPublicOut])
def list_questions_public(arena_id: int, db: Session = Depends(get_db)):
    """获取擂台赛题目列表（选手可见，不含答案与解析，防作弊）"""
    questions = crud.get_arena_questions(db, arena_id)
    result = []
    for q in questions:
        origin = q.question
        result.append(schemas.ArenaQuestionPublicOut(
            id=q.id,
            arena_id=q.arena_id,
            question_id=q.question_id,
            q_type=q.q_type,
            order_num=q.order_num,
            score=q.score,
            question_type=(origin.type if origin else ""),
            content=(origin.content if origin else ""),
            options=(origin.options if origin else "{}"),
        ))
    return result

@router.delete("/questions/{question_id}")
def delete_question(question_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    """移除擂台赛题目"""
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="需要管理员权限")
    question = crud.get_arena_question(db, question_id)
    if not question:
        raise HTTPException(status_code=404, detail="题目不存在")
    db.delete(question)
    db.commit()
    return {"message": "删除成功"}

# ===== 答案管理 =====

@router.post("/answers", response_model=schemas.TeamAnswerOut)
def submit_answer(answer_in: schemas.TeamAnswerSubmit, db: Session = Depends(get_db)):
    """提交答案（仅记录，判分由主持人完成）"""
    answer = crud.submit_team_answer(db, answer_in)
    if not answer:
        raise HTTPException(status_code=404, detail="提交失败")
    return schemas.TeamAnswerOut(
        id=answer.id,
        team_id=answer.team_id,
        question_id=answer.question_id,
        answer=answer.answer,
        is_correct=answer.is_correct,
        time_used=answer.time_used,
        score=answer.score,
        help_used=answer.help_used,
        submitted_at=answer.submitted_at,
    )

@router.post("/answers/{answer_id}/judge", response_model=schemas.TeamAnswerOut)
def judge_answer(answer_id: int, judge_in: schemas.TeamAnswerJudge,
                 db: Session = Depends(get_db), user=Depends(get_current_user)):
    """主持人判定答案（is_correct留空时自动比对客观题）"""
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="需要管理员权限")
    if judge_in.is_correct is None:
        # 自动判定：无法机器判定的题目（主观题/无标准答案）保持待判定状态
        answer, verdict = crud.auto_judge_team_answer(db, answer_id)
        if answer is None:
            raise HTTPException(status_code=404, detail="答案不存在")
        if verdict is None:
            raise HTTPException(status_code=400, detail="该题无法自动判定，请人工评分")
    else:
        answer = crud.judge_answer(db, answer_id, judge_in.is_correct, judge_in.score)
    if not answer:
        raise HTTPException(status_code=404, detail="答案不存在")
    return schemas.TeamAnswerOut(
        id=answer.id,
        team_id=answer.team_id,
        question_id=answer.question_id,
        answer=answer.answer,
        is_correct=answer.is_correct,
        time_used=answer.time_used,
        score=answer.score,
        help_used=answer.help_used,
        submitted_at=answer.submitted_at,
    )

@router.get("/teams/{team_id}/answers", response_model=List[schemas.TeamAnswerOut])
def get_team_answers(team_id: int, db: Session = Depends(get_db)):
    """获取队伍答题记录"""
    answers = crud.get_team_answers(db, team_id)
    return [
        schemas.TeamAnswerOut(
            id=a.id,
            team_id=a.team_id,
            question_id=a.question_id,
            answer=a.answer,
            is_correct=a.is_correct,
            time_used=a.time_used,
            score=a.score,
            help_used=a.help_used,
            submitted_at=a.submitted_at,
        ) for a in answers
    ]

@router.put("/answers/{answer_id}", response_model=schemas.TeamAnswerOut)
def update_answer(answer_id: int, is_correct: bool, score: int = 0, db: Session = Depends(get_db), user=Depends(get_current_user)):
    """主持人修改答案结果"""
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="需要管理员权限")
    answer = crud.judge_answer(db, answer_id, is_correct, score)
    if not answer:
        raise HTTPException(status_code=404, detail="答案不存在")
    return schemas.TeamAnswerOut(
        id=answer.id,
        team_id=answer.team_id,
        question_id=answer.question_id,
        answer=answer.answer,
        is_correct=answer.is_correct,
        time_used=answer.time_used,
        score=answer.score,
        help_used=answer.help_used,
        submitted_at=answer.submitted_at,
    )

# ===== 选手管理 =====

@router.post("/players/join", response_model=schemas.ArenaPlayerOut)
def player_join(join_in: schemas.ArenaPlayerJoin, db: Session = Depends(get_db)):
    """选手加入擂台赛"""
    player = crud.player_join_arena(db, join_in)
    if not player:
        raise HTTPException(status_code=404, detail="队伍不存在、邀请码已过期或人数已满")
    token = create_arena_player_token(player.id, player.team.arena_id, player.team_id)
    return schemas.ArenaPlayerOut(
        id=player.id,
        team_id=player.team_id,
        device_id=player.device_id,
        player_name=player.player_name,
        join_time=player.join_time,
        last_active=player.last_active,
        token=token,
    )

@router.get("/teams/{team_id}/players", response_model=List[schemas.ArenaPlayerOut])
def get_players(team_id: int, db: Session = Depends(get_db)):
    """获取队伍选手列表"""
    players = crud.get_team_players(db, team_id)
    return [
        schemas.ArenaPlayerOut(
            id=p.id,
            team_id=p.team_id,
            device_id=p.device_id,
            player_name=p.player_name,
            join_time=p.join_time,
            last_active=p.last_active,
        ) for p in players
    ]

# ===== 日志 =====

@router.get("/{arena_id}/logs", response_model=List[schemas.ArenaLogOut])
def get_logs(arena_id: int, limit: int = 100, db: Session = Depends(get_db)):
    """获取操作日志"""
    logs = crud.get_arena_logs(db, arena_id, limit)
    return [
        schemas.ArenaLogOut(
            id=log.id,
            arena_id=log.arena_id,
            action=log.action,
            actor_type=log.actor_type,
            actor_id=log.actor_id,
            actor_name=log.actor_name,
            detail=log.detail,
            timestamp=log.timestamp,
        ) for log in logs
    ]

# ===== 轮次管理 =====

@router.post("/{arena_id}/rounds", response_model=schemas.ArenaRoundOut)
def create_round(arena_id: int, round_in: schemas.ArenaRoundCreate, db: Session = Depends(get_db), user=Depends(get_current_user)):
    """创建轮次"""
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="需要管理员权限")
    round_record = crud.create_arena_round(db, arena_id, round_in)
    if not round_record:
        raise HTTPException(status_code=404, detail="擂台赛不存在")
    return schemas.ArenaRoundOut(
        id=round_record.id,
        arena_id=round_record.arena_id,
        round_num=round_record.round_num,
        round_type=round_record.round_type,
        status=round_record.status,
        start_time=round_record.start_time,
        end_time=round_record.end_time,
    )

@router.get("/{arena_id}/rounds", response_model=List[schemas.ArenaRoundOut])
def list_rounds(arena_id: int, db: Session = Depends(get_db)):
    """获取轮次列表"""
    rounds = crud.get_arena_rounds(db, arena_id)
    return [
        schemas.ArenaRoundOut(
            id=r.id,
            arena_id=r.arena_id,
            round_num=r.round_num,
            round_type=r.round_type,
            status=r.status,
            start_time=r.start_time,
            end_time=r.end_time,
        ) for r in rounds
    ]

# ===== 导出 =====

@router.get("/{arena_id}/export")
def export_answers(arena_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    """导出台词赛Excel报表（总成绩表 / 答题明细 / 统计表）"""
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="需要管理员权限")
    arena = crud.get_arena(db, arena_id)
    if not arena:
        raise HTTPException(status_code=404, detail="擂台赛不存在")
    buf = crud.export_arena_excel(db, arena_id)
    if not buf:
        raise HTTPException(status_code=404, detail="导出失败")
    filename = f"{arena.title}_成绩表.xlsx"
    quoted = quote(filename)
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quoted}"},
    )

@router.get("/{arena_id}/export/json")
def export_answers_json(arena_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    """导出答案明细JSON（供线下评分参考）"""
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="需要管理员权限")
    return crud.export_arena_answers(db, arena_id)

@router.get("/{arena_id}/standings", response_model=schemas.ArenaStandingsOut)
def get_standings(arena_id: int, db: Session = Depends(get_db)):
    """获取排名与平局判定"""
    if not crud.get_arena(db, arena_id):
        raise HTTPException(status_code=404, detail="擂台赛不存在")
    return crud.get_arena_standings(db, arena_id)

# ===== 淘汰 / 复活 =====

@router.post("/{arena_id}/eliminate")
def eliminate_teams(arena_id: int, payload: schemas.ArenaTeamIds,
                    db: Session = Depends(get_db), user=Depends(get_current_user)):
    """手动淘汰指定队伍"""
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="需要管理员权限")
    if not crud.get_arena(db, arena_id):
        raise HTTPException(status_code=404, detail="擂台赛不存在")
    eliminated = crud.eliminate_teams(db, arena_id, payload.team_ids)
    for team in eliminated:
        crud.log_arena_action(db, arena_id, "淘汰队伍", actor_type="host",
                              actor_id=team.id, actor_name=team.name)
    return {"message": "淘汰成功", "eliminated": [t.id for t in eliminated]}

@router.post("/{arena_id}/eliminate-bottom")
def eliminate_bottom(arena_id: int, count: int = None,
                     db: Session = Depends(get_db), user=Depends(get_current_user)):
    """按排名淘汰最后N支队伍"""
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="需要管理员权限")
    eliminated = crud.eliminate_bottom_teams(db, arena_id, count)
    for team in eliminated:
        crud.log_arena_action(db, arena_id, "淘汰队伍", actor_type="host",
                              actor_id=team.id, actor_name=team.name)
    return {"message": "淘汰成功", "eliminated": [t.id for t in eliminated]}

@router.post("/{arena_id}/resurrect")
def resurrect_team(arena_id: int, payload: schemas.ArenaTeamId,
                    db: Session = Depends(get_db), user=Depends(get_current_user)):
    """复活一支队伍（复活赛冠军）"""
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="需要管理员权限")
    team = crud.resurrect_team(db, payload.team_id)
    if not team or team.arena_id != arena_id:
        raise HTTPException(status_code=404, detail="队伍不存在")
    crud.log_arena_action(db, arena_id, "复活队伍", actor_type="host",
                          actor_id=team.id, actor_name=team.name)
    return {"message": "复活成功", "team_id": team.id}

@router.post("/{arena_id}/rounds/{round_id}/advance")
def advance_round(arena_id: int, round_id: int, db: Session = Depends(get_db),
                   user=Depends(get_current_user)):
    """推进轮次（新一轮开始时重置求助次数）"""
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="需要管理员权限")
    round_record = crud.update_arena_round(db, round_id, "active")
    if not round_record:
        raise HTTPException(status_code=404, detail="轮次不存在")
    arena = crud.get_arena(db, arena_id)
    if arena:
        arena.current_round = round_record.round_num
        db.commit()
        crud.reset_team_help_status(db, arena_id)
    return {"message": "轮次已开始", "round_num": round_record.round_num}

@router.post("/{arena_id}/reset-help")
def reset_team_help(arena_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    """重置队伍求助状态"""
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="需要管理员权限")
    crud.reset_team_help_status(db, arena_id)
    return {"message": "重置成功"}
