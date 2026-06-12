import sqlite3, os

# DB_PATH overridable via env var (Fly.io mounts the volume at /data).
# Default points at the repo's data/ dir for local development.
DB_PATH = os.environ.get(
    "DB_PATH",
    os.path.join(os.path.dirname(__file__), "../data/horse.db"),
)

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA case_sensitive_like = OFF")
    conn.create_function("LOWER", 1, lambda x: x.lower() if x else x)
    conn.create_function("UPPER", 1, lambda x: x.upper() if x else x)
    return conn

def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = get_db()
    conn.executescript("""
    PRAGMA foreign_keys = OFF;

    -- ── CORE TABLES ──
    CREATE TABLE IF NOT EXISTS herd (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL, notes TEXT, stallion_id INTEGER, active INTEGER DEFAULT 1
    );

    CREATE TABLE IF NOT EXISTS contact (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL, address TEXT, phone TEXT, email TEXT, city TEXT,
        type TEXT DEFAULT 'owner'
    );

    CREATE TABLE IF NOT EXISTS option (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        type TEXT NOT NULL, name TEXT NOT NULL, active INTEGER DEFAULT 1,
        UNIQUE(type, name)
    );

    CREATE TABLE IF NOT EXISTS stable (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT, type TEXT, location TEXT, row_count INTEGER DEFAULT 1,
        column_count INTEGER DEFAULT 1, active INTEGER DEFAULT 1
    );

    CREATE TABLE IF NOT EXISTS trainer (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL, phone TEXT, address TEXT,
        title TEXT DEFAULT 'none', notes TEXT, active INTEGER DEFAULT 1
    );

    CREATE TABLE IF NOT EXISTS naadam (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT, type TEXT, subtype TEXT, date TEXT, location TEXT, notes TEXT
    );

    -- ── HORSE ──
    CREATE TABLE IF NOT EXISTS horse (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        registration_code TEXT, number TEXT,
        sex TEXT,
        breed_id INTEGER, origin_id INTEGER,
        herd_id INTEGER, color_id INTEGER,
        status TEXT DEFAULT 'active',
        birth_date TEXT, birth_date_unknown INTEGER DEFAULT 0,
        chip TEXT, passport TEXT, dna TEXT,
        registered INTEGER DEFAULT 1, no_id INTEGER DEFAULT 0,
        blood_percentage TEXT,
        head_marking TEXT, body_marking TEXT, leg_marking TEXT, brand TEXT,
        stable_id INTEGER, location TEXT, herder_id INTEGER,
        notes TEXT, personal_note TEXT,
        gelded INTEGER DEFAULT 0,
        sire_id INTEGER, dam_id INTEGER,
        legacy_id TEXT, legacy_sire_id TEXT, legacy_dam_id TEXT,
        important INTEGER DEFAULT 0,
        active INTEGER DEFAULT 1,
        FOREIGN KEY (herd_id) REFERENCES herd(id)
    );

    CREATE TABLE IF NOT EXISTS horse_owner (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        horse_id INTEGER, owner_id INTEGER, share_percent INTEGER DEFAULT 100
    );

    CREATE TABLE IF NOT EXISTS horse_trainer (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        horse_id INTEGER, trainer_id INTEGER,
        start_date TEXT, end_date TEXT, notes TEXT,
        active INTEGER DEFAULT 1
    );

    -- ── PRACTICE RACE (sungaa: training scrimmage / mock race) ──
    CREATE TABLE IF NOT EXISTS practice_race (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        horse_id INTEGER, date TEXT, type TEXT, notes TEXT,
        distance_text TEXT, naadam_id INTEGER, trainer_id INTEGER,
        jockey TEXT, age_category TEXT, rank INTEGER,
        naadam_type TEXT, naadam_name TEXT,
        province TEXT, sum TEXT,
        owner_text TEXT, breed_text TEXT,
        distance_km REAL, time TEXT, venue TEXT
    );

    -- ── RACE (legacy old-system race records) ──
    CREATE TABLE IF NOT EXISTS race (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        horse_id INTEGER NOT NULL,
        date TEXT, naadam_name TEXT, rank TEXT,
        jockey TEXT, notes TEXT, legacy_id TEXT
    );

    -- ── PHOTO ──
    CREATE TABLE IF NOT EXISTS photo (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        horse_id INTEGER, file TEXT, date TEXT, notes TEXT, name TEXT
    );

    -- ── HEALTH RECORD ──
    CREATE TABLE IF NOT EXISTS health_record (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        horse_id INTEGER NOT NULL,
        date TEXT,
        type TEXT,        -- Тарилга / Эмчилгээ / Шимэгч устгал / Шүдний эмчилгээ / Бусад
        product TEXT,     -- Бүтээгдэхүүн / Вакцин
        amount TEXT,      -- Тоо хэмжээ
        vet TEXT,
        notes TEXT,
        legacy_id TEXT
    );

    -- ── MEASUREMENT ──
    CREATE TABLE IF NOT EXISTS measurement (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        horse_id INTEGER NOT NULL,
        date TEXT,
        weight REAL,        -- kg
        height REAL,        -- cm
        chest_girth REAL,   -- cm
        cannon_bone REAL,   -- cm
        notes TEXT
    );

    -- ── HOOF CARE ──
    CREATE TABLE IF NOT EXISTS hoof_care (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        horse_id INTEGER NOT NULL,
        date TEXT,
        next_date TEXT,
        type TEXT,          -- Урд / Хойд / Тусгай
        notes TEXT,
        farrier TEXT,
        legacy_id TEXT
    );

    -- ── FEEDING ──
    CREATE TABLE IF NOT EXISTS feeding (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        horse_id INTEGER NOT NULL,
        feed_name TEXT,
        start_date TEXT,
        end_date TEXT,
        notes TEXT
    );

    -- ── EIA TEST (Equine Infectious Anemia) ──
    CREATE TABLE IF NOT EXISTS eia_test (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        horse_id INTEGER NOT NULL,
        date TEXT,
        result TEXT,        -- Сөрөг / Эерэг
        province TEXT,
        lab TEXT,
        responsible TEXT,
        notes TEXT,
        legacy_id TEXT
    );

    -- ── ATTACHMENT ──
    CREATE TABLE IF NOT EXISTS attachment (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        horse_id INTEGER NOT NULL,
        file TEXT, name TEXT, date TEXT, notes TEXT
    );

    -- ── TRAINING SESSION ──
    CREATE TABLE IF NOT EXISTS training_session (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        horse_id INTEGER NOT NULL,
        trainer_id INTEGER,
        type TEXT NOT NULL,
        date TEXT,
        distance_km REAL,
        duration_min REAL,
        temperature_c REAL,
        wind_ms REAL,
        jockey TEXT,
        days INTEGER,
        notes TEXT,
        original_text TEXT
    );

    -- ── POLAR HRM SESSION ──
    CREATE TABLE IF NOT EXISTS polar_session (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        training_session_id INTEGER,
        horse_id INTEGER NOT NULL,
        trainer_id INTEGER,
        date TEXT,
        type TEXT,
        distance_km REAL,
        duration_min REAL,
        avg_speed REAL,                 -- km/h
        avg_heart_rate REAL,            -- bpm
        max_heart_rate REAL,
        min_heart_rate REAL,
        recovery_1min REAL,
        recovery_2min REAL,
        recovery_index TEXT,
        hrv REAL,
        hr_zone_resting REAL,           -- <100 bpm
        hr_zone_moderate REAL,          -- 100-130
        hr_zone_intense REAL,           -- 130-160
        hr_zone_very_intense REAL,      -- 160-180
        hr_zone_max REAL,               -- >180
        training_load REAL,
        hr_series TEXT,                 -- per-second HR (JSON)
        gps_series TEXT,                -- GPS route (JSON)
        polar_exercise_id TEXT,
        imported_at TEXT DEFAULT CURRENT_TIMESTAMP,
        notes TEXT
    );

    -- ── BREEDING EVENT ──
    CREATE TABLE IF NOT EXISTS breeding_event (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        horse_id INTEGER NOT NULL,
        date TEXT, type TEXT, notes TEXT, vet TEXT
    );

    -- ── GELDING EVENT ──
    CREATE TABLE IF NOT EXISTS gelding_event (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        horse_id INTEGER NOT NULL,
        date DATE NOT NULL,
        performed_by TEXT,
        notes TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (horse_id) REFERENCES horse(id)
    );

    -- ── NOTIFICATION ──
    CREATE TABLE IF NOT EXISTS notification (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        trainer_id INTEGER, horse_id INTEGER, note_id INTEGER,
        text TEXT, read INTEGER DEFAULT 0,
        date TEXT DEFAULT CURRENT_TIMESTAMP
    );

    -- ── TRAINING NOTE ──
    CREATE TABLE IF NOT EXISTS training_note (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        horse_id INTEGER, trainer_id INTEGER, date TEXT,
        type TEXT, distance_km REAL, duration_min REAL,
        notes TEXT, original_text TEXT
    );

    -- ── TASK (legacy, replaced by tasks/task_horses/task_logs below) ──
    CREATE TABLE IF NOT EXISTS task (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT, notes TEXT, date TEXT, time TEXT,
        repeat TEXT DEFAULT 'once', priority TEXT DEFAULT 'medium',
        status TEXT DEFAULT 'pending', assigned_to_id INTEGER
    );

    -- ── Ажлуудын төлөвлөгөө (арчилгааны хуваарь) ──
    CREATE TABLE IF NOT EXISTS tasks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        task_type TEXT NOT NULL,
        title TEXT,
        scheduled_date DATE NOT NULL,
        assignee TEXT,
        external_provider TEXT,
        horse_link_type TEXT,
        herd_id INTEGER,
        filter_json TEXT,
        recurrence TEXT DEFAULT 'none',
        notes TEXT,
        status TEXT DEFAULT 'planned',
        completed_date DATE,
        completion_notes TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS task_horses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        task_id INTEGER REFERENCES tasks(id),
        horse_id INTEGER REFERENCES horse(id)
    );

    CREATE TABLE IF NOT EXISTS task_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        task_id INTEGER REFERENCES tasks(id),
        action TEXT,
        reason TEXT,
        new_date DATE,
        logged_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    -- ── FINANCE RECORD ──
    CREATE TABLE IF NOT EXISTS finance_record (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        type TEXT, date TEXT, amount REAL,
        category TEXT, notes TEXT, horse_id INTEGER
    );

    -- ── USER (auth) ──
    CREATE TABLE IF NOT EXISTS user (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        full_name TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        active INTEGER DEFAULT 1
    );

    -- ── TRAINING PLAN ──
    CREATE TABLE IF NOT EXISTS training_plan (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        horse_id INTEGER NOT NULL,
        trainer_id INTEGER,
        date TEXT NOT NULL,
        type TEXT NOT NULL,
        status TEXT DEFAULT 'planned',
        notes TEXT,
        created_at TEXT DEFAULT (datetime('now'))
    );
    """)

    # Default option (lookup) values — Cyrillic Mongolian display strings.
    defaults = [
        ('color','Хар'),('color','Цагаан'),('color','Улаан хүрэн'),('color','Боро'),
        ('color','Алаг'),('color','Хүрэн'),('color','Зээрд'),('color','Шарга'),
        ('color','Халиун'),('color','Саарал'),('color','Хээр'),('color','Буурал'),
        ('color','Бор'),('color','Хонгор'),('color','Хүрэн халзан'),
        ('color','Хар буурал'),('color','Хээр буурал'),('color','Халиун халзан'),
        ('breed','Монгол адуу'),('breed','Хүнхэр адуу'),
        ('breed','Англи адуу'),('breed','Будан адуу'),
        ('origin','Дотоодын'),('origin','Гадаадын'),
        ('body_marking','Зүүн хошуу'),('body_marking','Баруун хошуу'),
        ('body_marking','Хоёр хошуу'),('body_marking','Шарагтай'),
        ('head_marking','Халзан'),('head_marking','Цагаан халзан'),
        ('leg_marking','Цагаан хөл'),('leg_marking','Дөрвөн цагаан'),
        # Training session types
        ('training_type','Амраах'),('training_type','Гэдэс солих'),
        ('training_type','Гишгүүлэх'),('training_type','Хөлс авах'),
        ('training_type','Тар'),('training_type','Хангар'),
        ('training_type','Бага сүнгаа'),('training_type','Дунд сүнгаа'),
        ('training_type','Их сүнгаа'),
    ]
    for t, n in defaults:
        conn.execute("INSERT OR IGNORE INTO option (type,name) VALUES (?,?)", (t, n))

    conn.commit()
    conn.close()
    print("✅ DB бэлэн!")

if __name__ == "__main__":
    init_db()
