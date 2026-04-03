from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel
from typing import Optional
import pymysql
from database import get_db
from core.security import verify_password, get_password_hash, create_access_token
from api.deps import get_current_user

router = APIRouter()

class UserCreate(BaseModel):
    username: str
    password: str
    email: str
    mother_tongue_lang_id: int = 1  # 1=German, 2=English

class UserSettingsUpdate(BaseModel):
    mother_tongue_lang_id: Optional[int] = None

@router.post("/register", status_code=status.HTTP_201_CREATED)
def register(user: UserCreate, db: pymysql.connections.Connection = Depends(get_db)):
    with db.cursor() as cursor:
        cursor.execute("SELECT user_id FROM USER WHERE username = %s", (user.username,))
        if cursor.fetchone():
            raise HTTPException(status_code=400, detail="Ein Konto mit diesem Benutzernamen existiert bereits.")
        
        cursor.execute("SELECT user_id FROM USER WHERE email = %s", (user.email,))
        if cursor.fetchone():
            raise HTTPException(status_code=400, detail="Diese E-Mail-Adresse ist bereits vergeben.")
        
        hashed_password = get_password_hash(user.password)
        query = "INSERT INTO USER (username, password_hash, email, mother_tongue_lang_id) VALUES (%s, %s, %s, %s)"
        cursor.execute(query, (user.username, hashed_password, user.email, user.mother_tongue_lang_id))
        user_id = cursor.lastrowid
        
        # Create default deck sections for the user
        default_sections = [
            ('Custom', True, 0), ('Manga', True, 1),
            ('Unit', True, 2), ('AI', True, 3)
        ]
        for name, is_system, order in default_sections:
            cursor.execute(
                "INSERT INTO DECK_SECTION (user_id, name, is_system, sort_order) VALUES (%s, %s, %s, %s)",
                (user_id, name, is_system, order)
            )
        
        # Create default AI settings
        cursor.execute("INSERT INTO AI_SETTINGS (user_id) VALUES (%s)", (user_id,))
        
        # Create initial user statistic entry
        cursor.execute(
            "INSERT INTO USER_STATISTIC (user_id, learning_lang_id) VALUES (%s, %s)",
            (user_id, 3)  # Default to Japanese
        )
        
        db.commit()
    return {"message": "User registered successfully", "user_id": user_id}

@router.post("/login")
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: pymysql.connections.Connection = Depends(get_db)):
    with db.cursor() as cursor:
        cursor.execute("SELECT * FROM USER WHERE username = %s", (form_data.username,))
        user_dict = cursor.fetchone()
        if not user_dict or not verify_password(form_data.password, user_dict['password_hash']):
            raise HTTPException(status_code=400, detail="Incorrect username or password")
        
        access_token = create_access_token(subject=user_dict['user_id'])
        
        # Get mother tongue language code
        cursor.execute("SELECT code FROM LANGUAGE WHERE lang_id = %s", (user_dict['mother_tongue_lang_id'],))
        lang = cursor.fetchone()
        
        return {
            "access_token": access_token,
            "token_type": "bearer",
            "user_id": user_dict['user_id'],
            "username": user_dict['username'],
            "email": user_dict['email'],
            "mother_tongue": lang['code'] if lang else 'de',
            "mother_tongue_lang_id": user_dict['mother_tongue_lang_id'],
        }

@router.get("/me")
def get_current_user_info(current_user: dict = Depends(get_current_user), db: pymysql.connections.Connection = Depends(get_db)):
    """Get the currently authenticated user's profile."""
    with db.cursor() as cursor:
        cursor.execute("SELECT code, name FROM LANGUAGE WHERE lang_id = %s", (current_user['mother_tongue_lang_id'],))
        lang = cursor.fetchone()
        
        cursor.execute("SELECT * FROM USER_STATISTIC WHERE user_id = %s", (current_user['user_id'],))
        stats = cursor.fetchall()
        
        cursor.execute("SELECT * FROM AI_SETTINGS WHERE user_id = %s", (current_user['user_id'],))
        ai_settings = cursor.fetchone()
    
    return {
        "user_id": current_user['user_id'],
        "username": current_user['username'],
        "email": current_user['email'],
        "mother_tongue": lang['code'] if lang else 'de',
        "mother_tongue_name": lang['name'] if lang else 'Deutsch',
        "mother_tongue_lang_id": current_user['mother_tongue_lang_id'],
        "created_at": str(current_user.get('created_at', '')),
        "statistics": stats,
        "ai_settings": ai_settings,
    }

@router.put("/settings")
def update_user_settings(settings: UserSettingsUpdate, current_user: dict = Depends(get_current_user), db: pymysql.connections.Connection = Depends(get_db)):
    """Update user settings (mother tongue, etc.)."""
    updates = []
    params = []
    
    if settings.mother_tongue_lang_id is not None:
        updates.append("mother_tongue_lang_id = %s")
        params.append(settings.mother_tongue_lang_id)
    
    if updates:
        params.append(current_user['user_id'])
        with db.cursor() as cursor:
            cursor.execute(f"UPDATE USER SET {', '.join(updates)} WHERE user_id = %s", params)
            db.commit()
    
    return {"status": "updated"}
