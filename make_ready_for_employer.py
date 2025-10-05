# make_ready_for_employer.py — единый прогон подготовки материалов “под вакансию”
import json, csv, os
from datetime import datetime, timedelta
from pathlib import Path

PLAN_JSON = 'q4_2025_plan.json'
CSV_ALL   = 'q4_2025_plan.csv'
CSV_NEXT7 = 'next_7_days_plan.csv'
SAMPLES   = 'samples_for_employer.txt'

# 1) Распределение продуктов и “прибитые” даты
FAVORITES = ['DERMACOMPLEX','OPHTALMOCOMPLEX','IMMUNOCOMPLEX']
PIN_DATES = {'2025-10-10': 'OPHTALMOCOMPLEX'}  # World Sight Day

# 2) Офлайн-шаблоны текстов по каналам (без API)
TEMPLATES = {
  'Instagram': """{product_ru}: {hook}
{benefits}
Как принимать: {dosage}
Немецкое качество. {cta} #Biotact #здоровье""",
  'Telegram': """{product_ru} — коротко:
{benefits}
Кому полезно: {target}
Подробнее скоро в канале. {cta}""",
  'Blog': """{product_ru}: подробный разбор
{hook}

Преимущества:
{benefits_bullets}

Кому подходит: {target}
Как принимать: {dosage}
{cta}""",
  'Podcast': """Скрипт выпуска: {product_ru}
1) Зачем: {hook}
2) Что внутри: {benefits}
3) Для кого: {target}
4) Советы по приёму: {dosage}
Завершение: {cta}""",
  'Email': """Тема: {product_ru} — поддержка каждый день
Здравствуйте!
{hook}
{benefits}
Кому подходит: {target}
Как принимать: {dosage}
{cta}
"""
}

PRODUCT_INFO = {
  'DERMACOMPLEX': {
    'product_ru':'DERMACOMPLEX',
    'hook':'здоровая кожа, волосы и ногти изнутри',
    'benefits':'Антиоксиданты уменьшают воспаления, биотин и цинк укрепляют волосы и ногти, пробиотики поддерживают чистую кожу.',
    'benefits_bullets':'- Антиоксиданты против воспалений\n- Биотин и цинк для волос и ногтей\n- Пробиотики — поддержка кожи изнутри',
    'dosage':'детям 4–8 лет — 1/2 капсулы (растворить), 8+ — 1 капсула, взрослым — 1–2 капсулы в день',
    'target':'дети 4+, взрослые, при проблемах кожи/волос/ногтей',
  },
  'OPHTALMOCOMPLEX': {
    'product_ru':'OPHTALMOCOMPLEX',
    'hook':'поддержка зрения и защита сетчатки',
    'benefits':'Лютеин/зеаксантин — защита макулы; витамины A/E/C — восстановление; Омега-3 и витамины группы B — поддержка зрительного нерва.',
    'benefits_bullets':'- Лютеин/зеаксантин для макулы\n- Витамины A/E/C — восстановление\n- Омега-3+B — поддержка передачи сигнала',
    'dosage':'детям 7+ — 1 капсула в день, взрослым — 2 капсулы в день',
    'target':'много экранного времени, сухость/утомление глаз, профилактика возрастных изменений',
  },
  'IMMUNOCOMPLEX': {
    'product_ru':'IMMUNOCOMPLEX',
    'hook':'ежедневная поддержка иммунитета для всей семьи',
    'benefits':'Сбалансированные витамины и минералы с антиоксидантами помогают защите в сезон нагрузок.',
    'benefits_bullets':'- Ежедневная поддержка\n- Антиоксиданты\n- Удобные капсулы',
    'dosage':'обычно 1–2 капсулы в день (по рекомендации специалиста)',
    'target':'дети и взрослые в сезон простуд/повышенных нагрузок',
  },
}
CTA = "Перед применением проконсультируйтесь со специалистом. Сделайте шаг к балансу с Biotact."

def load_plan(path):
    with open(path,'r',encoding='utf-8') as f:
        return json.load(f)

def save_plan(path, data):
    with open(path,'w',encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def tune_products(plan):
    i = 0
    for row in plan:
        d = row.get('date','')
        if d in PIN_DATES:
            row['product'] = PIN_DATES[d]
            row['title']   = row['product'].title()
        else:
            row['product'] = FAVORITES[i % len(FAVORITES)]
            row['title']   = row['product'].title()
            i += 1

def fill_texts_offline(plan):
    for row in plan:
        info = PRODUCT_INFO.get(row.get('product',''))
        tpl  = TEMPLATES.get(row.get('channel',''))
        if not info or not tpl:
            continue
        row['description'] = tpl.format(cta=CTA, **info)

def export_csv(plan, out_csv):
    fields = ['date','channel','title','description','product','target','image_prompt']
    with open(out_csv,'w',newline='',encoding='utf-8-sig') as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in plan:
            w.writerow({k: r.get(k,'') for k in fields})

def export_next7(plan, out_csv, today_str='2025-10-03'):
    today = datetime.fromisoformat(today_str).date()
    end   = today + timedelta(days=7)
    def to_date(s):
        try: return datetime.fromisoformat(s).date()
        except: return None
    rows = [r for r in plan if r.get('date') and (to_date(r['date']) is not None) and (today <= to_date(r['date']) <= end)]
    fields = ['date','channel','title','description','product','target','image_prompt']
    with open(out_csv,'w',newline='',encoding='utf-8-sig') as f:
        w = csv.DictWriter(f, fieldnames=fields); w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k,'') for k in fields})

def export_samples(plan, out_txt):
    def pick(ch):
        for r in plan:
            if r.get('channel','').lower()==ch.lower():
                return r
        return plan[0] if plan else {}
    def render(r, kind):
        d   = r.get('date',''); t=r.get('title','') or r.get('product',''); desc=r.get('description',''); tgt=r.get('target','семьи, здоровье, профилактика')
        if kind=='Instagram': return f"[Instagram • {d}]\n{t}\n{desc}\n#Biotact"
        if kind=='Telegram':  return f"[Telegram • {d}]\n{t}\n{desc}\nЦА: {tgt}"
        if kind=='Email':     return f"[Email • {d}]\nТема: {t} — поддержка здоровья\n{desc}"
        return ""
    inst = render(pick('Instagram'),'Instagram')
    tg   = render(pick('Telegram'),'Telegram')
    em   = render(pick('Email'),'Email')
    Path(out_txt).write_text("\n\n---\n\n".join([inst,tg,em]), encoding='utf-8')

def main():
    if not Path(PLAN_JSON).exists():
        raise SystemExit(f"Не найден {PLAN_JSON}. Сначала запусти: python biotact_ai_agent.py")
    plan = load_plan(PLAN_JSON)
    tune_products(plan)
    fill_texts_offline(plan)
    save_plan(PLAN_JSON, plan)
    export_csv(plan, CSV_ALL)
    export_next7(plan, CSV_NEXT7)
    export_samples(plan, SAMPLES)
    print("Готово:")
    print(" - Обновлён q4_2025_plan.json")
    print(" - Экспортирован", CSV_ALL)
    print(" - Сформирован", CSV_NEXT7)
    print(" - Образцы постов:", SAMPLES)

if __name__ == '__main__':
    main()
