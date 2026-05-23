import csv, os, sys
sys.path.insert(0, os.path.dirname(__file__))
from database import get_db, init_db

CSV_DIR = os.path.expanduser("~/Downloads/noots_data")

def read_csv(f):
    p = os.path.join(CSV_DIR, f)
    if not os.path.exists(p):
        print(f"⚠️ {f} олдсонгүй"); return []
    with open(p, encoding="utf-8", errors="replace") as fp:
        return list(csv.DictReader(fp))

def clean(v):
    if not v: return None
    v = str(v).strip(); return v if v else None

def clean_date(v):
    if not v: return None
    v = str(v).strip()[:10]
    return None if '0001' in v or '0000' in v else v

def import_all():
    init_db()
    conn = get_db()
    c = conn.cursor()
    if c.execute("SELECT COUNT(*) FROM horse").fetchone()[0] > 0:
        print("⚠️ Өгөгдөл байна. horse.db устгаад дахин ажиллуул."); conn.close(); return

    # Сүрэг
    herd_map = {}
    for r in read_csv("Potreros.csv"):
        cur = c.execute("INSERT INTO herd (name,us_zereg,sergel_zereg,belcheer_zereg,talabai,gazrin_baidal,busad_mal,notes,belcheer) VALUES (?,?,?,?,?,?,?,?,?)",
            (clean(r.get('Nombre')) or 'Нэргүй', clean(r.get('GradoAgua')), clean(r.get('GradoSombra')), clean(r.get('GradoPasto')),
             r.get('Superficie') or None, clean(r.get('Topografia')), clean(r.get('OtrosAnimales')), clean(r.get('Observaciones')), clean(r.get('Pastura'))))
        herd_map[str(r.get('idPotrero',''))] = cur.lastrowid
    print(f"✅ Сүрэг: {len(herd_map)}")

    # Эзэмшигч
    contact_map = {}
    for r in read_csv("Criadores.csv"):
        name = clean(r.get('Nombre')) or clean(r.get('RazonSocial'))
        if not name: continue
        cur = c.execute("INSERT INTO contact (name,address,phone,email,city,uls) VALUES (?,?,?,?,?,?)",
            (name, clean(r.get('Direccion')), clean(r.get('Telefono')), clean(r.get('Email')), clean(r.get('Ciudad')), clean(r.get('Pais'))))
        contact_map[str(r.get('idCriador',''))] = cur.lastrowid
    print(f"✅ Эзэмшигч: {len(contact_map)}")

    # Адуу
    def get_cfg(type, name):
        if not name: return None
        r = c.execute("SELECT id FROM option WHERE type=? AND name=?",(type,name)).fetchone()
        if r: return r[0]
        return c.execute("INSERT INTO option (type,name) VALUES (?,?)",(type,name)).lastrowid

    sex_map = {'Macho':'stallion','Hembra':'mare','Macho Castrado':'gelding','Potro':'colt','Potra':'filly'}
    caballos = read_csv("Caballos.csv")
    horse_map = {}
    for r in caballos:
        cur = c.execute("INSERT INTO horse (name,sex,color_id,breed_id,birth_date,herd_id,herder_id,notes,head_marking,body_marking,legacy_id,legacy_sire_id,legacy_dam_id) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (clean(r.get('Nombre')) or 'Нэргүй', sex_map.get(clean(r.get('Macho')),'mare'),
             get_cfg('color', clean(r.get('Color'))), get_cfg('breed_text', clean(r.get('Raza'))),
             clean_date(r.get('FechaNac')), herd_map.get(str(r.get('idPotrero','')).split('.')[0]),
             contact_map.get(str(r.get('idCriador','')).split('.')[0]),
             clean(r.get('Observaciones')), clean(r.get('ReseñaSVG') or r.get('ResenaSVG')),
             clean(r.get('SeniasParticulares')), r.get('idCaballo'), r.get('idPadre'), r.get('idMadre')))
        horse_map[str(r.get('idCaballo',''))] = cur.lastrowid

    for r in caballos:
        aid = horse_map.get(str(r.get('idCaballo','')))
        if not aid: continue
        eid = horse_map.get(str(r.get('idPadre','')).split('.')[0])
        mid = horse_map.get(str(r.get('idMadre','')).split('.')[0])
        if eid or mid: c.execute("UPDATE horse SET sire_id=?,dam_id=? WHERE id=?",(eid,mid,aid))
    print(f"✅ Адуу: {len(caballos)}")

    # Уралдаан
    cnt = 0
    for r in read_csv("Competencias.csv"):
        aid = horse_map.get(str(r.get('idCaballo','')).split('.')[0])
        if aid:
            c.execute("INSERT INTO practice_race (horse_id,date,type,notes,distance_text) VALUES (?,?,?,?,?)",
                (aid, clean_date(r.get('Fecha')), clean(r.get('Tipo') or r.get('TipoCarrera')), clean(r.get('Observaciones')), clean(r.get('Distancia'))))
            cnt += 1
    print(f"✅ Уралдаан: {cnt}")

    # Вакцин
    cnt = 0
    for r in read_csv("Vacunas.csv"):
        aid = horse_map.get(str(r.get('idCaballo','')).split('.')[0])
        if aid:
            c.execute("INSERT INTO vacsin (horse_id,date,type) VALUES (?,?,?)",
                (aid, clean_date(r.get('Fecha')), clean(r.get('Vacuna') or r.get('Tipo'))))
            cnt += 1
    print(f"✅ Вакцин: {cnt}")

    conn.commit(); conn.close()
    print(f"\n🎉 Импорт дууслаа! {len(caballos)} адуу, {len(herd_map)} сүрэг")

if __name__ == "__main__":
    import_all()
