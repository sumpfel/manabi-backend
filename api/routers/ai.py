import httpx
import json
import uuid
import subprocess
from datetime import datetime as DateTime
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional, List
import traceback
from api.deps import get_current_user
from database import get_db

router = APIRouter()

OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_CHAT_URL = "http://localhost:11434/api/chat"

# ── Request Models ──

class AIRequest(BaseModel):
    prompt: str
    model: str = "llama3.2:3b"
    cefr_level: str = "A1"
    restrict_to_known_vocab: bool = False
    max_new_words: int = 2
    conversation_id: Optional[int] = None
    learning_lang: str = "ja"
    mother_tongue: str = "de"
    show_romaji: bool = True
    show_hiragana: bool = True
    color_german: bool = True

class MessageEditRequest(BaseModel):
    message_id: int
    new_content: str

class QueryRequest(BaseModel):
    prompt: str
    model: str = "llama3.2:3b"
    system_prompt: Optional[str] = None
    history: Optional[List[dict]] = None

class GenerateUnitRequest(BaseModel):
    prompt: str
    model: str = "llama3.2:3b"
    learning_lang: str = "ja"
    mother_tongue: str = "de"
    cefr_level: str = "A1"
    is_public: bool = False
    language_level: Optional[str] = None
    tags: Optional[str] = None

class GenerateDeckRequest(BaseModel):
    prompt: str
    model: str = "llama3.2:3b"
    learning_lang: str = "ja"
    mother_tongue: str = "de"
    cefr_level: str = "A1"
    deck_name: Optional[str] = None
    section: str = "ai"
    is_public: bool = False
    language_level: Optional[str] = None
    tags: Optional[str] = None

class MakeUnitFromChatRequest(BaseModel):
    conversation_id: int
    title: Optional[str] = None
    additional_prompt: Optional[str] = None  # Phase 2 requirement
    is_public: bool = False

class MakeDeckFromChatRequest(BaseModel):
    conversation_id: int
    title: Optional[str] = None
    is_public: bool = False

# ── Ollama Models ──

@router.get("/models")
async def list_models():
    """List available Ollama models with quality labels."""
    try:
        async with httpx.AsyncClient(timeout=10.0, trust_env=False) as client:
            response = await client.get("http://localhost:11434/api/tags")
            if response.status_code == 200:
                models = response.json().get("models", [])
                # Predefined quality labels
                labels = {
                    'llama3.2:3b': 'fast',
                    'llama3.2:1b': 'fast',
                    'phi4:14b': 'slow',
                    'phi3:14b': 'slow',
                    'mistral:7b': 'balanced',
                    'gemma2:9b': 'balanced',
                    'qwen2.5:7b': 'balanced',
                }
                result = []
                for m in models:
                    name = m.get('name', '')
                    size_gb = round(m.get('size', 0) / 1e9, 1)
                    label = labels.get(name, 'balanced' if size_gb < 10 else 'slow')
                    result.append({
                        'name': name,
                        'size_gb': size_gb,
                        'quality': label,
                    })
                return result
            return []
    except Exception:
        return []

# ── Helper: Language names ──

LANG_NAMES = {
    'de': 'German', 'en': 'English', 'ja': 'Japanese',
    'es': 'Spanish', 'fr': 'French', 'ko': 'Korean', 'zh': 'Chinese'
}

LANG_IDS = {
    'de': 1, 'en': 2, 'ja': 3, 'es': 4, 'fr': 5, 'ko': 6, 'zh': 7
}

MOTHER_TONGUE_PROMPTS = {
    'de': 'Antworte auf Deutsch. Der Benutzer spricht Deutsch als Muttersprache.',
    'en': 'Respond in English. The user speaks English as their mother tongue.',
}

# ── Helper: Get user's AI settings ──

def _get_ai_settings(user_id: int, db):
    with db.cursor() as cursor:
        cursor.execute("SELECT * FROM AI_SETTINGS WHERE user_id = %s", (user_id,))
        settings = cursor.fetchone()
        if not settings:
            cursor.execute(
                "INSERT INTO AI_SETTINGS (user_id) VALUES (%s)", (user_id,))
            db.commit()
            cursor.execute("SELECT * FROM AI_SETTINGS WHERE user_id = %s", (user_id,))
            settings = cursor.fetchone()
    return settings

# ── Helper: Build colored grammar instruction ──

def _build_color_instruction(ai_settings: dict, color_german: bool = True) -> str:
    colors = {
        'particles': ai_settings.get('color_particles', '#4FC3F7'),
        'verbs': ai_settings.get('color_verbs', '#FF8A65'),
        'nouns': ai_settings.get('color_nouns', '#81C784'),
        'adjectives': ai_settings.get('color_adjectives', '#CE93D8'),
        'adverbs': ai_settings.get('color_adverbs', '#FFD54F'),
    }
    
    german_coloring = ""
    if color_german:
        german_coloring = f"""\nAlso color the GERMAN translation to show word correspondence:
Japanese: <color={colors['nouns']}>学校</color><color={colors['particles']}>に</color><color={colors['verbs']}>行きます</color>。
German:   <color={colors['particles']}>Zur</color> <color={colors['nouns']}>Schule</color> <color={colors['verbs']}>gehen</color>."""
    
    return f"""COLOR FORMATTING RULES (CRITICAL - follow exactly):
When writing Japanese sentences, wrap EVERY word/morpheme in color tags based on its grammar role:
- Particles (は、を、に、で、へ、の、と、が、も、から、まで): <color={colors['particles']}>particle</color>
- Verbs (食べます、行く、する): <color={colors['verbs']}>verb</color>
- Nouns (学校、猫、本): <color={colors['nouns']}>noun</color>
- Adjectives (大きい、きれいな): <color={colors['adjectives']}>adjective</color>  
- Adverbs (とても、ゆっくり): <color={colors['adverbs']}>adverb</color>
{german_coloring}

EXAMPLE of correct formatting:
<color={colors['nouns']}>猫</color><color={colors['particles']}>が</color><color={colors['nouns']}>魚</color><color={colors['particles']}>を</color><color={colors['verbs']}>食べます</color>。
Romaji: Neko ga sakana o tabemasu.
Deutsch: Die <color={colors['nouns']}>Katze</color> <color={colors['verbs']}>frisst</color> den <color={colors['nouns']}>Fisch</color>.

NEVER use random colors. ALWAYS close every <color=...> tag with </color>. NEVER leave unclosed tags."""


# ── Helper: Get conversation history ──

def _get_conversation_history(conversation_id: int, db, limit: int = 20) -> list:
    with db.cursor() as cursor:
        cursor.execute(
            "SELECT role, content FROM MESSAGE WHERE conversation_id = %s ORDER BY created_at DESC LIMIT %s",
            (conversation_id, limit)
        )
        messages = cursor.fetchall()
    return list(reversed(messages))


# ── Helper: Save message ──

def _save_message(conversation_id: int, user_id: int, role: str, content: str, db):
    with db.cursor() as cursor:
        cursor.execute(
            "INSERT INTO MESSAGE (conversation_id, user_id, role, content) VALUES (%s, %s, %s, %s)",
            (conversation_id, user_id, role, content)
        )
        msg_id = cursor.lastrowid
        # Update conversation timestamp
        cursor.execute(
            "UPDATE CHAT_CONVERSATION SET updated_at = NOW() WHERE conversation_id = %s",
            (conversation_id,)
        )
        db.commit()
    return msg_id


# ── Endpoints ──

@router.post("/query")
async def simple_query(request: QueryRequest):
    """Simple proxy to Ollama for straightforward translations/prompts not needing DB conversations."""
    messages = []
    if request.system_prompt:
        messages.append({"role": "system", "content": request.system_prompt})
    if request.history:
        for msg in request.history:
            messages.append({"role": msg.get("role", "user"), "content": msg.get("content", "")})
    messages.append({"role": "user", "content": request.prompt})

    try:
        async with httpx.AsyncClient(timeout=300.0, trust_env=False) as client:
            response = await client.post(OLLAMA_CHAT_URL, json={
                "model": request.model,
                "messages": messages,
                "stream": False
            })
            if response.status_code == 200:
                result = response.json()
                return {"response": result.get("message", {}).get("content", "")}
            raise HTTPException(status_code=response.status_code, detail="Ollama Error")
    except httpx.ConnectError:
        # Boot Ollama globally if it returns a strict network refusal
        subprocess.Popen(['ollama', 'serve'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        raise HTTPException(status_code=500, detail="Generation failed: All connections attempts failed. The Ollama daemon was offline, but a boot sequence was just initialized! Please try again in 5 seconds.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Generation failed: {str(e)}")

@router.get("/conversations")
async def list_conversations(current_user: dict = Depends(get_current_user), db=Depends(get_db)):
    """List all chat conversations for the current user."""
    with db.cursor() as cursor:
        cursor.execute(
            "SELECT * FROM CHAT_CONVERSATION WHERE user_id = %s ORDER BY updated_at DESC",
            (current_user['user_id'],)
        )
        convos = cursor.fetchall()
    return {"conversations": convos}


@router.post("/conversations")
async def create_conversation(current_user: dict = Depends(get_current_user), db=Depends(get_db)):
    """Create a new chat conversation."""
    with db.cursor() as cursor:
        cursor.execute(
            "INSERT INTO CHAT_CONVERSATION (user_id, title) VALUES (%s, %s)",
            (current_user['user_id'], f"Chat {DateTime.now().strftime('%d.%m.%Y %H:%M')}")
        )
        db.commit()
        conv_id = cursor.lastrowid
    return {"conversation_id": conv_id}


@router.get("/conversations/{conversation_id}/messages")
async def get_messages(conversation_id: int, current_user: dict = Depends(get_current_user), db=Depends(get_db)):
    """Get all messages in a conversation."""
    with db.cursor() as cursor:
        cursor.execute(
            "SELECT * FROM MESSAGE WHERE conversation_id = %s AND user_id = %s ORDER BY created_at ASC",
            (conversation_id, current_user['user_id'])
        )
        messages = cursor.fetchall()
    return {"messages": messages}


@router.delete("/conversations/{conversation_id}")
async def delete_conversation(conversation_id: int, current_user: dict = Depends(get_current_user), db=Depends(get_db)):
    """Delete a conversation and all its messages."""
    with db.cursor() as cursor:
        cursor.execute("DELETE FROM MESSAGE WHERE conversation_id = %s AND user_id = %s",
                       (conversation_id, current_user['user_id']))
        cursor.execute("DELETE FROM CHAT_CONVERSATION WHERE conversation_id = %s AND user_id = %s",
                       (conversation_id, current_user['user_id']))
        db.commit()
    return {"status": "deleted"}


@router.post("/chat")
async def ai_chat(request: AIRequest, current_user: dict = Depends(get_current_user), db=Depends(get_db)):
    """Main AI Sensei chat endpoint with conversation history and grammar coloring."""
    user_id = current_user['user_id']
    
    conversation_id = request.conversation_id
    try:
        # Get or create conversation
        if not conversation_id:
            with db.cursor() as cursor:
                cursor.execute(
                    "INSERT INTO CHAT_CONVERSATION (user_id, title, learning_lang_id, cefr_level) VALUES (%s, %s, %s, %s)",
                    (user_id, f"Chat {DateTime.now().strftime('%d.%m.%Y %H:%M')}",
                     LANG_IDS.get(request.learning_lang, 3), request.cefr_level)
                )
                db.commit()
                conversation_id = cursor.lastrowid

        # Get AI settings for coloring
        ai_settings = _get_ai_settings(user_id, db)
        color_german = getattr(request, 'color_german', True)
        color_instruction = _build_color_instruction(ai_settings, color_german=color_german)

        # Get conversation history for context
        history = _get_conversation_history(conversation_id, db)
        
        # Build vocab restriction context
        vocab_context = ""
        if request.restrict_to_known_vocab:
            with db.cursor() as cursor:
                cursor.execute("""
                    SELECT v.word_text FROM VOCAB v
                    JOIN DECK d ON v.deck_id = d.deck_id
                    WHERE d.user_id = %s
                """, (user_id,))
                known_words = [row['word_text'] for row in cursor.fetchall()]
                if known_words:
                    vocab_context = f" The user knows these words: {', '.join(known_words[:100])}. Use primarily these. Introduce at most {request.max_new_words} new words per response and explain them."
                else:
                    vocab_context = f" The user is a total beginner. Introduce at most {request.max_new_words} new words and explain them."

        # Romaji/Hiragana instructions
        display_instructions = ""
        show_romaji = getattr(request, 'show_romaji', True)
        show_furigana = getattr(request, 'show_hiragana', True)
        if show_romaji:
            display_instructions += "\nALWAYS show Romaji (latin alphabet reading) on a separate line below every Japanese sentence. Format: 'Romaji: ...'."
        if show_furigana:
            display_instructions += "\nALWAYS show Furigana (small hiragana readings) above or after Kanji. Format: 漢字（かんじ）."

        mt_label = 'Deutsch' if request.mother_tongue == 'de' else 'English'
        mt_instruction = MOTHER_TONGUE_PROMPTS.get(request.mother_tongue, MOTHER_TONGUE_PROMPTS['en'])
        
        system_prompt = f"""Du bist ein freundlicher Japanisch-Sensei. {mt_instruction}
Antworte EXTREM KURZ und PRÄGNANT. Keine langen Erklärungen.

Aktuelles Sprachniveau: {request.cefr_level}.{vocab_context}

FORMATIERUNGS-REGELN (STRENGSTENS EINHALTEN):
1. KEIN MARKDOWN verwenden (KEINE Sternchen **, KEINE Gitter #).
2. Nutze AUSSCHLIESSLICH die <color> Tags für Grammatik.
3. Jeder japanische Satz MUSS so aussehen:
   <color=#HEX>Wort</color><color=#HEX>Partikel</color>...
   Romaji: [Lesung]
   Deutsch: [Übersetzung]

4. Schließe JEDEN <color=...> Tag mit </color>.

{display_instructions}

{color_instruction}

Vokabeln am Ende NUR wenn neu:
VOCAB_START
wort|lesung|übersetzung
VOCAB_END"""

        # Build messages for Ollama chat API
        ollama_messages = [{"role": "system", "content": system_prompt}]
        for msg in history:
            ollama_messages.append({"role": msg['role'], "content": msg['content']})
        ollama_messages.append({"role": "user", "content": request.prompt})

        # Save user message
        _save_message(conversation_id, user_id, "user", request.prompt, db)

        async with httpx.AsyncClient(timeout=300.0, trust_env=False) as client:
            response = await client.post(OLLAMA_CHAT_URL, json={
                "model": request.model,
                "messages": ollama_messages,
                "stream": False
            })
            
            if response.status_code == 200:
                result = response.json()
                content = result.get("message", {}).get("content", "")
                
                # Parse and extract new vocab
                new_vocab = []
                clean_content = content
                if "VOCAB_START" in content and "VOCAB_END" in content:
                    try:
                        vocab_block = content.split("VOCAB_START")[1].split("VOCAB_END")[0].strip()
                        clean_content = content.split("VOCAB_START")[0].strip()
                        for line in vocab_block.split("\n"):
                            parts = line.strip().split("|")
                            if len(parts) >= 3:
                                new_vocab.append({
                                    "word": parts[0].strip(),
                                    "reading": parts[1].strip(),
                                    "translation": parts[2].strip()
                                })
                    except:
                        pass
                
                # Add vocab to AI deck
                if new_vocab:
                    _add_to_ai_deck(user_id, conversation_id, new_vocab, request, ai_settings, db)
                
                # Save assistant message
                msg_id = _save_message(conversation_id, user_id, "assistant", clean_content, db)
                
                # Update conversation title from first message
                if len(history) == 0:
                    title = request.prompt[:50] + ("..." if len(request.prompt) > 50 else "")
                    with db.cursor() as cursor:
                        cursor.execute("UPDATE CHAT_CONVERSATION SET title = %s WHERE conversation_id = %s",
                                       (title, conversation_id))
                        db.commit()
                
                return {
                    "response": clean_content,
                    "conversation_id": conversation_id,
                    "message_id": msg_id,
                    "new_vocab": new_vocab
                }
            raise HTTPException(status_code=response.status_code, detail="Ollama Error")
    except httpx.ConnectError:
        raise HTTPException(status_code=503, detail="Ollama is not running. Please start it with 'ollama serve'")
    except httpx.ReadTimeout:
        raise HTTPException(status_code=504, detail="Ollama generation timed out. The model is likely too large for your current CPU/GPU setup.")
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=f"Ollama connection error: {str(e)}")


@router.post("/chat/regenerate")
async def regenerate_response(request: AIRequest, current_user: dict = Depends(get_current_user), db=Depends(get_db)):
    """Regenerate the last AI response in a conversation."""
    if not request.conversation_id:
        raise HTTPException(status_code=400, detail="conversation_id is required")
    
    with db.cursor() as cursor:
        # Delete the last assistant message
        cursor.execute(
            "DELETE FROM MESSAGE WHERE conversation_id = %s AND role = 'assistant' ORDER BY created_at DESC LIMIT 1",
            (request.conversation_id,)
        )
        # Get the last user message
        cursor.execute(
            "SELECT content FROM MESSAGE WHERE conversation_id = %s AND role = 'user' ORDER BY created_at DESC LIMIT 1",
            (request.conversation_id,)
        )
        last_msg = cursor.fetchone()
        db.commit()
    
    if not last_msg:
        raise HTTPException(status_code=404, detail="No user message found to regenerate from")
    
    request.prompt = last_msg['content']
    return await ai_chat(request, current_user, db)


@router.put("/chat/edit")
async def edit_message(edit_req: MessageEditRequest, current_user: dict = Depends(get_current_user), db=Depends(get_db)):
    """Edit a user message and delete all subsequent messages."""
    with db.cursor() as cursor:
        # Verify ownership
        cursor.execute(
            "SELECT conversation_id, created_at FROM MESSAGE WHERE message_id = %s AND user_id = %s AND role = 'user'",
            (edit_req.message_id, current_user['user_id'])
        )
        msg = cursor.fetchone()
        if not msg:
            raise HTTPException(status_code=404, detail="Message not found")
        
        # Update message content
        cursor.execute(
            "UPDATE MESSAGE SET content = %s, is_edited = TRUE, version = version + 1 WHERE message_id = %s",
            (edit_req.new_content, edit_req.message_id)
        )
        
        # Delete all messages after this one in the conversation
        cursor.execute(
            "DELETE FROM MESSAGE WHERE conversation_id = %s AND created_at > %s",
            (msg['conversation_id'], msg['created_at'])
        )
        db.commit()
    
    return {"status": "edited", "conversation_id": msg['conversation_id']}


@router.get("/settings")
async def get_ai_settings(current_user: dict = Depends(get_current_user), db=Depends(get_db)):
    """Get AI coloring and routing settings."""
    settings = _get_ai_settings(current_user['user_id'], db)
    return settings


@router.put("/settings")
async def update_ai_settings(
    color_particles: Optional[str] = None,
    color_verbs: Optional[str] = None,
    color_nouns: Optional[str] = None,
    color_adjectives: Optional[str] = None,
    color_adverbs: Optional[str] = None,
    deck_routing: Optional[str] = None,
    deck_routing_count: Optional[int] = None,
    target_deck_id: Optional[int] = None,
    target_section: Optional[str] = None,
    current_user: dict = Depends(get_current_user),
    db=Depends(get_db)
):
    """Update AI settings."""
    _get_ai_settings(current_user['user_id'], db)  # ensure exists
    
    updates = []
    params = []
    for field, val in [
        ('color_particles', color_particles), ('color_verbs', color_verbs),
        ('color_nouns', color_nouns), ('color_adjectives', color_adjectives),
        ('color_adverbs', color_adverbs), ('deck_routing', deck_routing),
        ('deck_routing_count', deck_routing_count), ('target_deck_id', target_deck_id),
        ('target_section', target_section)
    ]:
        if val is not None:
            updates.append(f"{field} = %s")
            params.append(val)
    
    if updates:
        params.append(current_user['user_id'])
        with db.cursor() as cursor:
            cursor.execute(f"UPDATE AI_SETTINGS SET {', '.join(updates)} WHERE user_id = %s", params)
            db.commit()
    
    return _get_ai_settings(current_user['user_id'], db)


def _add_to_ai_deck(user_id: int, conversation_id: int, words: list, request: AIRequest, ai_settings: dict, db):
    """Add extracted vocab to the appropriate AI deck based on user settings."""
    routing = ai_settings.get('deck_routing', 'per_chat')
    lang_id = LANG_IDS.get(request.learning_lang, 3)
    mt_lang_id = LANG_IDS.get(request.mother_tongue, 1)
    
    with db.cursor() as cursor:
        if routing == 'per_chat':
            deck_name = f"AI Chat {conversation_id}"
            cursor.execute("SELECT deck_id FROM DECK WHERE user_id = %s AND name = %s AND type = 'ai_chat'",
                           (user_id, deck_name))
            deck = cursor.fetchone()
            if not deck:
                cursor.execute(
                    "INSERT INTO DECK (user_id, lang_id, name, type, is_ai_generated) VALUES (%s, %s, %s, %s, TRUE)",
                    (user_id, lang_id, deck_name, 'ai_chat'))
                deck_id = cursor.lastrowid
            else:
                deck_id = deck['deck_id']
                
        elif routing == 'target_deck':
            target_id = ai_settings.get('target_deck_id')
            if target_id:
                deck_id = target_id
            else:
                # Fallback to per_chat
                deck_name = f"AI Chat {conversation_id}"
                cursor.execute("SELECT deck_id FROM DECK WHERE user_id = %s AND name = %s AND type = 'ai_chat'",
                               (user_id, deck_name))
                deck = cursor.fetchone()
                if not deck:
                    cursor.execute(
                        "INSERT INTO DECK (user_id, lang_id, name, type, is_ai_generated) VALUES (%s, %s, %s, %s, TRUE)",
                        (user_id, lang_id, deck_name, 'ai_chat'))
                    deck_id = cursor.lastrowid
                else:
                    deck_id = deck['deck_id']
        else:
            # Default: per_chat
            deck_name = f"AI Chat {conversation_id}"
            cursor.execute("SELECT deck_id FROM DECK WHERE user_id = %s AND name = %s AND type = 'ai_chat'",
                           (user_id, deck_name))
            deck = cursor.fetchone()
            if not deck:
                cursor.execute(
                    "INSERT INTO DECK (user_id, lang_id, name, type, is_ai_generated) VALUES (%s, %s, %s, %s, TRUE)",
                    (user_id, lang_id, deck_name, 'ai_chat'))
                deck_id = cursor.lastrowid
            else:
                deck_id = deck['deck_id']

        # Add words (skip duplicates)
        for item in words:
            cursor.execute(
                "SELECT vocab_id FROM VOCAB WHERE deck_id = %s AND word_text = %s",
                (deck_id, item['word']))
            if not cursor.fetchone():
                cursor.execute(
                    "INSERT INTO VOCAB (deck_id, learning_lang_id, word_text, reading_text) VALUES (%s, %s, %s, %s)",
                    (deck_id, lang_id, item['word'], item.get('reading', '')))
                vocab_id = cursor.lastrowid
                cursor.execute(
                    "INSERT INTO VOCAB_TRANSLATION (vocab_id, mother_tongue_lang_id, translated_text) VALUES (%s, %s, %s)",
                    (vocab_id, mt_lang_id, item.get('translation', '')))
        db.commit()


@router.post("/generate_vocab")
async def generate_vocab(request: AIRequest, current_user: dict = Depends(get_current_user)):
    """Generate vocabulary based on a theme/prompt."""
    lang_name = LANG_NAMES.get(request.learning_lang, 'Japanese')
    mt_name = LANG_NAMES.get(request.mother_tongue, 'German')
    
    prompt = f"""Generate a vocabulary list for learning {lang_name}. Theme: {request.prompt}
Level: {request.cefr_level}
Output as JSON array: [{{"word": "...", "reading": "...", "translation_to_{request.mother_tongue}": "...", "example_sentence": "...", "example_translation": "..."}}]
The translations must be in {mt_name}. Generate 10-15 words. No other text, just the JSON."""

    try:
        async with httpx.AsyncClient(timeout=300.0, trust_env=False) as client:
            response = await client.post(OLLAMA_URL, json={
                "model": request.model,
                "prompt": prompt,
                "stream": False
            })
            if response.status_code == 200:
                return response.json()
            raise HTTPException(status_code=response.status_code, detail="Ollama Error")
    except httpx.ConnectError:
        raise HTTPException(status_code=503, detail="Ollama is not running")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ollama error: {str(e)}")


@router.post("/generate_unit")
async def generate_unit(request: GenerateUnitRequest, current_user: dict = Depends(get_current_user), db=Depends(get_db)):
    """AI generates a full unit with lessons, exercises and vocabulary deck."""
    import re
    user_id = current_user['user_id']
    lang_name = LANG_NAMES.get(request.learning_lang, 'Japanese')
    mt_name = LANG_NAMES.get(request.mother_tongue, 'German')
    lang_id = LANG_IDS.get(request.learning_lang, 3)
    mt_lang_id = LANG_IDS.get(request.mother_tongue, 1)
    
    prompt = f"""Create a language learning unit for {lang_name} learners (level: {request.cefr_level}).
Theme: {request.prompt}
The unit explanation and translations must be in {mt_name}.

Output ONLY valid JSON in this exact format:
{{
  "title": "Unit title in {mt_name}",
  "description": "Short description in {mt_name}",
  "lessons": [
    {{
      "title": "Lesson title in {mt_name}",
      "grammar_markdown": "Grammar explanation in markdown. Use colors: <color=#4FC3F7>particles</color>, <color=#FF8A65>verbs</color>, <color=#81C784>nouns</color>.",
      "vocab": [
        {{"word": "...", "reading": "...", "translation": "translation in {mt_name}"}}
      ],
      "exercises": [
        {{
          "type": "multiple_choice",
          "question": "question text in {lang_name} or {mt_name}",
          "instruction": "instruction like 'Translate to {mt_name}'",
          "correctOption": "correct answer",
          "options": ["correct answer", "wrong 1", "wrong 2", "wrong 3"]
        }},
        {{
          "type": "typing",
          "question": "question text",
          "instruction": "instruction",
          "answer": "exact correct answer"
        }}
      ]
    }}
  ]
}}

Generate 2-3 lessons. Each lesson must have 5-10 vocab words and 3-5 exercises. No other text, just the JSON."""

    try:
        async with httpx.AsyncClient(timeout=300.0, trust_env=False) as client:
            response = await client.post(OLLAMA_URL, json={
                "model": request.model or "llama3.2:3b",
                "prompt": prompt,
                "stream": False,
                "format": "json"
            })
            
            if response.status_code != 200:
                raise HTTPException(status_code=response.status_code, detail="Ollama Error")
            
            ai_response = response.json().get("response", "")
            
            try:
                # Robust extraction
                match = re.search(r'\{.*\}', ai_response, re.DOTALL)
                if match:
                    unit_data = json.loads(match.group(0))
                else:
                    raise ValueError("No JSON found")
            except Exception as e:
                return {"error": f"AI response was not valid JSON: {str(e)}", "raw_response": ai_response}
            
            with db.cursor() as cursor:
                share_code = str(uuid.uuid4())[:8]
                cursor.execute(
                    """INSERT INTO UNIT (lang_id, creator_user_id, title, description, is_basic_global, 
                       share_code, is_public, is_ai_generated, language_level, tags)
                       VALUES (%s, %s, %s, %s, FALSE, %s, %s, TRUE, %s, %s)""",
                    (lang_id, user_id, unit_data.get('title', 'AI Unit'),
                     unit_data.get('description', ''), share_code,
                     request.is_public, request.language_level, request.tags)
                )
                unit_id = cursor.lastrowid
                
                cursor.execute(
                    "INSERT INTO DECK (user_id, lang_id, name, type, parent_unit_id, is_ai_generated) VALUES (%s, %s, %s, 'unit', %s, TRUE)",
                    (user_id, lang_id, f"{unit_data.get('title', 'AI Unit')} - Vocab", unit_id)
                )
                deck_id = cursor.lastrowid
                
                for i, lesson_data in enumerate(unit_data.get('lessons', [])):
                    cursor.execute(
                        """INSERT INTO LESSON (unit_id, lesson_order, title, grammar_markdown, recommended_deck_id, exercises_json) 
                           VALUES (%s, %s, %s, %s, %s, %s)""",
                        (unit_id, i + 1, lesson_data.get('title', f'Lesson {i+1}'),
                         lesson_data.get('grammar_markdown', ''), deck_id, json.dumps(lesson_data.get('exercises', [])))
                    )
                    lesson_id = cursor.lastrowid
                    
                    for v in lesson_data.get('vocab', []):
                        cursor.execute(
                            "INSERT INTO VOCAB (deck_id, learning_lang_id, lesson_id, word_text, reading_text) VALUES (%s, %s, %s, %s, %s)",
                            (deck_id, lang_id, lesson_id, v.get('word', ''), v.get('reading', ''))
                        )
                        v_id = cursor.lastrowid
                        cursor.execute(
                            "INSERT INTO VOCAB_TRANSLATION (vocab_id, mother_tongue_lang_id, translated_text) VALUES (%s, 1, %s)",
                            (v_id, v.get('translation', ''))
                        )
                db.commit()
            
            return {"unit_id": unit_id, "deck_id": deck_id, "share_code": share_code}
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Generation failed: {str(e)}")


@router.post("/generate_deck")
async def generate_deck(request: GenerateDeckRequest, current_user: dict = Depends(get_current_user), db=Depends(get_db)):
    """AI generates a vocabulary deck based on a theme."""
    import re
    user_id = current_user['user_id']
    lang_name = LANG_NAMES.get(request.learning_lang, 'Japanese')
    mt_name = LANG_NAMES.get(request.mother_tongue, 'German')
    lang_id = LANG_IDS.get(request.learning_lang, 3)
    mt_lang_id = LANG_IDS.get(request.mother_tongue, 1)
    
    system_prompt = f"Generate a vocabulary deck for {lang_name} learners (level: {request.cefr_level})."
    
    prompt = system_prompt + f"\nTheme: {request.prompt}\nOutput ONLY a JSON array: [{{'word': '...', 'reading': '...', 'translation': 'in {mt_name}', 'example': 'sentence', 'example_translation': 'in {mt_name}'}}]\nGenerate 20 words. No other text."

    try:
        async with httpx.AsyncClient(timeout=300.0, trust_env=False) as client:
            response = await client.post(OLLAMA_URL, json={
                "model": request.model or "llama3.2:3b",
                "prompt": system_prompt + f"\n\nThema: {request.prompt}",
                "stream": False,
                "format": "json"
            })
            
            ai_text = response.json().get("response", "")
            match = re.search(r'\[.*\]', ai_text, re.DOTALL)
            if match:
                vocab_list = json.loads(match.group(0))
            else:
                raise ValueError("No JSON array found")
            
            deck_name = request.deck_name or f"AI: {request.prompt[:40]}"
            share_code = str(uuid.uuid4())[:8]
            
            with db.cursor() as cursor:
                cursor.execute(
                    """INSERT INTO DECK (user_id, lang_id, name, type, share_code, 
                       is_public, is_ai_generated, language_level, tags, description)
                       VALUES (%s, %s, %s, 'custom', %s, %s, TRUE, %s, %s, %s)""",
                    (user_id, lang_id, deck_name, share_code,
                     request.is_public, request.language_level, request.tags, request.prompt)
                )
                deck_id = cursor.lastrowid
                
                for item in vocab_list:
                    cursor.execute(
                        "INSERT INTO VOCAB (deck_id, learning_lang_id, word_text, reading_text) VALUES (%s, %s, %s, %s)",
                        (deck_id, lang_id, item.get('word', ''), item.get('reading', ''))
                    )
                    v_id = cursor.lastrowid
                    cursor.execute(
                        "INSERT INTO VOCAB_TRANSLATION (vocab_id, mother_tongue_lang_id, translated_text) VALUES (%s, %s, %s)",
                        (v_id, mt_lang_id, item.get('translation', ''))
                    )
                db.commit()
            return {"deck_id": deck_id, "vocab_count": len(vocab_list)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Generation failed: {str(e)}")


@router.post("/make_unit_from_chat")
async def make_unit_from_chat(request: MakeUnitFromChatRequest, current_user: dict = Depends(get_current_user), db=Depends(get_db)):
    """Convert a chat conversation into a structured unit."""
    user_id = current_user['user_id']
    
    # Get all messages from the conversation
    history = _get_conversation_history(request.conversation_id, db, limit=100)
    if not history:
        raise HTTPException(status_code=404, detail="No messages found")
    
    # Compile the conversation content
    chat_content = "\n".join([f"{m['role']}: {m['content']}" for m in history])
    
    # Get user's mother tongue
    with db.cursor() as cursor:
        cursor.execute("SELECT mother_tongue_lang_id FROM USER WHERE user_id = %s", (user_id,))
        user_data = cursor.fetchone()
        cursor.execute("SELECT code FROM LANGUAGE WHERE lang_id = %s", (user_data['mother_tongue_lang_id'],))
        lang_row = cursor.fetchone()
    
    mt_code = lang_row['code'] if lang_row else 'de'
    
    # Use AI to structure the conversation into a unit
    prompt_text = f"Based on this conversation, create a structured learning unit:\n{chat_content[:3000]}"
    if request.additional_prompt:
        prompt_text += f"\n\nAdditional user instructions: {request.additional_prompt}"

    gen_request = GenerateUnitRequest(
        prompt=prompt_text,
        model="llama3.2:3b", # Use a default fast model
        learning_lang="ja",
        mother_tongue=mt_code,
        cefr_level="A1",
        is_public=request.is_public
    )
    
    return await generate_unit(gen_request, current_user, db)

@router.post("/make_deck_from_chat")
async def make_deck_from_chat(request: MakeDeckFromChatRequest, current_user: dict = Depends(get_current_user), db=Depends(get_db)):
    """Convert a chat conversation into a vocabulary deck."""
    user_id = current_user['user_id']
    history = _get_conversation_history(request.conversation_id, db, limit=100)
    if not history:
        raise HTTPException(status_code=404, detail="No messages found")
    
    chat_content = "\n".join([f"{m['role']}: {m['content']}" for m in history])
    
    with db.cursor() as cursor:
        cursor.execute("SELECT mother_tongue_lang_id FROM USER WHERE user_id = %s", (user_id,))
        user_data = cursor.fetchone()
        cursor.execute("SELECT code FROM LANGUAGE WHERE lang_id = %s", (user_data['mother_tongue_lang_id'],))
        lang_row = cursor.fetchone()
    
    mt_code = lang_row['code'] if lang_row else 'de'
    mt_name = LANG_NAMES.get(mt_code, 'German')

    prompt = f"""Extract all relevant vocabulary words and phrases from the following Japanese learning conversation.
Conversation:
{chat_content[:3000]}

Format as a JSON array of objects:
[
  {{"word": "...", "reading": "...", "translation": "in {mt_name}", "example": "sentence", "example_translation": "in {mt_name}"}}
]
No other text, just the JSON."""

    gen_request = GenerateDeckRequest(
        prompt=prompt,
        model="llama3.2:3b",
        learning_lang="ja",
        mother_tongue=mt_code,
        cefr_level="A1",
        deck_name=request.title or f"Deck from Chat {request.conversation_id}",
        is_public=request.is_public
    )
    
    return await generate_deck(gen_request, current_user, db)


@router.post("/auto_fill")
async def auto_fill(request: AIRequest):
    """Auto-fill vocab entry with reading and translation."""
    lang_name = LANG_NAMES.get(request.learning_lang, 'Japanese')
    mt_name = LANG_NAMES.get(request.mother_tongue, 'German')
    
    prompt = f"""For the {lang_name} word '{request.prompt}', provide the reading and a {mt_name} translation.
Output as JSON only: {{"reading": "...", "translation": "..."}}. No other text."""
    
    try:
        async with httpx.AsyncClient(timeout=300.0, trust_env=False) as client:
            response = await client.post(OLLAMA_URL, json={
                "model": request.model,
                "prompt": prompt,
                "stream": False
            })
            if response.status_code == 200:
                return response.json()
            raise HTTPException(status_code=response.status_code, detail="Ollama Error")
    except httpx.ConnectError:
        raise HTTPException(status_code=503, detail="Ollama is not running")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ollama error: {str(e)}")
