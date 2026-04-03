from fastapi import APIRouter, Depends, HTTPException
from database import get_db
from api.deps import get_current_user
from pydantic import BaseModel
from typing import List
import json

router = APIRouter()

class SessionUpdate(BaseModel):
    deck_id: int
    study_method: str
    current_index: int
    shuffled_vocab_ids: List[int]
    is_active: bool = True

@router.post("/deck")
async def update_session(session: SessionUpdate, db = Depends(get_db), current_user: dict = Depends(get_current_user)):
    user_id = current_user['user_id']
    
    with db.cursor() as cursor:
        # Check if session exists
        cursor.execute(
            "SELECT session_id FROM DECK_SESSION WHERE user_id = %s AND deck_id = %s AND study_method = %s AND is_active = TRUE",
            (user_id, session.deck_id, session.study_method)
        )
        existing = cursor.fetchone()
        
        vocab_ids_json = json.dumps(session.shuffled_vocab_ids)
        
        if existing:
            cursor.execute(
                "UPDATE DECK_SESSION SET current_index = %s, shuffled_vocab_ids = %s, is_active = %s WHERE session_id = %s",
                (session.current_index, vocab_ids_json, session.is_active, existing['session_id'])
            )
        else:
            cursor.execute(
                "INSERT INTO DECK_SESSION (user_id, deck_id, study_method, current_index, shuffled_vocab_ids, is_active) VALUES (%s, %s, %s, %s, %s, %s)",
                (user_id, session.deck_id, session.study_method, session.current_index, vocab_ids_json, session.is_active)
            )
        db.commit()
    return {"status": "success"}

@router.get("/deck/{deck_id}/{method}")
async def get_session(deck_id: int, method: str, db = Depends(get_db), current_user: dict = Depends(get_current_user)):
    user_id = current_user['user_id']
    with db.cursor() as cursor:
        cursor.execute(
            "SELECT * FROM DECK_SESSION WHERE user_id = %s AND deck_id = %s AND study_method = %s AND is_active = TRUE ORDER BY updated_at DESC LIMIT 1",
            (user_id, deck_id, method)
        )
        session = cursor.fetchone()
        if not session:
            return None
        
        # Parse JSON
        if isinstance(session['shuffled_vocab_ids'], str):
            session['shuffled_vocab_ids'] = json.loads(session['shuffled_vocab_ids'])
            
        return session
