# tune_plan.py — распределяет продукты и закрепляет 10 окт за OPHTALMOCOMPLEX
import json

FAVORITES = ['DERMACOMPLEX','OPHTALMOCOMPLEX','IMMUNOCOMPLEX']
PIN_DATES = {'2025-10-10': 'OPHTALMOCOMPLEX'}  # World Sight Day

with open('q4_2025_plan.json','r',encoding='utf-8') as f:
    plan = json.load(f)

i = 0
for row in plan:
    if row['date'] in PIN_DATES:
        row['product'] = PIN_DATES[row['date']]
        row['title'] = row['product'].title()
    else:
        row['product'] = FAVORITES[i % len(FAVORITES)]
        row['title'] = row['product'].title()
        i += 1

with open('q4_2025_plan.json','w',encoding='utf-8') as f:
    json.dump(plan, f, ensure_ascii=False, indent=2)

print('Готово: продукты распределены, 10 окт -> OPHTALMOCOMPLEX')
