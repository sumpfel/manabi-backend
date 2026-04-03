import uuid
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import List, Optional
import pymysql
from database import get_db
from api.deps import get_current_user

router = APIRouter()

class DeckCreate(BaseModel):
    name: str
    type: str
    lang_id: int
    section_id: Optional[int] = None
    is_public: bool = False
    language_level: Optional[str] = None
    tags: Optional[str] = None
    description: Optional[str] = None

class VocabAdd(BaseModel):
    word_text: str
    reading_text: str = ""
    translation: str = ""
    lesson_id: Optional[int] = None

@router.get("/")
def get_decks(current_user: dict = Depends(get_current_user), db: pymysql.connections.Connection = Depends(get_db)):
    with db.cursor() as cursor:
        cursor.execute("SELECT * FROM DECK WHERE user_id = %s ORDER BY created_at DESC", (current_user['user_id'],))
        decks = cursor.fetchall()
        
        # Get vocab counts per deck
        for deck in decks:
            cursor.execute("SELECT COUNT(*) as c FROM VOCAB WHERE deck_id = %s", (deck['deck_id'],))
            deck['vocab_count'] = cursor.fetchone()['c']
    
    return {"decks": decks}

@router.get("/public")
def get_public_decks(
    search: Optional[str] = None,
    language_level: Optional[str] = None,
    is_ai: Optional[bool] = None,
    db: pymysql.connections.Connection = Depends(get_db)
):
    """Browse public decks with filters."""
    query = "SELECT d.*, usr.username as creator_name FROM DECK d LEFT JOIN USER usr ON d.user_id = usr.user_id WHERE d.is_public = TRUE"
    params = []
    if search:
        query += " AND (d.name LIKE %s OR d.description LIKE %s OR d.tags LIKE %s)"
        params.extend([f"%{search}%", f"%{search}%", f"%{search}%"])
    if language_level:
        query += " AND d.language_level = %s"
        params.append(language_level)
    if is_ai is not None:
        query += " AND d.is_ai_generated = %s"
        params.append(is_ai)
    query += " ORDER BY d.vote_count DESC LIMIT 50"
    
    with db.cursor() as cursor:
        cursor.execute(query, params)
        decks = cursor.fetchall()
    return {"decks": decks}

@router.post("/")
def create_deck(deck: DeckCreate, current_user: dict = Depends(get_current_user), db: pymysql.connections.Connection = Depends(get_db)):
    share_code = str(uuid.uuid4())[:8]
    with db.cursor() as cursor:
        cursor.execute(
            """INSERT INTO DECK (user_id, lang_id, name, type, section_id, share_code, 
               is_public, language_level, tags, description) 
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            (current_user['user_id'], deck.lang_id, deck.name, deck.type,
             deck.section_id, share_code, deck.is_public,
             deck.language_level, deck.tags, deck.description)
        )
        db.commit()
        deck_id = cursor.lastrowid
    return {"message": "Deck created", "deck_id": deck_id, "share_code": share_code}

@router.get("/{deck_id}")
def get_deck(deck_id: int, current_user: dict = Depends(get_current_user), db: pymysql.connections.Connection = Depends(get_db)):
    """Get deck details with all vocab."""
    with db.cursor() as cursor:
        cursor.execute("SELECT * FROM DECK WHERE deck_id = %s", (deck_id,))
        deck = cursor.fetchone()
        if not deck:
            raise HTTPException(status_code=404, detail="Deck not found")
        
        # Check access
        if not deck.get('is_public') and deck['user_id'] != current_user['user_id']:
            raise HTTPException(status_code=403, detail="Access denied")
        
        cursor.execute("""
            SELECT v.*, vt.translated_text FROM VOCAB v 
            LEFT JOIN VOCAB_TRANSLATION vt ON v.vocab_id = vt.vocab_id
            WHERE v.deck_id = %s ORDER BY v.vocab_id ASC
        """, (deck_id,))
        deck['vocab'] = cursor.fetchall()
        
        # Get comments
        cursor.execute("""
            SELECT c.*, usr.username FROM COMMENT c 
            LEFT JOIN USER usr ON c.user_id = usr.user_id
            WHERE c.target_type = 'deck' AND c.target_id = %s
            ORDER BY c.created_at ASC
        """, (deck_id,))
        deck['comments'] = cursor.fetchall()
    
    return deck

@router.post("/{deck_id}/vocab")
def add_vocab(deck_id: int, vocab: VocabAdd, current_user: dict = Depends(get_current_user), db: pymysql.connections.Connection = Depends(get_db)):
    """Add a vocab entry to a deck."""
    with db.cursor() as cursor:
        # Verify ownership
        cursor.execute("SELECT user_id, lang_id FROM DECK WHERE deck_id = %s", (deck_id,))
        deck = cursor.fetchone()
        if not deck or deck['user_id'] != current_user['user_id']:
            raise HTTPException(status_code=403, detail="Not your deck")
        
        cursor.execute(
            "INSERT INTO VOCAB (deck_id, learning_lang_id, word_text, reading_text, lesson_id) VALUES (%s, %s, %s, %s, %s)",
            (deck_id, deck['lang_id'], vocab.word_text, vocab.reading_text, vocab.lesson_id)
        )
        vocab_id = cursor.lastrowid
        
        if vocab.translation:
            mt_lang_id = current_user.get('mother_tongue_lang_id', 1)
            cursor.execute(
                "INSERT INTO VOCAB_TRANSLATION (vocab_id, mother_tongue_lang_id, translated_text) VALUES (%s, %s, %s)",
                (vocab_id, mt_lang_id, vocab.translation)
            )
        
        db.commit()
    return {"vocab_id": vocab_id}

@router.post("/{deck_id}/share")
def share_deck(deck_id: int, current_user: dict = Depends(get_current_user), db: pymysql.connections.Connection = Depends(get_db)):
    """Generate or return share code for a deck."""
    with db.cursor() as cursor:
        cursor.execute("SELECT share_code, user_id FROM DECK WHERE deck_id = %s", (deck_id,))
        deck = cursor.fetchone()
        if not deck or deck['user_id'] != current_user['user_id']:
            raise HTTPException(status_code=403, detail="Not your deck")
        
        share_code = deck['share_code']
        if not share_code:
            share_code = str(uuid.uuid4())[:8]
            cursor.execute("UPDATE DECK SET share_code = %s WHERE deck_id = %s", (share_code, deck_id))
            db.commit()
    
    return {"share_code": share_code}

@router.get("/shared/{share_code}")
def import_shared_deck(share_code: str, current_user: dict = Depends(get_current_user), db: pymysql.connections.Connection = Depends(get_db)):
    """View a shared deck by share code."""
    with db.cursor() as cursor:
        cursor.execute("""
            SELECT d.*, usr.username as creator_name FROM DECK d 
            LEFT JOIN USER usr ON d.user_id = usr.user_id
            WHERE d.share_code = %s
        """, (share_code,))
        deck = cursor.fetchone()
        if not deck:
            raise HTTPException(status_code=404, detail="Shared deck not found")
        
        cursor.execute("""
            SELECT v.*, vt.translated_text FROM VOCAB v 
            LEFT JOIN VOCAB_TRANSLATION vt ON v.vocab_id = vt.vocab_id
            WHERE v.deck_id = %s
        """, (deck['deck_id'],))
        deck['vocab'] = cursor.fetchall()
    
    return deck

@router.post("/shared/{share_code}/clone")
def clone_shared_deck(share_code: str, current_user: dict = Depends(get_current_user), db: pymysql.connections.Connection = Depends(get_db)):
    """Clone a shared deck into the user's own collection."""
    with db.cursor() as cursor:
        cursor.execute("SELECT * FROM DECK WHERE share_code = %s", (share_code,))
        source = cursor.fetchone()
        if not source:
            raise HTTPException(status_code=404, detail="Deck not found")
        
        new_share = str(uuid.uuid4())[:8]
        cursor.execute(
            """INSERT INTO DECK (user_id, lang_id, name, type, share_code, description) 
               VALUES (%s, %s, %s, 'custom', %s, %s)""",
            (current_user['user_id'], source['lang_id'], f"{source['name']} (Kopie)", new_share, source.get('description', ''))
        )
        new_deck_id = cursor.lastrowid
        
        # Clone all vocab
        cursor.execute("SELECT * FROM VOCAB WHERE deck_id = %s", (source['deck_id'],))
        vocab_items = cursor.fetchall()
        for v in vocab_items:
            cursor.execute(
                "INSERT INTO VOCAB (deck_id, learning_lang_id, word_text, reading_text) VALUES (%s, %s, %s, %s)",
                (new_deck_id, v['learning_lang_id'], v['word_text'], v['reading_text'])
            )
            new_vocab_id = cursor.lastrowid
            
            # Clone translations
            cursor.execute("SELECT * FROM VOCAB_TRANSLATION WHERE vocab_id = %s", (v['vocab_id'],))
            for t in cursor.fetchall():
                cursor.execute(
                    "INSERT INTO VOCAB_TRANSLATION (vocab_id, mother_tongue_lang_id, translated_text) VALUES (%s, %s, %s)",
                    (new_vocab_id, t['mother_tongue_lang_id'], t['translated_text'])
                )
        
        db.commit()
    return {"deck_id": new_deck_id, "share_code": new_share}

@router.put("/{deck_id}/public")
def toggle_public(deck_id: int, is_public: bool = True, current_user: dict = Depends(get_current_user), db: pymysql.connections.Connection = Depends(get_db)):
    """Make a deck public or private."""
    with db.cursor() as cursor:
        cursor.execute("SELECT user_id FROM DECK WHERE deck_id = %s", (deck_id,))
        deck = cursor.fetchone()
        if not deck or deck['user_id'] != current_user['user_id']:
            raise HTTPException(status_code=403, detail="Not your deck")
        
        cursor.execute("UPDATE DECK SET is_public = %s WHERE deck_id = %s", (is_public, deck_id))
        db.commit()
    return {"status": "updated"}
