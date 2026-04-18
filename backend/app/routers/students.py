from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from ..database import get_db
from .. import crud, schemas, models
from ..auth import get_current_user, require_admin

router = APIRouter(prefix="/api/students", tags=["students"])

@router.get("")
def list_students(skip: int = 0, limit: int = 20, search: str = "", dept: str = "",
                  db: Session = Depends(get_db), _=Depends(require_admin)):
    users, total = crud.get_users(db, skip=skip, limit=limit, search=search, dept=dept)
    return {"items": [schemas.UserOut.model_validate(u) for u in users], "total": total}

@router.post("", response_model=schemas.UserOut)
def create_student(user_in: schemas.UserCreate, db: Session = Depends(get_db), _=Depends(require_admin)):
    if crud.get_user_by_employee_id(db, user_in.employee_id):
        raise HTTPException(status_code=400, detail="工号已存在")
    return crud.create_user(db, user_in)

@router.put("/{user_id}", response_model=schemas.UserOut)
def update_student(user_id: int, user_in: schemas.UserUpdate, db: Session = Depends(get_db), _=Depends(require_admin)):
    user = crud.update_user(db, user_id, user_in)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    return user

@router.delete("/{user_id}")
def delete_student(user_id: int, db: Session = Depends(get_db), _=Depends(require_admin)):
    crud.delete_user(db, user_id)
    return {"ok": True}

@router.get("/{user_id}/records")
def get_student_records(user_id: int, db: Session = Depends(get_db), _=Depends(get_current_user)):
    records = crud.get_user_records(db, user_id)
    return [schemas.ExamRecordOut.model_validate(r) for r in records]
