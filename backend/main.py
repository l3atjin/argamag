from fastapi import FastAPI, HTTPException, Form
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
import csv, io
from pydantic import BaseModel
from typing import Optional, List
import os, sys
sys.path.insert(0, os.path.dirname(__file__))
from database import get_db, init_db

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
FRONTEND = os.path.join(os.path.dirname(__file__), "../frontend")
if os.path.exists(FRONTEND):
    app.mount("/static", StaticFiles(directory=FRONTEND), name="static")
UPLOADS = os.path.join(os.path.dirname(__file__), "../frontend/uploads")
os.makedirs(UPLOADS, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=UPLOADS), name="uploads")

@app.on_event("startup")
def startup():
    init_db()
    conn = get_db()
    # training_plan хүснэгт үүсгэх
    conn.execute("""CREATE TABLE IF NOT EXISTS training_plan (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        horse_id INTEGER NOT NULL,
        trainer_id INTEGER,
        date TEXT NOT NULL,
        type TEXT NOT NULL,
        status TEXT DEFAULT 'planned',
        notes TEXT,
        created_at TEXT DEFAULT (datetime('now'))
    )""")
    conn.commit()
    conn.close()
    # practice_race хүснэгтэд шинэ талбар нэмэх migration
    conn = get_db()
    new_cols = [
        ("naadam_type", "TEXT"),   # Улсын/Аймгийн/Сумын/Бусад
        ("naadam_name",   "TEXT"),   # Улсын наадам/Их хурд/...
        ("province",        "TEXT"),   # Аймгийн нэр
        ("sum",          "TEXT"),   # Сумын нэр
        ("owner_text",    "TEXT"),   # Эзэмшигч
        ("breed_text",       "TEXT"),   # Угшил
        ("distance_km",       "REAL"),   # Уралдсан зай
        ("time",         "TEXT"),
        ("venue",        "TEXT"),
    ]
    existing = [row[1] for row in conn.execute("PRAGMA table_info(practice_race)").fetchall()]
    for col, typ in new_cols:
        if col not in existing:
            conn.execute(f"ALTER TABLE practice_race ADD COLUMN {col} {typ}")
    conn.commit()
    conn.close()

@app.get("/")
def root(): return FileResponse(os.path.join(FRONTEND, "index.html"))

# ── STATS ──
class GeldingIn(BaseModel):
    horse_id: int
    date: str
    performed_by: Optional[str]=None
    notes: Optional[str]=None

@app.get("/api/stats")
def stats():
    conn = get_db()
    return {
        "total": conn.execute("SELECT COUNT(*) FROM horse WHERE active=1").fetchone()[0],
        "stallion": conn.execute("SELECT COUNT(*) FROM horse WHERE sex='stallion' AND active=1").fetchone()[0],
        "mare": conn.execute("SELECT COUNT(*) FROM horse WHERE sex='mare' AND active=1").fetchone()[0],
        "herd": conn.execute("SELECT COUNT(*) FROM herd WHERE active=1").fetchone()[0],
        "contact": conn.execute("SELECT COUNT(*) FROM contact").fetchone()[0],
        "task_pending": conn.execute("SELECT COUNT(*) FROM task WHERE status='pending'").fetchone()[0],
    }

# ── ADUU ──
@app.get("/api/horses")
def horse_list(
    name: Optional[str]=None,
    horse_id: Optional[str]=None,
    number: Optional[str]=None,
    sex: Optional[str]=None,
    status: Optional[str]=None,
    herd_id: Optional[int]=None,
    breed_id: Optional[int]=None,
    color_id: Optional[int]=None,
    owner_id: Optional[int]=None,
    herder_id: Optional[int]=None,
    chip: Optional[str]=None,
    birth_date_type: Optional[str]=None,
    birth_date_date: Optional[str]=None,
    birth_date_date2: Optional[str]=None,
    birth_date_on: Optional[str]=None,
    active: Optional[int]=1,
    limit: int=50,
    offset: int=0,
    export: int=0
):
    conn = get_db()
    sql = """SELECT a.id,a.name,a.sex,a.birth_date,a.status,a.registration_code,a.number,
        a.chip,a.important,a.herd_id, s.name as herd_name, tz.name as color_name, tu.name as breed_name,
        hm.name as herder_name, h.name as owner_name,
        e.name as sire_name, m.name as dam_name
        FROM horse a
        LEFT JOIN herd s ON a.herd_id=s.id
        LEFT JOIN option tz ON a.color_id=tz.id
        LEFT JOIN option tu ON a.breed_id=tu.id
        LEFT JOIN contact hm ON a.herder_id=hm.id
        LEFT JOIN horse_owner ae ON a.id=ae.horse_id
        LEFT JOIN contact h ON ae.owner_id=h.id
        LEFT JOIN horse e ON a.sire_id=e.id
        LEFT JOIN horse m ON a.dam_id=m.id
        WHERE (? IS NULL OR a.active=?)"""
    p = [active, active]
    if name: sql += " AND UPPER(a.name) LIKE UPPER(?)"; p.append(f"%{name}%")
    if horse_id: sql += " AND a.registration_code LIKE ?"; p.append(f"%{horse_id}%")
    if number: sql += " AND a.number LIKE ?"; p.append(f"%{number}%")
    if sex:
        sex_db = 'stallion' if sex == 'er' else ('mare' if sex == 'ohin' else ('gelding' if sex == 'gelding' else sex))
        sql += " AND a.sex=?"; p.append(sex_db)
    if status == 'foaling':
        sql += " AND a.sex='mare' AND EXISTS(SELECT 1 FROM breeding_event n WHERE n.horse_id=a.id AND n.type='foaling')"; 
    elif status == 'bred':
        import datetime
        this_yr = datetime.date.today().year
        this_year = str(this_yr)
        sql += """ AND a.sex='mare'
            AND a.birth_date IS NOT NULL
            AND (?-CAST(strftime('%Y',a.birth_date) AS INT)+1)>=4
            AND NOT EXISTS(SELECT 1 FROM horse u WHERE u.dam_id=a.id AND strftime('%Y',u.birth_date)=?)
            AND NOT EXISTS(SELECT 1 FROM breeding_event n WHERE n.horse_id=a.id AND n.type='foaling' AND strftime('%Y',n.date)=?)"""
        p += [this_yr, this_year, this_year]
    elif status:
        sql += " AND a.status=?"; p.append(status)
    if herd_id: sql += " AND a.herd_id=?"; p.append(herd_id)
    if breed_id: sql += " AND a.breed_id=?"; p.append(breed_id)
    if color_id: sql += " AND a.color_id=?"; p.append(color_id)
    if herder_id: sql += " AND a.herder_id=?"; p.append(herder_id)
    if owner_id: sql += " AND ae.owner_id=?"; p.append(owner_id)
    if chip: sql += " AND a.chip LIKE ?"; p.append(f"%{chip}%")
    if birth_date_on: sql += " AND strftime('%Y', a.birth_date)=?"; p.append(str(birth_date_on))
    if birth_date_type == "omno" and birth_date_date: sql += " AND a.birth_date < ?"; p.append(birth_date_date)
    elif birth_date_type == "daraa" and birth_date_date: sql += " AND a.birth_date > ?"; p.append(birth_date_date)
    elif birth_date_type == "dotor" and birth_date_date and birth_date_date2: sql += " AND a.birth_date BETWEEN ? AND ?"; p += [birth_date_date, birth_date_date2]
    # Нийт тоо болон хүйсийн тоог тусад нь тооцох
    rows_all = conn.execute(sql + " GROUP BY a.id ORDER BY a.name", p).fetchall()
    total = len(rows_all)
    male_count = sum(1 for r in rows_all if r['sex'] in ('stallion','er','gelding'))
    female_count = sum(1 for r in rows_all if r['sex'] in ('mare','ohin'))
    if export:
        conn.close()
        return {"total": total, "male_count": male_count, "female_count": female_count, "data": [dict(r) for r in rows_all]}
    rows = rows_all[offset:offset+limit]
    conn.close()
    return {"total": total, "male_count": male_count, "female_count": female_count, "data": [dict(r) for r in rows]}

@app.get("/api/horses/export/csv")
def horse_export_csv(
    name: Optional[str]=None, horse_id: Optional[str]=None, number: Optional[str]=None,
    sex: Optional[str]=None, status: Optional[str]=None, herd_id: Optional[int]=None,
    breed_id: Optional[int]=None, color_id: Optional[int]=None, owner_id: Optional[int]=None,
    herder_id: Optional[int]=None, chip: Optional[str]=None, birth_date_on: Optional[str]=None,
    active: Optional[int]=1
):
    import datetime
    conn = get_db()
    sql = """SELECT a.name,a.registration_code,a.number,a.sex,a.birth_date,
        tz.name as color_name, tu.name as breed_name,
        e.name as sire_name, m.name as dam_name,
        h.name as owner_name, s.name as herd_name, a.status, a.chip, a.passport
        FROM horse a
        LEFT JOIN herd s ON a.herd_id=s.id
        LEFT JOIN option tz ON a.color_id=tz.id
        LEFT JOIN option tu ON a.breed_id=tu.id
        LEFT JOIN horse_owner ae ON a.id=ae.horse_id
        LEFT JOIN contact h ON ae.owner_id=h.id
        LEFT JOIN horse e ON a.sire_id=e.id
        LEFT JOIN horse m ON a.dam_id=m.id
        WHERE (? IS NULL OR a.active=?)"""
    p = [active, active]
    if name: sql += " AND UPPER(a.name) LIKE UPPER(?)"; p.append(f"%{name}%")
    if horse_id: sql += " AND a.registration_code LIKE ?"; p.append(f"%{horse_id}%")
    if number: sql += " AND a.number LIKE ?"; p.append(f"%{number}%")
    if sex:
        sex_db = 'stallion' if sex=='er' else ('mare' if sex=='ohin' else sex)
        sql += " AND a.sex=?"; p.append(sex_db)
    if status: sql += " AND a.status=?"; p.append(status)
    if herd_id: sql += " AND a.herd_id=?"; p.append(herd_id)
    if breed_id: sql += " AND a.breed_id=?"; p.append(breed_id)
    if color_id: sql += " AND a.color_id=?"; p.append(color_id)
    if owner_id: sql += " AND ae.owner_id=?"; p.append(owner_id)
    if chip: sql += " AND a.chip LIKE ?"; p.append(f"%{chip}%")
    if birth_date_on: sql += " AND strftime('%Y',a.birth_date)=?"; p.append(str(birth_date_on))
    rows = conn.execute(sql + " GROUP BY a.id ORDER BY a.name", p).fetchall()
    conn.close()
    HUISMAP = {'stallion':'Азарга','mare':'Гүү','er':'Эр','ohin':'Охин','gelding':'Морь','colt':'Унага эр','filly':'Унага охин'}
    output = io.StringIO()
    output.write('\ufeff')  # BOM — Excel монгол тэмдэгт зөв харуулна
    writer = csv.writer(output)
    writer.writerow(['Нэр','ID','№','Хүйс','Зүс','Төрсөн','Угшил','Эцэг','Эх','Эзэмшигч','Сүрэг','Статус','Чип','Паспорт'])
    for r in rows:
        writer.writerow([
            r['name']or'', r['horse_id']or'', r['number']or'',
            HUISMAP.get(r['sex'],r['sex']or''),
            r['color_name']or'', r['birth_date']or'', r['breed_name']or'',
            r['sire_name']or'', r['dam_name']or'', r['owner_name']or'',
            r['herd_name']or'', r['status']or'', r['chip']or'', r['passport']or''
        ])
    filename = f"horse_{datetime.date.today().isoformat()}.csv"
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{filename}"}
    )

@app.get("/api/horses/{id}/pedigree")
def horse_pedigree(id: int, ue: int=3):
    conn = get_db()
    def get_node(aid, depth):
        if not aid or depth > ue: return None
        r = conn.execute("SELECT id,name,sex,birth_date,horse_id,number,sire_id,dam_id FROM horse WHERE id=?", (aid,)).fetchone()
        if not r: return None
        node = dict(r)
        if depth < ue:
            node['eceg'] = get_node(r['sire_id'], depth+1)
            node['eh'] = get_node(r['dam_id'], depth+1)
        return node
    return get_node(id, 0) or {}


@app.get("/api/horses/check_registration")
def horse_check_registration(registration_code: str, exclude_id: Optional[int]=None):
    conn = get_db()
    sql = "SELECT id, name FROM horse WHERE registration_code=?"
    p = [registration_code]
    if exclude_id:
        sql += " AND id!=?"
        p.append(exclude_id)
    r = conn.execute(sql, p).fetchone()
    conn.close()
    if r:
        return {"exists": True, "name": r["name"], "id": r["id"]}
    return {"exists": False}

@app.get("/api/horses/gelding_eligible")
def gelding_eligible(owner_id: Optional[int]=None, nas_min: int=3, nas_max: Optional[int]=None):
    import datetime
    conn = get_db()
    this_year = datetime.date.today().year
    sql = (
        "SELECT a.id, a.name, a.birth_date, a.sex, a.registration_code, h.name as owner_name, h.id as ez_id "
        "FROM horse a "
        "LEFT JOIN horse_owner ae ON a.id=ae.horse_id "
        "LEFT JOIN contact h ON ae.owner_id=h.id "
        "WHERE a.sex='stallion' AND a.active=1 AND a.birth_date IS NOT NULL"
    )
    p = []
    if owner_id:
        sql += " AND ae.owner_id=?"
        p.append(owner_id)
    rows = conn.execute(sql, p).fetchall()
    seen = set()
    result = []
    for r in rows:
        if r['id'] in seen: continue
        seen.add(r['id'])
        age = this_year - int(r['birth_date'][:4]) + 1
        if age < nas_min: continue
        if nas_max and age > nas_max: continue
        result.append({'id': r['id'], 'name': r['name'], 'birth_date': r['birth_date'],
                      'sex': r['sex'], 'registration_code': r['registration_code'], 'age': age,
                      'owner_name': r['owner_name'], 'owner_id': r['ez_id']})
    conn.close()
    return result

@app.get("/api/horses/{id}")
def horse_detail(id: int):
    conn = get_db()
    r = conn.execute("""SELECT a.*,s.name as herd_name,tz.name as color_name,tu.name as breed_name,
        tg.name as origin_name,h.name as herder_name,z.name as stable_name,
        e.name as sire_name, m.name as dam_name
        FROM horse a
        LEFT JOIN herd s ON a.herd_id=s.id
        LEFT JOIN option tz ON a.color_id=tz.id
        LEFT JOIN option tu ON a.breed_id=tu.id
        LEFT JOIN option tg ON a.origin_id=tg.id
        LEFT JOIN contact h ON a.herder_id=h.id
        LEFT JOIN stable z ON a.stable_id=z.id
        LEFT JOIN horse e ON a.sire_id=e.id
        LEFT JOIN horse m ON a.dam_id=m.id
        WHERE a.id=?""", (id,)).fetchone()
    if not r: raise HTTPException(404,"Олдсонгүй")
    d = dict(r)
    d['owners'] = [dict(x) for x in conn.execute(
        "SELECT h.id as contact_id,h.name,ae.share_percent FROM horse_owner ae JOIN contact h ON ae.owner_id=h.id WHERE ae.horse_id=?", (id,)).fetchall()]
    d['practice_race'] = [dict(x) for x in conn.execute("SELECT * FROM practice_race WHERE horse_id=? ORDER BY date DESC",(id,)).fetchall()]
    d['photos'] = [dict(x) for x in conn.execute("SELECT * FROM photo WHERE horse_id=?",(id,)).fetchall()]
    return d

class HorseIn(BaseModel):
    name: str
    registered: Optional[int]=1
    registration_code: Optional[str]=None
    no_id: Optional[int]=0
    number: Optional[str]=None
    sex: Optional[str]=None
    breed_id: Optional[int]=None
    blood_percentage: Optional[str]=None
    origin_id: Optional[int]=None
    herd_id: Optional[int]=None
    color_id: Optional[int]=None
    status: Optional[str]='active'
    birth_date: Optional[str]=None
    birth_date_unknown: Optional[int]=0
    chip: Optional[str]=None
    passport: Optional[str]=None
    dna: Optional[str]=None
    body_marking: Optional[str]=None
    head_marking: Optional[str]=None
    leg_marking: Optional[str]=None
    brand: Optional[str]=None
    stable_id: Optional[int]=None
    location: Optional[str]=None
    herder_id: Optional[int]=None
    notes: Optional[str]=None
    personal_note: Optional[str]=None
    gelded: Optional[int]=0
    sire_id: Optional[int]=None
    dam_id: Optional[int]=None
    owners: Optional[List[dict]]=[]
    important: Optional[int]=0

@app.post("/api/horses")
def horse_create(d: HorseIn):
    conn = get_db()
    # registration_code давхардал шалгах
    if d.registration_code and not d.no_id:
        existing = conn.execute("SELECT id, name FROM horse WHERE registration_code=?", (d.registration_code,)).fetchone()
        if existing:
            raise HTTPException(400, f"ID {d.registration_code} давхардаж байна! ({existing['name']})")
    cur = conn.execute("""INSERT INTO horse (name,registered,registration_code,no_id,number,sex,breed_id,blood_percentage,origin_id,herd_id,color_id,status,birth_date,birth_date_unknown,chip,passport,dna,body_marking,head_marking,leg_marking,brand,stable_id,location,herder_id,notes,personal_note,gelded,sire_id,dam_id,important)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (d.name,d.registered,d.registration_code,d.no_id,d.number,d.sex,d.breed_id,d.blood_percentage,d.origin_id,d.herd_id,d.color_id,d.status,d.birth_date,d.birth_date_unknown,d.chip,d.passport,d.dna,d.body_marking,d.head_marking,d.leg_marking,d.brand,d.stable_id,d.location,d.herder_id,d.notes,d.personal_note,d.gelded,d.sire_id,d.dam_id,d.important or 0))
    aid = cur.lastrowid
    for e in (d.owners or []):
        if e.get('contact_id'):
            conn.execute("INSERT INTO horse_owner (horse_id,owner_id,share_percent) VALUES (?,?,?)",(aid,e['contact_id'],e.get('share_percent',100)))
    conn.commit(); return {"id": aid}

@app.put("/api/horses/{id}")
def horse_update(id: int, d: HorseIn):
    conn = get_db()
    # registration_code давхардал шалгах (өөрийн id-г хасч)
    if d.registration_code and not d.no_id:
        existing = conn.execute("SELECT id, name FROM horse WHERE registration_code=? AND id!=?", (d.registration_code, id)).fetchone()
        if existing:
            raise HTTPException(400, f"ID {d.registration_code} давхардаж байна! ({existing['name']})")
    conn.execute("""UPDATE horse SET name=?,registered=?,registration_code=?,number=?,sex=?,breed_id=?,blood_percentage=?,origin_id=?,herd_id=?,color_id=?,status=?,birth_date=?,chip=?,passport=?,dna=?,body_marking=?,head_marking=?,leg_marking=?,brand=?,stable_id=?,location=?,herder_id=?,notes=?,gelded=?,sire_id=?,dam_id=?,important=? WHERE id=?""",
        (d.name,d.registered,d.registration_code,d.number,d.sex,d.breed_id,d.blood_percentage,d.origin_id,d.herd_id,d.color_id,d.status,d.birth_date,d.chip,d.passport,d.dna,d.body_marking,d.head_marking,d.leg_marking,d.brand,d.stable_id,d.location,d.herder_id,d.notes,d.gelded,d.sire_id,d.dam_id,d.important or 0,id))
    conn.execute("DELETE FROM horse_owner WHERE horse_id=?", (id,))
    for e in (d.owners or []):
        if e.get('contact_id'):
            conn.execute("INSERT INTO horse_owner (horse_id,owner_id,share_percent) VALUES (?,?,?)",(id,e['contact_id'],e.get('share_percent',100)))
    conn.commit(); return {"ok": True}


def age_label(birth_date: str, sex: str, gelded: int = 0) -> str:
    """Монгол адууны нас, нэршил тооцох"""
    if not birth_date:
        return ""
    from datetime import date
    try:
        born = date.fromisoformat(birth_date[:10])
    except:
        return ""
    today = date.today()
    # Монгол тооллоор: төрсөн жил = 1 нас
    nas = today.year - born.year + 1
    er = sex in ('stallion', 'er')
    if nas == 1:
        return "Эр унага" if er else "Эм унага"
    elif nas == 2:
        return "Эр даага" if er else "Охин даага"
    elif nas == 3:
        return "Шүдлэн үрээ" if er else "Шүдлэн байдас"
    elif nas == 4:
        return "Хязаалан үрээ" if er else "Хязаалан байдас"
    elif nas == 5:
        return "Соёолон үрээ" if er else "Соёолон байдас"
    elif nas == 6:
        return "Хавчиг морь" if er else "Хавчиг гүү"
    else:
        if er:
            return "Морь" if gelded else "Азарга"
        return "Гүү"

# ── HAILT ──
@app.get("/api/search")
def search(q: str="", sex: Optional[str]=None, include_pedigree: int=0, number: Optional[str]=None):
    conn = get_db()
    if number:
        # Эхлэлээс яг тохирох, дараа нь хаана ч байсан хайх
        sql = """SELECT a.id,a.name,a.sex,a.birth_date,a.number,tz.name as color_name,a.active
            FROM horse a LEFT JOIN option tz ON a.color_id=tz.id
            WHERE a.number=?"""
        p = [number]
        if sex: sql += " AND a.sex=?"; p.append(sex)
        rows = conn.execute(sql + " LIMIT 15", p).fetchall()
        if not rows:
            # Яг тохирохгүй бол эхлэлээс хайх
            sql2 = sql.replace("a.number=?", "a.number LIKE ?")
            p2 = [f"{number}%"]
            if sex: p2.append(sex)
            rows = conn.execute(sql2 + " LIMIT 15", p2).fetchall()
        return [dict(r) for r in rows]
    if include_pedigree:
        sql = "SELECT a.id,a.name,a.sex,a.birth_date,a.number,tz.name as color_name,a.active FROM horse a LEFT JOIN option tz ON a.color_id=tz.id WHERE UPPER(a.name) LIKE UPPER(?)"
    else:
        sql = "SELECT a.id,a.name,a.sex,a.birth_date,a.number,tz.name as color_name,a.active FROM horse a LEFT JOIN option tz ON a.color_id=tz.id WHERE a.active=1 AND UPPER(a.name) LIKE UPPER(?)"
    p = [f"%{q}%"]
    if sex:
        sql += " AND a.sex=?"; p.append(sex)
    sql += " LIMIT 15"
    rows = []
    for r in conn.execute(sql, p).fetchall():
        d = dict(r)
        # SQLite dict-д давхардсан нэр авахад сүүлийнх нь давдаг
        # horse.id-г тусдаа авахын тулд cursor description ашиглана
        rows.append(d)
    # horse.id-г cursor-аас шууд авах
    cur = conn.execute(sql, p)
    cols = [desc[0] for desc in cur.description]
    for i, r in enumerate(cur.fetchall()):
        vals = list(r)
        for j, col in enumerate(cols):
            if col == 'horse_sys_id':
                rows[i]['horse_sys_id'] = vals[j]
    return rows

# ── UDAM BURTGEL ──
@app.get("/api/pedigree")
def pedigree_list(q: Optional[str]=None, sex: Optional[str]=None, limit: int=100, offset: int=0):
    conn = get_db()
    sql = """SELECT a.id,a.name,a.sex,a.birth_date,a.number,a.registration_code,
        tz.name as color_name, tu.name as breed_name, tg.name as origin_name,
        e.name as sire_name, m.name as dam_name
        FROM horse a
        LEFT JOIN option tz ON a.color_id=tz.id
        LEFT JOIN option tu ON a.breed_id=tu.id
        LEFT JOIN option tg ON a.origin_id=tg.id
        LEFT JOIN horse e ON a.sire_id=e.id
        LEFT JOIN horse m ON a.dam_id=m.id
        WHERE a.active=0 AND a.status='pedigree'"""
    p = []
    if q: sql += " AND a.name LIKE ?"; p.append(f"%{q}%")
    if sex: sql += " AND a.sex=?"; p.append(sex)
    total = conn.execute(f"SELECT COUNT(*) FROM ({sql})", p).fetchone()[0]
    rows = conn.execute(sql + " ORDER BY a.name LIMIT ? OFFSET ?", p+[limit,offset]).fetchall()
    return {"total": total, "data": [dict(r) for r in rows]}

class PedigreeIn(BaseModel):
    name: str
    sex: Optional[str]=None
    birth_date: Optional[str]=None
    number: Optional[str]=None
    breed_id: Optional[int]=None
    origin_id: Optional[int]=None
    color_id: Optional[int]=None
    sire_id: Optional[int]=None
    dam_id: Optional[int]=None

@app.post("/api/pedigree")
def pedigree_create(d: PedigreeIn):
    conn = get_db()
    cur = conn.execute("""INSERT INTO horse (name,sex,birth_date,number,breed_id,origin_id,color_id,sire_id,dam_id,active,status,registered)
        VALUES (?,?,?,?,?,?,?,?,?,0,'pedigree',0)""",
        (d.name.upper(),d.sex,d.birth_date,d.number,d.breed_id,d.origin_id,d.color_id,d.sire_id,d.dam_id))
    conn.commit(); return {"id": cur.lastrowid}

@app.put("/api/pedigree/{id}")
def pedigree_update(id: int, d: PedigreeIn):
    conn = get_db()
    conn.execute("""UPDATE horse SET name=?,sex=?,birth_date=?,number=?,breed_id=?,origin_id=?,color_id=?,sire_id=?,dam_id=?
        WHERE id=? AND status='pedigree'""",
        (d.name.upper(),d.sex,d.birth_date,d.number,d.breed_id,d.origin_id,d.color_id,d.sire_id,d.dam_id,id))
    conn.commit(); return {"ok": True}

@app.delete("/api/pedigree/{id}")
def pedigree_delete(id: int):
    conn = get_db()
    refs = conn.execute("SELECT COUNT(*) FROM horse WHERE (sire_id=? OR dam_id=?) AND active=1",(id,id)).fetchone()[0]
    if refs > 0:
        raise HTTPException(400, f"Энэ адуу {refs} адууны удамд холбоотой, устгах боломжгүй")
    conn.execute("DELETE FROM horse WHERE id=? AND status='pedigree'",(id,))
    conn.commit(); return {"ok": True}

@app.post("/api/pedigree/{id}/promote")
def pedigree_promote(id: int):
    conn = get_db()
    r = conn.execute("SELECT id FROM horse WHERE id=? AND status='pedigree'",(id,)).fetchone()
    if not r: raise HTTPException(404,"Удам олдсонгүй")
    conn.execute("UPDATE horse SET active=1, status='active', registered=0 WHERE id=?",(id,))
    conn.commit(); return {"ok": True}

# ── ХӨНГӨЛӨХ ──
@app.post("/api/gelding_events")
def gelding_create(d: GeldingIn):
    conn = get_db()
    horse = conn.execute("SELECT sex, name FROM horse WHERE id=?", (d.horse_id,)).fetchone()
    if not horse:
        raise HTTPException(404, "Адуу олдсонгүй")
    if horse['sex'] not in ('stallion', 'er'):
        raise HTTPException(400, "Зөвхөн эр адуу хөнгөлөх боломжтой")
    conn.execute("UPDATE horse SET sex='gelding' WHERE id=?", (d.horse_id,))
    conn.execute("INSERT INTO gelding_event (horse_id, date, performed_by, notes) VALUES (?,?,?,?)",
        (d.horse_id, d.date, d.performed_by, d.notes))
    conn.commit()
    conn.close()
    return {"ok": True}

@app.get("/api/gelding_events")
def gelding_list(horse_id: Optional[int]=None):
    conn = get_db()
    sql = """SELECT h.*, a.name as horse_name FROM gelding_event h
             JOIN horse a ON h.horse_id=a.id WHERE 1=1"""
    p = []
    if horse_id:
        sql += " AND h.horse_id=?"
        p.append(horse_id)
    sql += " ORDER BY h.date DESC"
    rows = [dict(r) for r in conn.execute(sql, p).fetchall()]
    conn.close()
    return rows

@app.delete("/api/gelding_events/{id}")
def gelding_delete(id: int):
    conn = get_db()
    # Хөнгөлөлт устгахад sex-г буцаах
    h = conn.execute("SELECT horse_id FROM gelding_event WHERE id=?", (id,)).fetchone()
    if h:
        conn.execute("UPDATE horse SET sex='stallion' WHERE id=? AND sex='gelding'", (h['horse_id'],))
        conn.execute("DELETE FROM gelding_event WHERE id=?", (id,))
    conn.commit()
    conn.close()
    return {"ok": True}

# ── SURG ──
@app.get("/api/herds")
def herd_list():
    conn = get_db()
    return [dict(r) for r in conn.execute("""SELECT s.*,COUNT(ad.id) as horse_count
        FROM herd s 
        LEFT JOIN horse ad ON s.id=ad.herd_id AND ad.active=1
        WHERE s.active=1 GROUP BY s.id ORDER BY s.name""").fetchall()]

@app.get("/api/herds/{id}")
def herd_detail(id: int):
    conn = get_db()
    s = conn.execute("SELECT * FROM herd WHERE id=?", (id,)).fetchone()
    if not s: raise HTTPException(404,"Олдсонгүй")
    d = dict(s)
    d['horse_count'] = conn.execute("SELECT COUNT(*) FROM horse WHERE herd_id=? AND active=1",(id,)).fetchone()[0]
    return d

class HerdIn(BaseModel):
    name: str
    stallion_id: Optional[int]=None
    notes: Optional[str]=None

@app.post("/api/herds")
def herd_create(d: HerdIn):
    conn = get_db()
    cur = conn.execute("INSERT INTO herd (name,stallion_id,notes) VALUES (?,?,?)",(d.name,d.stallion_id,d.notes))
    conn.commit(); return {"id": cur.lastrowid}

# ── HOLBOO ──
@app.get("/api/contacts")
def contact_list(q: Optional[str]=None, type: Optional[str]=None):
    conn = get_db()
    sql = "SELECT h.*,COUNT(ae.id) as horse_count FROM contact h LEFT JOIN horse_owner ae ON h.id=ae.owner_id WHERE 1=1"
    p = []
    if q: sql += " AND h.name LIKE ?"; p.append(f"%{q}%")
    if type: sql += " AND h.type=?"; p.append(type)
    return [dict(r) for r in conn.execute(sql+" GROUP BY h.id ORDER BY h.name", p).fetchall()]

class ContactIn(BaseModel):
    name: str
    type: Optional[str]='owner_text'
    phone: Optional[str]=None
    email: Optional[str]=None
    city: Optional[str]=None
    address: Optional[str]=None

@app.post("/api/contacts")
def contact_create(d: ContactIn):
    conn = get_db()
    cur = conn.execute("INSERT INTO contact (name,type,phone,email,city,address) VALUES (?,?,?,?,?,?)",(d.name,d.type,d.phone,d.email,d.city,d.address))
    conn.commit(); return {"id": cur.lastrowid}

@app.get("/api/contacts/{id}")
def contact_get(id: int):
    conn = get_db()
    r = conn.execute("SELECT * FROM contact WHERE id=?", (id,)).fetchone()
    return dict(r) if r else {}

@app.delete("/api/contacts/{id}")
def contact_delete(id: int):
    conn = get_db()
    conn.execute("DELETE FROM contact WHERE id=?", (id,))
    conn.commit(); return {"ok": True}

@app.put("/api/contacts/{id}")
def contact_update(id: int, d: ContactIn):
    conn = get_db()
    conn.execute("UPDATE contact SET name=?,type=?,phone=?,email=?,city=?,address=? WHERE id=?",(d.name,d.type,d.phone,d.email,d.city,d.address,id))
    conn.commit(); return {"ok": True}

# ── TOHIRUULGA ──
@app.get("/api/options")
def option_list():
    conn = get_db()
    return [dict(r) for r in conn.execute("SELECT * FROM option WHERE active=1 ORDER BY type,name").fetchall()]

@app.post("/api/options")
def option_create(type: str=Form(...), name: str=Form(...)):
    conn = get_db()
    r = conn.execute("SELECT id FROM option WHERE type=? AND name=?",(type,name)).fetchone()
    if r: return {"id": r[0]}
    cur = conn.execute("INSERT INTO option (type,name) VALUES (?,?)",(type,name))
    conn.commit(); return {"id": cur.lastrowid}

@app.delete("/api/options/{id}")
def option_delete(id: int):
    conn = get_db()
    conn.execute("UPDATE option SET active=0 WHERE id=?",(id,))
    conn.commit(); return {"ok": True}

@app.put("/api/options/{id}")
def option_update(id: int, name: str = Form(...)):
    conn = get_db()
    conn.execute("UPDATE option SET name=? WHERE id=?", (name, id))
    conn.commit(); return {"ok": True}

# ── ZUCHEE ──
@app.get("/api/stables")
def stable_list(type: Optional[str]=None):
    conn = get_db()
    sql = "SELECT z.*,COUNT(a.id) as horse_count FROM stable z LEFT JOIN horse a ON z.id=a.stable_id WHERE z.active=1"
    p = []
    if type: sql += " AND z.type=?"; p.append(type)
    return [dict(r) for r in conn.execute(sql+" GROUP BY z.id ORDER BY z.name", p).fetchall()]

class StableIn(BaseModel):
    name: str
    type: Optional[str]='stable'
    location: Optional[str]='huvtee'
    row_count: Optional[int]=1
    column_count: Optional[int]=1

@app.post("/api/stables")
def stable_create(d: StableIn):
    conn = get_db()
    cur = conn.execute("INSERT INTO stable (name,type,location,row_count,column_count) VALUES (?,?,?,?,?)",(d.name,d.type,d.location,d.row_count,d.column_count))
    conn.commit(); return {"id": cur.lastrowid}

@app.delete("/api/stables/{id}")
def stable_delete(id: int):
    conn = get_db()
    conn.execute("UPDATE stable SET active=0 WHERE id=?",(id,))
    conn.commit(); return {"ok": True}

# ── AJIL ──
@app.get("/api/tasks")
def task_list(status: Optional[str]=None, limit: int=50):
    conn = get_db()
    sql = "SELECT aj.*,h.name as assigned_to_name FROM task aj LEFT JOIN contact h ON aj.assigned_to_id=h.id WHERE 1=1"
    p = []
    if status: sql += " AND aj.status=?"; p.append(status)
    return [dict(r) for r in conn.execute(sql+" ORDER BY aj.date LIMIT ?", p+[limit]).fetchall()]

class TaskIn(BaseModel):
    name: str
    notes: Optional[str]=None
    date: Optional[str]=None
    time: Optional[str]=None
    repeat: Optional[str]='once'
    priority: Optional[str]='dundaj'

@app.post("/api/tasks")
def task_create(d: TaskIn):
    conn = get_db()
    cur = conn.execute("INSERT INTO task (name,notes,date,time,repeat,priority) VALUES (?,?,?,?,?,?)",(d.name,d.notes,d.date,d.time,d.repeat,d.priority))
    conn.commit(); return {"id": cur.lastrowid}

@app.put("/api/tasks/{id}/status")
def task_status(id: int, status: str=Form(...)):
    conn = get_db()
    conn.execute("UPDATE task SET status=? WHERE id=?",(status,id))
    conn.commit(); return {"ok": True}

@app.delete("/api/tasks/{id}")
def task_delete(id: int):
    conn = get_db()
    conn.execute("DELETE FROM task WHERE id=?",(id,))
    conn.commit(); return {"ok": True}

# ── SUNGAA ──
@app.get("/api/practice_races")
def practice_race_list(horse_id: Optional[int]=None, naadam_id: Optional[int]=None):
    conn = get_db()
    sql = """SELECT sg.id,sg.horse_id,sg.trainer_id,sg.date,sg.type,sg.distance_text,sg.notes,
        sg.naadam_id,sg.jockey,sg.age_category,sg.rank,
        sg.naadam_type,sg.naadam_name,sg.province,sg.sum,
        sg.owner_text,sg.breed_text,sg.distance_km,sg.time,sg.venue,
        a.name as horse_name,
        a.birth_date as horse_birth_date,
        a.sex as horse_sex,
        a.gelded as horse_gelded,
        a.registration_code as horse_sys_id,
        a.number as horse_number,
        u.name as trainer_name,
        zus.name as color_name,
        ug.name as breed_name
        FROM practice_race sg
        JOIN horse a ON sg.horse_id=a.id
        LEFT JOIN trainer u ON sg.trainer_id=u.id
        LEFT JOIN option zus ON a.color_id=zus.id AND zus.type='color'
        LEFT JOIN option ug ON a.breed_id=ug.id AND ug.type='breed_text'
        WHERE 1=1"""
    p = []
    if horse_id: sql += " AND sg.horse_id=?"; p.append(horse_id)
    if naadam_id: sql += " AND sg.naadam_id=?"; p.append(naadam_id)
    sql += " ORDER BY sg.rank ASC, sg.date DESC LIMIT 200"
    return [dict(r) for r in conn.execute(sql, p).fetchall()]

class PracticeRaceIn(BaseModel):
    horse_id: int
    date: Optional[str]=None
    type: Optional[str]=None       # хуучин талбар — хэвээр үлдэнэ
    distance_text: Optional[str]=None
    notes: Optional[str]=None
    naadam_id: Optional[int]=None
    trainer_id: Optional[int]=None
    jockey: Optional[str]=None
    age_category: Optional[str]=None
    rank: Optional[int]=None
    # Шинэ талбарууд
    naadam_type: Optional[str]=None  # Улсын/Аймгийн/Сумын/Бусад
    naadam_name:   Optional[str]=None  # Улсын наадам/Их хурд/...
    province:        Optional[str]=None
    sum:          Optional[str]=None
    owner_text:    Optional[str]=None
    breed_text:       Optional[str]=None
    venue:        Optional[str]=None
    distance_km:       Optional[float]=None
    time:         Optional[str]=None
    distance_km:       Optional[float]=None
    time:         Optional[str]=None  # мм:сс.мс

@app.post("/api/practice_races")
def practice_race_create(d: PracticeRaceIn):
    conn = get_db()
    # naadam_name-ийг type талбарт хадгалах (хуучин системтэй нийцүүлэх)
    type = d.naadam_name or d.type
    cur = conn.execute(
        """INSERT INTO practice_race
           (horse_id,date,type,distance_text,notes,naadam_id,trainer_id,jockey,age_category,rank,
            naadam_type,naadam_name,province,sum,owner_text,breed_text,distance_km,time)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (d.horse_id,d.date,type,d.distance_text,d.notes,d.naadam_id,d.trainer_id,d.jockey,
         d.age_category,d.rank,d.naadam_type,d.naadam_name,d.province,d.sum,
         d.owner_text,d.breed_text,d.distance_km,d.time))
    conn.commit(); return {"id": cur.lastrowid}

@app.put("/api/practice_races/{id}")
def practice_race_update(id: int, d: PracticeRaceIn):
    conn = get_db()
    type = d.naadam_name or d.type
    conn.execute("""UPDATE practice_race SET
        horse_id=?,date=?,type=?,naadam_type=?,naadam_name=?,
        province=?,sum=?,owner_text=?,breed_text=?,
        age_category=?,rank=?,trainer_id=?,jockey=?,notes=?,
        distance_km=?,time=?,venue=?
        WHERE id=?""",
        (d.horse_id,d.date,type,d.naadam_type,d.naadam_name,
        d.province,d.sum,d.owner_text,d.breed_text,
        d.age_category,d.rank,d.trainer_id,d.jockey,d.notes,
        d.distance_km,d.time,d.venue,id))
    conn.commit()
    return {"ok":True}

@app.delete("/api/practice_races/{id}")
def practice_race_delete(id: int):
    conn = get_db()
    conn.execute("DELETE FROM practice_race WHERE id=?", (id,))
    conn.commit(); return {"ok": True}

# ── SANKHUU ──
@app.get("/api/finance")
def finance_record_list(limit: int=200):
    conn = get_db()
    data = [dict(r) for r in conn.execute("SELECT sk.*,a.name as horse_name FROM finance_record sk LEFT JOIN horse a ON sk.horse_id=a.id ORDER BY sk.date DESC LIMIT ?", (limit,)).fetchall()]
    orlogo = sum(r['amount'] for r in data if r['type']=='orlogo')
    zarlaga = sum(r['amount'] for r in data if r['type']=='zarlaga')
    return {"data": data, "orlogo": orlogo, "zarlaga": zarlaga, "tsever": orlogo-zarlaga}

class FinanceIn(BaseModel):
    type: str
    date: str
    amount: float
    category: Optional[str]=None
    notes: Optional[str]=None
    horse_id: Optional[int]=None

@app.post("/api/finance")
def finance_record_create(d: FinanceIn):
    conn = get_db()
    cur = conn.execute("INSERT INTO finance_record (type,date,amount,category,notes,horse_id) VALUES (?,?,?,?,?,?)",(d.type,d.date,d.amount,d.category,d.notes,d.horse_id))
    conn.commit(); return {"id": cur.lastrowid}

@app.delete("/api/finance/{id}")
def finance_record_delete(id: int):
    conn = get_db()
    conn.execute("DELETE FROM finance_record WHERE id=?",(id,))
    conn.commit(); return {"ok": True}

# ── МОРИ СОЙХЫН ТӨЛӨВЛӨГӨӨ ──────────────────────────────────
@app.get("/api/training_plans")
def plan_list(horse_id: Optional[int]=None, trainer_id: Optional[int]=None,
              sar: Optional[str]=None):
    conn = get_db()
    sql = """SELECT p.*,a.name as horse_name,a.registration_code as horse_number,
             u.name as trainer_name
             FROM training_plan p
             JOIN horse a ON p.horse_id=a.id
             LEFT JOIN trainer u ON p.trainer_id=u.id
             WHERE 1=1"""
    params = []
    if horse_id: sql += " AND p.horse_id=?"; params.append(horse_id)
    if trainer_id: sql += " AND p.trainer_id=?"; params.append(trainer_id)
    if sar: sql += " AND p.date LIKE ?"; params.append(sar+"%")
    sql += " ORDER BY p.date ASC"
    rows = [dict(r) for r in conn.execute(sql, params).fetchall()]
    conn.close()
    return rows

class TrainingPlanIn(BaseModel):
    horse_id: int
    trainer_id: Optional[int]=None
    date: str
    type: str
    status: Optional[str]="planned"
    notes: Optional[str]=None

@app.post("/api/training_plans")
def plan_create(d: TrainingPlanIn):
    conn = get_db()
    cur = conn.execute(
        "INSERT INTO training_plan (horse_id,trainer_id,date,type,status,notes) VALUES (?,?,?,?,?,?)",
        (d.horse_id, d.trainer_id, d.date, d.type, d.status or "planned", d.notes)
    )
    conn.commit()
    conn.close()
    return {"id": cur.lastrowid}

@app.put("/api/training_plans/{id}")
def plan_update(id: int, d: TrainingPlanIn):
    conn = get_db()
    conn.execute(
        "UPDATE training_plan SET horse_id=?,trainer_id=?,date=?,type=?,status=?,notes=? WHERE id=?",
        (d.horse_id, d.trainer_id, d.date, d.type, d.status or "planned", d.notes, id)
    )
    conn.commit()
    conn.close()
    return {"ok": True}

@app.delete("/api/training_plans/{id}")
def plan_delete(id: int):
    conn = get_db()
    conn.execute("DELETE FROM training_plan WHERE id=?", (id,))
    conn.commit()
    conn.close()
    return {"ok": True}

# Сарын нэгдсэн тайлан — уяач бүрийн адуу
@app.get("/api/training_plans/summary")
def plan_summary(trainer_id: Optional[int]=None, sar: Optional[str]=None):
    conn = get_db()
    sql = """SELECT p.horse_id, p.status, COUNT(*) as too
             FROM training_plan p WHERE 1=1"""
    params = []
    if trainer_id: sql += " AND p.trainer_id=?"; params.append(trainer_id)
    if sar: sql += " AND p.date LIKE ?"; params.append(sar+"%")
    sql += " GROUP BY p.horse_id, p.status"
    rows = [dict(r) for r in conn.execute(sql, params).fetchall()]
    conn.close()
    return rows

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)

@app.put("/api/herds/{id}")
def herd_update(id: int, d: HerdIn):
    conn = get_db()
    conn.execute("UPDATE herd SET name=?,stallion_id=?,notes=? WHERE id=?",(d.name,d.stallion_id,d.notes,id))
    conn.commit(); return {"ok": True}

@app.delete("/api/herds/{id}")
def herd_delete(id: int):
    conn = get_db()
    conn.execute("UPDATE herd SET active=0 WHERE id=?",(id,))
    conn.commit(); return {"ok": True}

# ── УЯАЧ ──
class TrainerIn(BaseModel):
    name: str
    phone: Optional[str]=None
    location: Optional[str]=None
    title: Optional[str]='none'
    notes: Optional[str]=None

@app.get("/api/trainers")
def trainer_list():
    conn = get_db()
    return [dict(r) for r in conn.execute(
        "SELECT u.*, COUNT(au.id) as horse_count FROM trainer u LEFT JOIN horse_trainer au ON u.id=au.trainer_id AND au.active=1 WHERE u.active=1 GROUP BY u.id ORDER BY u.name"
    ).fetchall()]

@app.get("/api/trainers/{id}")
def trainer_get(id: int):
    conn = get_db()
    u = conn.execute("SELECT * FROM trainer WHERE id=?", (id,)).fetchone()
    if not u: raise HTTPException(404, "Уяач олдсонгүй")
    horse = conn.execute("""
        SELECT a.id,a.name,a.sex,a.birth_date,a.number,a.gelded,au.start_date,au.end_date
        FROM horse_trainer au JOIN horse a ON au.horse_id=a.id
        WHERE au.trainer_id=? AND au.active=1 ORDER BY au.start_date DESC
    """, (id,)).fetchall()
    return {**dict(u), "horse": [dict(a) for a in horse]}

@app.post("/api/trainers")
def trainer_create(d: TrainerIn):
    conn = get_db()
    cur = conn.execute(
        "INSERT INTO trainer (name,phone,location,title,notes) VALUES (?,?,?,?,?)",
        (d.name,d.phone,d.location,d.title,d.notes))
    conn.commit(); return {"id": cur.lastrowid}

@app.put("/api/trainers/{id}")
def trainer_update(id: int, d: TrainerIn):
    conn = get_db()
    conn.execute("UPDATE trainer SET name=?,phone=?,location=?,title=?,notes=? WHERE id=?",
        (d.name,d.phone,d.location,d.title,d.notes,id))
    conn.commit(); return {"ok": True}

@app.delete("/api/trainers/{id}")
def trainer_delete(id: int):
    conn = get_db()
    conn.execute("UPDATE trainer SET active=0 WHERE id=?", (id,))
    conn.commit(); return {"ok": True}

# ── АДУУ-УЯАЧ ХОЛБОО ──
class HorseTrainerIn(BaseModel):
    horse_id: int
    trainer_id: int
    start_date: Optional[str]=None
    end_date: Optional[str]=None
    notes: Optional[str]=None

@app.get("/api/horse_trainers")
def horse_trainer_by_trainer(trainer_id: Optional[int]=None, horse_id: Optional[int]=None):
    conn = get_db()
    if trainer_id:
        return [dict(r) for r in conn.execute(
            "SELECT au.*, a.name as horse_name FROM horse_trainer au JOIN horse a ON au.horse_id=a.id WHERE au.trainer_id=? AND au.active=1 ORDER BY a.name",
            (trainer_id,)).fetchall()]
    if horse_id:
        return [dict(r) for r in conn.execute(
            "SELECT au.*,u.name as trainer_name,u.title FROM horse_trainer au JOIN trainer u ON au.trainer_id=u.id WHERE au.horse_id=? ORDER BY au.start_date DESC",
            (horse_id,)).fetchall()]
    return []

@app.get("/api/horses/{id}/trainer")
def horse_trainer_list(id: int):
    conn = get_db()
    return [dict(r) for r in conn.execute("""
        SELECT au.*,u.name as trainer_name,u.title
        FROM horse_trainer au JOIN trainer u ON au.trainer_id=u.id
        WHERE au.horse_id=? ORDER BY au.start_date DESC
    """, (id,)).fetchall()]

@app.post("/api/horse_trainers")
def horse_trainer_create(d: HorseTrainerIn):
    conn = get_db()
    cur = conn.execute(
        "INSERT INTO horse_trainer (horse_id,trainer_id,start_date,end_date,notes) VALUES (?,?,?,?,?)",
        (d.horse_id,d.trainer_id,d.start_date,d.end_date,d.notes))
    conn.commit(); return {"id": cur.lastrowid}

@app.put("/api/horse_trainers/{id}/end")
def horse_trainer_duusah(id: int):
    conn = get_db()
    from datetime import date
    conn.execute("UPDATE horse_trainer SET active=0, end_date=? WHERE id=?",
        (date.today().isoformat(), id))
    conn.commit(); return {"ok": True}

# ── УЯАНЫ ТЭМДЭГЛЭЛ ──
class TrainingNoteIn(BaseModel):
    horse_id: int
    trainer_id: int
    date: str
    type: str
    distance_km: Optional[float]=None
    duration_min: Optional[float]=None
    notes: Optional[str]=None
    original_text: Optional[str]=None

UYAAN_TURUL = ['Морь барих','Гишгүүлэлт','Хөлс','Хангар','Тар',
               'Бага сунгаа','Дунд сунгаа','Их сунгаа','Наадам']

@app.get("/api/training_notes")
def training_note_list(horse_id: Optional[int]=None, trainer_id: Optional[int]=None):
    conn = get_db()
    sql = """SELECT ut.*,a.name as horse_name,u.name as trainer_name
        FROM training_note ut
        JOIN horse a ON ut.horse_id=a.id
        JOIN trainer u ON ut.trainer_id=u.id WHERE 1=1"""
    p = []
    if horse_id: sql += " AND ut.horse_id=?"; p.append(horse_id)
    if trainer_id: sql += " AND ut.trainer_id=?"; p.append(trainer_id)
    sql += " ORDER BY ut.date DESC LIMIT 100"
    return [dict(r) for r in conn.execute(sql, p).fetchall()]

@app.post("/api/training_notes")
def training_note_create(d: TrainingNoteIn):
    conn = get_db()
    cur = conn.execute(
        "INSERT INTO training_note (horse_id,trainer_id,date,type,distance_km,duration_min,notes,original_text) VALUES (?,?,?,?,?,?,?,?)",
        (d.horse_id,d.trainer_id,d.date,d.type,d.distance_km,d.duration_min,d.notes,d.original_text))
    # Notification үүсгэх
    horse = conn.execute("SELECT name FROM horse WHERE id=?", (d.horse_id,)).fetchone()
    trainer = conn.execute("SELECT name FROM trainer WHERE id=?", (d.trainer_id,)).fetchone()
    if horse and trainer:
        text = f"{trainer['name']} уяач — {horse['name']}: {d.type}"
        if d.distance_km: text += f" {d.distance_km}км"
        if d.duration_min: text += f" {d.duration_min}мин"
        conn.execute("INSERT INTO notification (trainer_id,horse_id,note_id,text) VALUES (?,?,?,?)",
            (d.trainer_id, d.horse_id, cur.lastrowid, text))
    conn.commit(); return {"id": cur.lastrowid}

@app.delete("/api/training_notes/{id}")
def training_note_delete(id: int):
    conn = get_db()
    conn.execute("DELETE FROM training_note WHERE id=?", (id,))
    conn.commit(); return {"ok": True}

# ── NOTIFICATION ──
@app.get("/api/notification")
def notification_list(read: Optional[int]=None):
    conn = get_db()
    sql = "SELECT n.*,a.name as horse_name,u.name as trainer_name FROM notification n LEFT JOIN horse a ON n.horse_id=a.id LEFT JOIN trainer u ON n.trainer_id=u.id WHERE 1=1"
    p = []
    if read is not None: sql += " AND n.read=?"; p.append(read)
    sql += " ORDER BY n.date DESC LIMIT 50"
    return [dict(r) for r in conn.execute(sql, p).fetchall()]

@app.put("/api/notification/{id}/read")
def notification_read(id: int):
    conn = get_db()
    conn.execute("UPDATE notification SET read=1 WHERE id=?", (id,))
    conn.commit(); return {"ok": True}

@app.put("/api/notification/read_all")
def notification_all_read():
    conn = get_db()
    conn.execute("UPDATE notification SET read=1")
    conn.commit(); return {"ok": True}

# ── НААДАМ ──
class NaadamIn(BaseModel):
    name: str
    type: str
    subtype: Optional[str]=None
    date: Optional[str]=None
    location: Optional[str]=None
    notes: Optional[str]=None

@app.get("/api/naadam")
def naadam_list():
    conn = get_db()
    return [dict(r) for r in conn.execute(
        "SELECT * FROM naadam ORDER BY date DESC").fetchall()]

@app.post("/api/naadam")
def naadam_create(d: NaadamIn):
    conn = get_db()
    cur = conn.execute(
        "INSERT INTO naadam (name,type,subtype,date,location,notes) VALUES (?,?,?,?,?,?)",
        (d.name,d.type,d.subtype,d.date,d.location,d.notes))
    conn.commit(); return {"id": cur.lastrowid}

@app.put("/api/naadam/{id}")
def naadam_update(id: int, d: NaadamIn):
    conn = get_db()
    conn.execute("UPDATE naadam SET name=?,type=?,subtype=?,date=?,location=?,notes=? WHERE id=?",
        (d.name,d.type,d.subtype,d.date,d.location,d.notes,id))
    conn.commit(); return {"ok": True}

@app.delete("/api/naadam/{id}")
def naadam_delete(id: int):
    conn = get_db()
    conn.execute("DELETE FROM naadam WHERE id=?", (id,))
    conn.commit(); return {"ok": True}

# ── UPLOADS ──
UPLOADS = os.path.join(os.path.dirname(__file__), "../frontend/uploads")
os.makedirs(UPLOADS, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=UPLOADS), name="uploads")

# ── УРАЛДААН ──
class RaceIn(BaseModel):
    horse_id: int
    date: Optional[str]=None
    naadam_name: Optional[str]=None
    naadam_type: Optional[str]=None
    rank: Optional[str]=None
    jockey: Optional[str]=None
    notes: Optional[str]=None
    age_category: Optional[str]=None
    trainer_id: Optional[int]=None
    venue: Optional[str]=None
    province: Optional[str]=None
    sum: Optional[str]=None
    owner_text: Optional[str]=None
    distance_km: Optional[float]=None
    time: Optional[str]=None

@app.get("/api/races")
def race_list(horse_id: Optional[int]=None):
    conn = get_db()
    sql = "SELECT * FROM race WHERE 1=1"
    p = []
    if horse_id: sql += " AND horse_id=?"; p.append(horse_id)
    sql += " ORDER BY date DESC"
    return [dict(r) for r in conn.execute(sql, p).fetchall()]

@app.post("/api/races")
def race_create(d: RaceIn):
    conn = get_db()
    cur = conn.execute("INSERT INTO race (horse_id,date,naadam_name,rank,jockey,notes) VALUES (?,?,?,?,?,?)",
        (d.horse_id,d.date,d.naadam_name,d.rank,d.jockey,d.notes))
    conn.commit(); return {"id": cur.lastrowid}

@app.put("/api/races/{id}")
def race_update(id: int, d: RaceIn):
    conn = get_db()
    conn.execute("""UPDATE race SET
        horse_id=?,date=?,naadam_name=?,naadam_type=?,rank=?,jockey=?,notes=?,
        age_category=?,trainer_id=?,venue=?,province=?,sum=?,owner_text=?,distance_km=?,time=?
        WHERE id=?""",
        (d.horse_id,d.date,d.naadam_name,d.naadam_type,d.rank,d.jockey,d.notes,
         d.age_category,d.trainer_id,d.venue,d.province,d.sum,d.owner_text,d.distance_km,d.time,id))
    conn.commit()
    return {"ok": True}

@app.delete("/api/races/{id}")
def race_delete(id: int):
    conn = get_db()
    conn.execute("DELETE FROM race WHERE id=?", (id,))
    conn.commit(); return {"ok": True}

# ── ЭРҮҮЛ МЭНД ──
class HealthRecordIn(BaseModel):
    horse_id: int
    date: Optional[str]=None
    type: Optional[str]=None
    product: Optional[str]=None
    amount: Optional[str]=None
    vet: Optional[str]=None
    notes: Optional[str]=None

@app.get("/api/health_records")
def health_record_list(horse_id: Optional[int]=None):
    conn = get_db()
    sql = "SELECT * FROM health_record WHERE 1=1"
    p = []
    if horse_id: sql += " AND horse_id=?"; p.append(horse_id)
    sql += " ORDER BY date DESC"
    return [dict(r) for r in conn.execute(sql, p).fetchall()]

@app.post("/api/health_records")
def health_record_create(d: HealthRecordIn):
    conn = get_db()
    cur = conn.execute("INSERT INTO health_record (horse_id,date,type,product,amount,vet,notes) VALUES (?,?,?,?,?,?,?)",
        (d.horse_id,d.date,d.type,d.product,d.amount,d.vet,d.notes))
    conn.commit(); return {"id": cur.lastrowid}

@app.delete("/api/health_records/{id}")
def health_record_delete(id: int):
    conn = get_db()
    conn.execute("DELETE FROM health_record WHERE id=?", (id,))
    conn.commit(); return {"ok": True}

# ── НӨХӨН ҮРЖИХҮЙ ──
class BreedingEventIn(BaseModel):
    horse_id: int
    date: Optional[str]=None
    type: Optional[str]=None
    notes: Optional[str]=None
    vet: Optional[str]=None

@app.get("/api/horses/{horse_id}/breeding_event")
def breeding_event_list(horse_id: int):
    conn = get_db()
    rows = conn.execute("SELECT * FROM breeding_event WHERE horse_id=? ORDER BY date DESC", (horse_id,)).fetchall()
    return [dict(r) for r in rows]

@app.post("/api/breeding_events")
def breeding_event_create(d: BreedingEventIn):
    conn = get_db()
    cur = conn.execute("INSERT INTO breeding_event (horse_id,date,type,notes,vet) VALUES (?,?,?,?,?)",
        (d.horse_id, d.date, d.type, d.notes, d.vet))
    conn.commit(); return {"id": cur.lastrowid}

@app.delete("/api/breeding_events/{id}")
def breeding_event_delete(id: int):
    conn = get_db()
    conn.execute("DELETE FROM breeding_event WHERE id=?", (id,))
    conn.commit(); return {"ok": True}

# ── ХЭМЖИЛТ ──
class MeasurementIn(BaseModel):
    horse_id: int
    date: Optional[str]=None
    weight: Optional[float]=None
    height: Optional[float]=None
    chest_girth: Optional[float]=None
    cannon_bone: Optional[float]=None
    notes: Optional[str]=None

@app.get("/api/measurements")
def measurement_list(horse_id: Optional[int]=None):
    conn = get_db()
    sql = "SELECT * FROM measurement WHERE 1=1"
    p = []
    if horse_id: sql += " AND horse_id=?"; p.append(horse_id)
    sql += " ORDER BY date DESC"
    return [dict(r) for r in conn.execute(sql, p).fetchall()]

@app.post("/api/measurements")
def measurement_create(d: MeasurementIn):
    conn = get_db()
    cur = conn.execute("INSERT INTO measurement (horse_id,date,weight,height,chest_girth,cannon_bone,notes) VALUES (?,?,?,?,?,?,?)",
        (d.horse_id,d.date,d.weight,d.height,d.chest_girth,d.cannon_bone,d.notes))
    conn.commit(); return {"id": cur.lastrowid}

@app.delete("/api/measurements/{id}")
def measurement_delete(id: int):
    conn = get_db()
    conn.execute("DELETE FROM measurement WHERE id=?", (id,))
    conn.commit(); return {"ok": True}

# ── ТАХ ──
class HoofCareIn(BaseModel):
    horse_id: int
    date: Optional[str]=None
    next_date: Optional[str]=None
    type: Optional[str]=None
    notes: Optional[str]=None
    farrier: Optional[str]=None

@app.get("/api/hoof_care")
def hoof_care_list(horse_id: Optional[int]=None):
    conn = get_db()
    sql = "SELECT * FROM hoof_care WHERE 1=1"
    p = []
    if horse_id: sql += " AND horse_id=?"; p.append(horse_id)
    sql += " ORDER BY date DESC"
    return [dict(r) for r in conn.execute(sql, p).fetchall()]

@app.post("/api/hoof_care")
def hoof_care_create(d: HoofCareIn):
    conn = get_db()
    cur = conn.execute("INSERT INTO hoof_care (horse_id,date,next_date,type,notes,farrier) VALUES (?,?,?,?,?,?)",
        (d.horse_id,d.date,d.next_date,d.type,d.notes,d.farrier))
    conn.commit(); return {"id": cur.lastrowid}

@app.delete("/api/hoof_care/{id}")
def hoof_care_delete(id: int):
    conn = get_db()
    conn.execute("DELETE FROM hoof_care WHERE id=?", (id,))
    conn.commit(); return {"ok": True}

# ── ТЭЖЭЭЛ ──
class FeedingIn(BaseModel):
    horse_id: int
    feed_name: Optional[str]=None
    start_date: Optional[str]=None
    end_date: Optional[str]=None
    notes: Optional[str]=None

@app.get("/api/feedings")
def feeding_list(horse_id: Optional[int]=None):
    conn = get_db()
    sql = "SELECT * FROM feeding WHERE 1=1"
    p = []
    if horse_id: sql += " AND horse_id=?"; p.append(horse_id)
    return [dict(r) for r in conn.execute(sql, p).fetchall()]

@app.post("/api/feedings")
def feeding_create(d: FeedingIn):
    conn = get_db()
    cur = conn.execute("INSERT INTO feeding (horse_id,feed_name,start_date,end_date,notes) VALUES (?,?,?,?,?)",
        (d.horse_id,d.feed_name,d.start_date,d.end_date,d.notes))
    conn.commit(); return {"id": cur.lastrowid}

@app.delete("/api/feedings/{id}")
def feeding_delete(id: int):
    conn = get_db()
    conn.execute("DELETE FROM feeding WHERE id=?", (id,))
    conn.commit(); return {"ok": True}

# ── АИЭ ШИНЖИЛГЭЭ ──
class EiaTestIn(BaseModel):
    horse_id: int
    date: Optional[str]=None
    result: Optional[str]='Сөрөг'
    province: Optional[str]=None
    lab: Optional[str]=None
    responsible: Optional[str]=None
    notes: Optional[str]=None

@app.get("/api/eia_tests")
def eia_test_list(horse_id: Optional[int]=None):
    conn = get_db()
    sql = "SELECT * FROM eia_test WHERE 1=1"
    p = []
    if horse_id: sql += " AND horse_id=?"; p.append(horse_id)
    sql += " ORDER BY date DESC"
    return [dict(r) for r in conn.execute(sql, p).fetchall()]

@app.post("/api/eia_tests")
def eia_test_create(d: EiaTestIn):
    conn = get_db()
    cur = conn.execute("INSERT INTO eia_test (horse_id,date,result,province,lab,responsible,notes) VALUES (?,?,?,?,?,?,?)",
        (d.horse_id,d.date,d.result,d.province,d.lab,d.responsible,d.notes))
    conn.commit(); return {"id": cur.lastrowid}

@app.delete("/api/eia_tests/{id}")
def eia_test_delete(id: int):
    conn = get_db()
    conn.execute("DELETE FROM eia_test WHERE id=?", (id,))
    conn.commit(); return {"ok": True}

# ── ҮР ТӨЛ ──
@app.get("/api/horses/{id}/offspring")
def ur_tol(id: int):
    conn = get_db()
    rows = conn.execute("""
        SELECT a.id,a.name,a.sex,a.birth_date,a.registration_code,
               tz.name as color_name, m.name as dam_name
        FROM horse a
        LEFT JOIN option tz ON a.color_id=tz.id
        LEFT JOIN horse m ON a.dam_id=m.id
        WHERE (a.sire_id=? OR a.dam_id=?)
        ORDER BY a.birth_date DESC
    """, (id, id)).fetchall()
    return [dict(r) for r in rows]

# ── МОРЬ СОЙХ ──
SOIKH_TURLUUD = ['Амраах','Гэдэс солих','Гишгүүлэх','Хөлс авах','Тар','Хангар','Бага сүнгаа','Дунд сүнгаа','Их сүнгаа']

class TrainingSessionIn(BaseModel):
    horse_id: int
    trainer_id: Optional[int]=None
    type: str
    date: Optional[str]=None
    distance_km: Optional[float]=None
    duration_min: Optional[float]=None
    notes: Optional[str]=None
    original_text: Optional[str]=None

@app.get("/api/training_sessions")
def training_session_list(horse_id: Optional[int]=None, trainer_id: Optional[int]=None):
    conn = get_db()
    sql = """SELECT ms.*, a.name as horse_name, u.name as trainer_name
             FROM training_session ms
             JOIN horse a ON ms.horse_id=a.id
             LEFT JOIN trainer u ON ms.trainer_id=u.id
             WHERE 1=1"""
    p = []
    if horse_id: sql += " AND ms.horse_id=?"; p.append(horse_id)
    if trainer_id: sql += " AND ms.trainer_id=?"; p.append(trainer_id)
    sql += " ORDER BY ms.date DESC, ms.id DESC LIMIT 200"
    return [dict(r) for r in conn.execute(sql, p).fetchall()]

@app.post("/api/training_sessions")
def training_session_create(d: TrainingSessionIn):
    conn = get_db()
    date = d.date or __import__('datetime').date.today().isoformat()
    cur = conn.execute(
        "INSERT INTO training_session (horse_id,trainer_id,type,date,distance_km,duration_min,notes,original_text) VALUES (?,?,?,?,?,?,?,?)",
        (d.horse_id,d.trainer_id,d.type,date,d.distance_km,d.duration_min,d.notes,d.original_text))
    conn.commit()
    notif_id = cur.lastrowid
    # Notification үүсгэх — эзэмшигчдэд
    owners = conn.execute(
        "SELECT owner_id FROM horse_owner WHERE horse_id=?", (d.horse_id,)).fetchall()
    horse_name = conn.execute("SELECT name FROM horse WHERE id=?", (d.horse_id,)).fetchone()
    trainer_name = conn.execute("SELECT name FROM trainer WHERE id=?", (d.trainer_id,)).fetchone() if d.trainer_id else None
    text = f"🐴 {horse_name['name'] if horse_name else ''} — {d.type}" + (f" · {trainer_name['name']}" if trainer_name else "")
    for e in owners:
        conn.execute("INSERT INTO notification (horse_id,text,date) VALUES (?,?,?)",
            (d.horse_id, text, date))
    conn.commit()
    return {"id": notif_id}

@app.delete("/api/training_sessions/{id}")
def training_session_delete(id: int):
    conn = get_db()
    conn.execute("DELETE FROM training_session WHERE id=?", (id,))
    conn.commit(); return {"ok": True}

@app.get("/api/training_sessions/types")
def training_session_turluud():
    conn = get_db()
    rows = conn.execute(
        "SELECT name FROM option WHERE type='soikh_type' AND active=1 ORDER BY id"
    ).fetchall()
    conn.close()
    if rows:
        return [r['name'] for r in rows]
    return SOIKH_TURLUUD  # fallback

# ── DASHBOARD ──
@app.get("/api/dashboard")
def dashboard():
    import datetime
    conn = get_db()
    today = datetime.date.today()
    this_yr = today.year
    this_year = str(this_yr)

    # ── Үндсэн тоо ──
    total = conn.execute("SELECT COUNT(*) FROM horse WHERE active=1").fetchone()[0]
    azarga = conn.execute("SELECT COUNT(*) FROM horse WHERE sex='stallion' AND active=1").fetchone()[0]
    guu = conn.execute("SELECT COUNT(*) FROM horse WHERE sex='mare' AND active=1").fetchone()[0]
    in_training_count = conn.execute("SELECT COUNT(DISTINCT horse_id) FROM horse_trainer WHERE active=1").fetchone()[0]
    herd_count = conn.execute("SELECT COUNT(*) FROM herd WHERE active=1").fetchone()[0]

    # ── Насны бүлэг — 6 бүлэг ──
    # 1=Унага, 2=Даага, 3=Шүдлэн, 4=Хязаалан, 5=Соёолон, 6+=Морь/Гүү
    nas_groups = [
        ('Унага',1,1),('Даага',2,2),('Шүдлэн',3,3),
        ('Хязаалан',4,4),('Соёолон',5,5),('Морь/Гүү',6,99)
    ]
    nas_data = []
    for lbl,mn,mx in nas_groups:
        for h in ['stallion','mare']:
            n = conn.execute(
                "SELECT COUNT(*) FROM horse WHERE sex=? AND active=1 AND birth_date IS NOT NULL AND (?-CAST(strftime('%Y',birth_date) AS INT)+1) BETWEEN ? AND ?",
                (h, this_yr, mn, mx)).fetchone()[0]
            nas_data.append({'nas':lbl,'sex':h,'too':n})

    # ── Сүргийн бүрэлдэхүүн ──
    herd_data = [dict(r) for r in conn.execute(
        "SELECT s.id, s.name, COUNT(a.id) as too FROM herd s LEFT JOIN horse a ON a.herd_id=s.id AND a.active=1 GROUP BY s.id ORDER BY too DESC LIMIT 12").fetchall()]
    herd_all = [dict(r) for r in conn.execute(
        "SELECT s.id, s.name FROM herd s WHERE s.active=1 ORDER BY s.name").fetchall()]

    # ── Эзэмшигчийн жагсаалт ──
    ezen_data = [dict(r) for r in conn.execute(
        "SELECT h.id, h.name, COUNT(DISTINCT ae.horse_id) as too FROM contact h JOIN horse_owner ae ON h.id=ae.owner_id JOIN horse a ON ae.horse_id=a.id AND a.active=1 GROUP BY h.id ORDER BY too DESC LIMIT 8").fetchall()]
    ezen_all = [dict(r) for r in conn.execute(
        "SELECT h.id, h.name FROM contact h WHERE h.type='owner_text' ORDER BY h.name").fetchall()]

    # ── Энэ жилийн унагалалт ──
    # 4+ настай гүү л унагална
    guu_4plus = conn.execute(
        "SELECT COUNT(*) FROM horse WHERE sex='mare' AND active=1 AND birth_date IS NOT NULL AND (?-CAST(strftime('%Y',birth_date) AS INT)+1)>=4",
        (this_yr,)).fetchone()[0]
    unagalsan_guu = conn.execute(
        "SELECT COUNT(*) FROM horse WHERE sex='mare' AND active=1 AND birth_date IS NOT NULL AND strftime('%Y',birth_date)=?",
        (this_year,)).fetchone()[0]
    # Хээл хаясан гүү (энэ жил)
    heel_hayas = conn.execute(
        "SELECT COUNT(*) FROM breeding_event WHERE type='foaling' AND strftime('%Y',date)=?",
        (this_year,)).fetchone()[0]

    # Сувайрсан гүү = 4+ настай гүү - унагалсан - хээл хаясан
    suvairsan_guu = max(0, guu_4plus - unagalsan_guu - heel_hayas)

    # Төл авалтын хувь = унагалсан / (унагалсан + сувайрсан + хээл хаясан) * 100
    tol_avalt_pct = round(unagalsan_guu / guu_4plus * 100) if guu_4plus > 0 else 0

    # Нийт унага (энэ жил төрсөн)
    total_unaga = conn.execute(
        "SELECT COUNT(*) FROM horse WHERE active=1 AND birth_date IS NOT NULL AND strftime('%Y',birth_date)=?",
        (this_year,)).fetchone()[0]

    # ── Наадмын амжилт (1-5 байр) ──
    naadam_achievements = conn.execute(
        "SELECT COUNT(DISTINCT sg.horse_id) FROM practice_race sg WHERE sg.rank IS NOT NULL AND sg.rank BETWEEN 1 AND 5 AND strftime('%Y',sg.date)=?",
        (this_year,)).fetchone()[0]
    naadam_total = conn.execute(
        "SELECT COUNT(DISTINCT sg.horse_id) FROM practice_race sg WHERE strftime('%Y',sg.date)=?",
        (this_year,)).fetchone()[0]

    conn.close()
    return {
        "total":total,"stallion":azarga,"mare":guu,
        "in_training_count":in_training_count,"herd_count":herd_count,
        "nas_data":nas_data,"herd_data":herd_data,"herd_all":herd_all,"ezen_data":ezen_data,"ezen_all":ezen_all,
        "guu_4plus":guu_4plus,
        "unagalsan_guu":unagalsan_guu,"total_unaga":total_unaga,
        "unagalalt_pct":tol_avalt_pct,"foaling":heel_hayas,"suvairsan_guu":suvairsan_guu,
        "naadam_achievements":naadam_achievements,"naadam_total":naadam_total,
        "this_year":this_year
    }

# ── POLAR HRM ──
from fastapi import UploadFile, File
import json as json_lib

class PolarImportIn(BaseModel):
    horse_id: int
    trainer_id: Optional[int] = None
    type: Optional[str] = None
    polar_json: dict

def calc_recovery_index(zc_2min):
    if not zc_2min: return None
    if zc_2min < 100: return "Маш сайн"
    if zc_2min < 110: return "Сайн"
    if zc_2min < 120: return "Дунд"
    return "Муу"

def calc_hr_zones(hr_series_list):
    if not hr_series_list: return [0,0,0,0,0]
    total = len(hr_series_list)
    if total == 0: return [0,0,0,0,0]
    amar  = sum(1 for z in hr_series_list if z < 100)
    dund  = sum(1 for z in hr_series_list if 100 <= z < 130)
    huch  = sum(1 for z in hr_series_list if 130 <= z < 160)
    ih    = sum(1 for z in hr_series_list if 160 <= z < 180)
    deed  = sum(1 for z in hr_series_list if z >= 180)
    return [round(x/total*100,1) for x in [amar,dund,huch,ih,deed]]

@app.post("/api/polar/import")
def polar_import(d: PolarImportIn):
    conn = get_db()
    pj = d.polar_json
    
    # Polar Flow JSON бүтцийг задлах
    # Хэрэглэгч simulation JSON эсвэл бодит Polar JSON явуулж болно
    exercises = pj.get('exercises', [pj]) if 'exercises' in pj else [pj]
    
    imported = []
    for ex in exercises:
        # Үндсэн өгөгдөл
        date = ex.get('start_time', ex.get('date', ex.get('date','')))[:10] if ex.get('start_time') or ex.get('date') or ex.get('date') else None
        distance_km = ex.get('distance', ex.get('distance_km'))
        if distance_km: distance_km = round(float(distance_km)/1000 if float(distance_km) > 1000 else float(distance_km), 2)
        duration_sec = ex.get('duration', ex.get('duration_sec'))
        duration_min_direct = ex.get('duration_min')
        if duration_sec:
            duration_min = round(float(duration_sec)/60, 1)
        elif duration_min_direct:
            duration_min = float(duration_min_direct)
        else:
            duration_min = None
        speed = round(float(distance_km)/(float(duration_min)/60), 1) if distance_km and duration_min else ex.get('avg_speed')

        # ЗЦ
        heart_rate = ex.get('heart_rate', {})
        avg_heart_rate = heart_rate.get('average', ex.get('avg_heart_rate'))
        max_heart_rate    = heart_rate.get('maximum', ex.get('max_heart_rate'))
        min_heart_rate    = heart_rate.get('minimum', ex.get('min_heart_rate'))
        
        # Сэргэлт
        recovery_1 = ex.get('recovery', {}).get('heart_rate_1min', ex.get('recovery_1min'))
        recovery_2 = ex.get('recovery', {}).get('heart_rate_2min', ex.get('recovery_2min'))
        recovery_idx = calc_recovery_index(float(recovery_2) if recovery_2 else None)
        
        # HRV
        hrv_raw = ex.get('hrv')
        if isinstance(hrv_raw, dict):
            hrv = hrv_raw.get('rmssd')
        elif isinstance(hrv_raw, (int, float)):
            hrv = float(hrv_raw)
        else:
            hrv = None
        
        # ЗЦ цуврал
        hr_series = ex.get('samples', {}).get('heart_rate', ex.get('hr_series', []))
        if isinstance(hr_series, list) and hr_series:
            zc_vals = [s.get('value', s) if isinstance(s, dict) else s for s in hr_series]
            bus = calc_hr_zones([float(v) for v in zc_vals if v])
        else:
            bus = [0,0,0,0,0]
        
        # Training load
        training_load = ex.get('training_load', {}).get('score', ex.get('training_load'))
        
        # GPS
        gps = ex.get('route', ex.get('gps_series', []))
        
        # training_session дотор ч хадгалах
        ms_cur = conn.execute("""INSERT INTO training_session 
            (horse_id,trainer_id,type,date,distance_km,duration_min,notes)
            VALUES (?,?,?,?,?,?,'Polar HRM')""",
            (d.horse_id, d.trainer_id, d.type or 'Polar', date, distance_km, duration_min))
        ms_id = ms_cur.lastrowid
        
        # polar_session-д дэлгэрэнгүй хадгалах
        cur = conn.execute("""INSERT INTO polar_session 
            (training_session_id,horse_id,trainer_id,date,type,
             distance_km,duration_min,avg_speed,
             avg_heart_rate,max_heart_rate,min_heart_rate,
             recovery_1min,recovery_2min,recovery_index,hrv,
             hr_zone_resting,hr_zone_moderate,hr_zone_intense,hr_zone_very_intense,hr_zone_max,
             training_load,hr_series,gps_series,
             polar_exercise_id)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (ms_id, d.horse_id, d.trainer_id, date, d.type or 'Polar',
             distance_km, duration_min, speed,
             avg_heart_rate, max_heart_rate, min_heart_rate,
             recovery_1, recovery_2, recovery_idx, hrv,
             bus[0], bus[1], bus[2], bus[3], bus[4],
             training_load,
             json_lib.dumps(hr_series) if hr_series else None,
             json_lib.dumps(gps) if gps else None,
             ex.get('exercise_id', ex.get('id'))))
        imported.append(cur.lastrowid)
    
    # Эзэнд notification
    horse_name = conn.execute("SELECT name FROM horse WHERE id=?", (d.horse_id,)).fetchone()
    text = f"🐴 {horse_name['name'] if horse_name else ''} — Polar HRM өгөгдөл импортлогдлоо"
    for e in conn.execute("SELECT owner_id FROM horse_owner WHERE horse_id=?", (d.horse_id,)).fetchall():
        conn.execute("INSERT INTO notification (horse_id,text) VALUES (?,?)", (d.horse_id, text))
    
    conn.commit()
    return {"imported": len(imported), "ids": imported}

@app.get("/api/polar/{horse_id}")
def polar_list(horse_id: int):
    conn = get_db()
    rows = conn.execute("""
        SELECT ps.*, u.name as trainer_name
        FROM polar_session ps
        LEFT JOIN trainer u ON ps.trainer_id=u.id
        WHERE ps.horse_id=?
        ORDER BY ps.date DESC
    """, (horse_id,)).fetchall()
    result = []
    for r in rows:
        d = dict(r)
        # JSON цуврал задлах
        if d.get('hr_series'): 
            try: d['hr_series'] = json_lib.loads(d['hr_series'])
            except: d['hr_series'] = []
        result.append(d)
    return result

@app.get("/api/polar/{horse_id}/trend")
def polar_trend(horse_id: int, limit: int=30):
    conn = get_db()
    rows = conn.execute("""
        SELECT date, avg_speed, avg_heart_rate, recovery_2min, hrv, training_load, type
        FROM polar_session
        WHERE horse_id=?
        ORDER BY date DESC LIMIT ?
    """, (horse_id, limit)).fetchall()
    return [dict(r) for r in rows]

# ── ТАЙЛАН ──
@app.get("/api/dashboard/foaling")
def dashboard_unagalalt(on: Optional[int]=None):
    import datetime
    conn = get_db()
    this_yr = on or datetime.date.today().year
    this_year = str(this_yr)
    guu_4plus = conn.execute(
        "SELECT COUNT(*) FROM horse WHERE sex='mare' AND active=1 AND birth_date IS NOT NULL AND (?-CAST(strftime('%Y',birth_date) AS INT)+1)>=4",
        (this_yr,)).fetchone()[0]
    unagalsan_guu = conn.execute(
        "SELECT COUNT(*) FROM horse WHERE sex='mare' AND active=1 AND birth_date IS NOT NULL AND strftime('%Y',birth_date)=?",
        (this_year,)).fetchone()[0]
    total_unaga = conn.execute(
        "SELECT COUNT(*) FROM horse WHERE active=1 AND birth_date IS NOT NULL AND strftime('%Y',birth_date)=?",
        (this_year,)).fetchone()[0]
    heel_hayas = conn.execute(
        "SELECT COUNT(*) FROM breeding_event WHERE type='foaling' AND strftime('%Y',date)=?",
        (this_year,)).fetchone()[0]
    suvairsan_guu = max(0, guu_4plus - unagalsan_guu - heel_hayas)
    tol_avalt_pct = round(unagalsan_guu / guu_4plus * 100) if guu_4plus > 0 else 0
    conn.close()
    return {"on":this_year,"guu_4plus":guu_4plus,"unagalsan_guu":unagalsan_guu,
            "total_unaga":total_unaga,"foaling":heel_hayas,"suvairsan_guu":suvairsan_guu,
            "unagalalt_pct":tol_avalt_pct}

@app.get("/api/dashboard/naadam")
def dashboard_naadam(on: Optional[int]=None, horse_id: Optional[int]=None, ez: Optional[str]=None):
    conn = get_db()
    rank_lbls = ['Түрүү','Аман хүзүү','Айргийн-3','Айргийн-4','Айргийн-5']
    turluud = [
        {'key':'Улс',   'filter': "sg.naadam_type='Улсын'"},
        {'key':'Аймаг', 'filter': "sg.naadam_type='Аймгийн'"},
        {'key':'Сум',   'filter': "sg.naadam_type='Сумын'"},
        {'key':'Бусад', 'filter': "sg.naadam_type='Бусад' OR sg.naadam_type IS NULL"},
    ]
    extra = ""
    extra_params = []
    if horse_id:
        extra += " AND sg.horse_id=?"
        extra_params.append(horse_id)
    if ez:
        extra += " AND EXISTS(SELECT 1 FROM horse_owner ae JOIN contact h ON ae.owner_id=h.id WHERE ae.horse_id=sg.horse_id AND h.name LIKE ?)"
        extra_params.append(f"%{ez}%")
    on_filter = "strftime('%Y',sg.date)=?" if on else "1=1"
    on_param = [str(on)] if on else []
    # Адуу болон эзэмшигчийн жагсаалт (dropdown-д)
    horse_list = conn.execute("SELECT DISTINCT a.id, a.name FROM practice_race sg JOIN horse a ON sg.horse_id=a.id ORDER BY a.name").fetchall()
    ez_list = conn.execute("SELECT DISTINCT h.name FROM practice_race sg JOIN horse_owner ae ON ae.horse_id=sg.horse_id JOIN contact h ON ae.owner_id=h.id ORDER BY h.name").fetchall()
    result = {}
    for t in turluud:
        total = conn.execute(
            f"SELECT COUNT(*) FROM practice_race sg WHERE {on_filter} AND ({t['filter']}){extra}",
            on_param+extra_params).fetchone()[0]
        rank_counts = {}
        for i,lbl in enumerate(rank_lbls, 1):
            n = conn.execute(
                f"SELECT COUNT(*) FROM practice_race sg WHERE {on_filter} AND sg.rank=? AND ({t['filter']}){extra}",
                on_param+[i]+extra_params).fetchone()[0]
            rank_counts[lbl] = n
        result[t['key']] = {"total":total, "rank":rank_counts}
    conn.close()
    return {"on": str(on) if on else "Бүх он", "data": result,
            "horse_list": [{"id":r[0],"name":r[1]} for r in horse_list],
            "ez_list": [r[0] for r in ez_list]}

@app.get("/api/dashboard/composition")
def dashboard_butets(herd_id: Optional[int]=None, owner_id: Optional[int]=None):
    conn = get_db()
    sf = (f" AND a.herd_id={herd_id}" if herd_id else "")
    ef = (f" AND EXISTS(SELECT 1 FROM horse_owner ae WHERE ae.horse_id=a.id AND ae.owner_id={owner_id})" if owner_id else "")
    base = f"WHERE a.active=1{sf}{ef}"

    zus_rows = conn.execute(f"SELECT t.name, COUNT(a.id) as too FROM horse a LEFT JOIN option t ON a.color_id=t.id {base} GROUP BY a.color_id ORDER BY too DESC LIMIT 8").fetchall()
    breed_text_rows = conn.execute(f"SELECT t.name, COUNT(a.id) as too FROM horse a LEFT JOIN option t ON a.breed_id=t.id {base} GROUP BY a.breed_id ORDER BY too DESC").fetchall()
    az_rows = conn.execute(f"SELECT e.name as name, COUNT(a.id) as too FROM horse a JOIN horse e ON a.sire_id=e.id {base} AND e.sex IN ('stallion','er') GROUP BY a.sire_id ORDER BY too DESC LIMIT 6").fetchall()
    guu_rows = conn.execute(f"SELECT e.name as name, COUNT(a.id) as too FROM horse a JOIN horse e ON a.dam_id=e.id {base} AND e.sex IN ('mare','ohin') GROUP BY a.dam_id ORDER BY too DESC LIMIT 6").fetchall()
    conn.close()
    return {
        "color": [{"name": r["name"] or "Тодорхойгүй", "too": r["too"]} for r in zus_rows],
        "breed_text": [{"name": r["name"] or "Тодорхойгүй", "too": r["too"]} for r in breed_text_rows],
        "azarga_urtol": [{"name": r["name"], "too": r["too"]} for r in az_rows],
        "guu_urtol": [{"name": r["name"], "too": r["too"]} for r in guu_rows]
    }

@app.get("/api/dashboard/growth")
def dashboard_osolt(herd_id: Optional[int]=None, owner_id: Optional[int]=None):
    import datetime
    conn = get_db()
    this_yr = datetime.date.today().year
    sf = (f" AND a.herd_id={herd_id}" if herd_id else "")
    ef = (f" AND EXISTS(SELECT 1 FROM horse_owner ae WHERE ae.horse_id=a.id AND ae.owner_id={owner_id})" if owner_id else "")
    result = []
    for yr in range(this_yr-9, this_yr+1):
        base = f"SELECT COUNT(*) FROM horse a WHERE a.active=1 AND (a.birth_date IS NULL OR CAST(strftime('%Y',a.birth_date) AS INT)<={yr}){sf}{ef}"
        total = conn.execute(base).fetchone()[0]
        er   = conn.execute(base + " AND a.sex IN ('stallion','er')").fetchone()[0]
        ohin = conn.execute(base + " AND a.sex IN ('mare','ohin')").fetchone()[0]
        result.append({"on": yr, "total": total, "er": er, "ohin": ohin})
    conn.close()
    return result

@app.get("/api/dashboard/age_distribution")
def dashboard_nas(herd_id: Optional[int]=None, owner_id: Optional[int]=None, on: Optional[int]=None):
    import datetime
    conn = get_db()
    this_yr = on or datetime.date.today().year
    nas_groups = [
        ('Унага',1,1),('Даага',2,2),('Шүдлэн',3,3),
        ('Хязаалан',4,4),('Соёолон',5,5),('Морь/Гүү',6,99)
    ]
    nas_data = []
    for lbl,mn,mx in nas_groups:
        for h in ['stallion','mare']:
            sql = """SELECT COUNT(*) FROM horse a WHERE a.sex=? AND a.active=1
                     AND a.birth_date IS NOT NULL
                     AND (?-CAST(strftime('%Y',a.birth_date) AS INT)+1) BETWEEN ? AND ?"""
            params = [h, this_yr, mn, mx]
            if herd_id:
                sql += " AND a.herd_id=?"
                params.append(herd_id)
            if owner_id:
                sql += " AND EXISTS(SELECT 1 FROM horse_owner ae WHERE ae.horse_id=a.id AND ae.owner_id=?)"
                params.append(owner_id)
            n = conn.execute(sql, params).fetchone()[0]
            nas_data.append({'nas':lbl,'sex':h,'too':n})
    conn.close()
    return nas_data

@app.get("/api/dashboard/naadam_stats")
def dashboard_naadam_stat():
    """Наадмын амжилт — жилээр, насны ангиллаар (сүүлийн 5 жил)"""
    import datetime
    conn = get_db()
    this_yr = datetime.date.today().year
    age_category = ['Унага','Даага','Шүдлэн','Хязаалан','Соёолон','Морь']
    result = []
    for yr in range(this_yr - 4, this_yr + 1):
        y = str(yr)
        row = {"on": yr}
        # Нийт оролцсон
        row["total"] = conn.execute(
            "SELECT COUNT(DISTINCT horse_id) FROM practice_race WHERE strftime('%Y',date)=?", (y,)).fetchone()[0]
        # 1-3 байр авсан
        row["medalist"] = conn.execute(
            "SELECT COUNT(DISTINCT horse_id) FROM practice_race WHERE strftime('%Y',date)=? AND rank BETWEEN 1 AND 3", (y,)).fetchone()[0]
        # 1-р байр (Түрүү)
        row["turuulsen"] = conn.execute(
            "SELECT COUNT(DISTINCT horse_id) FROM practice_race WHERE strftime('%Y',date)=? AND rank=1", (y,)).fetchone()[0]
        # Насны ангиллаар: practice_race.age_category талбараас
        for na in age_category:
            row[na] = conn.execute(
                "SELECT COUNT(DISTINCT horse_id) FROM practice_race WHERE strftime('%Y',date)=? AND age_category LIKE ?",
                (y, f"%{na}%")).fetchone()[0]
        result.append(row)
    conn.close()
    return result

@app.get("/api/dashboard/breeding_trend")
def dashboard_urjil_trend():
    """Хээл хаясан vs Унагалсан — сүүлийн 5 жил"""
    import datetime
    conn = get_db()
    this_yr = datetime.date.today().year
    result = []
    for yr in range(this_yr - 4, this_yr + 1):
        y = str(yr)
        guu_4plus = conn.execute(
            "SELECT COUNT(*) FROM horse WHERE sex='mare' AND active=1 AND birth_date IS NOT NULL AND (?-CAST(strftime('%Y',birth_date) AS INT)+1)>=4",
            (yr,)).fetchone()[0]
        unagalsan = conn.execute(
            "SELECT COUNT(*) FROM horse WHERE sex='mare' AND active=1 AND birth_date IS NOT NULL AND strftime('%Y',birth_date)=?",
            (y,)).fetchone()[0]
        heel_hayas = conn.execute(
            "SELECT COUNT(*) FROM breeding_event WHERE type='foaling' AND strftime('%Y',date)=?",
            (y,)).fetchone()[0]
        suvairsan = max(0, guu_4plus - unagalsan - heel_hayas)
        pct = round(unagalsan / guu_4plus * 100) if guu_4plus > 0 else 0
        result.append({"on": yr, "unagalsan": unagalsan, "foaling": heel_hayas,
                       "bred": suvairsan, "guu_4plus": guu_4plus, "pct": pct})
    conn.close()
    return result

@app.get("/api/reports/performance")
def reports_performance(
    trainer_id: Optional[int]=None,
    horse_id: Optional[int]=None,
    horse_code: Optional[str]=None,
    ehleh: Optional[str]=None,
    duusah: Optional[str]=None
):
    """Гүйцэтгэлийн тайлан — адуу бүрээр төлөвлөсөн/хийсэн/хийгдээгүй"""
    import datetime
    conn = get_db()
    today = datetime.date.today().isoformat()
    if not ehleh: ehleh = today[:7] + '-01'
    if not duusah: duusah = today

    params_plan = []
    sql_plan = """
        SELECT p.horse_id, p.status, COUNT(*) as too, a.name as horse_name, a.registration_code as horse_code
        FROM training_plan p
        JOIN horse a ON p.horse_id=a.id
        WHERE p.date BETWEEN ? AND ?
    """
    params_plan = [ehleh, duusah]
    if trainer_id: sql_plan += " AND p.trainer_id=?"; params_plan.append(trainer_id)
    if horse_id: sql_plan += " AND p.horse_id=?"; params_plan.append(horse_id)
    if horse_code: sql_plan += " AND a.registration_code LIKE ?"; params_plan.append(horse_code+'%')
    sql_plan += " GROUP BY p.horse_id, p.status ORDER BY a.name"
    plan_rows = conn.execute(sql_plan, params_plan).fetchall()

    # training_session (хийгдсэн)
    sql_training = """
        SELECT ms.horse_id, COUNT(*) as too, a.name as horse_name, a.registration_code as horse_code
        FROM training_session ms
        JOIN horse a ON ms.horse_id=a.id
        WHERE ms.date BETWEEN ? AND ?
    """
    params_training = [ehleh, duusah]
    if trainer_id: sql_training += " AND ms.trainer_id=?"; params_training.append(trainer_id)
    if horse_id: sql_training += " AND ms.horse_id=?"; params_training.append(horse_id)
    if horse_code: sql_training += " AND a.registration_code LIKE ?"; params_training.append(horse_code+'%')
    sql_training += " GROUP BY ms.horse_id ORDER BY a.name"
    soikh_rows = conn.execute(sql_training, params_training).fetchall()

    # Нэгтгэх
    horse_map = {}
    for r in plan_rows:
        aid = r['horse_id']
        if aid not in horse_map:
            horse_map[aid] = {'horse_id':aid,'horse_name':r['horse_name'],'horse_code':r['horse_code'],'tolvlosen':0,'hiisgdsn':0,'training_count':0}
        if r['status']=='done': horse_map[aid]['hiisgdsn'] += r['too']
        else: horse_map[aid]['tolvlosen'] += r['too']
    for r in soikh_rows:
        aid = r['horse_id']
        if aid not in horse_map:
            horse_map[aid] = {'horse_id':aid,'horse_name':r['horse_name'],'horse_code':r['horse_code'],'tolvlosen':0,'hiisgdsn':0,'training_count':0}
        horse_map[aid]['training_count'] = r['too']

    result = []
    for d in horse_map.values():
        total = d['tolvlosen'] + d['hiisgdsn']
        hiigdsen = d['hiisgdsn'] + d['training_count']
        d['total'] = total + d['training_count']
        d['hiigdsen'] = hiigdsen
        d['hiigdgui'] = max(0, total - d['hiisgdsn'])
        d['pct'] = round(hiigdsen / d['total'] * 100) if d['total'] else 0
        result.append(d)
    conn.close()
    return sorted(result, key=lambda x: x['horse_name'])

@app.get("/api/reports/task_breakdown")
def reports_task_breakdown(
    trainer_id: Optional[int]=None,
    horse_id: Optional[int]=None,
    horse_code: Optional[str]=None,
    ehleh: Optional[str]=None,
    duusah: Optional[str]=None
):
    """Ажлын төрлөөр тайлан"""
    import datetime
    conn = get_db()
    today = datetime.date.today().isoformat()
    if not ehleh: ehleh = today[:7] + '-01'
    if not duusah: duusah = today

    result = {}
    # Plan-аас
    sql = "SELECT p.type, COUNT(*) as too FROM training_plan p JOIN horse a ON p.horse_id=a.id WHERE p.date BETWEEN ? AND ?"
    params = [ehleh, duusah]
    if trainer_id: sql += " AND p.trainer_id=?"; params.append(trainer_id)
    if horse_id: sql += " AND p.horse_id=?"; params.append(horse_id)
    if horse_code: sql += " AND a.registration_code LIKE ?"; params.append(horse_code+'%')
    sql += " GROUP BY p.type ORDER BY too DESC"
    for r in conn.execute(sql, params).fetchall():
        result[r['type']] = result.get(r['type'],0) + r['too']
    # training_session-аас
    sql2 = "SELECT ms.type, COUNT(*) as too FROM training_session ms JOIN horse a ON ms.horse_id=a.id WHERE ms.date BETWEEN ? AND ?"
    params2 = [ehleh, duusah]
    if trainer_id: sql2 += " AND ms.trainer_id=?"; params2.append(trainer_id)
    if horse_id: sql2 += " AND ms.horse_id=?"; params2.append(horse_id)
    if horse_code: sql2 += " AND a.registration_code LIKE ?"; params2.append(horse_code+'%')
    sql2 += " GROUP BY ms.type ORDER BY too DESC"
    for r in conn.execute(sql2, params2).fetchall():
        result[r['type']] = result.get(r['type'],0) + r['too']
    conn.close()
    return sorted([{'type':k,'too':v} for k,v in result.items()], key=lambda x:-x['too'])

@app.get("/api/reports/daily_schedule")
def reports_daily_schedule(
    trainer_id: Optional[int]=None,
    horse_id: Optional[int]=None,
    horse_code: Optional[str]=None,
    ehleh: Optional[str]=None,
    duusah: Optional[str]=None
):
    """Өдрийн хуваарийн тайлан"""
    import datetime
    conn = get_db()
    today = datetime.date.today().isoformat()
    if not ehleh: ehleh = today[:7] + '-01'
    if not duusah: duusah = today

    rows = []
    # Plan
    sql = """SELECT p.date, a.name as horse_name, a.registration_code as horse_code, p.type, p.status, 'plan' as src
             FROM training_plan p JOIN horse a ON p.horse_id=a.id
             WHERE p.date BETWEEN ? AND ?"""
    params = [ehleh, duusah]
    if trainer_id: sql += " AND p.trainer_id=?"; params.append(trainer_id)
    if horse_id: sql += " AND p.horse_id=?"; params.append(horse_id)
    if horse_code: sql += " AND a.registration_code LIKE ?"; params.append(horse_code+'%')
    rows += [dict(r) for r in conn.execute(sql+" ORDER BY p.date DESC", params).fetchall()]
    # training_session
    sql2 = """SELECT ms.date, a.name as horse_name, a.registration_code as horse_code, ms.type, 'done' as status, 'soikh' as src
              FROM training_session ms JOIN horse a ON ms.horse_id=a.id
              WHERE ms.date BETWEEN ? AND ?"""
    params2 = [ehleh, duusah]
    if trainer_id: sql2 += " AND ms.trainer_id=?"; params2.append(trainer_id)
    if horse_id: sql2 += " AND ms.horse_id=?"; params2.append(horse_id)
    if horse_code: sql2 += " AND a.registration_code LIKE ?"; params2.append(horse_code+'%')
    rows += [dict(r) for r in conn.execute(sql2+" ORDER BY ms.date DESC", params2).fetchall()]
    conn.close()
    return sorted(rows, key=lambda x: x['date'], reverse=True)
