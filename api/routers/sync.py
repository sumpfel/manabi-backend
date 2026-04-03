from fastapi import APIRouter, Depends
import pymysql
from database import get_db
from api.deps import get_current_user

router = APIRouter()

@router.get("/status")
def sync_status(current_user: dict = Depends(get_current_user), db: pymysql.connections.Connection = Depends(get_db)):
    with db.cursor() as cursor:
        cursor.execute("SELECT * FROM USER_STATISTIC WHERE user_id = %s", (current_user['user_id'],))
        stats = cursor.fetchone()
    return {"status": "ok", "stats": stats}
