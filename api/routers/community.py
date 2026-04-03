from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
import pymysql
from database import get_db
from api.deps import get_current_user

router = APIRouter()

class CommentCreate(BaseModel):
    content: str
    parent_comment_id: Optional[int] = None

# ── Notifications ──

@router.get("/notifications")
def list_notifications(current_user: dict = Depends(get_current_user), db: pymysql.connections.Connection = Depends(get_db)):
    """Get all notifications for current user."""
    with db.cursor() as cursor:
        cursor.execute(
            "SELECT * FROM NOTIFICATION WHERE user_id = %s ORDER BY created_at DESC LIMIT 50",
            (current_user['user_id'],)
        )
        notifications = cursor.fetchall()
        
        cursor.execute(
            "SELECT COUNT(*) as c FROM NOTIFICATION WHERE user_id = %s AND is_read = FALSE",
            (current_user['user_id'],)
        )
        unread = cursor.fetchone()['c']
    
    return {"notifications": notifications, "unread_count": unread}

@router.put("/notifications/{notification_id}/read")
def mark_read(notification_id: int, current_user: dict = Depends(get_current_user), db: pymysql.connections.Connection = Depends(get_db)):
    """Mark a notification as read."""
    with db.cursor() as cursor:
        cursor.execute(
            "UPDATE NOTIFICATION SET is_read = TRUE WHERE notification_id = %s AND user_id = %s",
            (notification_id, current_user['user_id'])
        )
        db.commit()
    return {"status": "read"}

@router.put("/notifications/read-all")
def mark_all_read(current_user: dict = Depends(get_current_user), db: pymysql.connections.Connection = Depends(get_db)):
    """Mark all notifications as read."""
    with db.cursor() as cursor:
        cursor.execute(
            "UPDATE NOTIFICATION SET is_read = TRUE WHERE user_id = %s",
            (current_user['user_id'],)
        )
        db.commit()
    return {"status": "all_read"}

# ── Deck Sections ──

@router.get("/sections")
def list_sections(current_user: dict = Depends(get_current_user), db: pymysql.connections.Connection = Depends(get_db)):
    """List user's deck sections."""
    with db.cursor() as cursor:
        cursor.execute(
            "SELECT * FROM DECK_SECTION WHERE user_id = %s ORDER BY sort_order ASC",
            (current_user['user_id'],)
        )
        sections = cursor.fetchall()
    return {"sections": sections}

@router.post("/sections")
def create_section(name: str, current_user: dict = Depends(get_current_user), db: pymysql.connections.Connection = Depends(get_db)):
    """Create a new custom deck section."""
    with db.cursor() as cursor:
        cursor.execute(
            "SELECT MAX(sort_order) as max_order FROM DECK_SECTION WHERE user_id = %s",
            (current_user['user_id'],)
        )
        max_order = cursor.fetchone()['max_order'] or 0
        
        cursor.execute(
            "INSERT INTO DECK_SECTION (user_id, name, is_system, sort_order) VALUES (%s, %s, FALSE, %s)",
            (current_user['user_id'], name, max_order + 1)
        )
        db.commit()
        section_id = cursor.lastrowid
    return {"section_id": section_id}

@router.put("/sections/{section_id}")
def rename_section(section_id: int, name: str, current_user: dict = Depends(get_current_user), db: pymysql.connections.Connection = Depends(get_db)):
    """Rename a custom section (system sections cannot be renamed)."""
    with db.cursor() as cursor:
        cursor.execute(
            "SELECT is_system FROM DECK_SECTION WHERE section_id = %s AND user_id = %s",
            (section_id, current_user['user_id'])
        )
        section = cursor.fetchone()
        if not section:
            raise HTTPException(status_code=404, detail="Section not found")
        if section['is_system']:
            raise HTTPException(status_code=403, detail="System sections cannot be renamed")
        
        cursor.execute("UPDATE DECK_SECTION SET name = %s WHERE section_id = %s", (name, section_id))
        db.commit()
    return {"status": "renamed"}

@router.delete("/sections/{section_id}")
def delete_section(section_id: int, current_user: dict = Depends(get_current_user), db: pymysql.connections.Connection = Depends(get_db)):
    """Delete a custom section (system sections cannot be deleted)."""
    with db.cursor() as cursor:
        cursor.execute(
            "SELECT is_system FROM DECK_SECTION WHERE section_id = %s AND user_id = %s",
            (section_id, current_user['user_id'])
        )
        section = cursor.fetchone()
        if not section:
            raise HTTPException(status_code=404, detail="Section not found")
        if section['is_system']:
            raise HTTPException(status_code=403, detail="System sections cannot be deleted")
        
        # Move decks in this section to no section
        cursor.execute("UPDATE DECK SET section_id = NULL WHERE section_id = %s", (section_id,))
        cursor.execute("DELETE FROM DECK_SECTION WHERE section_id = %s", (section_id,))
        db.commit()
    return {"status": "deleted"}

# ── Public Search (Units + Decks) ──

@router.get("/search")
def search_public(
    q: Optional[str] = None,
    type: Optional[str] = None,  # 'unit' or 'deck'
    language_level: Optional[str] = None,
    tags: Optional[str] = None,
    is_ai: Optional[bool] = None,
    db: pymysql.connections.Connection = Depends(get_db)
):
    """Search public units and decks."""
    results = {"units": [], "decks": []}
    
    if type != 'deck':
        # Search units
        query = "SELECT u.*, usr.username as creator_name FROM UNIT u LEFT JOIN USER usr ON u.creator_user_id = usr.user_id WHERE u.is_public = TRUE"
        params = []
        if q:
            query += " AND (u.title LIKE %s OR u.description LIKE %s OR u.tags LIKE %s)"
            params.extend([f"%{q}%", f"%{q}%", f"%{q}%"])
        if language_level:
            query += " AND u.language_level = %s"
            params.append(language_level)
        if is_ai is not None:
            query += " AND u.is_ai_generated = %s"
            params.append(is_ai)
        query += " ORDER BY u.vote_count DESC LIMIT 25"
        
        with db.cursor() as cursor:
            cursor.execute(query, params)
            results['units'] = cursor.fetchall()
    
    if type != 'unit':
        # Search decks
        query = "SELECT d.*, usr.username as creator_name FROM DECK d LEFT JOIN USER usr ON d.user_id = usr.user_id WHERE d.is_public = TRUE"
        params = []
        if q:
            query += " AND (d.name LIKE %s OR d.description LIKE %s OR d.tags LIKE %s)"
            params.extend([f"%{q}%", f"%{q}%", f"%{q}%"])
        if language_level:
            query += " AND d.language_level = %s"
            params.append(language_level)
        if is_ai is not None:
            query += " AND d.is_ai_generated = %s"
            params.append(is_ai)
        query += " ORDER BY d.vote_count DESC LIMIT 25"
        
        with db.cursor() as cursor:
            cursor.execute(query, params)
            results['decks'] = cursor.fetchall()
    
    return results

# ── Deck Comments & Votes ──

@router.post("/decks/{deck_id}/comment")
def comment_on_deck(deck_id: int, comment: CommentCreate, current_user: dict = Depends(get_current_user), db: pymysql.connections.Connection = Depends(get_db)):
    """Comment on a deck."""
    with db.cursor() as cursor:
        cursor.execute(
            "INSERT INTO COMMENT (user_id, target_type, target_id, parent_comment_id, content) VALUES (%s, 'deck', %s, %s, %s)",
            (current_user['user_id'], deck_id, comment.parent_comment_id, comment.content)
        )
        comment_id = cursor.lastrowid
        
        # Notify deck owner
        cursor.execute("SELECT user_id FROM DECK WHERE deck_id = %s", (deck_id,))
        deck = cursor.fetchone()
        if deck and deck['user_id'] != current_user['user_id']:
            cursor.execute(
                "INSERT INTO NOTIFICATION (user_id, type, message, target_type, target_id) VALUES (%s, 'comment', %s, 'deck', %s)",
                (deck['user_id'], f"{current_user['username']} hat dein Deck kommentiert", deck_id)
            )
        
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

@router.post("/decks/{deck_id}/vote")
def vote_on_deck(deck_id: int, value: int = 1, current_user: dict = Depends(get_current_user), db: pymysql.connections.Connection = Depends(get_db)):
    """Vote on a deck."""
    with db.cursor() as cursor:
        if value == 0:
            cursor.execute(
                "DELETE FROM VOTE WHERE user_id = %s AND target_type = 'deck' AND target_id = %s",
                (current_user['user_id'], deck_id)
            )
        else:
            cursor.execute(
                """INSERT INTO VOTE (user_id, target_type, target_id, value) VALUES (%s, 'deck', %s, %s)
                   ON DUPLICATE KEY UPDATE value = %s""",
                (current_user['user_id'], deck_id, value, value)
            )
        
        cursor.execute(
            "UPDATE DECK SET vote_count = (SELECT COALESCE(SUM(value), 0) FROM VOTE WHERE target_type = 'deck' AND target_id = %s) WHERE deck_id = %s",
            (deck_id, deck_id)
        )
        db.commit()
    return {"status": "voted"}

# ── Publishing & Cloning ──

class PublishPayload(BaseModel):
    deck: dict
    vocab: list

@router.post("/publish")
def publish_deck(payload: PublishPayload, current_user: dict = Depends(get_current_user), db: pymysql.connections.Connection = Depends(get_db)):
    deck_data = payload.deck
    vocab_list = payload.vocab
    
    with db.cursor() as cursor:
        cursor.execute("SELECT deck_id FROM DECK WHERE user_id = %s AND name = %s", (current_user['user_id'], deck_data['name']))
        existing = cursor.fetchone()
        
        if existing:
            cursor.execute("DELETE FROM VOCAB_TRANSLATION WHERE vocab_id IN (SELECT vocab_id FROM VOCAB WHERE deck_id = %s)", (existing['deck_id'],))
            cursor.execute("DELETE FROM VOCAB WHERE deck_id = %s", (existing['deck_id'],))
            deck_id = existing['deck_id']
            cursor.execute("""
                UPDATE DECK SET description = %s, language_level = %s, tags = %s, is_public = TRUE
                WHERE deck_id = %s
            """, (deck_data.get('description'), deck_data.get('language_level'), deck_data.get('tags'), deck_id))
        else:
            import uuid
            share_code = str(uuid.uuid4())[:8]
            cursor.execute("""
                INSERT INTO DECK (user_id, lang_id, name, type, share_code, is_public, description, language_level, tags)
                VALUES (%s, %s, %s, %s, %s, TRUE, %s, %s, %s)
            """, (current_user['user_id'], 3, deck_data['name'], deck_data.get('deck_type', 'custom'), 
                  share_code, deck_data.get('description'), deck_data.get('language_level'), deck_data.get('tags')))
            deck_id = cursor.lastrowid
            
        for v in vocab_list:
            cursor.execute("""
                INSERT INTO VOCAB (deck_id, learning_lang_id, word_text, reading_text)
                VALUES (%s, %s, %s, %s)
            """, (deck_id, 3, v.get('kanji') or v.get('kana', ''), v.get('kana', '')))
            vocab_id = cursor.lastrowid
            
            for lang_id, t_field in [(1, 'translation_de'), (2, 'translation_en')]:
                if v.get(t_field):
                    cursor.execute("""
                        INSERT INTO VOCAB_TRANSLATION (vocab_id, mother_tongue_lang_id, translated_text)
                        VALUES (%s, %s, %s)
                    """, (vocab_id, lang_id, v[t_field]))
            
            if v.get('translation') and not v.get('translation_de') and not v.get('translation_en'):
                mt_lang_id = current_user.get('mother_tongue_lang_id', 1)
                cursor.execute("""
                    INSERT INTO VOCAB_TRANSLATION (vocab_id, mother_tongue_lang_id, translated_text)
                    VALUES (%s, %s, %s)
                """, (vocab_id, mt_lang_id, v.get('translation')))
            
        db.commit()
    return {"status": "published", "deck_id": deck_id}

class UnpublishPayload(BaseModel):
    name: str

@router.post("/unpublish")
def unpublish_deck(payload: UnpublishPayload, current_user: dict = Depends(get_current_user), db: pymysql.connections.Connection = Depends(get_db)):
    with db.cursor() as cursor:
        cursor.execute("UPDATE DECK SET is_public = FALSE WHERE user_id = %s AND name = %s", (current_user['user_id'], payload.name))
        db.commit()
    return {"status": "unpublished"}

@router.post("/clone/{deck_id}")
def clone_community_deck(deck_id: int, current_user: dict = Depends(get_current_user), db: pymysql.connections.Connection = Depends(get_db)):
    with db.cursor() as cursor:
        cursor.execute("SELECT * FROM DECK WHERE deck_id = %s AND is_public = TRUE", (deck_id,))
        source = cursor.fetchone()
        if not source:
            raise HTTPException(status_code=404, detail="Community deck not found")
            
        import uuid
        new_share = str(uuid.uuid4())[:8]
        cursor.execute(
            """INSERT INTO DECK (user_id, lang_id, name, type, share_code, description, is_public) 
               VALUES (%s, %s, %s, 'custom', %s, %s, FALSE)""",
            (current_user['user_id'], source['lang_id'], f"{source['name']} (Kopie)", new_share, source.get('description', ''))
        )
        new_deck_id = cursor.lastrowid
        
        cursor.execute("SELECT * FROM VOCAB WHERE deck_id = %s", (source['deck_id'],))
        vocab_items = cursor.fetchall()
        for v in vocab_items:
            cursor.execute(
                "INSERT INTO VOCAB (deck_id, learning_lang_id, word_text, reading_text) VALUES (%s, %s, %s, %s)",
                (new_deck_id, v['learning_lang_id'], v['word_text'], v['reading_text'])
            )
            new_vocab_id = cursor.lastrowid
            
            cursor.execute("SELECT * FROM VOCAB_TRANSLATION WHERE vocab_id = %s", (v['vocab_id'],))
            for t in cursor.fetchall():
                cursor.execute(
                    "INSERT INTO VOCAB_TRANSLATION (vocab_id, mother_tongue_lang_id, translated_text) VALUES (%s, %s, %s)",
                    (new_vocab_id, t['mother_tongue_lang_id'], t['translated_text'])
                )
        
        db.commit()
    return {"deck_id": new_deck_id, "share_code": new_share}
