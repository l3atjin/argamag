"""
Apply Mongolian → English renames to a file in-place.

Usage:
    python3 backend/apply_renames.py <file_path>

Strategy:
  1. Precise pre-passes for aliased references that need special handling
     (e.g. `a.aduu_id` is registration_code, but `ms.aduu_id` is horse_id).
  2. Bulk identifier renames using word boundaries, longest-first.
  3. Endpoint path renames (exact string match, no word boundaries needed
     since paths begin with `/api/`).
  4. Enum value renames inside string literals (e.g. 'azarga' → 'stallion').
  5. Report any remaining Mongolian-Latin identifiers for manual review.
"""
import sys, re, os

sys.path.insert(0, os.path.dirname(__file__))
from rename_map import (
    TABLES, COMMON_COLUMNS, COLUMNS, DATA_VALUES, ENDPOINTS, SKIP_IDENTIFIERS,
    build_identifier_map,
)


# Aliased references in SQL queries where the alias points to the OLD aduu table.
# These should become `<alias>.registration_code`, not `<alias>.horse_id`.
ALIAS_FIXES_REGISTRATION_CODE = [
    # `a.aduu_id` where `a` aliases aduu/horse
    (r'\ba\.aduu_id\b', 'a.registration_code'),
    # `aduu.aduu_id` unqualified
    (r'\baduu\.aduu_id\b', 'horse.registration_code'),
]

# Enum/string-literal value renames. Applied inside Python/JS string contexts.
# We match the value with surrounding quotes to be safe.
ENUM_LITERAL_RENAMES: list[tuple[str, str]] = []
for (_tbl, _col), value_map in DATA_VALUES.items():
    for old, new in value_map.items():
        ENUM_LITERAL_RENAMES.append((f"'{old}'", f"'{new}'"))
        ENUM_LITERAL_RENAMES.append((f'"{old}"', f'"{new}"'))


def apply_endpoint_renames(text: str) -> str:
    # Endpoints: sort longest-first so /api/aduu_uyaach matches before /api/aduu
    paths = sorted(ENDPOINTS.items(), key=lambda kv: -len(kv[0]))
    for old, new in paths:
        text = text.replace(old, new)
    return text


def apply_identifier_renames(text: str) -> str:
    """
    Apply identifier renames using a boundary that treats `_` as a separator.
    Pattern: (?<![a-zA-Z0-9])X(?![a-zA-Z0-9])

    This lets `aduu` match inside `aduu_list` (becomes `horse_list`) while
    still rejecting matches inside identifiers like `naduuser`. Longest-first
    ordering ensures compound renames (aduu_uyaach → horse_trainer) win over
    component renames (aduu → horse).
    """
    pairs = build_identifier_map()
    # Filter out keys we never want auto-substituted (builtins, etc.)
    pairs = {k: v for k, v in pairs.items() if k not in SKIP_IDENTIFIERS}
    ordered = sorted(pairs.items(), key=lambda kv: -len(kv[0]))
    for old, new in ordered:
        text = re.sub(
            rf"(?<![a-zA-Z0-9]){re.escape(old)}(?![a-zA-Z0-9])",
            new, text
        )
    return text


def apply_enum_literals(text: str) -> str:
    for old, new in ENUM_LITERAL_RENAMES:
        text = text.replace(old, new)
    return text


def find_remaining_mongolian(text: str) -> list[str]:
    """
    Heuristic: find candidate Mongolian-Latin identifiers that look like they
    weren't translated. Reports tokens NOT in a small allowlist of English
    words and matching common Mongolian transliteration patterns.
    """
    # Source tokens that we know about and have intentionally NOT renamed
    intentional = {
        "naadam", "naadam_id", "naadam_type", "naadam_name", "naadam_stat",
        "naadam_stats", "notification", "polar", "polar_session",
        "polar_exercise_id", "polar_import", "polar_import_in",
        "hrv", "training_load", "gps_series",
        "Cyrillic", "Tahчин",  # safety
        # Spanish/Latin variable names from import script that aren't worth renaming yet
    }
    # Find all snake_case identifiers
    tokens = set(re.findall(r"\b[a-z][a-z0-9_]{2,}\b", text))
    suspicious = []
    # Common Mongolian-transliteration markers
    mn_patterns = re.compile(
        r"^(.*_(too|gui|ner|huis|id)|.*[aeiou]{3,}.*|.*sh[aeiou].*|.*kh[aeiou].*"
        r"|.*[aeiouy](aa|ee|ii|oo|uu)[aeiouy]?.*|aduu|surg|holboo|uyaach|sungaa|"
        r"uraldaan|zurag|tah|tejeel|hemjilt|naadam|nokhon|ognoo|tailbar|turul|"
        r"idevhtei|huvi|ezeshigch|malchin|ugshil|zus|garal|bayrshal|hongol|"
        r"udam|hailt|emch|jin|undur|dugaar|chuhal|bair|unach|dur|gazar|aimag|"
        r"sum|tsag|hugatsaa|zai|salhi|temp|honog|anhliin|tekst|fayl|chip|"
        r"pasport|dnh|registerlesen|tsus|senas|tamga|zuchee|huvaarlisan|"
        r"davtalt|erembe|todorhoi|duusan|dund|deed|huch|amar|ih|sergelt|zc_).*$"
    )
    for t in tokens:
        if t in intentional:
            continue
        if mn_patterns.search(t):
            suspicious.append(t)
    return sorted(suspicious)


def transform(path: str):
    with open(path) as f:
        text = f.read()
    original_len = len(text)

    # 1. Aliased pre-passes (must come BEFORE general aduu_id → horse_id)
    for pat, repl in ALIAS_FIXES_REGISTRATION_CODE:
        text = re.sub(pat, repl, text)

    # 2. Endpoint paths (strings, not identifiers)
    text = apply_endpoint_renames(text)

    # 3. Bulk identifier renames
    text = apply_identifier_renames(text)

    # 4. Enum literals
    text = apply_enum_literals(text)

    with open(path, "w") as f:
        f.write(text)

    print(f"  {path}: {original_len} → {len(text)} bytes")

    remaining = find_remaining_mongolian(text)
    if remaining:
        print(f"\n  ⚠ Potentially Mongolian tokens still present (review):")
        for t in remaining[:50]:
            print(f"    - {t}")
        if len(remaining) > 50:
            print(f"    ... and {len(remaining) - 50} more")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 backend/apply_renames.py <file_path>")
        sys.exit(1)
    for p in sys.argv[1:]:
        print(f"\nTransforming {p}...")
        transform(p)
