#!/usr/bin/env python3
"""HTML div тэнцлийг шалгагч — index.html хадгалахын өмнө ажиллуулна уу"""
import sys, re

def check_html(filepath):
    content = open(filepath).read()
    
    errors = []
    warnings = []
    
    # Modal-уудыг олох
    modals = re.findall(r'<div[^>]+id="([^"]+)"[^>]*>', content)
    modal_ids = [m for m in modals if 'modal' in m.lower()]
    
    # Div нээлт/хаалт тоолох (script, style дотрыг оруулахгүй)
    # Script болон style блокийг хасах
    clean = re.sub(r'<script[\s\S]*?</script>', '', content)
    clean = re.sub(r'<style[\s\S]*?</style>', '', clean)
    
    opens = len(re.findall(r'<div[\s>]', clean))
    closes = len(re.findall(r'</div>', clean))
    
    if opens != closes:
        errors.append(f"❌ div тэнцэхгүй байна: {opens} нээлт, {closes} хаалт ({abs(opens-closes)} дутуу/илүү)")
    else:
        print(f"✅ div тэнцэл зөв: {opens} нээлт = {closes} хаалт")
    
    # Modal бүрийг шалгах
    for modal_id in modal_ids:
        start = content.find(f'id="{modal_id}"')
        if start == -1:
            continue
        div_start = content.rfind('<div', 0, start)
        chunk = content[div_start:div_start+100000]
        
        depth = 0
        i = 0
        closed = False
        while i < len(chunk) - 6:
            if chunk[i:i+4] == '<div':
                depth += 1
                i += 4
            elif chunk[i:i+6] == '</div>':
                depth -= 1
                if depth == 0:
                    closed = True
                    break
                i += 6
            else:
                i += 1
        
        if closed:
            print(f"✅ #{modal_id} зөв хаагдсан")
        else:
            errors.append(f"❌ #{modal_id} хаагдаагүй байна! </div> дутуу.")
    
    # quick-modal parent шалгах (тусгай шалгалт)
    qm_pos = content.find('id="quick-modal"')
    if qm_pos != -1:
        # quick-modal-ийн өмнөх хаалтгүй div байгаа эсэх
        before = content[:qm_pos]
        # Хамгийн сүүлийн нээлттэй div
        before_clean = re.sub(r'<script[\s\S]*?</script>', '', before)
        before_clean = re.sub(r'<style[\s\S]*?</style>', '', before_clean)
        b_opens = len(re.findall(r'<div[\s>]', before_clean))
        b_closes = len(re.findall(r'</div>', before_clean))
        if b_opens != b_closes:
            errors.append(f"❌ quick-modal-ийн өмнө {b_opens-b_closes} хаагдаагүй div байна!")
        else:
            print(f"✅ quick-modal өмнөх div тэнцэл зөв")
    
    print()
    if errors:
        print("=" * 50)
        for e in errors:
            print(e)
        print("=" * 50)
        print(f"\n🔴 {len(errors)} алдаа олдлоо. Засварлана уу!")
        sys.exit(1)
    else:
        print("🟢 Бүх шалгалт амжилттай!")
        sys.exit(0)

if __name__ == '__main__':
    filepath = sys.argv[1] if len(sys.argv) > 1 else 'frontend/index.html'
    print(f"Шалгаж байна: {filepath}\n")
    check_html(filepath)
