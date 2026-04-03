import uuid
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional, List
import pymysql
from database import get_db
from api.deps import get_current_user

router = APIRouter()

# ── Request Models ──

class VocabCreate(BaseModel):
    word: str
    reading: Optional[str] = None
    translation: str

class LessonCreate(BaseModel):
    title: str
    description: Optional[str] = ""
    grammar_markdown: str
    lesson_order: int = 1
    required_accuracy: Optional[float] = None
    exercises: Optional[List[dict]] = []
    vocab: Optional[List[VocabCreate]] = []

class UnitCreate(BaseModel):
    title: str
    description: str = ""
    lang_id: int = 3
    mother_tongue: str = "de"
    is_public: bool = False
    language_level: Optional[str] = None
    tags: Optional[str] = None
    base_unit_id: Optional[int] = None
    lessons: Optional[List[LessonCreate]] = []

class CommentCreate(BaseModel):
    content: str
    parent_comment_id: Optional[int] = None


# ── Unit CRUD ──

@router.get("/")
def list_units(current_user: dict = Depends(get_current_user), db: pymysql.connections.Connection = Depends(get_db)):
    """List user's own units + official global units."""
    with db.cursor() as cursor:
        cursor.execute("""
            SELECT u.*, usr.username as creator_name FROM UNIT u 
            LEFT JOIN USER usr ON u.creator_user_id = usr.user_id
            WHERE u.creator_user_id = %s OR u.is_basic_global = TRUE
            ORDER BY u.is_basic_global DESC, u.created_at DESC
        """, (current_user['user_id'],))
        units = cursor.fetchall()
    return {"units": units}


@router.get("/public")
def list_public_units(
    search: Optional[str] = None,
    language_level: Optional[str] = None,
    tags: Optional[str] = None,
    lang_id: Optional[int] = None,
    is_ai: Optional[bool] = None,
    db: pymysql.connections.Connection = Depends(get_db)
):
    """Browse public units with filters."""
    query = """
        SELECT u.*, usr.username as creator_name FROM UNIT u 
        LEFT JOIN USER usr ON u.creator_user_id = usr.user_id
        WHERE u.is_public = TRUE
    """
    params = []
    
    if search:
        query += " AND (u.title LIKE %s OR u.description LIKE %s)"
        params.extend([f"%{search}%", f"%{search}%"])
    if language_level:
        query += " AND u.language_level = %s"
        params.append(language_level)
    if tags:
        query += " AND u.tags LIKE %s"
        params.append(f"%{tags}%")
    if lang_id:
        query += " AND u.lang_id = %s"
        params.append(lang_id)
    if is_ai is not None:
        query += " AND u.is_ai_generated = %s"
        params.append(is_ai)
    
    query += " ORDER BY u.vote_count DESC, u.created_at DESC LIMIT 50"
    
    with db.cursor() as cursor:
        cursor.execute(query, params)
        units = cursor.fetchall()
    return {"units": units}


@router.get("/community")
def list_community_units(
    search: Optional[str] = None,
    language_level: Optional[str] = None,
    db: pymysql.connections.Connection = Depends(get_db)
):
    """Browse community (non-AI, non-official) public units."""
    query = """
        SELECT u.*, usr.username as creator_name FROM UNIT u 
        LEFT JOIN USER usr ON u.creator_user_id = usr.user_id
        WHERE u.is_public = TRUE AND u.is_basic_global = FALSE AND u.is_ai_generated = FALSE
    """
    params = []
    if search:
        query += " AND (u.title LIKE %s OR u.description LIKE %s)"
        params.extend([f"%{search}%", f"%{search}%"])
    if language_level:
        query += " AND u.language_level = %s"
        params.append(language_level)
    
    query += " ORDER BY u.vote_count DESC, u.created_at DESC LIMIT 50"
    
    with db.cursor() as cursor:
        cursor.execute(query, params)
        units = cursor.fetchall()
    return {"units": units}


@router.get("/ai")
def list_ai_units(
    search: Optional[str] = None,
    current_user: dict = Depends(get_current_user),
    db: pymysql.connections.Connection = Depends(get_db)
):
    """List AI-generated units (own + public)."""
    query = """
        SELECT u.*, usr.username as creator_name FROM UNIT u 
        LEFT JOIN USER usr ON u.creator_user_id = usr.user_id
        WHERE u.is_ai_generated = TRUE AND (u.creator_user_id = %s OR u.is_public = TRUE)
    """
    params = [current_user['user_id']]
    if search:
        query += " AND (u.title LIKE %s OR u.description LIKE %s)"
        params.extend([f"%{search}%", f"%{search}%"])
    
    query += " ORDER BY u.created_at DESC LIMIT 50"
    
    with db.cursor() as cursor:
        cursor.execute(query, params)
        units = cursor.fetchall()
    return {"units": units}


@router.post("/")
def create_unit(unit: UnitCreate, current_user: dict = Depends(get_current_user), db: pymysql.connections.Connection = Depends(get_db)):
    """Create a new user unit (optionally with lessons)."""
    import json
    share_code = str(uuid.uuid4())[:8]
    mt_lang_id = LANG_IDS.get(unit.mother_tongue, 1)
    with db.cursor() as cursor:
        cursor.execute(
            """INSERT INTO UNIT (lang_id, creator_user_id, title, description, is_basic_global, 
               share_code, is_public, language_level, tags, base_unit_id)
               VALUES (%s, %s, %s, %s, FALSE, %s, %s, %s, %s, %s)""",
            (unit.lang_id, current_user['user_id'], unit.title, unit.description,
             share_code, unit.is_public, unit.language_level, unit.tags, unit.base_unit_id)
        )
        unit_id = cursor.lastrowid
        
        # Create associated vocab deck
        cursor.execute(
            "INSERT INTO DECK (user_id, lang_id, name, type, parent_unit_id) VALUES (%s, %s, %s, 'unit', %s)",
            (current_user['user_id'], unit.lang_id, f"{unit.title} - Vocab", unit_id)
        )
        deck_id = cursor.lastrowid

        # Insert nested lessons if any
        if unit.lessons:
            for l_idx, lesson in enumerate(unit.lessons):
                cursor.execute(
                    """INSERT INTO LESSON (unit_id, lesson_order, title, grammar_markdown, exercises_json, required_accuracy)
                       VALUES (%s, %s, %s, %s, %s, %s)""",
                    (unit_id, lesson.lesson_order or (l_idx + 1), lesson.title, lesson.grammar_markdown, 
                     json.dumps(lesson.exercises), lesson.required_accuracy)
                )
                lesson_id = cursor.lastrowid
                
                # Insert vocab for this lesson
                if lesson.vocab:
                    for v in lesson.vocab:
                        cursor.execute(
                            "INSERT INTO VOCAB (deck_id, learning_lang_id, lesson_id, word_text, reading_text) VALUES (%s, %s, %s, %s, %s)",
                            (deck_id, unit.lang_id, lesson_id, v.word, v.reading)
                        )
                        v_id = cursor.lastrowid
                        cursor.execute(
                            "INSERT INTO VOCAB_TRANSLATION (vocab_id, mother_tongue_lang_id, translated_text) VALUES (%s, %s, %s)",
                            (v_id, mt_lang_id, v.translation)
                        )
        
        db.commit()
    
    return {"unit_id": unit_id, "deck_id": deck_id, "share_code": share_code}


@router.get("/{unit_id}")
def get_unit(unit_id: int, current_user: dict = Depends(get_current_user), db: pymysql.connections.Connection = Depends(get_db)):
    """Get unit details with lessons."""
    with db.cursor() as cursor:
        cursor.execute("""
            SELECT u.*, usr.username as creator_name FROM UNIT u 
            LEFT JOIN USER usr ON u.creator_user_id = usr.user_id
            WHERE u.unit_id = %s
        """, (unit_id,))
        unit = cursor.fetchone()
        if not unit:
            raise HTTPException(status_code=404, detail="Unit not found")
        
        # Check access
        if not unit['is_public'] and not unit['is_basic_global'] and unit['creator_user_id'] != current_user['user_id']:
            raise HTTPException(status_code=403, detail="Access denied")
        
        cursor.execute("SELECT * FROM LESSON WHERE unit_id = %s ORDER BY lesson_order ASC", (unit_id,))
        lessons = cursor.fetchall()
        
        # Get vocab for each lesson
        for lesson in lessons:
            import json
            try:
                lesson['exercises'] = json.loads(lesson['exercises_json']) if lesson['exercises_json'] else []
            except:
                lesson['exercises'] = []
                
            cursor.execute("""
                SELECT v.*, vt.translated_text FROM VOCAB v 
                LEFT JOIN VOCAB_TRANSLATION vt ON v.vocab_id = vt.vocab_id
                WHERE v.lesson_id = %s
            """, (lesson['lesson_id'],))
            lesson['vocab'] = cursor.fetchall()
        
        # Get comments
        cursor.execute("""
            SELECT c.*, usr.username FROM COMMENT c 
            LEFT JOIN USER usr ON c.user_id = usr.user_id
            WHERE c.target_type = 'unit' AND c.target_id = %s
            ORDER BY c.created_at ASC
        """, (unit_id,))
        comments = cursor.fetchall()
        
        # Get user's vote
        cursor.execute(
            "SELECT value FROM VOTE WHERE user_id = %s AND target_type = 'unit' AND target_id = %s",
            (current_user['user_id'], unit_id)
        )
        user_vote = cursor.fetchone()
        
        # Get lesson progress
        cursor.execute(
            "SELECT lesson_id, is_completed FROM LESSON_PROGRESS WHERE user_id = %s AND lesson_id IN (SELECT lesson_id FROM LESSON WHERE unit_id = %s)",
            (current_user['user_id'], unit_id)
        )
        progress = {row['lesson_id']: row['is_completed'] for row in cursor.fetchall()}
    
    unit['lessons'] = lessons
    unit['comments'] = comments
    unit['user_vote'] = user_vote['value'] if user_vote else 0
    unit['lesson_progress'] = progress
    return unit


@router.post("/{unit_id}/lessons")
def add_lesson(unit_id: int, lesson: LessonCreate, current_user: dict = Depends(get_current_user), db: pymysql.connections.Connection = Depends(get_db)):
    """Add a lesson to a unit."""
    with db.cursor() as cursor:
        # Verify ownership
        cursor.execute("SELECT creator_user_id FROM UNIT WHERE unit_id = %s", (unit_id,))
        unit = cursor.fetchone()
        if not unit or unit['creator_user_id'] != current_user['user_id']:
            raise HTTPException(status_code=403, detail="Not your unit")
        
        cursor.execute(
            "INSERT INTO LESSON (unit_id, lesson_order, title, grammar_markdown) VALUES (%s, %s, %s, %s)",
            (unit_id, lesson.lesson_order, lesson.title, lesson.grammar_markdown)
        )
        db.commit()
        lesson_id = cursor.lastrowid
    return {"lesson_id": lesson_id}


@router.post("/{unit_id}/share")
def share_unit(unit_id: int, current_user: dict = Depends(get_current_user), db: pymysql.connections.Connection = Depends(get_db)):
    """Generate or return share link for a unit."""
    with db.cursor() as cursor:
        cursor.execute("SELECT share_code, creator_user_id FROM UNIT WHERE unit_id = %s", (unit_id,))
        unit = cursor.fetchone()
        if not unit:
            raise HTTPException(status_code=404, detail="Unit not found")
        if unit['creator_user_id'] != current_user['user_id']:
            raise HTTPException(status_code=403, detail="Not your unit")
        
        share_code = unit['share_code']
        if not share_code:
            share_code = str(uuid.uuid4())[:8]
            cursor.execute("UPDATE UNIT SET share_code = %s WHERE unit_id = %s", (share_code, unit_id))
            db.commit()
    
    return {"share_code": share_code}


@router.get("/shared/{share_code}")
def import_shared_unit(share_code: str, current_user: dict = Depends(get_current_user), db: pymysql.connections.Connection = Depends(get_db)):
    """Import a shared unit by share code."""
    with db.cursor() as cursor:
        cursor.execute("""
            SELECT u.*, usr.username as creator_name FROM UNIT u 
            LEFT JOIN USER usr ON u.creator_user_id = usr.user_id
            WHERE u.share_code = %s
        """, (share_code,))
        unit = cursor.fetchone()
        if not unit:
            raise HTTPException(status_code=404, detail="Shared unit not found")
        
        cursor.execute("SELECT * FROM LESSON WHERE unit_id = %s ORDER BY lesson_order ASC", (unit['unit_id'],))
        lessons = cursor.fetchall()
        
        for lesson in lessons:
            cursor.execute("""
                SELECT v.*, vt.translated_text FROM VOCAB v 
                LEFT JOIN VOCAB_TRANSLATION vt ON v.vocab_id = vt.vocab_id
                WHERE v.lesson_id = %s
            """, (lesson['lesson_id'],))
            lesson['vocab'] = cursor.fetchall()
    
    unit['lessons'] = lessons
    return unit


@router.post("/{unit_id}/comment")
def comment_on_unit(unit_id: int, comment: CommentCreate, current_user: dict = Depends(get_current_user), db: pymysql.connections.Connection = Depends(get_db)):
    """Add a comment to a unit."""
    with db.cursor() as cursor:
        cursor.execute(
            "INSERT INTO COMMENT (user_id, target_type, target_id, parent_comment_id, content) VALUES (%s, 'unit', %s, %s, %s)",
            (current_user['user_id'], unit_id, comment.parent_comment_id, comment.content)
        )
        comment_id = cursor.lastrowid
        
        # Send notification to unit creator
        cursor.execute("SELECT creator_user_id FROM UNIT WHERE unit_id = %s", (unit_id,))
        unit = cursor.fetchone()
        if unit and unit['creator_user_id'] != current_user['user_id']:
            cursor.execute(
                "INSERT INTO NOTIFICATION (user_id, type, message, target_type, target_id) VALUES (%s, 'comment', %s, 'unit', %s)",
                (unit['creator_user_id'], f"{current_user['username']} hat deine Unit kommentiert", unit_id)
            )
        
        # Notify parent comment author if it's a reply
        if comment.parent_comment_id:
            cursor.execute("SELECT user_id FROM COMMENT WHERE comment_id = %s", (comment.parent_comment_id,))
            parent = cursor.fetchone()
            if parent and parent['user_id'] != current_user['user_id']:
                cursor.execute(
                    "INSERT INTO NOTIFICATION (user_id, type, message, target_type, target_id) VALUES (%s, 'reply', %s, 'comment', %s)",
                    (parent['user_id'], f"{current_user['username']} hat auf deinen Kommentar geantwortet", comment.parent_comment_id)
                )
        
        db.commit()
    return {"comment_id": comment_id}


@router.post("/{unit_id}/vote")
def vote_on_unit(unit_id: int, value: int = 1, current_user: dict = Depends(get_current_user), db: pymysql.connections.Connection = Depends(get_db)):
    """Vote on a unit (1=upvote, -1=downvote, 0=remove)."""
    with db.cursor() as cursor:
        if value == 0:
            cursor.execute(
                "DELETE FROM VOTE WHERE user_id = %s AND target_type = 'unit' AND target_id = %s",
                (current_user['user_id'], unit_id)
            )
        else:
            cursor.execute(
                """INSERT INTO VOTE (user_id, target_type, target_id, value) VALUES (%s, 'unit', %s, %s)
                   ON DUPLICATE KEY UPDATE value = %s""",
                (current_user['user_id'], unit_id, value, value)
            )
        
        # Update vote count
        cursor.execute(
            "UPDATE UNIT SET vote_count = (SELECT COALESCE(SUM(value), 0) FROM VOTE WHERE target_type = 'unit' AND target_id = %s) WHERE unit_id = %s",
            (unit_id, unit_id)
        )
        db.commit()
    return {"status": "voted"}
