import json, re
from pathlib import Path
from collections import defaultdict

data = json.loads(Path(r'D:\FoxAI\FOXAI_PRM project_resource_management\daily\tasks.json').read_text(encoding='utf-8'))
tasks = data['tasks']
print(f"Tong: {len(tasks)} tasks\n")

# 1. Trung title chinh xac
groups = defaultdict(list)
for t in tasks:
    key = t['title'].lower().strip()
    groups[key].append(t)

dups = {k: v for k, v in groups.items() if len(v) > 1}
if dups:
    print(f"=== TRUNG TITLE CHINH XAC: {len(dups)} nhom ===")
    for key, ts in dups.items():
        print(f"  [{len(ts)} task] {key[:70]}")
        for t in ts:
            print(f"    #{t['id']} [{t['status']}] {t['owner']} | {t['deadline']}")
else:
    print("Khong co task trung title chinh xac.\n")

# 2. Title tuong tu >= 70%
def words(s):
    return set(re.findall(r'\w+', s.lower()))

print("=== TITLE TUONG TU >= 70% ===")
similar = []
for i, a in enumerate(tasks):
    for b in tasks[i+1:]:
        wa, wb = words(a['title']), words(b['title'])
        if not wa or not wb:
            continue
        overlap = len(wa & wb) / max(len(wa), len(wb))
        if overlap >= 0.7:
            similar.append((overlap, a, b))

similar.sort(reverse=True)
if similar:
    for score, a, b in similar:
        print(f"  [{score:.0%}] #{a['id']} vs #{b['id']}")
        print(f"    A: {a['title'][:70]}")
        print(f"    B: {b['title'][:70]}")
        print()
else:
    print("  Khong co cap nao tuong tu >= 70%")
