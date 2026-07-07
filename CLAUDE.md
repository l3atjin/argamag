# Argamag Equine Registry — Claude Code Context

## Системийн танилцуулга
Монгол морины бүртгэлийн систем. Хуучин Windows desktop программыг ("Хурдан Морины Програм") орлуулах зорилготой.
- **URL:** https://argamag.ai
- **GitHub:** https://github.com/l3atjin/argamag
- **Local:** ~/Desktop/horse/

## Stack
- **Backend:** FastAPI + SQLite (`backend/main.py`)
- **Frontend:** Vanilla JS, HTML/CSS (`frontend/index.html`)
- **DB:** `data/horse.db`
- **Hosting:** Fly.io
- **Server:** `python3 -m uvicorn backend.main:app --reload --port 8000`
- **Server restart:** `lsof -ti:8000 | xargs kill -9 && sleep 1 && python3 -m uvicorn backend.main:app --port 8000 --reload`

## DB-ийн чухал дүрмүүд
- `aduu.aduu_id` = хэрэглэгчийн харах ID (текст, жишээ нь "107006")
- `aduu.id` = системийн integer ID
- SQL-д **заавал alias** хэрэглэх: `aduu.id as system_id, aduu.aduu_id as horse_code` — SQLite column override bug гардаг
- **Cyrillic:** SQLite-ийн `UPPER()`/`LOWER()` Кирилл үсэгтэй ажиллахгүй → `database.py`-д `conn.create_function("LOWER", 1, lambda x: x.lower() if x else x)` хэрэглэнэ
- **Lineage адуу:** `idevhtei=0`, `status='udam'` — үндсэн жагсаалтад харагдахгүй, гэхдээ эцэг эх болгон холбоно

## Кодлох дүрмүүд (заавал дагах)
1. **Нэг өөрчлөлт нэг удаа** — олон зүйл нэгэн зэрэг бүү өөрчил, debug хэцүү болно
2. **SQL alias заавал** — дээрхийг үз
3. **JS pattern** — `createElement` + `addEventListener` хэрэглэ, `innerHTML` string concatenation бүү хэрэглэ (quote-escaping асуудал гардаг)
4. **Cyrillic** — дээрхийг үз
5. **Backup** — өөрчлөлтөөс өмнө ZIP хадгал (`~/Desktop/horse_YYYYMMDD.zip`)
6. **Verification** — backend өөрчилсний дараа шалга: `python3 -c "from backend.main import aduu_list; r=aduu_list(limit=1); assert r['total']>0"`
7. **Inspect before edit** — `sed -n 'START,ENDp' file` ашиглан тухайн мөрүүдийг уншсаны дараа засварла

## Одоогийн модулиуд
| Модуль | Байдал |
|---|---|
| Адуу бүртгэл | ✅ Ажиллаж байна (368 адуу) |
| Сүрэг удирдлага | ✅ Ажиллаж байна (24 сүрэг) |
| Уралдааны үр дүн | ✅ `sungaa` хүснэгт — цорын ганц эх үүсвэр |
| Удмын мод | ✅ 5 үе |
| Морь сойх | ✅ |
| Dashboard | ✅ Насны бүтэц, өсөлт, зүс, угшил |
| Арчилгааны хуваарь | 🔧 Хийж байгаа |
| Санхүү | 📋 Sidebar-д байгаа, хийгдээгүй |

## Адууны профайлын табууд

### Одоогийн 12 таб
Үндсэн · Зураг · Удмын мод · Үр төл · Амжилт · Эруул мэнд · Хэмжилт · Тах · Тэжээл · АИЭ · Уяач · Морь сойх

### Шинэ 6 таб (төлөвлөсөн)
| Шинэ таб | Нэгтгэх табууд |
|---|---|
| Үндсэн | Үндсэн (хэвээр) |
| Гүйцэтгэл | Амжилт + Үр төл + Зураг |
| Эруул мэнд | Эруул мэнд + Хэмжилт + Тах + Тэжээл + АИЭ |
| Сургалт | Морь сойх + Уяач |
| Удмын мод | Удмын мод (хэвээр) |
| Арчилгаа | **ШИНЭ** — ажлын хуваарь, гүйцэтгэл |

## Арчилгааны хуваарь модуль

### DB хүснэгт
```sql
CREATE TABLE tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_type TEXT NOT NULL,
    -- Төрлүүд: 'vaccine','vet','hoof','pregnancy_check','branding','race','other'
    title TEXT,
    scheduled_date DATE NOT NULL,
    assignee TEXT,           -- Хариуцагч (малчин/ажилтан)
    external_provider TEXT,  -- Гадны үйлчилгээ (малын эмч гэх мэт)
    horse_link_type TEXT,    -- 'specific','herd','filter'
    herd_id INTEGER,         -- horse_link_type='herd' үед
    filter_json TEXT,        -- horse_link_type='filter' үед (нас, хүйс гэх мэт)
    recurrence TEXT,         -- 'none','yearly','quarterly','monthly'
    notes TEXT,
    status TEXT DEFAULT 'planned', -- 'planned','done','late','cancelled'
    completed_date DATE,
    completion_notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE task_horses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id INTEGER REFERENCES tasks(id),
    horse_id INTEGER REFERENCES aduu(id)
);

CREATE TABLE task_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id INTEGER REFERENCES tasks(id),
    action TEXT,             -- 'completed','late','cancelled'
    reason TEXT,
    new_date DATE,           -- Хоцорсон үед шинэ огноо
    logged_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### Ажлын төрлүүд
```python
TASK_TYPES = {
    'vaccine': 'Вакцин хийлгэх',
    'vet': 'Малын эмчийн үзлэг',
    'hoof': 'Туурай засах',
    'pregnancy_check': 'Гүүний хээл шалгах',
    'branding': 'Унага тамгалах',
    'race': 'Уралдах хуваарь',
    'other': 'Бусад'
}
```

### API endpoints
| Method | Path | Зориулалт |
|---|---|---|
| GET | `/api/tasks` | Жагсаалт (сар/сүрэг/хариуцагчаар шүүх) |
| POST | `/api/tasks` | Шинэ ажил |
| PUT | `/api/tasks/{id}` | Засах |
| POST | `/api/tasks/{id}/complete` | Дууссан тэмдэглэх |
| POST | `/api/tasks/{id}/late` | Хоцорсон + шалтгаан |
| POST | `/api/tasks/{id}/cancel` | Цуцлах |
| GET | `/api/tasks/horse/{horse_id}` | Тухайн адууны ажлуудын түүх |
| GET | `/api/tasks/upcoming` | Ойрын 7 хоногийн ажлууд (dashboard) |

### Статусын урсгал
```
Төлөвлөсөн → Дууссан (огноо + тэмдэглэл)
           → Хоцорсон (шалтгаан + шинэ огноо → шинэ task автоматаар үүснэ)
           → Цуцалсан (шалтгаан)
```

### Давтагдах логик
- `yearly` → дараагийн жилийн мөн огноо
- `quarterly` → 3 сарын дараа
- `monthly` → 1 сарын дараа
- `none` → давтахгүй

### UI — Хуваарийн хуудас (3 таб)
1. **Хуанли** — сарын grid, өнгөөр ялгасан
2. **Жагсаалт** — шүүлттэй жагсаалт, статус харагдана
3. **Давтагдах** — давтагдах ажлуудын тохиргоо

### Адуу сонгогч (Шинэ ажил / Ажил засах форм)
`horse_link_type='specific'` үед scroll multi-select-ийг хайлттай picker-ээр сольсон (`.hp-*` класс, `ajilHP*` функцууд):
- **Хайлтын input** — нэр / № дугаар / registration_code / зүсээр шүүнэ. JS `toLowerCase()` ашигласан тул Cyrillic зөв (SQLite `UPPER/LOWER`-ийн Кирилл алдаанаас ялгаатай)
- **Сонгосон адуу** — X товчтой badge, тус бүрийг хасна (`createElement`, escape-гүй)
- **"+ Сүргээр нэмэх" dropdown** — сүргийн бүх адууг badge болгон нэмнэ, тус бүр хасагдана
- State: `window._ajilHP = {all:[], sel:Map}`; `saveAjil` нь `sel`-ээс `horse_ids` авна
- `herd`, `filter` link type-ууд хэвээр (dynamic семантик эвдээгүй)
- Live дээр E2E батлагдсан (create/edit/delete)

### Ажлын төрлийн өнгө
```css
vaccine:          #1D9E75  /* ногоон */
vet:              #378ADD  /* цэнхэр */
hoof:             #EF9F27  /* шар */
branding:         #D4537E  /* ягаан */
race:             #7F77DD  /* нил */
pregnancy_check:  #639922  /* гүн ногоон */
```

## UI Color Palette
```css
--sidebar-bg: #1A1710
--main-bg:    #F2EFE8
--amber:      #B8860B
--amber-m:    #E5A820
--amber-d:    #8B6508
--amber-l:    #FDF3DC
--card-bg:    #FFFFFF
```

## Одоо байгаа алдаанууд
- [x] ~~Pedigree endpoint 500 error~~ — зассан: `/api/horses/{id}/pedigree` нь `id: int` авч `registration_code AS horse_id` alias-тай зөв ажиллаж байна
- [x] ~~GitHub-д push хийгдээгүй~~ — remote-той синк болсон (origin/main)

## Ирээдүйн төлөвлөгөө
1. 🔧 Арчилгааны хуваарь модуль (одоо хийж байгаа)
2. Профайлын таб цөөлөх (12 → 6)
3. Олон хэрэглэгч / нэвтрэх систем
4. Зургийн хавсралт
5. Санхүүгийн модуль
6. Garmin Blaze / Polar H10 интеграц судлах
7. React Native гар утасны апп (offline-capable)

## Технологийн жагсаалт
- **Backend:** FastAPI, SQLite, Python 3, Uvicorn
- **Frontend:** Vanilla JS, HTML/CSS (нэг `index.html` файл)
- **Charts:** Chart.js
- **Hosting:** Fly.io + GitHub (l3atjin акаунт)
- **Dev tools:** Terminal (Mac), `sed`, `python3` scripts, `flyctl`, Claude Code
- **Data migration:** Legacy MDB (`khurdanmori.mdb`) → mdbtools ашиглан хөрвүүлсэн
