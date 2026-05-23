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
    if c.execute("SELECT COUNT(*) FROM aduu").fetchone()[0] > 0:
        print("⚠️ Өгөгдөл байна. horse.db устгаад дахин ажиллуул."); conn.close(); return

    # Сүрэг
    surg_map = {}
    for r in read_csv("Potreros.csv"):
        cur = c.execute("INSERT INTO surg (ner,us_zereg,sergel_zereg,belcheer_zereg,talabai,gazrin_baidal,busad_mal,tailbar,belcheer) VALUES (?,?,?,?,?,?,?,?,?)",
            (clean(r.get('Nombre')) or 'Нэргүй', clean(r.get('GradoAgua')), clean(r.get('GradoSombra')), clean(r.get('GradoPasto')),
             r.get('Superficie') or None, clean(r.get('Topografia')), clean(r.get('OtrosAnimales')), clean(r.get('Observaciones')), clean(r.get('Pastura'))))
        surg_map[str(r.get('idPotrero',''))] = cur.lastrowid
    print(f"✅ Сүрэг: {len(surg_map)}")

    # Эзэмшигч
    holboo_map = {}
    for r in read_csv("Criadores.csv"):
        ner = clean(r.get('Nombre')) or clean(r.get('RazonSocial'))
        if not ner: continue
        cur = c.execute("INSERT INTO holboo (ner,hayag,utas,email,hot,uls) VALUES (?,?,?,?,?,?)",
            (ner, clean(r.get('Direccion')), clean(r.get('Telefono')), clean(r.get('Email')), clean(r.get('Ciudad')), clean(r.get('Pais'))))
        holboo_map[str(r.get('idCriador',''))] = cur.lastrowid
    print(f"✅ Эзэмшигч: {len(holboo_map)}")

    # Адуу
    def get_cfg(turul, ner):
        if not ner: return None
        r = c.execute("SELECT id FROM tohiruulga WHERE turul=? AND ner=?",(turul,ner)).fetchone()
        if r: return r[0]
        return c.execute("INSERT INTO tohiruulga (turul,ner) VALUES (?,?)",(turul,ner)).lastrowid

    huis_map = {'Macho':'azarga','Hembra':'guu','Macho Castrado':'morini','Potro':'unaga_er','Potra':'unaga_em'}
    caballos = read_csv("Caballos.csv")
    aduu_map = {}
    for r in caballos:
        cur = c.execute("INSERT INTO aduu (ner,huis,zus_id,ugshil_id,torson,surg_id,malchin_id,tailbar,senas_tolgoi,senas_bie,orig_id,orig_eceg_id,orig_eh_id) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (clean(r.get('Nombre')) or 'Нэргүй', huis_map.get(clean(r.get('Macho')),'guu'),
             get_cfg('zus', clean(r.get('Color'))), get_cfg('ugshil', clean(r.get('Raza'))),
             clean_date(r.get('FechaNac')), surg_map.get(str(r.get('idPotrero','')).split('.')[0]),
             holboo_map.get(str(r.get('idCriador','')).split('.')[0]),
             clean(r.get('Observaciones')), clean(r.get('ReseñaSVG') or r.get('ResenaSVG')),
             clean(r.get('SeniasParticulares')), r.get('idCaballo'), r.get('idPadre'), r.get('idMadre')))
        aduu_map[str(r.get('idCaballo',''))] = cur.lastrowid

    for r in caballos:
        aid = aduu_map.get(str(r.get('idCaballo','')))
        if not aid: continue
        eid = aduu_map.get(str(r.get('idPadre','')).split('.')[0])
        mid = aduu_map.get(str(r.get('idMadre','')).split('.')[0])
        if eid or mid: c.execute("UPDATE aduu SET eceg_id=?,eh_id=? WHERE id=?",(eid,mid,aid))
    print(f"✅ Адуу: {len(caballos)}")

    # Уралдаан
    cnt = 0
    for r in read_csv("Competencias.csv"):
        aid = aduu_map.get(str(r.get('idCaballo','')).split('.')[0])
        if aid:
            c.execute("INSERT INTO sungaa (aduu_id,ognoo,turul,tailbar,dur) VALUES (?,?,?,?,?)",
                (aid, clean_date(r.get('Fecha')), clean(r.get('Tipo') or r.get('TipoCarrera')), clean(r.get('Observaciones')), clean(r.get('Distancia'))))
            cnt += 1
    print(f"✅ Уралдаан: {cnt}")

    # Вакцин
    cnt = 0
    for r in read_csv("Vacunas.csv"):
        aid = aduu_map.get(str(r.get('idCaballo','')).split('.')[0])
        if aid:
            c.execute("INSERT INTO vacsin (aduu_id,ognoo,turul) VALUES (?,?,?)",
                (aid, clean_date(r.get('Fecha')), clean(r.get('Vacuna') or r.get('Tipo'))))
            cnt += 1
    print(f"✅ Вакцин: {cnt}")

    conn.commit(); conn.close()
    print(f"\n🎉 Импорт дууслаа! {len(caballos)} адуу, {len(surg_map)} сүрэг")

if __name__ == "__main__":
    import_all()
