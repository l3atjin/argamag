"""
Canonical Mongolian → English rename map for the Argamag schema and codebase.

Drives two artifacts:
  1. backend/migrate_to_english.py — SQL-level renames on the live DB
  2. The text substitutions applied across main.py and frontend/index.html

Substitutions are applied with word boundaries, longest-key-first, so that
compound names (e.g. aduu_ezeshigch) are renamed before their components
(aduu, ezeshigch).
"""

# Tables: live DB schema name -> new name.
# `naadam` and `notification` keep their names intentionally.
TABLES = {
    "aduu_ezeshigch": "horse_owner",
    "aduu_uyaach": "horse_trainer",
    "aie_shinjilgee": "eia_test",
    "ajil": "task",
    "eruul_mend": "health_record",
    "havsral": "attachment",
    "hemjilt": "measurement",
    "holboo": "contact",
    "hongol": "gelding_event",
    "mori_soikh_plan": "training_plan",
    "mori_soikh": "training_session",
    "nokhon_urjikh": "breeding_event",
    "polar_soikh": "polar_session",
    "sankhuu": "finance_record",
    "sungaa": "practice_race",
    "surg": "herd",
    "tah": "hoof_care",
    "tejeel": "feeding",
    "tohiruulga": "option",
    "uraldaan": "race",
    "uyaach": "trainer",
    "uyaan_temdeglel": "training_note",
    "zuchee": "stable",
    "zurag": "photo",
    "aduu": "horse",
}

# Per-table column renames. Each key is the *original* table name (pre-rename).
# Common columns (ner/ognoo/tailbar/idevhtei/turul) live in COMMON_COLUMNS
# and are applied to every table that has them.
COMMON_COLUMNS = {
    "ner": "name",
    "ognoo": "date",
    "tailbar": "notes",
    "idevhtei": "active",
    "turul": "type",
    "orig_id": "legacy_id",
    "aduu_id": "horse_id",  # FK on every non-aduu table
}

# Columns that need a table-specific name (and don't follow the common map).
COLUMNS = {
    "surg": {
        "azarga_id": "stallion_id",
    },
    "holboo": {
        "hayag": "address",
        "utas": "phone",
        "hot": "city",
    },
    "zuchee": {
        "bayrshal": "location",
        "mur_too": "row_count",
        "haircag_too": "column_count",
    },
    "uyaach": {
        "utas": "phone",
        "hayg": "address",  # typo in original schema (should have been hayag)
        "tsol": "title",
    },
    "naadam": {
        "dund_turul": "subtype",
        "hayg": "location",
    },
    "aduu": {
        "aduu_id": "registration_code",  # the official external horse ID (string)
        "dugaar": "number",
        "huis": "sex",
        "ugshil_id": "breed_id",
        "garal_id": "origin_id",
        "surg_id": "herd_id",
        "zus_id": "color_id",
        "torson": "birth_date",
        "ognoo_gui": "birth_date_unknown",
        "pasport": "passport",
        "dnh": "dna",
        "registerlesen": "registered",
        "id_gui": "no_id",
        "tsusni_huvi": "blood_percentage",
        "senas_tolgoi": "head_marking",
        "senas_bie": "body_marking",
        "senas_hel": "leg_marking",
        "tamga": "brand",
        "zuchee_id": "stable_id",
        "bayrshal": "location",
        "malchin_id": "herder_id",
        "huviin_temdeglel": "personal_note",
        "hongoloson": "gelded",
        "eceg_id": "sire_id",
        "eh_id": "dam_id",
        "orig_eceg_id": "legacy_sire_id",
        "orig_eh_id": "legacy_dam_id",
        "chuhal": "important",
    },
    "aduu_ezeshigch": {
        "ezeshigch_id": "owner_id",
        "huvi": "share_percent",
    },
    "aduu_uyaach": {
        "uyaach_id": "trainer_id",
        "ehleh_ognoo": "start_date",
        "duusah_ognoo": "end_date",
    },
    "sungaa": {
        "dur": "distance_text",
        "naadam_id": "naadam_id",  # no change (naadam table keeps name)
        "uyaach_id": "trainer_id",
        "unach": "jockey",
        "nas_angilal": "age_category",
        "bair": "rank",
        "naadam_turul": "naadam_type",
        "naadam_ner": "naadam_name",
        "aimag": "province",
        # NOTE: `sum` column not renamed — conflicts with Python builtin sum().
        # Mongolian "sum" = sub-province / district. Keeps name for code clarity.
        "ezeshigch": "owner_text",
        "ugshil": "breed_text",
        "zai_km": "distance_km",
        "tsag": "time",
        "gazar": "venue",
    },
    "uraldaan": {
        "naadam_ner": "naadam_name",
        "bair": "rank",
        "unach": "jockey",
    },
    "zurag": {
        "fayl": "file",
    },
    "eruul_mend": {
        "buten": "product",
        "hemjee": "amount",
        "emch": "vet",
    },
    "hemjilt": {
        "jin": "weight",
        "undur": "height",
        "tseezhiin_yas": "chest_girth",
        "urd_hol": "cannon_bone",
    },
    "tah": {
        "daragiih_ognoo": "next_date",
        "tahchin": "farrier",
    },
    "tejeel": {
        "tejeel_ner": "feed_name",
        "ehleh_ognoo": "start_date",
        "duusah_ognoo": "end_date",
    },
    "aie_shinjilgee": {
        "ur_dun": "result",
        "aimag": "province",
        "laboratort": "lab",
        "hariutsan": "responsible",
    },
    "havsral": {
        "fayl": "file",
    },
    "mori_soikh": {
        "uyaach_id": "trainer_id",
        "zai_km": "distance_km",
        "hugatsaa_min": "duration_min",
        "temp_c": "temperature_c",
        "salhi_ms": "wind_ms",
        "unach": "jockey",
        "honog": "days",
        "anhliin_tekst": "original_text",
    },
    "polar_soikh": {
        "mori_soikh_id": "training_session_id",
        "uyaach_id": "trainer_id",
        "zai_km": "distance_km",
        "hugatsaa_min": "duration_min",
        "hurd_dundaj": "avg_speed",
        "zc_dundaj": "avg_heart_rate",
        "zc_max": "max_heart_rate",
        "zc_min": "min_heart_rate",
        "sergelt_1min": "recovery_1min",
        "sergelt_2min": "recovery_2min",
        "sergelt_indeks": "recovery_index",
        "zc_bus_amar": "hr_zone_resting",
        "zc_bus_dund": "hr_zone_moderate",
        "zc_bus_huchten": "hr_zone_intense",
        "zc_bus_ih_huch": "hr_zone_very_intense",
        "zc_bus_deed": "hr_zone_max",
        "zc_series": "hr_series",
        "import_ognoo": "imported_at",
    },
    "nokhon_urjikh": {
        "emch": "vet",
    },
    "notification": {
        "uyaach_id": "trainer_id",
        "temdeglel_id": "note_id",
        "tekst": "text",
        "unshlaa": "read",
    },
    "uyaan_temdeglel": {
        "uyaach_id": "trainer_id",
        "zai_km": "distance_km",
        "hugatsaa_min": "duration_min",
        "anhliin_tekst": "original_text",
    },
    "ajil": {
        "tsag": "time",
        "davtalt": "repeat",
        "erembe": "priority",
        "huvaarlisan_id": "assigned_to_id",
    },
    "sankhuu": {
        "dun": "amount",
        "angilal": "category",
    },
    "mori_soikh_plan": {
        "uyaach_id": "trainer_id",
    },
    "hongol": {
        "hiin_ner": "performed_by",  # who did the gelding
        "burtgesen": "created_at",
    },
}

# Data value renames: stored enum strings that need updating.
# Format: { (table_name, column_name): { old_value: new_value, ... } }
DATA_VALUES = {
    ("aduu", "huis"): {
        "azarga": "stallion",
        "guu": "mare",
        "morini": "gelding",
        "unaga_er": "colt",     # not in current live data but in default mappings
        "unaga_em": "filly",
    },
    ("aduu", "status"): {
        "idevhtei": "active",
        "hongolson": "retired",
        "zaragdsan": "sold",
        "nas_barsan": "deceased",
        "idvhigui": "inactive",
        "udam": "pedigree_only",
    },
    ("tohiruulga", "turul"): {
        "zus": "color",
        "ugshil": "breed",
        "garal": "origin",
        "senas_tolgoi": "head_marking",
        "senas_bie": "body_marking",
        "senas_hel": "leg_marking",
        "tamga": "brand",
        "soikh_turul": "training_type",
    },
    ("nokhon_urjikh", "turul"): {
        # TODO: confirm these with the user. Best guesses:
        "heel_hayas": "foaling",
        "suvairsan": "bred",
    },
    ("ajil", "status"): {
        "todorhoi": "pending",
        "duusan": "done",
    },
    ("ajil", "davtalt"): {
        "ganc": "once",
    },
    ("uyaach", "tsol"): {
        "tsolgui": "none",
    },
}

# Endpoint path renames. URL-safe English, plural for collections.
ENDPOINTS = {
    # Resource collections (order: long compound paths first)
    "/api/aduu_uyaach": "/api/horse_trainers",
    "/api/udam_burtgel": "/api/pedigree",
    "/api/mori_soikh": "/api/training_sessions",
    "/api/uyaan_temdeglel": "/api/training_notes",
    "/api/eruul_mend": "/api/health_records",
    "/api/aie": "/api/eia_tests",
    "/api/nokhon": "/api/breeding_events",
    "/api/hongol": "/api/gelding_events",
    "/api/sungaa": "/api/practice_races",
    "/api/uraldaan": "/api/races",
    "/api/zuchee": "/api/stables",
    "/api/sankhuu": "/api/finance",
    "/api/tohiruulga": "/api/options",
    "/api/holboo": "/api/contacts",
    "/api/uyaach": "/api/trainers",
    "/api/hemjilt": "/api/measurements",
    "/api/tejeel": "/api/feedings",
    "/api/ajil": "/api/tasks",
    "/api/tah": "/api/hoof_care",
    "/api/surg": "/api/herds",
    "/api/plan": "/api/training_plans",  # mori_soikh_plan endpoint
    "/api/hailt": "/api/search",
    "/api/aduu": "/api/horses",

    # Action sub-paths
    "/hongol_eligible": "/gelding_eligible",
    "/check_id": "/check_registration",
    "/udam": "/pedigree",
    "/ur_tol": "/offspring",
    "/duusah": "/end",
    "/shiljuuleh": "/promote",
    "/bukhniig_unshlaa": "/read_all",
    "/unshlaa": "/read",
    "/turluud": "/types",

    # Dashboard sub-paths
    "/api/dashboard/butets": "/api/dashboard/composition",
    "/api/dashboard/nas": "/api/dashboard/age_distribution",
    "/api/dashboard/osolt": "/api/dashboard/growth",
    "/api/dashboard/unagalalt": "/api/dashboard/foaling",
    "/api/dashboard/urjil_trend": "/api/dashboard/breeding_trend",
    "/api/dashboard/naadam_stat": "/api/dashboard/naadam_stats",
    # /api/dashboard/naadam stays as-is

    # Reports
    "/api/taillan/ajliin_turul": "/api/reports/task_breakdown",
    "/api/taillan/guitsetgel": "/api/reports/performance",
    "/api/taillan/odrii_huvaari": "/api/reports/daily_schedule",
}


def build_identifier_map():
    """
    Build the full ordered substitution list for find/replace across code.
    Longest keys first to avoid prefix collisions (aduu_ezeshigch before aduu).
    """
    pairs: dict[str, str] = {}

    # Add all column renames per table — but most appear as bare identifiers
    # in Python/JS code, not qualified by table. So we dedupe into a global map
    # and rely on the rename being consistent across tables (e.g. aduu_id
    # always renames to horse_id, even on the aduu table itself the column
    # was renamed to registration_code via SQL — code references to
    # `aduu.aduu_id` will be a separate manual fix).
    for col_old, col_new in COMMON_COLUMNS.items():
        pairs.setdefault(col_old, col_new)
    for tbl, cols in COLUMNS.items():
        for col_old, col_new in cols.items():
            # Special case: aduu_id on the aduu table renames to registration_code,
            # but globally `aduu_id` is most often a FK that should become horse_id.
            # The `a.aduu_id → a.registration_code` conversion is done by
            # ALIAS_FIXES_REGISTRATION_CODE in apply_renames.py before the bulk pass.
            # AduuIn.aduu_id field renames are fixed by hand after the bulk pass.
            if tbl == "aduu" and col_old == "aduu_id":
                continue
            # If the same old name resolves to different new names across
            # tables, the LAST one wins here — manual cleanup needed in code.
            pairs[col_old] = col_new

    # Plus join-aliased columns the backend constructs in SELECTs
    # (e.g. `s.ner as surg_ner` → `s.name as herd_name`)
    aliases = {
        "ezeshigch_ner": "owner_name",
        "malchin_ner": "herder_name",
        "zuchee_ner": "stable_name",
        "ugshil_ner": "breed_name",
        "zus_ner": "color_name",
        "garal_ner": "origin_name",
        "surg_ner": "herd_name",
        "eceg_ner": "sire_name",
        "eh_ner": "dam_name",
        "aduu_ner": "horse_name",
        "aduu_too": "horse_count",
        "surg_too": "herd_count",
        "bair_too": "rank_counts",
        "soikh_too": "training_count",
        "sql_soikh": "sql_training",
        "params_soikh": "params_training",
        "er_too": "male_count",
        "ohin_too": "female_count",
        "zuragnuud": "photos",
        "ezeshigchid": "owners",
        "aduu_sys_id": "horse_sys_id",
    }
    pairs.update(aliases)

    # Tables
    for tbl_old, tbl_new in TABLES.items():
        pairs[tbl_old] = tbl_new

    # Function names that contain Mongolian roots
    pairs["nas_nershil"] = "age_label"
    pairs["hongol_eligible"] = "gelding_eligible"
    pairs["hongol_create"] = "gelding_create"
    pairs["hongol_list"] = "gelding_list"
    pairs["hongol_delete"] = "gelding_delete"
    pairs["udam_list"] = "pedigree_list"
    pairs["udam_create"] = "pedigree_create"
    pairs["udam_update"] = "pedigree_update"
    pairs["udam_delete"] = "pedigree_delete"
    pairs["udam_shiljuuleh"] = "pedigree_promote"
    # Function-name root shorthands (these are not table names, but appear as
    # prefixes in many handler/helper function names — adding them makes the
    # bulk substitution rename functions like `nokhon_list` → `breeding_event_list`.)
    pairs["taillan"] = "reports"
    pairs["guitsetgel"] = "performance"
    pairs["ajliin_turul"] = "task_breakdown"
    pairs["odrii_huvaari"] = "daily_schedule"
    pairs["amjilt"] = "achievements"
    pairs["niit"] = "total"
    pairs["ezen_id"] = "owner_id"
    pairs["uyaagdaj"] = "in_training_count"
    pairs["aie"] = "eia_test"
    pairs["nokhon"] = "breeding_event"
    pairs["udam"] = "pedigree"
    pairs["hongol"] = "gelding_event"
    pairs["mori_soikh"] = "training_session"   # already in TABLES, but re-emphasize
    pairs["calc_zc_bus"] = "calc_hr_zones"
    pairs["hugatsaa_sec"] = "duration_sec"
    pairs["hugatsaa"] = "duration"
    pairs["huvaarlisan"] = "assigned_to"
    pairs["hurd"] = "speed"
    pairs["sergelt_1"] = "recovery_1"
    pairs["sergelt_2"] = "recovery_2"
    pairs["sergelt_idx"] = "recovery_idx"

    # Pydantic class names
    class_renames = {
        "AduuIn": "HorseIn",
        "HongolIn": "GeldingIn",
        "UdamIn": "PedigreeIn",
        "SurgIn": "HerdIn",
        "HolbooIn": "ContactIn",
        "ZucheeIn": "StableIn",
        "AjilIn": "TaskIn",
        "SungaaIn": "PracticeRaceIn",
        "SankhuuIn": "FinanceIn",
        "PlanIn": "TrainingPlanIn",
        "UyaachIn": "TrainerIn",
        "AduuUyaachIn": "HorseTrainerIn",
        "UyaanTemdeglel": "TrainingNoteIn",
        "UraldaanIn": "RaceIn",
        "EruulMendIn": "HealthRecordIn",
        "NokhonIn": "BreedingEventIn",
        "HemjiltIn": "MeasurementIn",
        "TahIn": "HoofCareIn",
        "TejeelIn": "FeedingIn",
        "AieIn": "EiaTestIn",
        "MoriSoikhIn": "TrainingSessionIn",
    }
    pairs.update(class_renames)
    pairs["hailt"] = "search"

    return pairs


# Identifiers EXCLUDED from auto-substitution because they clash with
# Python/JS builtins or common words. The corresponding column renames still
# happen in the SQL migration; SQL-context references in code are fixed
# manually after the bulk pass.
SKIP_IDENTIFIERS = {
    "sum",   # Python builtin sum() — conflicts with sungaa.sum (sub-province)
}


if __name__ == "__main__":
    # Quick sanity dump
    pairs = build_identifier_map()
    print(f"Total identifier substitutions: {len(pairs)}")
    print(f"Tables to rename: {len(TABLES)}")
    print(f"Endpoint paths to rename: {len(ENDPOINTS)}")
    print(f"Data value migrations: {sum(len(v) for v in DATA_VALUES.values())}")
