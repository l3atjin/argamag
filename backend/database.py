import sqlite3, os
DB_PATH = os.path.join(os.path.dirname(__file__), "../data/horse.db")

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

    -- ── ҮНДСЭН ХҮСНЭГТҮҮД ──
    CREATE TABLE IF NOT EXISTS surg (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ner TEXT NOT NULL, tailbar TEXT, azarga_id INTEGER, idevhtei INTEGER DEFAULT 1
    );

    CREATE TABLE IF NOT EXISTS holboo (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ner TEXT NOT NULL, hayag TEXT, utas TEXT, email TEXT, hot TEXT,
        turul TEXT DEFAULT 'ezeshigch'
    );

    CREATE TABLE IF NOT EXISTS tohiruulga (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        turul TEXT NOT NULL, ner TEXT NOT NULL, idevhtei INTEGER DEFAULT 1,
        UNIQUE(turul, ner)
    );

    CREATE TABLE IF NOT EXISTS zuchee (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ner TEXT, turul TEXT, bayrshal TEXT, mur_too INTEGER DEFAULT 1,
        haircag_too INTEGER DEFAULT 1, idevhtei INTEGER DEFAULT 1
    );

    CREATE TABLE IF NOT EXISTS uyaach (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ner TEXT NOT NULL, utas TEXT, hayg TEXT,
        tsol TEXT DEFAULT 'tsolgui', tailbar TEXT, idevhtei INTEGER DEFAULT 1
    );

    CREATE TABLE IF NOT EXISTS naadam (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ner TEXT, turul TEXT, dund_turul TEXT, ognoo TEXT, hayg TEXT, tailbar TEXT
    );

    -- ── АДУУ ──
    CREATE TABLE IF NOT EXISTS aduu (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ner TEXT NOT NULL,
        aduu_id TEXT, dugaar TEXT,
        huis TEXT,
        ugshil_id INTEGER, garal_id INTEGER,
        surg_id INTEGER, zus_id INTEGER,
        status TEXT DEFAULT 'idevhtei',
        torson TEXT, ognoo_gui INTEGER DEFAULT 0,
        chip TEXT, pasport TEXT, dnh TEXT,
        registerlesen INTEGER DEFAULT 1, id_gui INTEGER DEFAULT 0,
        tsusni_huvi TEXT,
        senas_tolgoi TEXT, senas_bie TEXT, senas_hel TEXT, tamga TEXT,
        zuchee_id INTEGER, bayrshal TEXT, malchin_id INTEGER,
        tailbar TEXT, huviin_temdeglel TEXT,
        hongoloson INTEGER DEFAULT 0,
        eceg_id INTEGER, eh_id INTEGER,
        orig_id TEXT, orig_eceg_id TEXT, orig_eh_id TEXT,
        chuhal INTEGER DEFAULT 0,
        idevhtei INTEGER DEFAULT 1,
        FOREIGN KEY (surg_id) REFERENCES surg(id)
    );

    CREATE TABLE IF NOT EXISTS aduu_ezeshigch (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        aduu_id INTEGER, ezeshigch_id INTEGER, huvi INTEGER DEFAULT 100
    );

    CREATE TABLE IF NOT EXISTS aduu_uyaach (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        aduu_id INTEGER, uyaach_id INTEGER,
        ehleh_ognoo TEXT, duusah_ognoo TEXT, tailbar TEXT,
        idevhtei INTEGER DEFAULT 1
    );

    -- ── СҮНГАА ──
    CREATE TABLE IF NOT EXISTS sungaa (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        aduu_id INTEGER, ognoo TEXT, turul TEXT, tailbar TEXT,
        dur TEXT, naadam_id INTEGER, uyaach_id INTEGER,
        unach TEXT, nas_angilal TEXT, bair INTEGER
    );

    -- ── УРАЛДААН (хуучин системээс) ──
    CREATE TABLE IF NOT EXISTS uraldaan (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        aduu_id INTEGER NOT NULL,
        ognoo TEXT, naadam_ner TEXT, bair TEXT,
        unach TEXT, tailbar TEXT, orig_id TEXT
    );

    -- ── ЗУРАГ ──
    CREATE TABLE IF NOT EXISTS zurag (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        aduu_id INTEGER, fayl TEXT, ognoo TEXT, tailbar TEXT, ner TEXT
    );

    -- ── ЭРҮҮЛ МЭНД ──
    CREATE TABLE IF NOT EXISTS eruul_mend (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        aduu_id INTEGER NOT NULL,
        ognoo TEXT,
        turul TEXT,        -- Тарилга / Эмчилгээ / Шимэгч устгал / Шүдний эмчилгээ / Бусад
        buten TEXT,        -- Бүтээгдэхүүн / Вакцин
        hemjee TEXT,       -- Тоо хэмжээ
        emch TEXT,
        tailbar TEXT,
        orig_id TEXT
    );

    -- ── ХЭМЖИЛТ ──
    CREATE TABLE IF NOT EXISTS hemjilt (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        aduu_id INTEGER NOT NULL,
        ognoo TEXT,
        jin REAL,           -- КГ
        undur REAL,         -- СМ
        tseezhiin_yas REAL, -- СМ
        urd_hol REAL,       -- СМ
        tailbar TEXT
    );

    -- ── ТАХ ──
    CREATE TABLE IF NOT EXISTS tah (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        aduu_id INTEGER NOT NULL,
        ognoo TEXT,
        daragiih_ognoo TEXT,
        turul TEXT,         -- Урд / Хойд / Тусгай
        tailbar TEXT,
        tahchin TEXT,
        orig_id TEXT
    );

    -- ── ТЭЖЭЭЛ ──
    CREATE TABLE IF NOT EXISTS tejeel (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        aduu_id INTEGER NOT NULL,
        tejeel_ner TEXT,
        ehleh_ognoo TEXT,
        duusah_ognoo TEXT,
        tailbar TEXT
    );

    -- ── АИЭ ШИНЖИЛГЭЭ (Цус багадалт) ──
    CREATE TABLE IF NOT EXISTS aie_shinjilgee (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        aduu_id INTEGER NOT NULL,
        ognoo TEXT,
        ur_dun TEXT,        -- Сөрөг / Эерэг
        aimag TEXT,
        laboratort TEXT,
        hariutsan TEXT,
        tailbar TEXT,
        orig_id TEXT
    );

    -- ── ХАВСРАЛ ФАЙЛ ──
    CREATE TABLE IF NOT EXISTS havsral (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        aduu_id INTEGER NOT NULL,
        fayl TEXT, ner TEXT, ognoo TEXT, tailbar TEXT
    );

    -- ── НӨХӨН ҮРЖИХҮЙ ──
    CREATE TABLE IF NOT EXISTS mori_soikh (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        aduu_id INTEGER NOT NULL,
        uyaach_id INTEGER,
        turul TEXT NOT NULL,
        ognoo TEXT,
        zai_km REAL,
        hugatsaa_min REAL,
        temp_c REAL,
        salhi_ms REAL,
        unach TEXT,
        honog INTEGER,
        tailbar TEXT,
        anhliin_tekst TEXT
    );

    -- ── POLAR HRM ӨГӨГДӨЛ ──
    CREATE TABLE IF NOT EXISTS polar_soikh (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        mori_soikh_id INTEGER,          -- mori_soikh-тай холбоос
        aduu_id INTEGER NOT NULL,
        uyaach_id INTEGER,
        ognoo TEXT,
        turul TEXT,                     -- Бага/Дунд/Их сүнгаа г.м.
        -- Үндсэн хэмжилтүүд
        zai_km REAL,
        hugatsaa_min REAL,
        hurd_dundaj REAL,               -- км/цаг
        -- Зүрхний цохилт
        zc_dundaj REAL,                 -- цох/мин
        zc_max REAL,
        zc_min REAL,
        -- Сэргэлт
        sergelt_1min REAL,              -- 1 минутын дараах ЗЦ
        sergelt_2min REAL,              -- 2 минутын дараах ЗЦ
        sergelt_indeks TEXT,            -- Маш сайн/Сайн/Дунд/Муу
        -- HRV
        hrv REAL,                       -- ms
        -- ЗЦ бүсийн хуваарилалт (%)
        zc_bus_amar REAL,               -- <100 цох/мин
        zc_bus_dund REAL,               -- 100-130
        zc_bus_huchten REAL,            -- 130-160
        zc_bus_ih_huch REAL,            -- 160-180
        zc_bus_deed REAL,               -- >180
        -- Training load
        training_load REAL,
        -- Дэлгэрэнгүй цуврал өгөгдөл (JSON)
        zc_series TEXT,                 -- секунд бүрийн ЗЦ
        gps_series TEXT,                -- GPS маршрут
        -- Эх сурвалж
        polar_exercise_id TEXT,         -- Polar-ийн exercise ID
        import_ognoo TEXT DEFAULT CURRENT_TIMESTAMP,
        tailbar TEXT
    );

    CREATE TABLE IF NOT EXISTS nokhon_urjikh (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        aduu_id INTEGER NOT NULL,
        ognoo TEXT, turul TEXT, tailbar TEXT, emch TEXT
    );

    -- ── БУСАД ──
    CREATE TABLE IF NOT EXISTS notification (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        uyaach_id INTEGER, aduu_id INTEGER, temdeglel_id INTEGER,
        tekst TEXT, unshlaa INTEGER DEFAULT 0,
        ognoo TEXT DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS uyaan_temdeglel (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        aduu_id INTEGER, uyaach_id INTEGER, ognoo TEXT,
        turul TEXT, zai_km REAL, hugatsaa_min REAL,
        tailbar TEXT, anhliin_tekst TEXT
    );

    CREATE TABLE IF NOT EXISTS ajil (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ner TEXT, tailbar TEXT, ognoo TEXT, tsag TEXT,
        davtalt TEXT DEFAULT 'ganc', erembe TEXT DEFAULT 'dundaj',
        status TEXT DEFAULT 'todorhoi', huvaarlisan_id INTEGER
    );

    CREATE TABLE IF NOT EXISTS sankhuu (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        turul TEXT, ognoo TEXT, dun REAL,
        angilal TEXT, tailbar TEXT, aduu_id INTEGER
    );
    """)

    # Үндсэн тохиргоонууд
    defaults = [
        ('zus','Хар'),('zus','Цагаан'),('zus','Улаан хүрэн'),('zus','Боро'),
        ('zus','Алаг'),('zus','Хүрэн'),('zus','Зээрд'),('zus','Шарга'),
        ('zus','Халиун'),('zus','Саарал'),('zus','Хээр'),('zus','Буурал'),
        ('zus','Бор'),('zus','Хонгор'),('zus','Хүрэн халзан'),
        ('zus','Хар буурал'),('zus','Хээр буурал'),('zus','Халиун халзан'),
        ('ugshil','Монгол адуу'),('ugshil','Хүнхэр адуу'),
        ('ugshil','Англи адуу'),('ugshil','Будан адуу'),
        ('garal','Дотоодын'),('garal','Гадаадын'),
        ('senas_bie','Зүүн хошуу'),('senas_bie','Баруун хошуу'),
        ('senas_bie','Хоёр хошуу'),('senas_bie','Шарагтай'),
        ('senas_tolgoi','Халзан'),('senas_tolgoi','Цагаан халзан'),
        ('senas_hel','Цагаан хөл'),('senas_hel','Дөрвөн цагаан'),
        # Морь сойхын ажлын төрөл
        ('soikh_turul','Амраах'),('soikh_turul','Гэдэс солих'),
        ('soikh_turul','Гишгүүлэх'),('soikh_turul','Хөлс авах'),
        ('soikh_turul','Тар'),('soikh_turul','Хангар'),
        ('soikh_turul','Бага сүнгаа'),('soikh_turul','Дунд сүнгаа'),
        ('soikh_turul','Их сүнгаа'),
    ]
    for t, n in defaults:
        conn.execute("INSERT OR IGNORE INTO tohiruulga (turul,ner) VALUES (?,?)", (t, n))

    conn.commit()
    conn.close()
    print("✅ DB бэлэн!")

if __name__ == "__main__":
    init_db()
