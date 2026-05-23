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
    # mori_soikh_plan хүснэгт үүсгэх
    conn.execute("""CREATE TABLE IF NOT EXISTS mori_soikh_plan (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        aduu_id INTEGER NOT NULL,
        uyaach_id INTEGER,
        ognoo TEXT NOT NULL,
        turul TEXT NOT NULL,
        status TEXT DEFAULT 'planned',
        tailbar TEXT,
        created_at TEXT DEFAULT (datetime('now'))
    )""")
    conn.commit()
    conn.close()
    # sungaa хүснэгтэд шинэ талбар нэмэх migration
    conn = get_db()
    new_cols = [
        ("naadam_turul", "TEXT"),   # Улсын/Аймгийн/Сумын/Бусад
        ("naadam_ner",   "TEXT"),   # Улсын наадам/Их хурд/...
        ("aimag",        "TEXT"),   # Аймгийн нэр
        ("sum",          "TEXT"),   # Сумын нэр
        ("ezeshigch",    "TEXT"),   # Эзэмшигч
        ("ugshil",       "TEXT"),   # Угшил
        ("zai_km",       "REAL"),   # Уралдсан зай
        ("tsag",         "TEXT"),
        ("gazar",        "TEXT"),
    ]
    existing = [row[1] for row in conn.execute("PRAGMA table_info(sungaa)").fetchall()]
    for col, typ in new_cols:
        if col not in existing:
            conn.execute(f"ALTER TABLE sungaa ADD COLUMN {col} {typ}")
    conn.commit()
    conn.close()

@app.get("/")
def root(): return FileResponse(os.path.join(FRONTEND, "index.html"))

# ── STATS ──
class HongolIn(BaseModel):
    aduu_id: int
    ognoo: str
    hiin_ner: Optional[str]=None
    tailbar: Optional[str]=None

@app.get("/api/stats")
def stats():
    conn = get_db()
    return {
        "total": conn.execute("SELECT COUNT(*) FROM aduu WHERE idevhtei=1").fetchone()[0],
        "azarga": conn.execute("SELECT COUNT(*) FROM aduu WHERE huis='azarga' AND idevhtei=1").fetchone()[0],
        "guu": conn.execute("SELECT COUNT(*) FROM aduu WHERE huis='guu' AND idevhtei=1").fetchone()[0],
        "surg": conn.execute("SELECT COUNT(*) FROM surg WHERE idevhtei=1").fetchone()[0],
        "holboo": conn.execute("SELECT COUNT(*) FROM holboo").fetchone()[0],
        "ajil_todorhoigui": conn.execute("SELECT COUNT(*) FROM ajil WHERE status='todorhoi'").fetchone()[0],
    }

# ── ADUU ──
@app.get("/api/aduu")
def aduu_list(
    ner: Optional[str]=None,
    aduu_id: Optional[str]=None,
    dugaar: Optional[str]=None,
    huis: Optional[str]=None,
    status: Optional[str]=None,
    surg_id: Optional[int]=None,
    ugshil_id: Optional[int]=None,
    zus_id: Optional[int]=None,
    ezeshigch_id: Optional[int]=None,
    malchin_id: Optional[int]=None,
    chip: Optional[str]=None,
    torson_type: Optional[str]=None,
    torson_date: Optional[str]=None,
    torson_date2: Optional[str]=None,
    torson_on: Optional[str]=None,
    idevhtei: Optional[int]=1,
    limit: int=50,
    offset: int=0,
    export: int=0
):
    conn = get_db()
    sql = """SELECT a.id,a.ner,a.huis,a.torson,a.status,a.aduu_id,a.dugaar,
        a.chip,a.chuhal,a.surg_id, s.ner as surg_ner, tz.ner as zus_ner, tu.ner as ugshil_ner,
        hm.ner as malchin_ner, h.ner as ezeshigch_ner,
        e.ner as eceg_ner, m.ner as eh_ner
        FROM aduu a
        LEFT JOIN surg s ON a.surg_id=s.id
        LEFT JOIN tohiruulga tz ON a.zus_id=tz.id
        LEFT JOIN tohiruulga tu ON a.ugshil_id=tu.id
        LEFT JOIN holboo hm ON a.malchin_id=hm.id
        LEFT JOIN aduu_ezeshigch ae ON a.id=ae.aduu_id
        LEFT JOIN holboo h ON ae.ezeshigch_id=h.id
        LEFT JOIN aduu e ON a.eceg_id=e.id
        LEFT JOIN aduu m ON a.eh_id=m.id
        WHERE (? IS NULL OR a.idevhtei=?)"""
    p = [idevhtei, idevhtei]
    if ner: sql += " AND UPPER(a.ner) LIKE UPPER(?)"; p.append(f"%{ner}%")
    if aduu_id: sql += " AND a.aduu_id LIKE ?"; p.append(f"%{aduu_id}%")
    if dugaar: sql += " AND a.dugaar LIKE ?"; p.append(f"%{dugaar}%")
    if huis:
        huis_db = 'azarga' if huis == 'er' else ('guu' if huis == 'ohin' else ('morini' if huis == 'morini' else huis))
        sql += " AND a.huis=?"; p.append(huis_db)
    if status == 'heel_hayas':
        sql += " AND a.huis='guu' AND EXISTS(SELECT 1 FROM nokhon_urjikh n WHERE n.aduu_id=a.id AND n.turul='heel_hayas')"; 
    elif status == 'suvairsan':
        import datetime
        this_yr = datetime.date.today().year
        this_year = str(this_yr)
        sql += """ AND a.huis='guu'
            AND a.torson IS NOT NULL
            AND (?-CAST(strftime('%Y',a.torson) AS INT)+1)>=4
            AND NOT EXISTS(SELECT 1 FROM aduu u WHERE u.eh_id=a.id AND strftime('%Y',u.torson)=?)
            AND NOT EXISTS(SELECT 1 FROM nokhon_urjikh n WHERE n.aduu_id=a.id AND n.turul='heel_hayas' AND strftime('%Y',n.ognoo)=?)"""
        p += [this_yr, this_year, this_year]
    elif status:
        sql += " AND a.status=?"; p.append(status)
    if surg_id: sql += " AND a.surg_id=?"; p.append(surg_id)
    if ugshil_id: sql += " AND a.ugshil_id=?"; p.append(ugshil_id)
    if zus_id: sql += " AND a.zus_id=?"; p.append(zus_id)
    if malchin_id: sql += " AND a.malchin_id=?"; p.append(malchin_id)
    if ezeshigch_id: sql += " AND ae.ezeshigch_id=?"; p.append(ezeshigch_id)
    if chip: sql += " AND a.chip LIKE ?"; p.append(f"%{chip}%")
    if torson_on: sql += " AND strftime('%Y', a.torson)=?"; p.append(str(torson_on))
    if torson_type == "omno" and torson_date: sql += " AND a.torson < ?"; p.append(torson_date)
    elif torson_type == "daraa" and torson_date: sql += " AND a.torson > ?"; p.append(torson_date)
    elif torson_type == "dotor" and torson_date and torson_date2: sql += " AND a.torson BETWEEN ? AND ?"; p += [torson_date, torson_date2]
    # Нийт тоо болон хүйсийн тоог тусад нь тооцох
    rows_all = conn.execute(sql + " GROUP BY a.id ORDER BY a.ner", p).fetchall()
    total = len(rows_all)
    er_too = sum(1 for r in rows_all if r['huis'] in ('azarga','er','morini'))
    ohin_too = sum(1 for r in rows_all if r['huis'] in ('guu','ohin'))
    if export:
        conn.close()
        return {"total": total, "er_too": er_too, "ohin_too": ohin_too, "data": [dict(r) for r in rows_all]}
    rows = rows_all[offset:offset+limit]
    conn.close()
    return {"total": total, "er_too": er_too, "ohin_too": ohin_too, "data": [dict(r) for r in rows]}

@app.get("/api/aduu/export/csv")
def aduu_export_csv(
    ner: Optional[str]=None, aduu_id: Optional[str]=None, dugaar: Optional[str]=None,
    huis: Optional[str]=None, status: Optional[str]=None, surg_id: Optional[int]=None,
    ugshil_id: Optional[int]=None, zus_id: Optional[int]=None, ezeshigch_id: Optional[int]=None,
    malchin_id: Optional[int]=None, chip: Optional[str]=None, torson_on: Optional[str]=None,
    idevhtei: Optional[int]=1
):
    import datetime
    conn = get_db()
    sql = """SELECT a.ner,a.aduu_id,a.dugaar,a.huis,a.torson,
        tz.ner as zus_ner, tu.ner as ugshil_ner,
        e.ner as eceg_ner, m.ner as eh_ner,
        h.ner as ezeshigch_ner, s.ner as surg_ner, a.status, a.chip, a.pasport
        FROM aduu a
        LEFT JOIN surg s ON a.surg_id=s.id
        LEFT JOIN tohiruulga tz ON a.zus_id=tz.id
        LEFT JOIN tohiruulga tu ON a.ugshil_id=tu.id
        LEFT JOIN aduu_ezeshigch ae ON a.id=ae.aduu_id
        LEFT JOIN holboo h ON ae.ezeshigch_id=h.id
        LEFT JOIN aduu e ON a.eceg_id=e.id
        LEFT JOIN aduu m ON a.eh_id=m.id
        WHERE (? IS NULL OR a.idevhtei=?)"""
    p = [idevhtei, idevhtei]
    if ner: sql += " AND UPPER(a.ner) LIKE UPPER(?)"; p.append(f"%{ner}%")
    if aduu_id: sql += " AND a.aduu_id LIKE ?"; p.append(f"%{aduu_id}%")
    if dugaar: sql += " AND a.dugaar LIKE ?"; p.append(f"%{dugaar}%")
    if huis:
        huis_db = 'azarga' if huis=='er' else ('guu' if huis=='ohin' else huis)
        sql += " AND a.huis=?"; p.append(huis_db)
    if status: sql += " AND a.status=?"; p.append(status)
    if surg_id: sql += " AND a.surg_id=?"; p.append(surg_id)
    if ugshil_id: sql += " AND a.ugshil_id=?"; p.append(ugshil_id)
    if zus_id: sql += " AND a.zus_id=?"; p.append(zus_id)
    if ezeshigch_id: sql += " AND ae.ezeshigch_id=?"; p.append(ezeshigch_id)
    if chip: sql += " AND a.chip LIKE ?"; p.append(f"%{chip}%")
    if torson_on: sql += " AND strftime('%Y',a.torson)=?"; p.append(str(torson_on))
    rows = conn.execute(sql + " GROUP BY a.id ORDER BY a.ner", p).fetchall()
    conn.close()
    HUISMAP = {'azarga':'Азарга','guu':'Гүү','er':'Эр','ohin':'Охин','morini':'Морь','unaga_er':'Унага эр','unaga_em':'Унага охин'}
    output = io.StringIO()
    output.write('\ufeff')  # BOM — Excel монгол тэмдэгт зөв харуулна
    writer = csv.writer(output)
    writer.writerow(['Нэр','ID','№','Хүйс','Зүс','Төрсөн','Угшил','Эцэг','Эх','Эзэмшигч','Сүрэг','Статус','Чип','Паспорт'])
    for r in rows:
        writer.writerow([
            r['ner']or'', r['aduu_id']or'', r['dugaar']or'',
            HUISMAP.get(r['huis'],r['huis']or''),
            r['zus_ner']or'', r['torson']or'', r['ugshil_ner']or'',
            r['eceg_ner']or'', r['eh_ner']or'', r['ezeshigch_ner']or'',
            r['surg_ner']or'', r['status']or'', r['chip']or'', r['pasport']or''
        ])
    filename = f"aduu_{datetime.date.today().isoformat()}.csv"
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{filename}"}
    )

@app.get("/api/aduu/{id}/udam")
def aduu_udam(id: int, ue: int=3):
    conn = get_db()
    def get_node(aid, depth):
        if not aid or depth > ue: return None
        r = conn.execute("SELECT id,ner,huis,torson,aduu_id,dugaar,eceg_id,eh_id FROM aduu WHERE id=?", (aid,)).fetchone()
        if not r: return None
        node = dict(r)
        if depth < ue:
            node['eceg'] = get_node(r['eceg_id'], depth+1)
            node['eh'] = get_node(r['eh_id'], depth+1)
        return node
    return get_node(id, 0) or {}


@app.get("/api/aduu/check_id")
def aduu_check_id(aduu_id: str, exclude_id: Optional[int]=None):
    conn = get_db()
    sql = "SELECT id, ner FROM aduu WHERE aduu_id=?"
    p = [aduu_id]
    if exclude_id:
        sql += " AND id!=?"
        p.append(exclude_id)
    r = conn.execute(sql, p).fetchone()
    conn.close()
    if r:
        return {"exists": True, "ner": r["ner"], "id": r["id"]}
    return {"exists": False}

@app.get("/api/aduu/hongol_eligible")
def hongol_eligible(ezeshigch_id: Optional[int]=None, nas_min: int=3, nas_max: Optional[int]=None):
    import datetime
    conn = get_db()
    this_year = datetime.date.today().year
    sql = (
        "SELECT a.id, a.ner, a.torson, a.huis, a.aduu_id, h.ner as ezeshigch_ner, h.id as ez_id "
        "FROM aduu a "
        "LEFT JOIN aduu_ezeshigch ae ON a.id=ae.aduu_id "
        "LEFT JOIN holboo h ON ae.ezeshigch_id=h.id "
        "WHERE a.huis='azarga' AND a.idevhtei=1 AND a.torson IS NOT NULL"
    )
    p = []
    if ezeshigch_id:
        sql += " AND ae.ezeshigch_id=?"
        p.append(ezeshigch_id)
    rows = conn.execute(sql, p).fetchall()
    seen = set()
    result = []
    for r in rows:
        if r['id'] in seen: continue
        seen.add(r['id'])
        age = this_year - int(r['torson'][:4]) + 1
        if age < nas_min: continue
        if nas_max and age > nas_max: continue
        result.append({'id': r['id'], 'ner': r['ner'], 'torson': r['torson'],
                      'huis': r['huis'], 'aduu_id': r['aduu_id'], 'age': age,
                      'ezeshigch_ner': r['ezeshigch_ner'], 'ezeshigch_id': r['ez_id']})
    conn.close()
    return result

@app.get("/api/aduu/{id}")
def aduu_detail(id: int):
    conn = get_db()
    r = conn.execute("""SELECT a.*,s.ner as surg_ner,tz.ner as zus_ner,tu.ner as ugshil_ner,
        tg.ner as garal_ner,h.ner as malchin_ner,z.ner as zuchee_ner,
        e.ner as eceg_ner, m.ner as eh_ner
        FROM aduu a
        LEFT JOIN surg s ON a.surg_id=s.id
        LEFT JOIN tohiruulga tz ON a.zus_id=tz.id
        LEFT JOIN tohiruulga tu ON a.ugshil_id=tu.id
        LEFT JOIN tohiruulga tg ON a.garal_id=tg.id
        LEFT JOIN holboo h ON a.malchin_id=h.id
        LEFT JOIN zuchee z ON a.zuchee_id=z.id
        LEFT JOIN aduu e ON a.eceg_id=e.id
        LEFT JOIN aduu m ON a.eh_id=m.id
        WHERE a.id=?""", (id,)).fetchone()
    if not r: raise HTTPException(404,"Олдсонгүй")
    d = dict(r)
    d['ezeshigchid'] = [dict(x) for x in conn.execute(
        "SELECT h.id as holboo_id,h.ner,ae.huvi FROM aduu_ezeshigch ae JOIN holboo h ON ae.ezeshigch_id=h.id WHERE ae.aduu_id=?", (id,)).fetchall()]
    d['sungaa'] = [dict(x) for x in conn.execute("SELECT * FROM sungaa WHERE aduu_id=? ORDER BY ognoo DESC",(id,)).fetchall()]
    d['zuragnuud'] = [dict(x) for x in conn.execute("SELECT * FROM zurag WHERE aduu_id=?",(id,)).fetchall()]
    return d

class AduuIn(BaseModel):
    ner: str
    registerlesen: Optional[int]=1
    aduu_id: Optional[str]=None
    id_gui: Optional[int]=0
    dugaar: Optional[str]=None
    huis: Optional[str]=None
    ugshil_id: Optional[int]=None
    tsusni_huvi: Optional[str]=None
    garal_id: Optional[int]=None
    surg_id: Optional[int]=None
    zus_id: Optional[int]=None
    status: Optional[str]='idevhtei'
    torson: Optional[str]=None
    ognoo_gui: Optional[int]=0
    chip: Optional[str]=None
    pasport: Optional[str]=None
    dnh: Optional[str]=None
    senas_bie: Optional[str]=None
    senas_tolgoi: Optional[str]=None
    senas_hel: Optional[str]=None
    tamga: Optional[str]=None
    zuchee_id: Optional[int]=None
    bayrshal: Optional[str]=None
    malchin_id: Optional[int]=None
    tailbar: Optional[str]=None
    huviin_temdeglel: Optional[str]=None
    hongoloson: Optional[int]=0
    eceg_id: Optional[int]=None
    eh_id: Optional[int]=None
    ezeshigchid: Optional[List[dict]]=[]
    chuhal: Optional[int]=0

@app.post("/api/aduu")
def aduu_create(d: AduuIn):
    conn = get_db()
    # aduu_id давхардал шалгах
    if d.aduu_id and not d.id_gui:
        existing = conn.execute("SELECT id, ner FROM aduu WHERE aduu_id=?", (d.aduu_id,)).fetchone()
        if existing:
            raise HTTPException(400, f"ID {d.aduu_id} давхардаж байна! ({existing['ner']})")
    cur = conn.execute("""INSERT INTO aduu (ner,registerlesen,aduu_id,id_gui,dugaar,huis,ugshil_id,tsusni_huvi,garal_id,surg_id,zus_id,status,torson,ognoo_gui,chip,pasport,dnh,senas_bie,senas_tolgoi,senas_hel,tamga,zuchee_id,bayrshal,malchin_id,tailbar,huviin_temdeglel,hongoloson,eceg_id,eh_id,chuhal)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (d.ner,d.registerlesen,d.aduu_id,d.id_gui,d.dugaar,d.huis,d.ugshil_id,d.tsusni_huvi,d.garal_id,d.surg_id,d.zus_id,d.status,d.torson,d.ognoo_gui,d.chip,d.pasport,d.dnh,d.senas_bie,d.senas_tolgoi,d.senas_hel,d.tamga,d.zuchee_id,d.bayrshal,d.malchin_id,d.tailbar,d.huviin_temdeglel,d.hongoloson,d.eceg_id,d.eh_id,d.chuhal or 0))
    aid = cur.lastrowid
    for e in (d.ezeshigchid or []):
        if e.get('holboo_id'):
            conn.execute("INSERT INTO aduu_ezeshigch (aduu_id,ezeshigch_id,huvi) VALUES (?,?,?)",(aid,e['holboo_id'],e.get('huvi',100)))
    conn.commit(); return {"id": aid}

@app.put("/api/aduu/{id}")
def aduu_update(id: int, d: AduuIn):
    conn = get_db()
    # aduu_id давхардал шалгах (өөрийн id-г хасч)
    if d.aduu_id and not d.id_gui:
        existing = conn.execute("SELECT id, ner FROM aduu WHERE aduu_id=? AND id!=?", (d.aduu_id, id)).fetchone()
        if existing:
            raise HTTPException(400, f"ID {d.aduu_id} давхардаж байна! ({existing['ner']})")
    conn.execute("""UPDATE aduu SET ner=?,registerlesen=?,aduu_id=?,dugaar=?,huis=?,ugshil_id=?,tsusni_huvi=?,garal_id=?,surg_id=?,zus_id=?,status=?,torson=?,chip=?,pasport=?,dnh=?,senas_bie=?,senas_tolgoi=?,senas_hel=?,tamga=?,zuchee_id=?,bayrshal=?,malchin_id=?,tailbar=?,hongoloson=?,eceg_id=?,eh_id=?,chuhal=? WHERE id=?""",
        (d.ner,d.registerlesen,d.aduu_id,d.dugaar,d.huis,d.ugshil_id,d.tsusni_huvi,d.garal_id,d.surg_id,d.zus_id,d.status,d.torson,d.chip,d.pasport,d.dnh,d.senas_bie,d.senas_tolgoi,d.senas_hel,d.tamga,d.zuchee_id,d.bayrshal,d.malchin_id,d.tailbar,d.hongoloson,d.eceg_id,d.eh_id,d.chuhal or 0,id))
    conn.execute("DELETE FROM aduu_ezeshigch WHERE aduu_id=?", (id,))
    for e in (d.ezeshigchid or []):
        if e.get('holboo_id'):
            conn.execute("INSERT INTO aduu_ezeshigch (aduu_id,ezeshigch_id,huvi) VALUES (?,?,?)",(id,e['holboo_id'],e.get('huvi',100)))
    conn.commit(); return {"ok": True}


def nas_nershil(torson: str, huis: str, hongoloson: int = 0) -> str:
    """Монгол адууны нас, нэршил тооцох"""
    if not torson:
        return ""
    from datetime import date
    try:
        born = date.fromisoformat(torson[:10])
    except:
        return ""
    today = date.today()
    # Монгол тооллоор: төрсөн жил = 1 нас
    nas = today.year - born.year + 1
    er = huis in ('azarga', 'er')
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
            return "Морь" if hongoloson else "Азарга"
        return "Гүү"

# ── HAILT ──
@app.get("/api/hailt")
def hailt(q: str="", huis: Optional[str]=None, include_udam: int=0, dugaar: Optional[str]=None):
    conn = get_db()
    if dugaar:
        # Эхлэлээс яг тохирох, дараа нь хаана ч байсан хайх
        sql = """SELECT a.id,a.ner,a.huis,a.torson,a.dugaar,tz.ner as zus_ner,a.idevhtei
            FROM aduu a LEFT JOIN tohiruulga tz ON a.zus_id=tz.id
            WHERE a.dugaar=?"""
        p = [dugaar]
        if huis: sql += " AND a.huis=?"; p.append(huis)
        rows = conn.execute(sql + " LIMIT 15", p).fetchall()
        if not rows:
            # Яг тохирохгүй бол эхлэлээс хайх
            sql2 = sql.replace("a.dugaar=?", "a.dugaar LIKE ?")
            p2 = [f"{dugaar}%"]
            if huis: p2.append(huis)
            rows = conn.execute(sql2 + " LIMIT 15", p2).fetchall()
        return [dict(r) for r in rows]
    if include_udam:
        sql = "SELECT a.id,a.ner,a.huis,a.torson,a.dugaar,tz.ner as zus_ner,a.idevhtei FROM aduu a LEFT JOIN tohiruulga tz ON a.zus_id=tz.id WHERE UPPER(a.ner) LIKE UPPER(?)"
    else:
        sql = "SELECT a.id,a.ner,a.huis,a.torson,a.dugaar,tz.ner as zus_ner,a.idevhtei FROM aduu a LEFT JOIN tohiruulga tz ON a.zus_id=tz.id WHERE a.idevhtei=1 AND UPPER(a.ner) LIKE UPPER(?)"
    p = [f"%{q}%"]
    if huis:
        sql += " AND a.huis=?"; p.append(huis)
    sql += " LIMIT 15"
    rows = []
    for r in conn.execute(sql, p).fetchall():
        d = dict(r)
        # SQLite dict-д давхардсан нэр авахад сүүлийнх нь давдаг
        # aduu.id-г тусдаа авахын тулд cursor description ашиглана
        rows.append(d)
    # aduu.id-г cursor-аас шууд авах
    cur = conn.execute(sql, p)
    cols = [desc[0] for desc in cur.description]
    for i, r in enumerate(cur.fetchall()):
        vals = list(r)
        for j, col in enumerate(cols):
            if col == 'aduu_sys_id':
                rows[i]['aduu_sys_id'] = vals[j]
    return rows

# ── UDAM BURTGEL ──
@app.get("/api/udam_burtgel")
def udam_list(q: Optional[str]=None, huis: Optional[str]=None, limit: int=100, offset: int=0):
    conn = get_db()
    sql = """SELECT a.id,a.ner,a.huis,a.torson,a.dugaar,a.aduu_id,
        tz.ner as zus_ner, tu.ner as ugshil_ner, tg.ner as garal_ner,
        e.ner as eceg_ner, m.ner as eh_ner
        FROM aduu a
        LEFT JOIN tohiruulga tz ON a.zus_id=tz.id
        LEFT JOIN tohiruulga tu ON a.ugshil_id=tu.id
        LEFT JOIN tohiruulga tg ON a.garal_id=tg.id
        LEFT JOIN aduu e ON a.eceg_id=e.id
        LEFT JOIN aduu m ON a.eh_id=m.id
        WHERE a.idevhtei=0 AND a.status='udam'"""
    p = []
    if q: sql += " AND a.ner LIKE ?"; p.append(f"%{q}%")
    if huis: sql += " AND a.huis=?"; p.append(huis)
    total = conn.execute(f"SELECT COUNT(*) FROM ({sql})", p).fetchone()[0]
    rows = conn.execute(sql + " ORDER BY a.ner LIMIT ? OFFSET ?", p+[limit,offset]).fetchall()
    return {"total": total, "data": [dict(r) for r in rows]}

class UdamIn(BaseModel):
    ner: str
    huis: Optional[str]=None
    torson: Optional[str]=None
    dugaar: Optional[str]=None
    ugshil_id: Optional[int]=None
    garal_id: Optional[int]=None
    zus_id: Optional[int]=None
    eceg_id: Optional[int]=None
    eh_id: Optional[int]=None

@app.post("/api/udam_burtgel")
def udam_create(d: UdamIn):
    conn = get_db()
    cur = conn.execute("""INSERT INTO aduu (ner,huis,torson,dugaar,ugshil_id,garal_id,zus_id,eceg_id,eh_id,idevhtei,status,registerlesen)
        VALUES (?,?,?,?,?,?,?,?,?,0,'udam',0)""",
        (d.ner.upper(),d.huis,d.torson,d.dugaar,d.ugshil_id,d.garal_id,d.zus_id,d.eceg_id,d.eh_id))
    conn.commit(); return {"id": cur.lastrowid}

@app.put("/api/udam_burtgel/{id}")
def udam_update(id: int, d: UdamIn):
    conn = get_db()
    conn.execute("""UPDATE aduu SET ner=?,huis=?,torson=?,dugaar=?,ugshil_id=?,garal_id=?,zus_id=?,eceg_id=?,eh_id=?
        WHERE id=? AND status='udam'""",
        (d.ner.upper(),d.huis,d.torson,d.dugaar,d.ugshil_id,d.garal_id,d.zus_id,d.eceg_id,d.eh_id,id))
    conn.commit(); return {"ok": True}

@app.delete("/api/udam_burtgel/{id}")
def udam_delete(id: int):
    conn = get_db()
    refs = conn.execute("SELECT COUNT(*) FROM aduu WHERE (eceg_id=? OR eh_id=?) AND idevhtei=1",(id,id)).fetchone()[0]
    if refs > 0:
        raise HTTPException(400, f"Энэ адуу {refs} адууны удамд холбоотой, устгах боломжгүй")
    conn.execute("DELETE FROM aduu WHERE id=? AND status='udam'",(id,))
    conn.commit(); return {"ok": True}

@app.post("/api/udam_burtgel/{id}/shiljuuleh")
def udam_shiljuuleh(id: int):
    conn = get_db()
    r = conn.execute("SELECT id FROM aduu WHERE id=? AND status='udam'",(id,)).fetchone()
    if not r: raise HTTPException(404,"Удам олдсонгүй")
    conn.execute("UPDATE aduu SET idevhtei=1, status='idevhtei', registerlesen=0 WHERE id=?",(id,))
    conn.commit(); return {"ok": True}

# ── ХӨНГӨЛӨХ ──
@app.post("/api/hongol")
def hongol_create(d: HongolIn):
    conn = get_db()
    aduu = conn.execute("SELECT huis, ner FROM aduu WHERE id=?", (d.aduu_id,)).fetchone()
    if not aduu:
        raise HTTPException(404, "Адуу олдсонгүй")
    if aduu['huis'] not in ('azarga', 'er'):
        raise HTTPException(400, "Зөвхөн эр адуу хөнгөлөх боломжтой")
    conn.execute("UPDATE aduu SET huis='morini' WHERE id=?", (d.aduu_id,))
    conn.execute("INSERT INTO hongol (aduu_id, ognoo, hiin_ner, tailbar) VALUES (?,?,?,?)",
        (d.aduu_id, d.ognoo, d.hiin_ner, d.tailbar))
    conn.commit()
    conn.close()
    return {"ok": True}

@app.get("/api/hongol")
def hongol_list(aduu_id: Optional[int]=None):
    conn = get_db()
    sql = """SELECT h.*, a.ner as aduu_ner FROM hongol h
             JOIN aduu a ON h.aduu_id=a.id WHERE 1=1"""
    p = []
    if aduu_id:
        sql += " AND h.aduu_id=?"
        p.append(aduu_id)
    sql += " ORDER BY h.ognoo DESC"
    rows = [dict(r) for r in conn.execute(sql, p).fetchall()]
    conn.close()
    return rows

@app.delete("/api/hongol/{id}")
def hongol_delete(id: int):
    conn = get_db()
    # Хөнгөлөлт устгахад huis-г буцаах
    h = conn.execute("SELECT aduu_id FROM hongol WHERE id=?", (id,)).fetchone()
    if h:
        conn.execute("UPDATE aduu SET huis='azarga' WHERE id=? AND huis='morini'", (h['aduu_id'],))
        conn.execute("DELETE FROM hongol WHERE id=?", (id,))
    conn.commit()
    conn.close()
    return {"ok": True}

# ── SURG ──
@app.get("/api/surg")
def surg_list():
    conn = get_db()
    return [dict(r) for r in conn.execute("""SELECT s.*,COUNT(ad.id) as aduu_too
        FROM surg s 
        LEFT JOIN aduu ad ON s.id=ad.surg_id AND ad.idevhtei=1
        WHERE s.idevhtei=1 GROUP BY s.id ORDER BY s.ner""").fetchall()]

@app.get("/api/surg/{id}")
def surg_detail(id: int):
    conn = get_db()
    s = conn.execute("SELECT * FROM surg WHERE id=?", (id,)).fetchone()
    if not s: raise HTTPException(404,"Олдсонгүй")
    d = dict(s)
    d['aduu_too'] = conn.execute("SELECT COUNT(*) FROM aduu WHERE surg_id=? AND idevhtei=1",(id,)).fetchone()[0]
    return d

class SurgIn(BaseModel):
    ner: str
    azarga_id: Optional[int]=None
    tailbar: Optional[str]=None

@app.post("/api/surg")
def surg_create(d: SurgIn):
    conn = get_db()
    cur = conn.execute("INSERT INTO surg (ner,azarga_id,tailbar) VALUES (?,?,?)",(d.ner,d.azarga_id,d.tailbar))
    conn.commit(); return {"id": cur.lastrowid}

# ── HOLBOO ──
@app.get("/api/holboo")
def holboo_list(q: Optional[str]=None, turul: Optional[str]=None):
    conn = get_db()
    sql = "SELECT h.*,COUNT(ae.id) as aduu_too FROM holboo h LEFT JOIN aduu_ezeshigch ae ON h.id=ae.ezeshigch_id WHERE 1=1"
    p = []
    if q: sql += " AND h.ner LIKE ?"; p.append(f"%{q}%")
    if turul: sql += " AND h.turul=?"; p.append(turul)
    return [dict(r) for r in conn.execute(sql+" GROUP BY h.id ORDER BY h.ner", p).fetchall()]

class HolbooIn(BaseModel):
    ner: str
    turul: Optional[str]='ezeshigch'
    utas: Optional[str]=None
    email: Optional[str]=None
    hot: Optional[str]=None
    hayag: Optional[str]=None

@app.post("/api/holboo")
def holboo_create(d: HolbooIn):
    conn = get_db()
    cur = conn.execute("INSERT INTO holboo (ner,turul,utas,email,hot,hayag) VALUES (?,?,?,?,?,?)",(d.ner,d.turul,d.utas,d.email,d.hot,d.hayag))
    conn.commit(); return {"id": cur.lastrowid}

@app.get("/api/holboo/{id}")
def holboo_get(id: int):
    conn = get_db()
    r = conn.execute("SELECT * FROM holboo WHERE id=?", (id,)).fetchone()
    return dict(r) if r else {}

@app.delete("/api/holboo/{id}")
def holboo_delete(id: int):
    conn = get_db()
    conn.execute("DELETE FROM holboo WHERE id=?", (id,))
    conn.commit(); return {"ok": True}

@app.put("/api/holboo/{id}")
def holboo_update(id: int, d: HolbooIn):
    conn = get_db()
    conn.execute("UPDATE holboo SET ner=?,turul=?,utas=?,email=?,hot=?,hayag=? WHERE id=?",(d.ner,d.turul,d.utas,d.email,d.hot,d.hayag,id))
    conn.commit(); return {"ok": True}

# ── TOHIRUULGA ──
@app.get("/api/tohiruulga")
def tohiruulga_list():
    conn = get_db()
    return [dict(r) for r in conn.execute("SELECT * FROM tohiruulga WHERE idevhtei=1 ORDER BY turul,ner").fetchall()]

@app.post("/api/tohiruulga")
def tohiruulga_create(turul: str=Form(...), ner: str=Form(...)):
    conn = get_db()
    r = conn.execute("SELECT id FROM tohiruulga WHERE turul=? AND ner=?",(turul,ner)).fetchone()
    if r: return {"id": r[0]}
    cur = conn.execute("INSERT INTO tohiruulga (turul,ner) VALUES (?,?)",(turul,ner))
    conn.commit(); return {"id": cur.lastrowid}

@app.delete("/api/tohiruulga/{id}")
def tohiruulga_delete(id: int):
    conn = get_db()
    conn.execute("UPDATE tohiruulga SET idevhtei=0 WHERE id=?",(id,))
    conn.commit(); return {"ok": True}

@app.put("/api/tohiruulga/{id}")
def tohiruulga_update(id: int, ner: str = Form(...)):
    conn = get_db()
    conn.execute("UPDATE tohiruulga SET ner=? WHERE id=?", (ner, id))
    conn.commit(); return {"ok": True}

# ── ZUCHEE ──
@app.get("/api/zuchee")
def zuchee_list(turul: Optional[str]=None):
    conn = get_db()
    sql = "SELECT z.*,COUNT(a.id) as aduu_too FROM zuchee z LEFT JOIN aduu a ON z.id=a.zuchee_id WHERE z.idevhtei=1"
    p = []
    if turul: sql += " AND z.turul=?"; p.append(turul)
    return [dict(r) for r in conn.execute(sql+" GROUP BY z.id ORDER BY z.ner", p).fetchall()]

class ZucheeIn(BaseModel):
    ner: str
    turul: Optional[str]='zuchee'
    bayrshal: Optional[str]='huvtee'
    mur_too: Optional[int]=1
    haircag_too: Optional[int]=1

@app.post("/api/zuchee")
def zuchee_create(d: ZucheeIn):
    conn = get_db()
    cur = conn.execute("INSERT INTO zuchee (ner,turul,bayrshal,mur_too,haircag_too) VALUES (?,?,?,?,?)",(d.ner,d.turul,d.bayrshal,d.mur_too,d.haircag_too))
    conn.commit(); return {"id": cur.lastrowid}

@app.delete("/api/zuchee/{id}")
def zuchee_delete(id: int):
    conn = get_db()
    conn.execute("UPDATE zuchee SET idevhtei=0 WHERE id=?",(id,))
    conn.commit(); return {"ok": True}

# ── AJIL ──
@app.get("/api/ajil")
def ajil_list(status: Optional[str]=None, limit: int=50):
    conn = get_db()
    sql = "SELECT aj.*,h.ner as huvaarlisan_ner FROM ajil aj LEFT JOIN holboo h ON aj.huvaarlisan_id=h.id WHERE 1=1"
    p = []
    if status: sql += " AND aj.status=?"; p.append(status)
    return [dict(r) for r in conn.execute(sql+" ORDER BY aj.ognoo LIMIT ?", p+[limit]).fetchall()]

class AjilIn(BaseModel):
    ner: str
    tailbar: Optional[str]=None
    ognoo: Optional[str]=None
    tsag: Optional[str]=None
    davtalt: Optional[str]='ganc'
    erembe: Optional[str]='dundaj'

@app.post("/api/ajil")
def ajil_create(d: AjilIn):
    conn = get_db()
    cur = conn.execute("INSERT INTO ajil (ner,tailbar,ognoo,tsag,davtalt,erembe) VALUES (?,?,?,?,?,?)",(d.ner,d.tailbar,d.ognoo,d.tsag,d.davtalt,d.erembe))
    conn.commit(); return {"id": cur.lastrowid}

@app.put("/api/ajil/{id}/status")
def ajil_status(id: int, status: str=Form(...)):
    conn = get_db()
    conn.execute("UPDATE ajil SET status=? WHERE id=?",(status,id))
    conn.commit(); return {"ok": True}

@app.delete("/api/ajil/{id}")
def ajil_delete(id: int):
    conn = get_db()
    conn.execute("DELETE FROM ajil WHERE id=?",(id,))
    conn.commit(); return {"ok": True}

# ── SUNGAA ──
@app.get("/api/sungaa")
def sungaa_list(aduu_id: Optional[int]=None, naadam_id: Optional[int]=None):
    conn = get_db()
    sql = """SELECT sg.id,sg.aduu_id,sg.uyaach_id,sg.ognoo,sg.turul,sg.dur,sg.tailbar,
        sg.naadam_id,sg.unach,sg.nas_angilal,sg.bair,
        sg.naadam_turul,sg.naadam_ner,sg.aimag,sg.sum,
        sg.ezeshigch,sg.ugshil,sg.zai_km,sg.tsag,sg.gazar,
        a.ner as aduu_ner,
        a.torson as aduu_torson,
        a.huis as aduu_huis,
        a.hongoloson as aduu_hongoloson,
        a.aduu_id as aduu_sys_id,
        a.dugaar as aduu_dugaar,
        u.ner as uyaach_ner,
        zus.ner as zus_ner,
        ug.ner as ugshil_ner
        FROM sungaa sg
        JOIN aduu a ON sg.aduu_id=a.id
        LEFT JOIN uyaach u ON sg.uyaach_id=u.id
        LEFT JOIN tohiruulga zus ON a.zus_id=zus.id AND zus.turul='zus'
        LEFT JOIN tohiruulga ug ON a.ugshil_id=ug.id AND ug.turul='ugshil'
        WHERE 1=1"""
    p = []
    if aduu_id: sql += " AND sg.aduu_id=?"; p.append(aduu_id)
    if naadam_id: sql += " AND sg.naadam_id=?"; p.append(naadam_id)
    sql += " ORDER BY sg.bair ASC, sg.ognoo DESC LIMIT 200"
    return [dict(r) for r in conn.execute(sql, p).fetchall()]

class SungaaIn(BaseModel):
    aduu_id: int
    ognoo: Optional[str]=None
    turul: Optional[str]=None       # хуучин талбар — хэвээр үлдэнэ
    dur: Optional[str]=None
    tailbar: Optional[str]=None
    naadam_id: Optional[int]=None
    uyaach_id: Optional[int]=None
    unach: Optional[str]=None
    nas_angilal: Optional[str]=None
    bair: Optional[int]=None
    # Шинэ талбарууд
    naadam_turul: Optional[str]=None  # Улсын/Аймгийн/Сумын/Бусад
    naadam_ner:   Optional[str]=None  # Улсын наадам/Их хурд/...
    aimag:        Optional[str]=None
    sum:          Optional[str]=None
    ezeshigch:    Optional[str]=None
    ugshil:       Optional[str]=None
    gazar:        Optional[str]=None
    zai_km:       Optional[float]=None
    tsag:         Optional[str]=None
    zai_km:       Optional[float]=None
    tsag:         Optional[str]=None  # мм:сс.мс

@app.post("/api/sungaa")
def sungaa_create(d: SungaaIn):
    conn = get_db()
    # naadam_ner-ийг turul талбарт хадгалах (хуучин системтэй нийцүүлэх)
    turul = d.naadam_ner or d.turul
    cur = conn.execute(
        """INSERT INTO sungaa
           (aduu_id,ognoo,turul,dur,tailbar,naadam_id,uyaach_id,unach,nas_angilal,bair,
            naadam_turul,naadam_ner,aimag,sum,ezeshigch,ugshil,zai_km,tsag)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (d.aduu_id,d.ognoo,turul,d.dur,d.tailbar,d.naadam_id,d.uyaach_id,d.unach,
         d.nas_angilal,d.bair,d.naadam_turul,d.naadam_ner,d.aimag,d.sum,
         d.ezeshigch,d.ugshil,d.zai_km,d.tsag))
    conn.commit(); return {"id": cur.lastrowid}

@app.put("/api/sungaa/{id}")
def sungaa_update(id: int, d: SungaaIn):
    conn = get_db()
    turul = d.naadam_ner or d.turul
    conn.execute("""UPDATE sungaa SET
        aduu_id=?,ognoo=?,turul=?,naadam_turul=?,naadam_ner=?,
        aimag=?,sum=?,ezeshigch=?,ugshil=?,
        nas_angilal=?,bair=?,uyaach_id=?,unach=?,tailbar=?,
        zai_km=?,tsag=?,gazar=?
        WHERE id=?""",
        (d.aduu_id,d.ognoo,turul,d.naadam_turul,d.naadam_ner,
        d.aimag,d.sum,d.ezeshigch,d.ugshil,
        d.nas_angilal,d.bair,d.uyaach_id,d.unach,d.tailbar,
        d.zai_km,d.tsag,d.gazar,id))
    conn.commit()
    return {"ok":True}

@app.delete("/api/sungaa/{id}")
def sungaa_delete(id: int):
    conn = get_db()
    conn.execute("DELETE FROM sungaa WHERE id=?", (id,))
    conn.commit(); return {"ok": True}

# ── SANKHUU ──
@app.get("/api/sankhuu")
def sankhuu_list(limit: int=200):
    conn = get_db()
    data = [dict(r) for r in conn.execute("SELECT sk.*,a.ner as aduu_ner FROM sankhuu sk LEFT JOIN aduu a ON sk.aduu_id=a.id ORDER BY sk.ognoo DESC LIMIT ?", (limit,)).fetchall()]
    orlogo = sum(r['dun'] for r in data if r['turul']=='orlogo')
    zarlaga = sum(r['dun'] for r in data if r['turul']=='zarlaga')
    return {"data": data, "orlogo": orlogo, "zarlaga": zarlaga, "tsever": orlogo-zarlaga}

class SankhuuIn(BaseModel):
    turul: str
    ognoo: str
    dun: float
    angilal: Optional[str]=None
    tailbar: Optional[str]=None
    aduu_id: Optional[int]=None

@app.post("/api/sankhuu")
def sankhuu_create(d: SankhuuIn):
    conn = get_db()
    cur = conn.execute("INSERT INTO sankhuu (turul,ognoo,dun,angilal,tailbar,aduu_id) VALUES (?,?,?,?,?,?)",(d.turul,d.ognoo,d.dun,d.angilal,d.tailbar,d.aduu_id))
    conn.commit(); return {"id": cur.lastrowid}

@app.delete("/api/sankhuu/{id}")
def sankhuu_delete(id: int):
    conn = get_db()
    conn.execute("DELETE FROM sankhuu WHERE id=?",(id,))
    conn.commit(); return {"ok": True}

# ── МОРИ СОЙХЫН ТӨЛӨВЛӨГӨӨ ──────────────────────────────────
@app.get("/api/plan")
def plan_list(aduu_id: Optional[int]=None, uyaach_id: Optional[int]=None,
              sar: Optional[str]=None):
    conn = get_db()
    sql = """SELECT p.*,a.ner as aduu_ner,a.aduu_id as aduu_dugaar,
             u.ner as uyaach_ner
             FROM mori_soikh_plan p
             JOIN aduu a ON p.aduu_id=a.id
             LEFT JOIN uyaach u ON p.uyaach_id=u.id
             WHERE 1=1"""
    params = []
    if aduu_id: sql += " AND p.aduu_id=?"; params.append(aduu_id)
    if uyaach_id: sql += " AND p.uyaach_id=?"; params.append(uyaach_id)
    if sar: sql += " AND p.ognoo LIKE ?"; params.append(sar+"%")
    sql += " ORDER BY p.ognoo ASC"
    rows = [dict(r) for r in conn.execute(sql, params).fetchall()]
    conn.close()
    return rows

class PlanIn(BaseModel):
    aduu_id: int
    uyaach_id: Optional[int]=None
    ognoo: str
    turul: str
    status: Optional[str]="planned"
    tailbar: Optional[str]=None

@app.post("/api/plan")
def plan_create(d: PlanIn):
    conn = get_db()
    cur = conn.execute(
        "INSERT INTO mori_soikh_plan (aduu_id,uyaach_id,ognoo,turul,status,tailbar) VALUES (?,?,?,?,?,?)",
        (d.aduu_id, d.uyaach_id, d.ognoo, d.turul, d.status or "planned", d.tailbar)
    )
    conn.commit()
    conn.close()
    return {"id": cur.lastrowid}

@app.put("/api/plan/{id}")
def plan_update(id: int, d: PlanIn):
    conn = get_db()
    conn.execute(
        "UPDATE mori_soikh_plan SET aduu_id=?,uyaach_id=?,ognoo=?,turul=?,status=?,tailbar=? WHERE id=?",
        (d.aduu_id, d.uyaach_id, d.ognoo, d.turul, d.status or "planned", d.tailbar, id)
    )
    conn.commit()
    conn.close()
    return {"ok": True}

@app.delete("/api/plan/{id}")
def plan_delete(id: int):
    conn = get_db()
    conn.execute("DELETE FROM mori_soikh_plan WHERE id=?", (id,))
    conn.commit()
    conn.close()
    return {"ok": True}

# Сарын нэгдсэн тайлан — уяач бүрийн адуу
@app.get("/api/plan/summary")
def plan_summary(uyaach_id: Optional[int]=None, sar: Optional[str]=None):
    conn = get_db()
    sql = """SELECT p.aduu_id, p.status, COUNT(*) as too
             FROM mori_soikh_plan p WHERE 1=1"""
    params = []
    if uyaach_id: sql += " AND p.uyaach_id=?"; params.append(uyaach_id)
    if sar: sql += " AND p.ognoo LIKE ?"; params.append(sar+"%")
    sql += " GROUP BY p.aduu_id, p.status"
    rows = [dict(r) for r in conn.execute(sql, params).fetchall()]
    conn.close()
    return rows

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)

@app.put("/api/surg/{id}")
def surg_update(id: int, d: SurgIn):
    conn = get_db()
    conn.execute("UPDATE surg SET ner=?,azarga_id=?,tailbar=? WHERE id=?",(d.ner,d.azarga_id,d.tailbar,id))
    conn.commit(); return {"ok": True}

@app.delete("/api/surg/{id}")
def surg_delete(id: int):
    conn = get_db()
    conn.execute("UPDATE surg SET idevhtei=0 WHERE id=?",(id,))
    conn.commit(); return {"ok": True}

# ── УЯАЧ ──
class UyaachIn(BaseModel):
    ner: str
    utas: Optional[str]=None
    hayg: Optional[str]=None
    tsol: Optional[str]='tsolgui'
    tailbar: Optional[str]=None

@app.get("/api/uyaach")
def uyaach_list():
    conn = get_db()
    return [dict(r) for r in conn.execute(
        "SELECT u.*, COUNT(au.id) as aduu_too FROM uyaach u LEFT JOIN aduu_uyaach au ON u.id=au.uyaach_id AND au.idevhtei=1 WHERE u.idevhtei=1 GROUP BY u.id ORDER BY u.ner"
    ).fetchall()]

@app.get("/api/uyaach/{id}")
def uyaach_get(id: int):
    conn = get_db()
    u = conn.execute("SELECT * FROM uyaach WHERE id=?", (id,)).fetchone()
    if not u: raise HTTPException(404, "Уяач олдсонгүй")
    aduu = conn.execute("""
        SELECT a.id,a.ner,a.huis,a.torson,a.dugaar,a.hongoloson,au.ehleh_ognoo,au.duusah_ognoo
        FROM aduu_uyaach au JOIN aduu a ON au.aduu_id=a.id
        WHERE au.uyaach_id=? AND au.idevhtei=1 ORDER BY au.ehleh_ognoo DESC
    """, (id,)).fetchall()
    return {**dict(u), "aduu": [dict(a) for a in aduu]}

@app.post("/api/uyaach")
def uyaach_create(d: UyaachIn):
    conn = get_db()
    cur = conn.execute(
        "INSERT INTO uyaach (ner,utas,hayg,tsol,tailbar) VALUES (?,?,?,?,?)",
        (d.ner,d.utas,d.hayg,d.tsol,d.tailbar))
    conn.commit(); return {"id": cur.lastrowid}

@app.put("/api/uyaach/{id}")
def uyaach_update(id: int, d: UyaachIn):
    conn = get_db()
    conn.execute("UPDATE uyaach SET ner=?,utas=?,hayg=?,tsol=?,tailbar=? WHERE id=?",
        (d.ner,d.utas,d.hayg,d.tsol,d.tailbar,id))
    conn.commit(); return {"ok": True}

@app.delete("/api/uyaach/{id}")
def uyaach_delete(id: int):
    conn = get_db()
    conn.execute("UPDATE uyaach SET idevhtei=0 WHERE id=?", (id,))
    conn.commit(); return {"ok": True}

# ── АДУУ-УЯАЧ ХОЛБОО ──
class AduuUyaachIn(BaseModel):
    aduu_id: int
    uyaach_id: int
    ehleh_ognoo: Optional[str]=None
    duusah_ognoo: Optional[str]=None
    tailbar: Optional[str]=None

@app.get("/api/aduu_uyaach")
def aduu_uyaach_by_uyaach(uyaach_id: Optional[int]=None, aduu_id: Optional[int]=None):
    conn = get_db()
    if uyaach_id:
        return [dict(r) for r in conn.execute(
            "SELECT au.*, a.ner as aduu_ner FROM aduu_uyaach au JOIN aduu a ON au.aduu_id=a.id WHERE au.uyaach_id=? AND au.idevhtei=1 ORDER BY a.ner",
            (uyaach_id,)).fetchall()]
    if aduu_id:
        return [dict(r) for r in conn.execute(
            "SELECT au.*,u.ner as uyaach_ner,u.tsol FROM aduu_uyaach au JOIN uyaach u ON au.uyaach_id=u.id WHERE au.aduu_id=? ORDER BY au.ehleh_ognoo DESC",
            (aduu_id,)).fetchall()]
    return []

@app.get("/api/aduu/{id}/uyaach")
def aduu_uyaach_list(id: int):
    conn = get_db()
    return [dict(r) for r in conn.execute("""
        SELECT au.*,u.ner as uyaach_ner,u.tsol
        FROM aduu_uyaach au JOIN uyaach u ON au.uyaach_id=u.id
        WHERE au.aduu_id=? ORDER BY au.ehleh_ognoo DESC
    """, (id,)).fetchall()]

@app.post("/api/aduu_uyaach")
def aduu_uyaach_create(d: AduuUyaachIn):
    conn = get_db()
    cur = conn.execute(
        "INSERT INTO aduu_uyaach (aduu_id,uyaach_id,ehleh_ognoo,duusah_ognoo,tailbar) VALUES (?,?,?,?,?)",
        (d.aduu_id,d.uyaach_id,d.ehleh_ognoo,d.duusah_ognoo,d.tailbar))
    conn.commit(); return {"id": cur.lastrowid}

@app.put("/api/aduu_uyaach/{id}/duusah")
def aduu_uyaach_duusah(id: int):
    conn = get_db()
    from datetime import date
    conn.execute("UPDATE aduu_uyaach SET idevhtei=0, duusah_ognoo=? WHERE id=?",
        (date.today().isoformat(), id))
    conn.commit(); return {"ok": True}

# ── УЯАНЫ ТЭМДЭГЛЭЛ ──
class UyaanTemdeglel(BaseModel):
    aduu_id: int
    uyaach_id: int
    ognoo: str
    turul: str
    zai_km: Optional[float]=None
    hugatsaa_min: Optional[float]=None
    tailbar: Optional[str]=None
    anhliin_tekst: Optional[str]=None

UYAAN_TURUL = ['Морь барих','Гишгүүлэлт','Хөлс','Хангар','Тар',
               'Бага сунгаа','Дунд сунгаа','Их сунгаа','Наадам']

@app.get("/api/uyaan_temdeglel")
def uyaan_temdeglel_list(aduu_id: Optional[int]=None, uyaach_id: Optional[int]=None):
    conn = get_db()
    sql = """SELECT ut.*,a.ner as aduu_ner,u.ner as uyaach_ner
        FROM uyaan_temdeglel ut
        JOIN aduu a ON ut.aduu_id=a.id
        JOIN uyaach u ON ut.uyaach_id=u.id WHERE 1=1"""
    p = []
    if aduu_id: sql += " AND ut.aduu_id=?"; p.append(aduu_id)
    if uyaach_id: sql += " AND ut.uyaach_id=?"; p.append(uyaach_id)
    sql += " ORDER BY ut.ognoo DESC LIMIT 100"
    return [dict(r) for r in conn.execute(sql, p).fetchall()]

@app.post("/api/uyaan_temdeglel")
def uyaan_temdeglel_create(d: UyaanTemdeglel):
    conn = get_db()
    cur = conn.execute(
        "INSERT INTO uyaan_temdeglel (aduu_id,uyaach_id,ognoo,turul,zai_km,hugatsaa_min,tailbar,anhliin_tekst) VALUES (?,?,?,?,?,?,?,?)",
        (d.aduu_id,d.uyaach_id,d.ognoo,d.turul,d.zai_km,d.hugatsaa_min,d.tailbar,d.anhliin_tekst))
    # Notification үүсгэх
    aduu = conn.execute("SELECT ner FROM aduu WHERE id=?", (d.aduu_id,)).fetchone()
    uyaach = conn.execute("SELECT ner FROM uyaach WHERE id=?", (d.uyaach_id,)).fetchone()
    if aduu and uyaach:
        tekst = f"{uyaach['ner']} уяач — {aduu['ner']}: {d.turul}"
        if d.zai_km: tekst += f" {d.zai_km}км"
        if d.hugatsaa_min: tekst += f" {d.hugatsaa_min}мин"
        conn.execute("INSERT INTO notification (uyaach_id,aduu_id,temdeglel_id,tekst) VALUES (?,?,?,?)",
            (d.uyaach_id, d.aduu_id, cur.lastrowid, tekst))
    conn.commit(); return {"id": cur.lastrowid}

@app.delete("/api/uyaan_temdeglel/{id}")
def uyaan_temdeglel_delete(id: int):
    conn = get_db()
    conn.execute("DELETE FROM uyaan_temdeglel WHERE id=?", (id,))
    conn.commit(); return {"ok": True}

# ── NOTIFICATION ──
@app.get("/api/notification")
def notification_list(unshlaa: Optional[int]=None):
    conn = get_db()
    sql = "SELECT n.*,a.ner as aduu_ner,u.ner as uyaach_ner FROM notification n LEFT JOIN aduu a ON n.aduu_id=a.id LEFT JOIN uyaach u ON n.uyaach_id=u.id WHERE 1=1"
    p = []
    if unshlaa is not None: sql += " AND n.unshlaa=?"; p.append(unshlaa)
    sql += " ORDER BY n.ognoo DESC LIMIT 50"
    return [dict(r) for r in conn.execute(sql, p).fetchall()]

@app.put("/api/notification/{id}/unshlaa")
def notification_unshlaa(id: int):
    conn = get_db()
    conn.execute("UPDATE notification SET unshlaa=1 WHERE id=?", (id,))
    conn.commit(); return {"ok": True}

@app.put("/api/notification/bukhniig_unshlaa")
def notification_all_unshlaa():
    conn = get_db()
    conn.execute("UPDATE notification SET unshlaa=1")
    conn.commit(); return {"ok": True}

# ── НААДАМ ──
class NaadamIn(BaseModel):
    ner: str
    turul: str
    dund_turul: Optional[str]=None
    ognoo: Optional[str]=None
    hayg: Optional[str]=None
    tailbar: Optional[str]=None

@app.get("/api/naadam")
def naadam_list():
    conn = get_db()
    return [dict(r) for r in conn.execute(
        "SELECT * FROM naadam ORDER BY ognoo DESC").fetchall()]

@app.post("/api/naadam")
def naadam_create(d: NaadamIn):
    conn = get_db()
    cur = conn.execute(
        "INSERT INTO naadam (ner,turul,dund_turul,ognoo,hayg,tailbar) VALUES (?,?,?,?,?,?)",
        (d.ner,d.turul,d.dund_turul,d.ognoo,d.hayg,d.tailbar))
    conn.commit(); return {"id": cur.lastrowid}

@app.put("/api/naadam/{id}")
def naadam_update(id: int, d: NaadamIn):
    conn = get_db()
    conn.execute("UPDATE naadam SET ner=?,turul=?,dund_turul=?,ognoo=?,hayg=?,tailbar=? WHERE id=?",
        (d.ner,d.turul,d.dund_turul,d.ognoo,d.hayg,d.tailbar,id))
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
class UraldaanIn(BaseModel):
    aduu_id: int
    ognoo: Optional[str]=None
    naadam_ner: Optional[str]=None
    naadam_turul: Optional[str]=None
    bair: Optional[str]=None
    unach: Optional[str]=None
    tailbar: Optional[str]=None
    nas_angilal: Optional[str]=None
    uyaach_id: Optional[int]=None
    gazar: Optional[str]=None
    aimag: Optional[str]=None
    sum: Optional[str]=None
    ezeshigch: Optional[str]=None
    zai_km: Optional[float]=None
    tsag: Optional[str]=None

@app.get("/api/uraldaan")
def uraldaan_list(aduu_id: Optional[int]=None):
    conn = get_db()
    sql = "SELECT * FROM uraldaan WHERE 1=1"
    p = []
    if aduu_id: sql += " AND aduu_id=?"; p.append(aduu_id)
    sql += " ORDER BY ognoo DESC"
    return [dict(r) for r in conn.execute(sql, p).fetchall()]

@app.post("/api/uraldaan")
def uraldaan_create(d: UraldaanIn):
    conn = get_db()
    cur = conn.execute("INSERT INTO uraldaan (aduu_id,ognoo,naadam_ner,bair,unach,tailbar) VALUES (?,?,?,?,?,?)",
        (d.aduu_id,d.ognoo,d.naadam_ner,d.bair,d.unach,d.tailbar))
    conn.commit(); return {"id": cur.lastrowid}

@app.put("/api/uraldaan/{id}")
def uraldaan_update(id: int, d: UraldaanIn):
    conn = get_db()
    conn.execute("""UPDATE uraldaan SET
        aduu_id=?,ognoo=?,naadam_ner=?,naadam_turul=?,bair=?,unach=?,tailbar=?,
        nas_angilal=?,uyaach_id=?,gazar=?,aimag=?,sum=?,ezeshigch=?,zai_km=?,tsag=?
        WHERE id=?""",
        (d.aduu_id,d.ognoo,d.naadam_ner,d.naadam_turul,d.bair,d.unach,d.tailbar,
         d.nas_angilal,d.uyaach_id,d.gazar,d.aimag,d.sum,d.ezeshigch,d.zai_km,d.tsag,id))
    conn.commit()
    return {"ok": True}

@app.delete("/api/uraldaan/{id}")
def uraldaan_delete(id: int):
    conn = get_db()
    conn.execute("DELETE FROM uraldaan WHERE id=?", (id,))
    conn.commit(); return {"ok": True}

# ── ЭРҮҮЛ МЭНД ──
class EruulMendIn(BaseModel):
    aduu_id: int
    ognoo: Optional[str]=None
    turul: Optional[str]=None
    buten: Optional[str]=None
    hemjee: Optional[str]=None
    emch: Optional[str]=None
    tailbar: Optional[str]=None

@app.get("/api/eruul_mend")
def eruul_mend_list(aduu_id: Optional[int]=None):
    conn = get_db()
    sql = "SELECT * FROM eruul_mend WHERE 1=1"
    p = []
    if aduu_id: sql += " AND aduu_id=?"; p.append(aduu_id)
    sql += " ORDER BY ognoo DESC"
    return [dict(r) for r in conn.execute(sql, p).fetchall()]

@app.post("/api/eruul_mend")
def eruul_mend_create(d: EruulMendIn):
    conn = get_db()
    cur = conn.execute("INSERT INTO eruul_mend (aduu_id,ognoo,turul,buten,hemjee,emch,tailbar) VALUES (?,?,?,?,?,?,?)",
        (d.aduu_id,d.ognoo,d.turul,d.buten,d.hemjee,d.emch,d.tailbar))
    conn.commit(); return {"id": cur.lastrowid}

@app.delete("/api/eruul_mend/{id}")
def eruul_mend_delete(id: int):
    conn = get_db()
    conn.execute("DELETE FROM eruul_mend WHERE id=?", (id,))
    conn.commit(); return {"ok": True}

# ── НӨХӨН ҮРЖИХҮЙ ──
class NokhonIn(BaseModel):
    aduu_id: int
    ognoo: Optional[str]=None
    turul: Optional[str]=None
    tailbar: Optional[str]=None
    emch: Optional[str]=None

@app.get("/api/aduu/{aduu_id}/nokhon")
def nokhon_list(aduu_id: int):
    conn = get_db()
    rows = conn.execute("SELECT * FROM nokhon_urjikh WHERE aduu_id=? ORDER BY ognoo DESC", (aduu_id,)).fetchall()
    return [dict(r) for r in rows]

@app.post("/api/nokhon")
def nokhon_create(d: NokhonIn):
    conn = get_db()
    cur = conn.execute("INSERT INTO nokhon_urjikh (aduu_id,ognoo,turul,tailbar,emch) VALUES (?,?,?,?,?)",
        (d.aduu_id, d.ognoo, d.turul, d.tailbar, d.emch))
    conn.commit(); return {"id": cur.lastrowid}

@app.delete("/api/nokhon/{id}")
def nokhon_delete(id: int):
    conn = get_db()
    conn.execute("DELETE FROM nokhon_urjikh WHERE id=?", (id,))
    conn.commit(); return {"ok": True}

# ── ХЭМЖИЛТ ──
class HemjiltIn(BaseModel):
    aduu_id: int
    ognoo: Optional[str]=None
    jin: Optional[float]=None
    undur: Optional[float]=None
    tseezhiin_yas: Optional[float]=None
    urd_hol: Optional[float]=None
    tailbar: Optional[str]=None

@app.get("/api/hemjilt")
def hemjilt_list(aduu_id: Optional[int]=None):
    conn = get_db()
    sql = "SELECT * FROM hemjilt WHERE 1=1"
    p = []
    if aduu_id: sql += " AND aduu_id=?"; p.append(aduu_id)
    sql += " ORDER BY ognoo DESC"
    return [dict(r) for r in conn.execute(sql, p).fetchall()]

@app.post("/api/hemjilt")
def hemjilt_create(d: HemjiltIn):
    conn = get_db()
    cur = conn.execute("INSERT INTO hemjilt (aduu_id,ognoo,jin,undur,tseezhiin_yas,urd_hol,tailbar) VALUES (?,?,?,?,?,?,?)",
        (d.aduu_id,d.ognoo,d.jin,d.undur,d.tseezhiin_yas,d.urd_hol,d.tailbar))
    conn.commit(); return {"id": cur.lastrowid}

@app.delete("/api/hemjilt/{id}")
def hemjilt_delete(id: int):
    conn = get_db()
    conn.execute("DELETE FROM hemjilt WHERE id=?", (id,))
    conn.commit(); return {"ok": True}

# ── ТАХ ──
class TahIn(BaseModel):
    aduu_id: int
    ognoo: Optional[str]=None
    daragiih_ognoo: Optional[str]=None
    turul: Optional[str]=None
    tailbar: Optional[str]=None
    tahchin: Optional[str]=None

@app.get("/api/tah")
def tah_list(aduu_id: Optional[int]=None):
    conn = get_db()
    sql = "SELECT * FROM tah WHERE 1=1"
    p = []
    if aduu_id: sql += " AND aduu_id=?"; p.append(aduu_id)
    sql += " ORDER BY ognoo DESC"
    return [dict(r) for r in conn.execute(sql, p).fetchall()]

@app.post("/api/tah")
def tah_create(d: TahIn):
    conn = get_db()
    cur = conn.execute("INSERT INTO tah (aduu_id,ognoo,daragiih_ognoo,turul,tailbar,tahchin) VALUES (?,?,?,?,?,?)",
        (d.aduu_id,d.ognoo,d.daragiih_ognoo,d.turul,d.tailbar,d.tahchin))
    conn.commit(); return {"id": cur.lastrowid}

@app.delete("/api/tah/{id}")
def tah_delete(id: int):
    conn = get_db()
    conn.execute("DELETE FROM tah WHERE id=?", (id,))
    conn.commit(); return {"ok": True}

# ── ТЭЖЭЭЛ ──
class TejeelIn(BaseModel):
    aduu_id: int
    tejeel_ner: Optional[str]=None
    ehleh_ognoo: Optional[str]=None
    duusah_ognoo: Optional[str]=None
    tailbar: Optional[str]=None

@app.get("/api/tejeel")
def tejeel_list(aduu_id: Optional[int]=None):
    conn = get_db()
    sql = "SELECT * FROM tejeel WHERE 1=1"
    p = []
    if aduu_id: sql += " AND aduu_id=?"; p.append(aduu_id)
    return [dict(r) for r in conn.execute(sql, p).fetchall()]

@app.post("/api/tejeel")
def tejeel_create(d: TejeelIn):
    conn = get_db()
    cur = conn.execute("INSERT INTO tejeel (aduu_id,tejeel_ner,ehleh_ognoo,duusah_ognoo,tailbar) VALUES (?,?,?,?,?)",
        (d.aduu_id,d.tejeel_ner,d.ehleh_ognoo,d.duusah_ognoo,d.tailbar))
    conn.commit(); return {"id": cur.lastrowid}

@app.delete("/api/tejeel/{id}")
def tejeel_delete(id: int):
    conn = get_db()
    conn.execute("DELETE FROM tejeel WHERE id=?", (id,))
    conn.commit(); return {"ok": True}

# ── АИЭ ШИНЖИЛГЭЭ ──
class AieIn(BaseModel):
    aduu_id: int
    ognoo: Optional[str]=None
    ur_dun: Optional[str]='Сөрөг'
    aimag: Optional[str]=None
    laboratort: Optional[str]=None
    hariutsan: Optional[str]=None
    tailbar: Optional[str]=None

@app.get("/api/aie")
def aie_list(aduu_id: Optional[int]=None):
    conn = get_db()
    sql = "SELECT * FROM aie_shinjilgee WHERE 1=1"
    p = []
    if aduu_id: sql += " AND aduu_id=?"; p.append(aduu_id)
    sql += " ORDER BY ognoo DESC"
    return [dict(r) for r in conn.execute(sql, p).fetchall()]

@app.post("/api/aie")
def aie_create(d: AieIn):
    conn = get_db()
    cur = conn.execute("INSERT INTO aie_shinjilgee (aduu_id,ognoo,ur_dun,aimag,laboratort,hariutsan,tailbar) VALUES (?,?,?,?,?,?,?)",
        (d.aduu_id,d.ognoo,d.ur_dun,d.aimag,d.laboratort,d.hariutsan,d.tailbar))
    conn.commit(); return {"id": cur.lastrowid}

@app.delete("/api/aie/{id}")
def aie_delete(id: int):
    conn = get_db()
    conn.execute("DELETE FROM aie_shinjilgee WHERE id=?", (id,))
    conn.commit(); return {"ok": True}

# ── ҮР ТӨЛ ──
@app.get("/api/aduu/{id}/ur_tol")
def ur_tol(id: int):
    conn = get_db()
    rows = conn.execute("""
        SELECT a.id,a.ner,a.huis,a.torson,a.aduu_id,
               tz.ner as zus_ner, m.ner as eh_ner
        FROM aduu a
        LEFT JOIN tohiruulga tz ON a.zus_id=tz.id
        LEFT JOIN aduu m ON a.eh_id=m.id
        WHERE (a.eceg_id=? OR a.eh_id=?)
        ORDER BY a.torson DESC
    """, (id, id)).fetchall()
    return [dict(r) for r in rows]

# ── МОРЬ СОЙХ ──
SOIKH_TURLUUD = ['Амраах','Гэдэс солих','Гишгүүлэх','Хөлс авах','Тар','Хангар','Бага сүнгаа','Дунд сүнгаа','Их сүнгаа']

class MoriSoikhIn(BaseModel):
    aduu_id: int
    uyaach_id: Optional[int]=None
    turul: str
    ognoo: Optional[str]=None
    zai_km: Optional[float]=None
    hugatsaa_min: Optional[float]=None
    tailbar: Optional[str]=None
    anhliin_tekst: Optional[str]=None

@app.get("/api/mori_soikh")
def mori_soikh_list(aduu_id: Optional[int]=None, uyaach_id: Optional[int]=None):
    conn = get_db()
    sql = """SELECT ms.*, a.ner as aduu_ner, u.ner as uyaach_ner
             FROM mori_soikh ms
             JOIN aduu a ON ms.aduu_id=a.id
             LEFT JOIN uyaach u ON ms.uyaach_id=u.id
             WHERE 1=1"""
    p = []
    if aduu_id: sql += " AND ms.aduu_id=?"; p.append(aduu_id)
    if uyaach_id: sql += " AND ms.uyaach_id=?"; p.append(uyaach_id)
    sql += " ORDER BY ms.ognoo DESC, ms.id DESC LIMIT 200"
    return [dict(r) for r in conn.execute(sql, p).fetchall()]

@app.post("/api/mori_soikh")
def mori_soikh_create(d: MoriSoikhIn):
    conn = get_db()
    ognoo = d.ognoo or __import__('datetime').date.today().isoformat()
    cur = conn.execute(
        "INSERT INTO mori_soikh (aduu_id,uyaach_id,turul,ognoo,zai_km,hugatsaa_min,tailbar,anhliin_tekst) VALUES (?,?,?,?,?,?,?,?)",
        (d.aduu_id,d.uyaach_id,d.turul,ognoo,d.zai_km,d.hugatsaa_min,d.tailbar,d.anhliin_tekst))
    conn.commit()
    notif_id = cur.lastrowid
    # Notification үүсгэх — эзэмшигчдэд
    ezeshigchid = conn.execute(
        "SELECT ezeshigch_id FROM aduu_ezeshigch WHERE aduu_id=?", (d.aduu_id,)).fetchall()
    aduu_ner = conn.execute("SELECT ner FROM aduu WHERE id=?", (d.aduu_id,)).fetchone()
    uyaach_ner = conn.execute("SELECT ner FROM uyaach WHERE id=?", (d.uyaach_id,)).fetchone() if d.uyaach_id else None
    tekst = f"🐴 {aduu_ner['ner'] if aduu_ner else ''} — {d.turul}" + (f" · {uyaach_ner['ner']}" if uyaach_ner else "")
    for e in ezeshigchid:
        conn.execute("INSERT INTO notification (aduu_id,tekst,ognoo) VALUES (?,?,?)",
            (d.aduu_id, tekst, ognoo))
    conn.commit()
    return {"id": notif_id}

@app.delete("/api/mori_soikh/{id}")
def mori_soikh_delete(id: int):
    conn = get_db()
    conn.execute("DELETE FROM mori_soikh WHERE id=?", (id,))
    conn.commit(); return {"ok": True}

@app.get("/api/mori_soikh/turluud")
def mori_soikh_turluud():
    conn = get_db()
    rows = conn.execute(
        "SELECT ner FROM tohiruulga WHERE turul='soikh_turul' AND idevhtei=1 ORDER BY id"
    ).fetchall()
    conn.close()
    if rows:
        return [r['ner'] for r in rows]
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
    total = conn.execute("SELECT COUNT(*) FROM aduu WHERE idevhtei=1").fetchone()[0]
    azarga = conn.execute("SELECT COUNT(*) FROM aduu WHERE huis='azarga' AND idevhtei=1").fetchone()[0]
    guu = conn.execute("SELECT COUNT(*) FROM aduu WHERE huis='guu' AND idevhtei=1").fetchone()[0]
    uyaagdaj = conn.execute("SELECT COUNT(DISTINCT aduu_id) FROM aduu_uyaach WHERE idevhtei=1").fetchone()[0]
    surg_too = conn.execute("SELECT COUNT(*) FROM surg WHERE idevhtei=1").fetchone()[0]

    # ── Насны бүлэг — 6 бүлэг ──
    # 1=Унага, 2=Даага, 3=Шүдлэн, 4=Хязаалан, 5=Соёолон, 6+=Морь/Гүү
    nas_groups = [
        ('Унага',1,1),('Даага',2,2),('Шүдлэн',3,3),
        ('Хязаалан',4,4),('Соёолон',5,5),('Морь/Гүү',6,99)
    ]
    nas_data = []
    for lbl,mn,mx in nas_groups:
        for h in ['azarga','guu']:
            n = conn.execute(
                "SELECT COUNT(*) FROM aduu WHERE huis=? AND idevhtei=1 AND torson IS NOT NULL AND (?-CAST(strftime('%Y',torson) AS INT)+1) BETWEEN ? AND ?",
                (h, this_yr, mn, mx)).fetchone()[0]
            nas_data.append({'nas':lbl,'huis':h,'too':n})

    # ── Сүргийн бүрэлдэхүүн ──
    surg_data = [dict(r) for r in conn.execute(
        "SELECT s.id, s.ner, COUNT(a.id) as too FROM surg s LEFT JOIN aduu a ON a.surg_id=s.id AND a.idevhtei=1 GROUP BY s.id ORDER BY too DESC LIMIT 12").fetchall()]
    surg_all = [dict(r) for r in conn.execute(
        "SELECT s.id, s.ner FROM surg s WHERE s.idevhtei=1 ORDER BY s.ner").fetchall()]

    # ── Эзэмшигчийн жагсаалт ──
    ezen_data = [dict(r) for r in conn.execute(
        "SELECT h.id, h.ner, COUNT(DISTINCT ae.aduu_id) as too FROM holboo h JOIN aduu_ezeshigch ae ON h.id=ae.ezeshigch_id JOIN aduu a ON ae.aduu_id=a.id AND a.idevhtei=1 GROUP BY h.id ORDER BY too DESC LIMIT 8").fetchall()]
    ezen_all = [dict(r) for r in conn.execute(
        "SELECT h.id, h.ner FROM holboo h WHERE h.turul='ezeshigch' ORDER BY h.ner").fetchall()]

    # ── Энэ жилийн унагалалт ──
    # 4+ настай гүү л унагална
    guu_4plus = conn.execute(
        "SELECT COUNT(*) FROM aduu WHERE huis='guu' AND idevhtei=1 AND torson IS NOT NULL AND (?-CAST(strftime('%Y',torson) AS INT)+1)>=4",
        (this_yr,)).fetchone()[0]
    unagalsan_guu = conn.execute(
        "SELECT COUNT(*) FROM aduu WHERE huis='guu' AND idevhtei=1 AND torson IS NOT NULL AND strftime('%Y',torson)=?",
        (this_year,)).fetchone()[0]
    # Хээл хаясан гүү (энэ жил)
    heel_hayas = conn.execute(
        "SELECT COUNT(*) FROM nokhon_urjikh WHERE turul='heel_hayas' AND strftime('%Y',ognoo)=?",
        (this_year,)).fetchone()[0]

    # Сувайрсан гүү = 4+ настай гүү - унагалсан - хээл хаясан
    suvairsan_guu = max(0, guu_4plus - unagalsan_guu - heel_hayas)

    # Төл авалтын хувь = унагалсан / (унагалсан + сувайрсан + хээл хаясан) * 100
    tol_avalt_pct = round(unagalsan_guu / guu_4plus * 100) if guu_4plus > 0 else 0

    # Нийт унага (энэ жил төрсөн)
    niit_unaga = conn.execute(
        "SELECT COUNT(*) FROM aduu WHERE idevhtei=1 AND torson IS NOT NULL AND strftime('%Y',torson)=?",
        (this_year,)).fetchone()[0]

    # ── Наадмын амжилт (1-5 байр) ──
    naadam_amjilt = conn.execute(
        "SELECT COUNT(DISTINCT sg.aduu_id) FROM sungaa sg WHERE sg.bair IS NOT NULL AND sg.bair BETWEEN 1 AND 5 AND strftime('%Y',sg.ognoo)=?",
        (this_year,)).fetchone()[0]
    naadam_niit = conn.execute(
        "SELECT COUNT(DISTINCT sg.aduu_id) FROM sungaa sg WHERE strftime('%Y',sg.ognoo)=?",
        (this_year,)).fetchone()[0]

    conn.close()
    return {
        "total":total,"azarga":azarga,"guu":guu,
        "uyaagdaj":uyaagdaj,"surg_too":surg_too,
        "nas_data":nas_data,"surg_data":surg_data,"surg_all":surg_all,"ezen_data":ezen_data,"ezen_all":ezen_all,
        "guu_4plus":guu_4plus,
        "unagalsan_guu":unagalsan_guu,"niit_unaga":niit_unaga,
        "unagalalt_pct":tol_avalt_pct,"heel_hayas":heel_hayas,"suvairsan_guu":suvairsan_guu,
        "naadam_amjilt":naadam_amjilt,"naadam_niit":naadam_niit,
        "this_year":this_year
    }

# ── POLAR HRM ──
from fastapi import UploadFile, File
import json as json_lib

class PolarImportIn(BaseModel):
    aduu_id: int
    uyaach_id: Optional[int] = None
    turul: Optional[str] = None
    polar_json: dict

def calc_sergelt_indeks(zc_2min):
    if not zc_2min: return None
    if zc_2min < 100: return "Маш сайн"
    if zc_2min < 110: return "Сайн"
    if zc_2min < 120: return "Дунд"
    return "Муу"

def calc_zc_bus(zc_series_list):
    if not zc_series_list: return [0,0,0,0,0]
    total = len(zc_series_list)
    if total == 0: return [0,0,0,0,0]
    amar  = sum(1 for z in zc_series_list if z < 100)
    dund  = sum(1 for z in zc_series_list if 100 <= z < 130)
    huch  = sum(1 for z in zc_series_list if 130 <= z < 160)
    ih    = sum(1 for z in zc_series_list if 160 <= z < 180)
    deed  = sum(1 for z in zc_series_list if z >= 180)
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
        ognoo = ex.get('start_time', ex.get('date', ex.get('ognoo','')))[:10] if ex.get('start_time') or ex.get('date') or ex.get('ognoo') else None
        zai_km = ex.get('distance', ex.get('zai_km'))
        if zai_km: zai_km = round(float(zai_km)/1000 if float(zai_km) > 1000 else float(zai_km), 2)
        hugatsaa_sec = ex.get('duration', ex.get('hugatsaa_sec'))
        hugatsaa_min_direct = ex.get('hugatsaa_min')
        if hugatsaa_sec:
            hugatsaa_min = round(float(hugatsaa_sec)/60, 1)
        elif hugatsaa_min_direct:
            hugatsaa_min = float(hugatsaa_min_direct)
        else:
            hugatsaa_min = None
        hurd = round(float(zai_km)/(float(hugatsaa_min)/60), 1) if zai_km and hugatsaa_min else ex.get('hurd_dundaj')

        # ЗЦ
        heart_rate = ex.get('heart_rate', {})
        zc_dundaj = heart_rate.get('average', ex.get('zc_dundaj'))
        zc_max    = heart_rate.get('maximum', ex.get('zc_max'))
        zc_min    = heart_rate.get('minimum', ex.get('zc_min'))
        
        # Сэргэлт
        sergelt_1 = ex.get('recovery', {}).get('heart_rate_1min', ex.get('sergelt_1min'))
        sergelt_2 = ex.get('recovery', {}).get('heart_rate_2min', ex.get('sergelt_2min'))
        sergelt_idx = calc_sergelt_indeks(float(sergelt_2) if sergelt_2 else None)
        
        # HRV
        hrv_raw = ex.get('hrv')
        if isinstance(hrv_raw, dict):
            hrv = hrv_raw.get('rmssd')
        elif isinstance(hrv_raw, (int, float)):
            hrv = float(hrv_raw)
        else:
            hrv = None
        
        # ЗЦ цуврал
        zc_series = ex.get('samples', {}).get('heart_rate', ex.get('zc_series', []))
        if isinstance(zc_series, list) and zc_series:
            zc_vals = [s.get('value', s) if isinstance(s, dict) else s for s in zc_series]
            bus = calc_zc_bus([float(v) for v in zc_vals if v])
        else:
            bus = [0,0,0,0,0]
        
        # Training load
        training_load = ex.get('training_load', {}).get('score', ex.get('training_load'))
        
        # GPS
        gps = ex.get('route', ex.get('gps_series', []))
        
        # mori_soikh дотор ч хадгалах
        ms_cur = conn.execute("""INSERT INTO mori_soikh 
            (aduu_id,uyaach_id,turul,ognoo,zai_km,hugatsaa_min,tailbar)
            VALUES (?,?,?,?,?,?,'Polar HRM')""",
            (d.aduu_id, d.uyaach_id, d.turul or 'Polar', ognoo, zai_km, hugatsaa_min))
        ms_id = ms_cur.lastrowid
        
        # polar_soikh-д дэлгэрэнгүй хадгалах
        cur = conn.execute("""INSERT INTO polar_soikh 
            (mori_soikh_id,aduu_id,uyaach_id,ognoo,turul,
             zai_km,hugatsaa_min,hurd_dundaj,
             zc_dundaj,zc_max,zc_min,
             sergelt_1min,sergelt_2min,sergelt_indeks,hrv,
             zc_bus_amar,zc_bus_dund,zc_bus_huchten,zc_bus_ih_huch,zc_bus_deed,
             training_load,zc_series,gps_series,
             polar_exercise_id)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (ms_id, d.aduu_id, d.uyaach_id, ognoo, d.turul or 'Polar',
             zai_km, hugatsaa_min, hurd,
             zc_dundaj, zc_max, zc_min,
             sergelt_1, sergelt_2, sergelt_idx, hrv,
             bus[0], bus[1], bus[2], bus[3], bus[4],
             training_load,
             json_lib.dumps(zc_series) if zc_series else None,
             json_lib.dumps(gps) if gps else None,
             ex.get('exercise_id', ex.get('id'))))
        imported.append(cur.lastrowid)
    
    # Эзэнд notification
    aduu_ner = conn.execute("SELECT ner FROM aduu WHERE id=?", (d.aduu_id,)).fetchone()
    tekst = f"🐴 {aduu_ner['ner'] if aduu_ner else ''} — Polar HRM өгөгдөл импортлогдлоо"
    for e in conn.execute("SELECT ezeshigch_id FROM aduu_ezeshigch WHERE aduu_id=?", (d.aduu_id,)).fetchall():
        conn.execute("INSERT INTO notification (aduu_id,tekst) VALUES (?,?)", (d.aduu_id, tekst))
    
    conn.commit()
    return {"imported": len(imported), "ids": imported}

@app.get("/api/polar/{aduu_id}")
def polar_list(aduu_id: int):
    conn = get_db()
    rows = conn.execute("""
        SELECT ps.*, u.ner as uyaach_ner
        FROM polar_soikh ps
        LEFT JOIN uyaach u ON ps.uyaach_id=u.id
        WHERE ps.aduu_id=?
        ORDER BY ps.ognoo DESC
    """, (aduu_id,)).fetchall()
    result = []
    for r in rows:
        d = dict(r)
        # JSON цуврал задлах
        if d.get('zc_series'): 
            try: d['zc_series'] = json_lib.loads(d['zc_series'])
            except: d['zc_series'] = []
        result.append(d)
    return result

@app.get("/api/polar/{aduu_id}/trend")
def polar_trend(aduu_id: int, limit: int=30):
    conn = get_db()
    rows = conn.execute("""
        SELECT ognoo, hurd_dundaj, zc_dundaj, sergelt_2min, hrv, training_load, turul
        FROM polar_soikh
        WHERE aduu_id=?
        ORDER BY ognoo DESC LIMIT ?
    """, (aduu_id, limit)).fetchall()
    return [dict(r) for r in rows]

# ── ТАЙЛАН ──
@app.get("/api/dashboard/unagalalt")
def dashboard_unagalalt(on: Optional[int]=None):
    import datetime
    conn = get_db()
    this_yr = on or datetime.date.today().year
    this_year = str(this_yr)
    guu_4plus = conn.execute(
        "SELECT COUNT(*) FROM aduu WHERE huis='guu' AND idevhtei=1 AND torson IS NOT NULL AND (?-CAST(strftime('%Y',torson) AS INT)+1)>=4",
        (this_yr,)).fetchone()[0]
    unagalsan_guu = conn.execute(
        "SELECT COUNT(*) FROM aduu WHERE huis='guu' AND idevhtei=1 AND torson IS NOT NULL AND strftime('%Y',torson)=?",
        (this_year,)).fetchone()[0]
    niit_unaga = conn.execute(
        "SELECT COUNT(*) FROM aduu WHERE idevhtei=1 AND torson IS NOT NULL AND strftime('%Y',torson)=?",
        (this_year,)).fetchone()[0]
    heel_hayas = conn.execute(
        "SELECT COUNT(*) FROM nokhon_urjikh WHERE turul='heel_hayas' AND strftime('%Y',ognoo)=?",
        (this_year,)).fetchone()[0]
    suvairsan_guu = max(0, guu_4plus - unagalsan_guu - heel_hayas)
    tol_avalt_pct = round(unagalsan_guu / guu_4plus * 100) if guu_4plus > 0 else 0
    conn.close()
    return {"on":this_year,"guu_4plus":guu_4plus,"unagalsan_guu":unagalsan_guu,
            "niit_unaga":niit_unaga,"heel_hayas":heel_hayas,"suvairsan_guu":suvairsan_guu,
            "unagalalt_pct":tol_avalt_pct}

@app.get("/api/dashboard/naadam")
def dashboard_naadam(on: Optional[int]=None, aduu_id: Optional[int]=None, ez: Optional[str]=None):
    conn = get_db()
    bair_lbls = ['Түрүү','Аман хүзүү','Айргийн-3','Айргийн-4','Айргийн-5']
    turluud = [
        {'key':'Улс',   'filter': "sg.naadam_turul='Улсын'"},
        {'key':'Аймаг', 'filter': "sg.naadam_turul='Аймгийн'"},
        {'key':'Сум',   'filter': "sg.naadam_turul='Сумын'"},
        {'key':'Бусад', 'filter': "sg.naadam_turul='Бусад' OR sg.naadam_turul IS NULL"},
    ]
    extra = ""
    extra_params = []
    if aduu_id:
        extra += " AND sg.aduu_id=?"
        extra_params.append(aduu_id)
    if ez:
        extra += " AND EXISTS(SELECT 1 FROM aduu_ezeshigch ae JOIN holboo h ON ae.ezeshigch_id=h.id WHERE ae.aduu_id=sg.aduu_id AND h.ner LIKE ?)"
        extra_params.append(f"%{ez}%")
    on_filter = "strftime('%Y',sg.ognoo)=?" if on else "1=1"
    on_param = [str(on)] if on else []
    # Адуу болон эзэмшигчийн жагсаалт (dropdown-д)
    aduu_list = conn.execute("SELECT DISTINCT a.id, a.ner FROM sungaa sg JOIN aduu a ON sg.aduu_id=a.id ORDER BY a.ner").fetchall()
    ez_list = conn.execute("SELECT DISTINCT h.ner FROM sungaa sg JOIN aduu_ezeshigch ae ON ae.aduu_id=sg.aduu_id JOIN holboo h ON ae.ezeshigch_id=h.id ORDER BY h.ner").fetchall()
    result = {}
    for t in turluud:
        niit = conn.execute(
            f"SELECT COUNT(*) FROM sungaa sg WHERE {on_filter} AND ({t['filter']}){extra}",
            on_param+extra_params).fetchone()[0]
        bair_too = {}
        for i,lbl in enumerate(bair_lbls, 1):
            n = conn.execute(
                f"SELECT COUNT(*) FROM sungaa sg WHERE {on_filter} AND sg.bair=? AND ({t['filter']}){extra}",
                on_param+[i]+extra_params).fetchone()[0]
            bair_too[lbl] = n
        result[t['key']] = {"niit":niit, "bair":bair_too}
    conn.close()
    return {"on": str(on) if on else "Бүх он", "data": result,
            "aduu_list": [{"id":r[0],"ner":r[1]} for r in aduu_list],
            "ez_list": [r[0] for r in ez_list]}

@app.get("/api/dashboard/butets")
def dashboard_butets(surg_id: Optional[int]=None, ezen_id: Optional[int]=None):
    conn = get_db()
    sf = (f" AND a.surg_id={surg_id}" if surg_id else "")
    ef = (f" AND EXISTS(SELECT 1 FROM aduu_ezeshigch ae WHERE ae.aduu_id=a.id AND ae.ezeshigch_id={ezen_id})" if ezen_id else "")
    base = f"WHERE a.idevhtei=1{sf}{ef}"

    zus_rows = conn.execute(f"SELECT t.ner, COUNT(a.id) as too FROM aduu a LEFT JOIN tohiruulga t ON a.zus_id=t.id {base} GROUP BY a.zus_id ORDER BY too DESC LIMIT 8").fetchall()
    ugshil_rows = conn.execute(f"SELECT t.ner, COUNT(a.id) as too FROM aduu a LEFT JOIN tohiruulga t ON a.ugshil_id=t.id {base} GROUP BY a.ugshil_id ORDER BY too DESC").fetchall()
    az_rows = conn.execute(f"SELECT e.ner as ner, COUNT(a.id) as too FROM aduu a JOIN aduu e ON a.eceg_id=e.id {base} AND e.huis IN ('azarga','er') GROUP BY a.eceg_id ORDER BY too DESC LIMIT 6").fetchall()
    guu_rows = conn.execute(f"SELECT e.ner as ner, COUNT(a.id) as too FROM aduu a JOIN aduu e ON a.eh_id=e.id {base} AND e.huis IN ('guu','ohin') GROUP BY a.eh_id ORDER BY too DESC LIMIT 6").fetchall()
    conn.close()
    return {
        "zus": [{"ner": r["ner"] or "Тодорхойгүй", "too": r["too"]} for r in zus_rows],
        "ugshil": [{"ner": r["ner"] or "Тодорхойгүй", "too": r["too"]} for r in ugshil_rows],
        "azarga_urtol": [{"ner": r["ner"], "too": r["too"]} for r in az_rows],
        "guu_urtol": [{"ner": r["ner"], "too": r["too"]} for r in guu_rows]
    }

@app.get("/api/dashboard/osolt")
def dashboard_osolt(surg_id: Optional[int]=None, ezen_id: Optional[int]=None):
    import datetime
    conn = get_db()
    this_yr = datetime.date.today().year
    sf = (f" AND a.surg_id={surg_id}" if surg_id else "")
    ef = (f" AND EXISTS(SELECT 1 FROM aduu_ezeshigch ae WHERE ae.aduu_id=a.id AND ae.ezeshigch_id={ezen_id})" if ezen_id else "")
    result = []
    for yr in range(this_yr-9, this_yr+1):
        base = f"SELECT COUNT(*) FROM aduu a WHERE a.idevhtei=1 AND (a.torson IS NULL OR CAST(strftime('%Y',a.torson) AS INT)<={yr}){sf}{ef}"
        niit = conn.execute(base).fetchone()[0]
        er   = conn.execute(base + " AND a.huis IN ('azarga','er')").fetchone()[0]
        ohin = conn.execute(base + " AND a.huis IN ('guu','ohin')").fetchone()[0]
        result.append({"on": yr, "niit": niit, "er": er, "ohin": ohin})
    conn.close()
    return result

@app.get("/api/dashboard/nas")
def dashboard_nas(surg_id: Optional[int]=None, ezen_id: Optional[int]=None, on: Optional[int]=None):
    import datetime
    conn = get_db()
    this_yr = on or datetime.date.today().year
    nas_groups = [
        ('Унага',1,1),('Даага',2,2),('Шүдлэн',3,3),
        ('Хязаалан',4,4),('Соёолон',5,5),('Морь/Гүү',6,99)
    ]
    nas_data = []
    for lbl,mn,mx in nas_groups:
        for h in ['azarga','guu']:
            sql = """SELECT COUNT(*) FROM aduu a WHERE a.huis=? AND a.idevhtei=1
                     AND a.torson IS NOT NULL
                     AND (?-CAST(strftime('%Y',a.torson) AS INT)+1) BETWEEN ? AND ?"""
            params = [h, this_yr, mn, mx]
            if surg_id:
                sql += " AND a.surg_id=?"
                params.append(surg_id)
            if ezen_id:
                sql += " AND EXISTS(SELECT 1 FROM aduu_ezeshigch ae WHERE ae.aduu_id=a.id AND ae.ezeshigch_id=?)"
                params.append(ezen_id)
            n = conn.execute(sql, params).fetchone()[0]
            nas_data.append({'nas':lbl,'huis':h,'too':n})
    conn.close()
    return nas_data

@app.get("/api/dashboard/naadam_stat")
def dashboard_naadam_stat():
    """Наадмын амжилт — жилээр, насны ангиллаар (сүүлийн 5 жил)"""
    import datetime
    conn = get_db()
    this_yr = datetime.date.today().year
    nas_angilal = ['Унага','Даага','Шүдлэн','Хязаалан','Соёолон','Морь']
    result = []
    for yr in range(this_yr - 4, this_yr + 1):
        y = str(yr)
        row = {"on": yr}
        # Нийт оролцсон
        row["niit"] = conn.execute(
            "SELECT COUNT(DISTINCT aduu_id) FROM sungaa WHERE strftime('%Y',ognoo)=?", (y,)).fetchone()[0]
        # 1-3 байр авсан
        row["medalist"] = conn.execute(
            "SELECT COUNT(DISTINCT aduu_id) FROM sungaa WHERE strftime('%Y',ognoo)=? AND bair BETWEEN 1 AND 3", (y,)).fetchone()[0]
        # 1-р байр (Түрүү)
        row["turuulsen"] = conn.execute(
            "SELECT COUNT(DISTINCT aduu_id) FROM sungaa WHERE strftime('%Y',ognoo)=? AND bair=1", (y,)).fetchone()[0]
        # Насны ангиллаар: sungaa.nas_angilal талбараас
        for na in nas_angilal:
            row[na] = conn.execute(
                "SELECT COUNT(DISTINCT aduu_id) FROM sungaa WHERE strftime('%Y',ognoo)=? AND nas_angilal LIKE ?",
                (y, f"%{na}%")).fetchone()[0]
        result.append(row)
    conn.close()
    return result

@app.get("/api/dashboard/urjil_trend")
def dashboard_urjil_trend():
    """Хээл хаясан vs Унагалсан — сүүлийн 5 жил"""
    import datetime
    conn = get_db()
    this_yr = datetime.date.today().year
    result = []
    for yr in range(this_yr - 4, this_yr + 1):
        y = str(yr)
        guu_4plus = conn.execute(
            "SELECT COUNT(*) FROM aduu WHERE huis='guu' AND idevhtei=1 AND torson IS NOT NULL AND (?-CAST(strftime('%Y',torson) AS INT)+1)>=4",
            (yr,)).fetchone()[0]
        unagalsan = conn.execute(
            "SELECT COUNT(*) FROM aduu WHERE huis='guu' AND idevhtei=1 AND torson IS NOT NULL AND strftime('%Y',torson)=?",
            (y,)).fetchone()[0]
        heel_hayas = conn.execute(
            "SELECT COUNT(*) FROM nokhon_urjikh WHERE turul='heel_hayas' AND strftime('%Y',ognoo)=?",
            (y,)).fetchone()[0]
        suvairsan = max(0, guu_4plus - unagalsan - heel_hayas)
        pct = round(unagalsan / guu_4plus * 100) if guu_4plus > 0 else 0
        result.append({"on": yr, "unagalsan": unagalsan, "heel_hayas": heel_hayas,
                       "suvairsan": suvairsan, "guu_4plus": guu_4plus, "pct": pct})
    conn.close()
    return result

@app.get("/api/taillan/guitsetgel")
def taillan_guitsetgel(
    uyaach_id: Optional[int]=None,
    aduu_id: Optional[int]=None,
    aduu_code: Optional[str]=None,
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
        SELECT p.aduu_id, p.status, COUNT(*) as too, a.ner as aduu_ner, a.aduu_id as aduu_code
        FROM mori_soikh_plan p
        JOIN aduu a ON p.aduu_id=a.id
        WHERE p.ognoo BETWEEN ? AND ?
    """
    params_plan = [ehleh, duusah]
    if uyaach_id: sql_plan += " AND p.uyaach_id=?"; params_plan.append(uyaach_id)
    if aduu_id: sql_plan += " AND p.aduu_id=?"; params_plan.append(aduu_id)
    if aduu_code: sql_plan += " AND a.aduu_id LIKE ?"; params_plan.append(aduu_code+'%')
    sql_plan += " GROUP BY p.aduu_id, p.status ORDER BY a.ner"
    plan_rows = conn.execute(sql_plan, params_plan).fetchall()

    # mori_soikh (хийгдсэн)
    sql_soikh = """
        SELECT ms.aduu_id, COUNT(*) as too, a.ner as aduu_ner, a.aduu_id as aduu_code
        FROM mori_soikh ms
        JOIN aduu a ON ms.aduu_id=a.id
        WHERE ms.ognoo BETWEEN ? AND ?
    """
    params_soikh = [ehleh, duusah]
    if uyaach_id: sql_soikh += " AND ms.uyaach_id=?"; params_soikh.append(uyaach_id)
    if aduu_id: sql_soikh += " AND ms.aduu_id=?"; params_soikh.append(aduu_id)
    if aduu_code: sql_soikh += " AND a.aduu_id LIKE ?"; params_soikh.append(aduu_code+'%')
    sql_soikh += " GROUP BY ms.aduu_id ORDER BY a.ner"
    soikh_rows = conn.execute(sql_soikh, params_soikh).fetchall()

    # Нэгтгэх
    aduu_map = {}
    for r in plan_rows:
        aid = r['aduu_id']
        if aid not in aduu_map:
            aduu_map[aid] = {'aduu_id':aid,'aduu_ner':r['aduu_ner'],'aduu_code':r['aduu_code'],'tolvlosen':0,'hiisgdsn':0,'soikh_too':0}
        if r['status']=='done': aduu_map[aid]['hiisgdsn'] += r['too']
        else: aduu_map[aid]['tolvlosen'] += r['too']
    for r in soikh_rows:
        aid = r['aduu_id']
        if aid not in aduu_map:
            aduu_map[aid] = {'aduu_id':aid,'aduu_ner':r['aduu_ner'],'aduu_code':r['aduu_code'],'tolvlosen':0,'hiisgdsn':0,'soikh_too':0}
        aduu_map[aid]['soikh_too'] = r['too']

    result = []
    for d in aduu_map.values():
        niit = d['tolvlosen'] + d['hiisgdsn']
        hiigdsen = d['hiisgdsn'] + d['soikh_too']
        d['niit'] = niit + d['soikh_too']
        d['hiigdsen'] = hiigdsen
        d['hiigdgui'] = max(0, niit - d['hiisgdsn'])
        d['pct'] = round(hiigdsen / d['niit'] * 100) if d['niit'] else 0
        result.append(d)
    conn.close()
    return sorted(result, key=lambda x: x['aduu_ner'])

@app.get("/api/taillan/ajliin_turul")
def taillan_ajliin_turul(
    uyaach_id: Optional[int]=None,
    aduu_id: Optional[int]=None,
    aduu_code: Optional[str]=None,
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
    sql = "SELECT p.turul, COUNT(*) as too FROM mori_soikh_plan p JOIN aduu a ON p.aduu_id=a.id WHERE p.ognoo BETWEEN ? AND ?"
    params = [ehleh, duusah]
    if uyaach_id: sql += " AND p.uyaach_id=?"; params.append(uyaach_id)
    if aduu_id: sql += " AND p.aduu_id=?"; params.append(aduu_id)
    if aduu_code: sql += " AND a.aduu_id LIKE ?"; params.append(aduu_code+'%')
    sql += " GROUP BY p.turul ORDER BY too DESC"
    for r in conn.execute(sql, params).fetchall():
        result[r['turul']] = result.get(r['turul'],0) + r['too']
    # mori_soikh-аас
    sql2 = "SELECT ms.turul, COUNT(*) as too FROM mori_soikh ms JOIN aduu a ON ms.aduu_id=a.id WHERE ms.ognoo BETWEEN ? AND ?"
    params2 = [ehleh, duusah]
    if uyaach_id: sql2 += " AND ms.uyaach_id=?"; params2.append(uyaach_id)
    if aduu_id: sql2 += " AND ms.aduu_id=?"; params2.append(aduu_id)
    if aduu_code: sql2 += " AND a.aduu_id LIKE ?"; params2.append(aduu_code+'%')
    sql2 += " GROUP BY ms.turul ORDER BY too DESC"
    for r in conn.execute(sql2, params2).fetchall():
        result[r['turul']] = result.get(r['turul'],0) + r['too']
    conn.close()
    return sorted([{'turul':k,'too':v} for k,v in result.items()], key=lambda x:-x['too'])

@app.get("/api/taillan/odrii_huvaari")
def taillan_odrii_huvaari(
    uyaach_id: Optional[int]=None,
    aduu_id: Optional[int]=None,
    aduu_code: Optional[str]=None,
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
    sql = """SELECT p.ognoo, a.ner as aduu_ner, a.aduu_id as aduu_code, p.turul, p.status, 'plan' as src
             FROM mori_soikh_plan p JOIN aduu a ON p.aduu_id=a.id
             WHERE p.ognoo BETWEEN ? AND ?"""
    params = [ehleh, duusah]
    if uyaach_id: sql += " AND p.uyaach_id=?"; params.append(uyaach_id)
    if aduu_id: sql += " AND p.aduu_id=?"; params.append(aduu_id)
    if aduu_code: sql += " AND a.aduu_id LIKE ?"; params.append(aduu_code+'%')
    rows += [dict(r) for r in conn.execute(sql+" ORDER BY p.ognoo DESC", params).fetchall()]
    # mori_soikh
    sql2 = """SELECT ms.ognoo, a.ner as aduu_ner, a.aduu_id as aduu_code, ms.turul, 'done' as status, 'soikh' as src
              FROM mori_soikh ms JOIN aduu a ON ms.aduu_id=a.id
              WHERE ms.ognoo BETWEEN ? AND ?"""
    params2 = [ehleh, duusah]
    if uyaach_id: sql2 += " AND ms.uyaach_id=?"; params2.append(uyaach_id)
    if aduu_id: sql2 += " AND ms.aduu_id=?"; params2.append(aduu_id)
    if aduu_code: sql2 += " AND a.aduu_id LIKE ?"; params2.append(aduu_code+'%')
    rows += [dict(r) for r in conn.execute(sql2+" ORDER BY ms.ognoo DESC", params2).fetchall()]
    conn.close()
    return sorted(rows, key=lambda x: x['ognoo'], reverse=True)
