import pymysql
import sys
from core.config import Config

def create_database():
    try:
        # Connect to MariaDB Server using Config
        print("Connecting to local MariaDB instance...")
        connection = pymysql.connect(
            host=Config.DB_HOST,
            port=Config.DB_PORT,
            user=Config.DB_USER,
            password=Config.DB_PASSWORD,
            charset='utf8mb4',
            cursorclass=pymysql.cursors.DictCursor
        )
        
        with connection.cursor() as cursor:
            # Create Database
            print("Creating nexus_lingua database if it doesn't exist...")
            cursor.execute("CREATE DATABASE IF NOT EXISTS nexus_lingua CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;")
            cursor.execute("USE nexus_lingua;")
            
            # Create Tables
            tables = [
                """
                CREATE TABLE IF NOT EXISTS USER (
                    user_id INT AUTO_INCREMENT PRIMARY KEY,
                    username VARCHAR(255) NOT NULL,
                    password_hash VARCHAR(255) NOT NULL,
                    email VARCHAR(255) NOT NULL,
                    mother_tongue_lang_id INT NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                );
                """,

                """
                CREATE TABLE IF NOT EXISTS LANGUAGE (
                    lang_id INT AUTO_INCREMENT PRIMARY KEY,
                    code VARCHAR(10) NOT NULL,
                    name VARCHAR(255) NOT NULL,
                    requires_writing_pad BOOLEAN DEFAULT FALSE
                );
                """,
                """
                CREATE TABLE IF NOT EXISTS USER_STATISTIC (
                    stat_id INT AUTO_INCREMENT PRIMARY KEY,
                    user_id INT NOT NULL,
                    learning_lang_id INT NOT NULL,
                    current_streak INT DEFAULT 0,
                    total_vocab_learned INT DEFAULT 0,
                    units_completed INT DEFAULT 0,
                    accuracy_percent FLOAT DEFAULT 0.0,
                    last_activity DATETIME DEFAULT CURRENT_TIMESTAMP
                );
                """,
                """
                CREATE TABLE IF NOT EXISTS USER_SESSION (
                    session_id INT AUTO_INCREMENT PRIMARY KEY,
                    user_id INT NOT NULL,
                    device_id VARCHAR(255) NOT NULL,
                    last_active_tab VARCHAR(50),
                    session_state_json JSON,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
                );
                """,
                # ── Deck Sections (grouping) ──
                """
                CREATE TABLE IF NOT EXISTS DECK_SECTION (
                    section_id INT AUTO_INCREMENT PRIMARY KEY,
                    user_id INT NOT NULL,
                    name VARCHAR(255) NOT NULL,
                    is_system BOOLEAN DEFAULT FALSE,
                    sort_order INT DEFAULT 0,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                );
                """,
                """
                CREATE TABLE IF NOT EXISTS DECK (
                    deck_id INT AUTO_INCREMENT PRIMARY KEY,
                    user_id INT NOT NULL,
                    lang_id INT NOT NULL,
                    name VARCHAR(255) NOT NULL,
                    type VARCHAR(50) NOT NULL,
                    parent_unit_id INT,
                    share_code VARCHAR(255),
                    thumbnail_url VARCHAR(500),
                    section_id INT,
                    is_public BOOLEAN DEFAULT FALSE,
                    is_ai_generated BOOLEAN DEFAULT FALSE,
                    language_level VARCHAR(10),
                    tags TEXT,
                    vote_count INT DEFAULT 0,
                    description TEXT,
                    is_official BOOLEAN DEFAULT FALSE,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                );
                """,
                """
                CREATE TABLE IF NOT EXISTS MANGA_SOURCE (
                    source_id INT AUTO_INCREMENT PRIMARY KEY,
                    title VARCHAR(255) NOT NULL,
                    url VARCHAR(500) NOT NULL,
                    cover_image_url VARCHAR(500)
                );
                """,
                """
                CREATE TABLE IF NOT EXISTS MANGA_CHAPTER (
                    chapter_id INT AUTO_INCREMENT PRIMARY KEY,
                    source_id INT NOT NULL,
                    chapter_number INT NOT NULL,
                    chapter_title VARCHAR(255)
                );
                """,
                """
                CREATE TABLE IF NOT EXISTS MANGA_PAGE (
                    page_id INT AUTO_INCREMENT PRIMARY KEY,
                    chapter_id INT NOT NULL,
                    page_number INT NOT NULL,
                    image_url VARCHAR(500)
                );
                """,
                """
                CREATE TABLE IF NOT EXISTS VOCAB (
                    vocab_id INT AUTO_INCREMENT PRIMARY KEY,
                    deck_id INT NOT NULL,
                    learning_lang_id INT NOT NULL,
                    manga_page_id INT,
                    lesson_id INT,
                    word_text TEXT NOT NULL,
                    reading_text TEXT,
                    next_review_date DATETIME,
                    srs_level INT DEFAULT 0
                );
                """,
                """
                CREATE TABLE IF NOT EXISTS CHARACTER_PRACTICE (
                    practice_id INT AUTO_INCREMENT PRIMARY KEY,
                    user_id INT NOT NULL,
                    lang_id INT NOT NULL,
                    `character` VARCHAR(10) NOT NULL,
                    accuracy FLOAT DEFAULT 0.0,
                    times_practiced INT DEFAULT 0,
                    last_practiced DATETIME
                );
                """,
                """
                CREATE TABLE IF NOT EXISTS VOCAB_TRANSLATION (
                    translation_id INT AUTO_INCREMENT PRIMARY KEY,
                    vocab_id INT NOT NULL,
                    mother_tongue_lang_id INT NOT NULL,
                    translated_text TEXT NOT NULL
                );
                """,
                """
                CREATE TABLE IF NOT EXISTS EXAMPLE_SENTENCE (
                    example_id INT AUTO_INCREMENT PRIMARY KEY,
                    vocab_id INT NOT NULL,
                    sentence_text TEXT NOT NULL,
                    reading_text TEXT
                );
                """,
                """
                CREATE TABLE IF NOT EXISTS EXAMPLE_TRANSLATION (
                    trans_id INT AUTO_INCREMENT PRIMARY KEY,
                    example_id INT NOT NULL,
                    mother_tongue_lang_id INT NOT NULL,
                    translated_text TEXT NOT NULL
                );
                """,
                """
                CREATE TABLE IF NOT EXISTS UNIT (
                    unit_id INT AUTO_INCREMENT PRIMARY KEY,
                    lang_id INT NOT NULL,
                    creator_user_id INT,
                    title VARCHAR(255) NOT NULL,
                    description TEXT,
                    is_basic_global BOOLEAN DEFAULT TRUE,
                    share_code VARCHAR(255),
                    is_public BOOLEAN DEFAULT FALSE,
                    is_ai_generated BOOLEAN DEFAULT FALSE,
                    language_level VARCHAR(10),
                    tags TEXT,
                    vote_count INT DEFAULT 0,
                    base_unit_id INT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                );
                """,
                """
                CREATE TABLE IF NOT EXISTS LESSON (
                    lesson_id INT AUTO_INCREMENT PRIMARY KEY,
                    unit_id INT NOT NULL,
                    lesson_order INT NOT NULL,
                    title VARCHAR(255) NOT NULL,
                    grammar_markdown TEXT NOT NULL,
                    recommended_deck_id INT,
                    exercises_json JSON,
                    required_accuracy FLOAT
                );
                """,
                """
                CREATE TABLE IF NOT EXISTS LESSON_PROGRESS (
                    progress_id INT AUTO_INCREMENT PRIMARY KEY,
                    user_id INT NOT NULL,
                    lesson_id INT NOT NULL,
                    is_completed BOOLEAN DEFAULT FALSE,
                    completed_at DATETIME DEFAULT CURRENT_TIMESTAMP
                );
                """,
                # ── AI Chat Conversations ──
                """
                CREATE TABLE IF NOT EXISTS CHAT_CONVERSATION (
                    conversation_id INT AUTO_INCREMENT PRIMARY KEY,
                    user_id INT NOT NULL,
                    title VARCHAR(255) DEFAULT 'Neues Gespräch',
                    learning_lang_id INT,
                    cefr_level VARCHAR(10) DEFAULT 'A1',
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
                );
                """,
                """
                CREATE TABLE IF NOT EXISTS MESSAGE (
                    message_id INT AUTO_INCREMENT PRIMARY KEY,
                    conversation_id INT NOT NULL,
                    user_id INT NOT NULL,
                    role VARCHAR(50) NOT NULL,
                    content TEXT NOT NULL,
                    is_edited BOOLEAN DEFAULT FALSE,
                    version INT DEFAULT 1,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                );
                """,
                # ── Community: Comments ──
                """
                CREATE TABLE IF NOT EXISTS COMMENT (
                    comment_id INT AUTO_INCREMENT PRIMARY KEY,
                    user_id INT NOT NULL,
                    target_type VARCHAR(50) NOT NULL,
                    target_id INT NOT NULL,
                    parent_comment_id INT,
                    content TEXT NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                );
                """,
                # ── Community: Votes ──
                """
                CREATE TABLE IF NOT EXISTS VOTE (
                    vote_id INT AUTO_INCREMENT PRIMARY KEY,
                    user_id INT NOT NULL,
                    target_type VARCHAR(50) NOT NULL,
                    target_id INT NOT NULL,
                    value INT DEFAULT 1,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE KEY unique_vote (user_id, target_type, target_id)
                );
                """,
                # ── Notifications ──
                """
                CREATE TABLE IF NOT EXISTS NOTIFICATION (
                    notification_id INT AUTO_INCREMENT PRIMARY KEY,
                    user_id INT NOT NULL,
                    type VARCHAR(50) NOT NULL,
                    message TEXT NOT NULL,
                    target_type VARCHAR(50),
                    target_id INT,
                    is_read BOOLEAN DEFAULT FALSE,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                );
                """,
                # ── AI Settings per user ──
                """
                CREATE TABLE IF NOT EXISTS AI_SETTINGS (
                    settings_id INT AUTO_INCREMENT PRIMARY KEY,
                    user_id INT NOT NULL UNIQUE,
                    color_particles VARCHAR(20) DEFAULT '#4FC3F7',
                    color_verbs VARCHAR(20) DEFAULT '#FF8A65',
                    color_nouns VARCHAR(20) DEFAULT '#81C784',
                    color_adjectives VARCHAR(20) DEFAULT '#CE93D8',
                    color_adverbs VARCHAR(20) DEFAULT '#FFD54F',
                    deck_routing VARCHAR(50) DEFAULT 'per_chat',
                    deck_routing_count INT DEFAULT 20,
                    target_deck_id INT,
                    target_section VARCHAR(50) DEFAULT 'ai'
                );
                """,
                """
                CREATE TABLE IF NOT EXISTS DECK_SESSION (
                    session_id INT AUTO_INCREMENT PRIMARY KEY,
                    user_id INT NOT NULL,
                    deck_id INT NOT NULL,
                    study_method VARCHAR(50) NOT NULL,
                    current_index INT DEFAULT 0,
                    shuffled_vocab_ids JSON NOT NULL,
                    is_active BOOLEAN DEFAULT TRUE,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
                );
                """
            ]
            
            print("Creating tables...")
            for table_sql in tables:
                cursor.execute(table_sql)
            
            # Seed default languages if not exist
            cursor.execute("SELECT COUNT(*) as c FROM LANGUAGE")
            if cursor.fetchone()['c'] == 0:
                print("Seeding default languages...")
                langs = [
                    (1, 'de', 'Deutsch', False),
                    (2, 'en', 'English', False),
                    (3, 'ja', '日本語', True),
                    (4, 'es', 'Español', False),
                    (5, 'fr', 'Français', False),
                    (6, 'ko', '한국어', True),
                    (7, 'zh', '中文', True),
                ]
                for lid, code, name, wp in langs:
                    cursor.execute(
                        "INSERT INTO LANGUAGE (lang_id, code, name, requires_writing_pad) VALUES (%s, %s, %s, %s)",
                        (lid, code, name, wp)
                    )

            # Add columns to existing tables if they don't exist (safe migration)
            migrations = [
                ("DECK", "section_id", "ALTER TABLE DECK ADD COLUMN section_id INT AFTER thumbnail_url"),
                ("DECK", "is_public", "ALTER TABLE DECK ADD COLUMN is_public BOOLEAN DEFAULT FALSE"),
                ("DECK", "is_ai_generated", "ALTER TABLE DECK ADD COLUMN is_ai_generated BOOLEAN DEFAULT FALSE"),
                ("DECK", "language_level", "ALTER TABLE DECK ADD COLUMN language_level VARCHAR(10)"),
                ("DECK", "tags", "ALTER TABLE DECK ADD COLUMN tags TEXT"),
                ("DECK", "vote_count", "ALTER TABLE DECK ADD COLUMN vote_count INT DEFAULT 0"),
                ("DECK", "description", "ALTER TABLE DECK ADD COLUMN description TEXT"),
                ("DECK", "created_at", "ALTER TABLE DECK ADD COLUMN created_at DATETIME DEFAULT CURRENT_TIMESTAMP"),
                ("UNIT", "is_public", "ALTER TABLE UNIT ADD COLUMN is_public BOOLEAN DEFAULT FALSE"),
                ("UNIT", "is_ai_generated", "ALTER TABLE UNIT ADD COLUMN is_ai_generated BOOLEAN DEFAULT FALSE"),
                ("UNIT", "language_level", "ALTER TABLE UNIT ADD COLUMN language_level VARCHAR(10)"),
                ("UNIT", "tags", "ALTER TABLE UNIT ADD COLUMN tags TEXT"),
                ("UNIT", "vote_count", "ALTER TABLE UNIT ADD COLUMN vote_count INT DEFAULT 0"),
                ("UNIT", "base_unit_id", "ALTER TABLE UNIT ADD COLUMN base_unit_id INT"),
                ("UNIT", "created_at", "ALTER TABLE UNIT ADD COLUMN created_at DATETIME DEFAULT CURRENT_TIMESTAMP"),
                ("DECK", "is_official", "ALTER TABLE DECK ADD COLUMN is_official BOOLEAN DEFAULT FALSE"),
                ("MESSAGE", "conversation_id", "ALTER TABLE MESSAGE ADD COLUMN conversation_id INT AFTER message_id"),
                ("MESSAGE", "is_edited", "ALTER TABLE MESSAGE ADD COLUMN is_edited BOOLEAN DEFAULT FALSE"),
                ("MESSAGE", "version", "ALTER TABLE MESSAGE ADD COLUMN version INT DEFAULT 1"),
                ("LESSON", "exercises_json", "ALTER TABLE LESSON ADD COLUMN exercises_json JSON"),
                ("LESSON", "required_accuracy", "ALTER TABLE LESSON ADD COLUMN required_accuracy FLOAT"),
                ("CHAT_CONVERSATION", "learning_lang_id", "ALTER TABLE CHAT_CONVERSATION ADD COLUMN learning_lang_id INT"),
                ("CHAT_CONVERSATION", "cefr_level", "ALTER TABLE CHAT_CONVERSATION ADD COLUMN cefr_level VARCHAR(10) DEFAULT 'A1'"),
            ]
            
            for table, col, sql in migrations:
                try:
                    cursor.execute(f"SELECT {col} FROM {table} LIMIT 1")
                except:
                    try:
                        print(f"  Adding {table}.{col}...")
                        cursor.execute(sql)
                    except Exception as e:
                        print(f"  Warning: Could not add {table}.{col}: {e}")

            print("Successfully initialized nexus_lingua schema!")
        
        connection.commit()
    except pymysql.MySQLError as e:
        print(f"Error connecting to MariaDB Platform: {e}")
        sys.exit(1)
    finally:
        if 'connection' in locals() and connection.open:
            connection.close()

if __name__ == "__main__":
    create_database()
