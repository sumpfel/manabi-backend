import pymysql
from database import Config

# Dummy JLPT Vocab Set
official_decks = [
    {
        "name": "JLPT N5 Core",
        "description": "Essential JLPT N5 Vocabulary",
        "language_level": "A1",
        "tags": "jlpt, n5",
        "vocab": [
            {"kanji": "水", "kana": "みず", "de": "Wasser", "en": "Water"},
            {"kanji": "本", "kana": "ほん", "de": "Buch", "en": "Book"},
            {"kanji": "先生", "kana": "せんせい", "de": "Lehrer", "en": "Teacher"}
        ]
    },
    {
        "name": "JLPT N4 Essentials",
        "description": "Essential JLPT N4 Vocabulary",
        "language_level": "A2",
        "tags": "jlpt, n4",
        "vocab": [
            {"kanji": "家族", "kana": "かぞく", "de": "Familie", "en": "Family"},
            {"kanji": "意味", "kana": "いみ", "de": "Bedeutung", "en": "Meaning"},
            {"kanji": "約束", "kana": "やくそく", "de": "Versprechen", "en": "Promise"}
        ]
    },
    {
        "name": "JLPT N3 Mastery",
        "description": "JLPT N3 Vocabulary",
        "language_level": "B1",
        "tags": "jlpt, n3",
        "vocab": [
            {"kanji": "複雑", "kana": "ふくざつ", "de": "Kompliziert", "en": "Complex"},
            {"kanji": "経験", "kana": "けいけん", "de": "Erfahrung", "en": "Experience"}
        ]
    }
]

def seed():
    conn = pymysql.connect(
        host=Config.DB_HOST,
        port=Config.DB_PORT,
        user=Config.DB_USER,
        password=Config.DB_PASSWORD,
        database=Config.DB_NAME,
        cursorclass=pymysql.cursors.DictCursor
    )
    
    with conn.cursor() as cursor:
        # Create a system/admin user if not exists to own the decks
        cursor.execute("SELECT user_id FROM USER WHERE username = 'admin'")
        admin = cursor.fetchone()
        if not admin:
            cursor.execute("INSERT INTO USER (username, email, password_hash) VALUES ('admin', 'admin@system.local', 'invalid')")
            admin_id = cursor.lastrowid
        else:
            admin_id = admin['user_id']
            
        import uuid
            
        for deck in official_decks:
            # Check if exists
            cursor.execute("SELECT deck_id FROM DECK WHERE name = %s", (deck['name'],))
            existing = cursor.fetchone()
            if existing:
                print(f"Deck {deck['name']} already exists. Skipping.")
                continue
                
            share_code = str(uuid.uuid4())[:8]
            cursor.execute("""
                INSERT INTO DECK (user_id, lang_id, name, type, share_code, is_public, description, language_level, tags, is_official)
                VALUES (%s, 3, %s, 'custom', %s, TRUE, %s, %s, %s, TRUE)
            """, (admin_id, deck['name'], share_code, deck['description'], deck['language_level'], deck['tags']))
            
            deck_id = cursor.lastrowid
            print(f"Generated Official Deck: {deck['name']}")
            
            for v in deck['vocab']:
                cursor.execute("""
                    INSERT INTO VOCAB (deck_id, learning_lang_id, word_text, reading_text)
                    VALUES (%s, 3, %s, %s)
                """, (deck_id, v['kanji'], v['kana']))
                vocab_id = cursor.lastrowid
                
                cursor.execute("""
                    INSERT INTO VOCAB_TRANSLATION (vocab_id, mother_tongue_lang_id, translated_text) VALUES (%s, 1, %s)
                """, (vocab_id, v['de']))
                
                cursor.execute("""
                    INSERT INTO VOCAB_TRANSLATION (vocab_id, mother_tongue_lang_id, translated_text) VALUES (%s, 2, %s)
                """, (vocab_id, v['en']))
                
        conn.commit()
    conn.close()
    print("Seed complete.")

if __name__ == "__main__":
    seed()
