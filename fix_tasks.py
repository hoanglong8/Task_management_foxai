import json, shutil
from pathlib import Path

f = Path(r'D:\FoxAI\FOXAI_PRM project_resource_management\daily\tasks.json')

shutil.copy(f, str(f) + '.bak')

raw = f.read_text(encoding='utf-8', errors='replace')

# Find the opening { of task #28 object
marker = '"id": 28,'
cut = raw.find(marker)
last_brace = raw.rfind('{', 0, cut)
comma_pos = raw.rfind(',', 0, last_brace)
trimmed = raw[:comma_pos].rstrip()
fixed = trimmed + '\n  ],\n  "last_id": 27\n}'

# Validate before writing
data = json.loads(fixed)
print("Tasks:", len(data["tasks"]), "| last_id:", data["last_id"])

# WRITE first, print after
f.write_text(fixed, encoding='utf-8')
print("Saved OK")

pending = [t for t in data["tasks"] if t["status"] != "completed"]
print("Active tasks:", len(pending))
