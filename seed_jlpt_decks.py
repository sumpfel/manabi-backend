import pymysql
import sys
import os

# Add parent dir to path for imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from core.config import Config

JLPT_DECKS = [
    {'name': 'JLPT N5 Vokabeln', 'description': 'Grundwortschatz ~800 Wörter', 'level': 'N5', 'type': 'vocab'},
    {'name': 'JLPT N4 Vokabeln', 'description': 'Elementarer Wortschatz ~1500 Wörter', 'level': 'N4', 'type': 'vocab'},
    {'name': 'JLPT N3 Vokabeln', 'description': 'Mittelstufe Wortschatz ~3750 Wörter', 'level': 'N3', 'type': 'vocab'},
    {'name': 'JLPT N2 Vokabeln', 'description': 'Fortgeschrittener Wortschatz ~6000 Wörter', 'level': 'N2', 'type': 'vocab'},
    {'name': 'JLPT N1 Vokabeln', 'description': 'Experten Wortschatz ~10000 Wörter', 'level': 'N1', 'type': 'vocab'},
    {'name': 'JLPT N5 Kanji', 'description': '~100 grundlegende Kanji', 'level': 'N5', 'type': 'kanji'},
    {'name': 'JLPT N4 Kanji', 'description': '~300 elementare Kanji', 'level': 'N4', 'type': 'kanji'},
    {'name': 'JLPT N3 Kanji', 'description': '~650 mittlere Kanji', 'level': 'N3', 'type': 'kanji'},
    {'name': 'JLPT N2 Kanji', 'description': '~1000 fortgeschrittene Kanji', 'level': 'N2', 'type': 'kanji'},
    {'name': 'JLPT N1 Kanji', 'description': '~2000+ Experten Kanji', 'level': 'N1', 'type': 'kanji'},
]

def seed_decks():
    try:
        connection = pymysql.connect(
            host=Config.DB_HOST,
            port=Config.DB_PORT,
            user=Config.DB_USER,
            password=Config.DB_PASSWORD,
            db='nexus_lingua',
            charset='utf8mb4',
            cursorclass=pymysql.cursors.DictCursor
        )
        
        with connection.cursor() as cursor:
            # Ensure a "System" user exists (id=1)
            cursor.execute("SELECT user_id FROM USER WHERE user_id = 1")
            if not cursor.fetchone():
                print("Creating system user...")
                cursor.execute(
                    "INSERT INTO USER (user_id, username, password_hash, email, mother_tongue_lang_id) VALUES (1, 'System', 'system', 'system@example.com', 2)"
                )

            for deck in JLPT_DECKS:
                # Check if already exists
                cursor.execute("SELECT deck_id FROM DECK WHERE name = %s AND user_id = 1", (deck['name'],))
                if cursor.fetchone():
                    print(f"Skipping {deck['name']}, already seeded.")
                    continue
                
                print(f"Seeding {deck['name']}...")
                cursor.execute(
                    """INSERT INTO DECK (user_id, lang_id, name, type, is_public, is_official, language_level, description) 
                       VALUES (1, 3, %s, %s, TRUE, TRUE, %s, %s)""",
                    (deck['name'], deck['type'], deck['level'], deck['description'])
                )
            
            connection.commit()
            print("Successfully seeded official JLPT decks!")
            
    except Exception as e:
        print(f"Error seeding decks: {e}")
        sys.exit(1)
    finally:
        if 'connection' in locals() and connection.open:
            connection.close()

if __name__ == "__main__":
    seed_decks()
