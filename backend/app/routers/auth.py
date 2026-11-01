from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..database import get_db
from .. import crud, schemas, models
from ..auth import (verify_password, hash_password, create_access_token,
                    get_current_db_user, invalidate_user_cache)

router = APIRouter(prefix="/api/auth", tags=["auth"])

@router.post("/login", response_model=schemas.TokenResponse)
def login(req: schemas.LoginRequest, db: Session = Depends(get_db)):
    user = crud.get_user_by_employee_id(db, req.employee_id)
    if not user or not verify_password(req.password, user.password_hash):
        raise HTTPException(status_code=401, detail="工号或密码错误")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="账号已被禁用，请联系管理员")
    token = create_access_token({"sub": str(user.id)})
    return schemas.TokenResponse(
        access_token=token,
        user_id=user.id,
        name=user.name,
        is_admin=user.is_admin,
        employee_id=user.employee_id,
        must_change_password=bool(getattr(user, "must_change_password", False)),
    )


@router.post("/change-password")
def change_password(req: schemas.ChangePasswordRequest,
                    db: Session = Depends(get_db),
                    current_user: models.User = Depends(get_current_db_user)):
    """修改自己的密码。

    初始密码（环境变量里定的或随机生成的）登录后必须走这里改一次，
    改完 must_change_password 置 False，其余接口才放行。
    """
    if not verify_password(req.old_password, current_user.password_hash):
        raise HTTPException(status_code=400, detail="原密码不正确")
    if req.new_password == req.old_password:
        raise HTTPException(status_code=400, detail="新密码不能与原密码相同")
    if len(req.new_password) < 8:
        raise HTTPException(status_code=400, detail="新密码至少 8 位")
    current_user.password_hash = hash_password(req.new_password)
    current_user.must_change_password = False
    db.commit()
    db.refresh(current_user)
    # 缓存里的快照还带着旧密码和 must_change_password，必须立刻作废
    invalidate_user_cache(current_user.id)
    return {"ok": True, "message": "密码修改成功"}
