import json, csv, os

with open('q4_2025_plan.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

fields = ['date','channel','title','description','product','target','image_prompt']
out_path = 'q4_2025_plan.csv'

with open(out_path, 'w', newline='', encoding='utf-8-sig') as f:
    w = csv.DictWriter(f, fieldnames=fields)
    w.writeheader()
    for row in data:
        w.writerow({k: row.get(k, '') for k in fields})

print('Готово: ' + os.path.abspath(out_path))
