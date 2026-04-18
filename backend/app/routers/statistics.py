from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from ..database import get_db
from .. import crud
from ..auth import require_admin

router = APIRouter(prefix="/api/statistics", tags=["statistics"])

@router.get("")
def get_statistics(db: Session = Depends(get_db), _=Depends(require_admin)):
    return crud.get_statistics(db)
