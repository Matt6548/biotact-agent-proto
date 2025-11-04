# -*- coding: utf-8 -*-
from fastapi import FastAPI, Request, Form
from fastapi.responses import JSONResponse, HTMLResponse, Response, RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from apscheduler.schedulers.background import BackgroundScheduler
from dotenv import load_dotenv
from fastapi.staticfiles import StaticFiles

import io
import csv
import os
import re
import json
import time
import hashlib
from urllib.parse import urlparse
from typing import Any, Dict, List

# --- проектные модули (из репозитория) ---
# если их нет, приложение всё равно запустится — просто логи/правила будут пустыми
try:
    from agent.policy import load_rules, save_rules, check_event   # noqa: F401
except Exception:
    def load_rules() -> Dict[str, Any]:
        return {}
    def save_rules(rules: Dict[str, Any]) -> None:
        os.makedirs("data", exist_ok=True)
        with open(os.path.join("data", "rules.json"), "w", encoding="utf-8") as f:
            json.dump(rules, f, ensure_ascii=False, indent=2)
    def check_event(*args, **kwargs):
        # заглушка: всегда allow
        return {"action": "allow"}

try:
    from agent.logs import add_event, list_events, stats          # noqa: F401
except Exception:
    # простейшая локальная реализация логов
    def _events_path() -> str:
        os.makedirs("data", exist_ok=True)
        return os.path.join("data", "events.jsonl")

    def add_event(event: Dict[str, Any]) -> None:
        with open(_events_path(), "a", encoding="utf-8") as f:
            f.write(json.dumps(event, ensure_ascii=False) + "\n")

    def list_events(limit: int = 1000) -> List[Dict[str, Any]]:
        path = _events_path()
        if not os.path.exists(path):
            return []
        out: List[Dict[str, Any]] = []
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    out.append(json.loads(line))
                except Exception:
                    pass
        return out[-limit:]

    def stats() -> Dict[str, Any]:
        return {"total": len(list_events())}

# ------------------- конфиг -------------------
load_dotenv()
ADMIN_PIN    = os.getenv("ADMIN_PIN")
PRIV_STRICT  = os.getenv("PRIVACY_STRICT", "1") == "1"
HASH_DOMAINS = os.getenv("HASH_DOMAINS",  "0") == "1"
HASH_SALT    = os.getenv("HASH_SALT", "biotact-local-salt")
LOG_RET_DAYS = int(os.getenv("LOG_RETENTION_DAYS", "7"))

DATA_DIR   = os.path.join(os.getcwd(), "data")
EVENTS_JL  = os.path.join(DATA_DIR, "events.jsonl")

# ------------------- утилиты -------------------
def as_html(body: str, **kwargs) -> HTMLResponse:
    """
    Возвращает HTML с гарантированным <meta charset="utf-8">
    Поддерживает дополнительные параметры (например, status_code=403)
    """
    bl = body.lower()
    if "<meta charset=" not in bl:
        if "<head>" in bl:
            body = body.replace("<head>", '<head><meta charset="utf-8">', 1)
        else:
            body = '<meta charset="utf-8">' + body
    return HTMLResponse(content=body, media_type="text/html; charset=utf-8", **kwargs)

def _now() -> float:
    return time.time()

def _norm_input_url(u: str) -> str:
    if not u:
        return ""
    if "://" not in u:
        return "https://" + u.strip("/")
    return u

def _domain(url: str) -> str:
    try:
        return (urlparse(url).hostname or "").lower()
    except Exception:
        return ""

def _hash(s: str) -> str:
    return hashlib.sha256((HASH_SALT + "|" + (s or "")).encode("utf-8")).hexdigest()[:12]

def sanitize_url_keep_domain(u: str) -> str:
    host = _domain(_norm_input_url(u))
    if not host:
        return ""
    return _hash(host) if HASH_DOMAINS else host

def sanitize_event_for_log(ev: Dict[str, Any]) -> Dict[str, Any]:
    """Санитизируем поля событий для списка/CSV (почты, query, длинные куски пути)."""
    out = dict(ev or {})
    out["target"] = sanitize_url_keep_domain(out.get("target", ""))
    for k in list(out.keys()):
        if isinstance(out[k], str):
            s = out[k]
            s = re.sub(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", "[email]", s)
            s = re.sub(r"\?[^ ]*", "", s)                 # выпиливаем querystring
            s = re.sub(r"/[\w\-]{6,}", "/…", s)           # длинные куски пути
            out[k] = s
    return out
def _fmt_ts(v) -> str:
    try:
        # если пришло число/строка с числом — считаем это epoch-seconds
        f = float(v)
        return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(f))
    except Exception:
        # иначе — уже строка, отдаём как есть
        return str(v or "")

def _privacy_badge() -> str:
    mode = "Strict ON" if PRIV_STRICT else "Strict OFF"
    hashed = " · Hashed domains" if HASH_DOMAINS else ""
    panic = " · PANIC ON" if _is_panic() else ""
    return f"<span style='color:#666;font-size:12px'>(Privacy: {mode}{hashed}{panic})</span>"

def prune_logs(days: int):
    cutoff = _now() - days * 86400
    if not os.path.exists(EVENTS_JL):
        return
    kept: List[str] = []
    with open(EVENTS_JL, "r", encoding="utf-8") as f:
        for line in f:
            try:
                j = json.loads(line)
                if float(j.get("ts", 0)) >= cutoff:
                    kept.append(line)
            except Exception:
                pass
    tmp = EVENTS_JL + ".tmp"
    with open(tmp, "w", encoding="utf-8") as w:
        for line in kept:
            w.write(line)
    os.replace(tmp, EVENTS_JL)

# ------------------- состояние фокуса/паники -------------------
focus_state: Dict[str, Any] = {"active": False, "end_ts": 0.0, "allow": []}
panic_until: float = 0.0

def _is_panic() -> bool:
    global panic_until
    if panic_until and _now() >= panic_until:
        panic_until = 0.0
    return panic_until > 0

# ------------------- PIN guard -------------------
def _pin_guard(request: Request):
    """Если задан ADMIN_PIN — требуем куку для админ-страниц."""
    if not ADMIN_PIN:
        return None
    if request.cookies.get("biotact_pin") == ADMIN_PIN:
        return None

    page = f"""
<!doctype html>
<html><head><meta charset="utf-8"><title>Biotact PIN</title>
<style>body{{font-family:system-ui;margin:40px}} input,button{{padding:10px}}</style></head>
<body>
  <h3>Доступ по PIN</h3>
  <form method="post" action="/auth/pin">
    <input type="password" name="pin" required placeholder="PIN">
    <input type="hidden" name="next" value="{request.url.path}">
    <button>Войти</button>
  </form>
</body></html>
"""
    return as_html(page)

# ------------------- приложение -------------------
app = FastAPI(title="Biotact Agent Server")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Глобально принуждаем text/html к UTF-8
@app.middleware("http")
async def force_utf8(request: Request, call_next):
    response = await call_next(request)
    ct = response.headers.get("content-type", "")
    if ct.startswith("text/html") and "charset" not in ct.lower():
        response.headers["content-type"] = "text/html; charset=utf-8"
    return response

# Планировщик очистки логов
scheduler = BackgroundScheduler()
scheduler.start()
scheduler.add_job(lambda: prune_logs(LOG_RET_DAYS), "interval", hours=6, id="retention", replace_existing=True)

# ------------------- auth -------------------
@app.post("/auth/pin")
async def auth_pin(request: Request, pin: str = Form(...), next: str = Form("/dashboard")):
    if ADMIN_PIN and pin == ADMIN_PIN:
        r = RedirectResponse(url=next or "/dashboard", status_code=302)
        r.set_cookie("biotact_pin", ADMIN_PIN, max_age=86400, httponly=True)
        return r
    return as_html("<meta charset=utf-8><h3>Неверный PIN</h3>", status_code=403)

# ------------------- health -------------------
@app.get("/health")
def health():
    return {
        "ok": True,
        "privacy_strict": PRIV_STRICT,
        "hash_domains": HASH_DOMAINS,
        "panic": _is_panic(),
        "focus": focus_state,
    }

# ------------------- rules API -------------------
@app.get("/rules")
def get_rules():
    try:
        r = load_rules() or {}
    except Exception:
        r = {}
    r.setdefault("blocked_services", [])
    r.setdefault("allowed_domains", [])
    r.setdefault("scope_domains", [])
    r.setdefault("log_external", False)
    r.setdefault("warn_only_domains", [])
    r.setdefault("time_windows", r.get("time_windows", []))
    return r

@app.post("/rules")
async def set_rules(request: Request):
    guard = _pin_guard(request)
    if guard:
        return guard
    data = await request.json()
    norm = lambda xs: [x.strip().lower() for x in (xs or []) if x and x.strip()]
    data["blocked_services"]  = norm(data.get("blocked_services"))
    data["allowed_domains"]   = norm(data.get("allowed_domains"))
    data["scope_domains"]     = norm(data.get("scope_domains"))
    data["warn_only_domains"] = norm(data.get("warn_only_domains"))
    data["log_external"]      = bool(data.get("log_external", False))
    # time windows
    tws = []
    for tw in data.get("time_windows", []) or []:
        tws.append({"start": (tw.get("start","") or "").strip(),
                    "end":   (tw.get("end","")   or "").strip()})
    data["time_windows"] = tws
    save_rules(data)
    return {"ok": True, "rules": get_rules()}

# ------------------- rules view -------------------
@app.get("/rules/view")
def rules_view(request: Request):
    guard = _pin_guard(request)
    if guard:
        return guard
    r = get_rules()

    def join(xs): return "\n".join(xs or [])
    def twjoin(tws): return "\n".join([f"{tw.get('start','')}-{tw.get('end','')}" for tw in (tws or [])])

    page = f"""<!doctype html>
<html><head><meta charset="utf-8"><title>Biotact Rules</title>
<style>
body{{font-family:system-ui;margin:18px;max-width:900px}}
textarea{{width:100%;height:140px}}
.row{{margin:14px 0}}
.btn{{padding:8px 14px}}
</style></head>
<body>
  <h2>Biotact Правила { _privacy_badge() }</h2>
  <div class="row"><a href="/logs/view">Журнал</a> · <a href="/dashboard">Dashboard</a></div>

  <form onsubmit="return save()">
    <div class="row"><b>Разрешённые домены</b><br>
      <textarea id="allowed">{join(r.get('allowed_domains'))}</textarea>
    </div>
    <div class="row"><b>Доменная область (scope)</b><br>
      <textarea id="scope">{join(r.get('scope_domains'))}</textarea>
    </div>
    <div class="row"><b>Только предупреждать (warn-only)</b><br>
      <textarea id="warnonly">{join(r.get('warn_only_domains'))}</textarea>
    </div>
    <div class="row"><b>Блокируемые сервисы</b><br>
      <textarea id="blocked">{join(r.get('blocked_services'))}</textarea>
    </div>
    <div class="row"><b>Окна времени (HH:MM-HH:MM, по одному в строке)</b><br>
      <textarea id="tws">{twjoin(r.get('time_windows'))}</textarea>
    </div>
    <div class="row"><label><input id="logext" type="checkbox" {"checked" if r.get("log_external") else ""}> Логировать внешние события</label></div>
    <div class="row"><button class="btn" type="submit">Сохранить</button></div>
  </form>

<script>
function parseLines(txt) {{
  return txt.split(/\\r?\\n/).map(s => s.trim().toLowerCase()).filter(Boolean);
}}
function parseTimeWindows(txt) {{
  return txt.split(/\\r?\\n/).map(s => s.trim()).filter(Boolean).map(x => {{
    const m = x.split('-'); return {{start: (m[0]||'').trim(), end: (m[1]||'').trim()}};
  }});
}}
async function save() {{
  const payload = {{
    allowed_domains:   parseLines(document.getElementById('allowed').value),
    scope_domains:     parseLines(document.getElementById('scope').value),
    warn_only_domains: parseLines(document.getElementById('warnonly').value),
    blocked_services:  parseLines(document.getElementById('blocked').value),
    time_windows:      parseTimeWindows(document.getElementById('tws').value),
    log_external:      document.getElementById('logext').checked
  }};
  const r = await fetch('/rules', {{
    method:'POST',
    headers: {{'Content-Type': 'application/json'}},
    body: JSON.stringify(payload)
  }});
  if (r.ok) alert('Сохранено'); else alert('Ошибка сохранения');
  return false;
}}
</script>
</body></html>"""
    return as_html(page)

# ------------------- dashboard -------------------
@app.get("/dashboard")
def dashboard(request: Request):
    guard = _pin_guard(request)
    if guard:
        return guard

    focus = "ON до " + time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(focus_state["end_ts"])) if focus_state["active"] else "OFF"
    panic = "ON" if _is_panic() else "OFF"

    page = f"""<!doctype html>
<html><head><meta charset="utf-8"><title>Biotact Dashboard</title>
<style>
body{{font-family:system-ui;margin:18px;max-width:900px}}
.card{{border:1px solid #ddd;border-radius:10px;padding:14px;margin:10px 0}}
.btn{{padding:8px 14px}}
</style></head>
<body>
  <h2>Biotact Dashboard { _privacy_badge() }</h2>
  <div><a href="/logs/view">Журнал</a> · <a href="/rules/view">Правила</a></div>

  <div class="card">
    <h3>Паника: {panic}</h3>
    <form method="post" action="/panic/on" style="display:inline">
      <input type="hidden" name="minutes" value="15"><button class="btn">Паника 15м</button>
    </form>
    <form method="post" action="/panic/on" style="display:inline">
      <input type="hidden" name="minutes" value="60"><button class="btn">Паника 1ч</button>
    </form>
    <form method="post" action="/panic/on" style="display:inline">
      <input type="hidden" name="minutes" value="1440"><button class="btn">Паника 24ч</button>
    </form>
    <form method="post" action="/panic/off" style="display:inline">
      <button class="btn">Снять панику</button>
    </form>
  </div>

  <div class="card">
    <h3>Фокус-режим: {focus}</h3>
    <form method="post" action="/focus/on">
      <div>Минуты: <input type="number" name="minutes" value="60" min="1" style="width:80px"></div>
      <div>Разрешить домены (через запятую):<br>
        <input type="text" name="allow" style="width:100%" placeholder="example.com, another.org">
      </div>
      <button class="btn" type="submit">Включить фокус</button>
    </form>
    <form method="post" action="/focus/off" style="margin-top:8px">
      <button class="btn" type="submit">Выключить фокус</button>
    </form>
  </div>
</body></html>
"""
    return as_html(page)

# ------------------- журнал -------------------
@app.get("/logs")
def logs():
    # чистые данные (как JSON)
    events = list_events()
    return {"events": events, "stats": stats()}

@app.get("/logs.csv")
def logs_csv():
    # CSV из санитизированных данных
    events = [sanitize_event_for_log(e) for e in list_events()]
    buf = io.StringIO()
    buf.write("\ufeff")  # BOM для Excel
    if events:
        fieldnames = sorted({k for e in events for k in e.keys()})
    else:
        fieldnames = ["ts", "source", "target", "action"]
    w = csv.DictWriter(buf, fieldnames=fieldnames)
    w.writeheader()
    for e in events:
        w.writerow(e)
    out = Response(content=buf.getvalue(), media_type="text/csv; charset=utf-8")
    out.headers["Content-Disposition"] = 'attachment; filename="biotact_logs.csv"'
    return out

@app.get("/logs/view")
def logs_view(request: Request):
    guard = _pin_guard(request)
    if guard:
        return guard
    rows = [sanitize_event_for_log(e) for e in list_events()]
    parts: List[str] = []
    parts.append("""<!doctype html><html><head><meta charset="utf-8"><title>Biotact Logs</title>
<style>
body{font-family:system-ui;margin:18px}
table{border-collapse:collapse;width:100%}
td,th{border-bottom:1px solid #eee;padding:6px 8px;text-align:left}
thead th{border-bottom:2px solid #ccc}
a.btn{display:inline-block;padding:6px 10px;border:1px solid #ccc;border-radius:6px;text-decoration:none}
</style></head><body>""")
    parts.append(f"<h2>Biotact — Последние события {_privacy_badge()}</h2>")
    parts.append('<div style="margin:8px 0"><a class="btn" href="/logs.csv">Скачать CSV</a> · <a class="btn" href="/dashboard">Dashboard</a> · <a class="btn" href="/rules/view">Правила</a></div>')
    parts.append("<table><thead><tr><th>ID</th><th>Время</th><th>Источник</th><th>Цель</th></tr></thead><tbody>")
    # Номера по возрастанию
    start_id = max(1, len(rows) - len(rows) + 1)
    for idx, e in enumerate(rows, start=1):
        ts  = _fmt_ts(e.get("ts") or e.get("time"))
        src = e.get("source", "")
        tgt = e.get("target", "")
        parts.append(f"<tr><td>{idx}</td><td>{ts}</td><td>{src}</td><td>{tgt}</td></tr>")
    parts.append("</tbody></table></body></html>")
    return as_html("".join(parts))

# ------------------- focus/panic endpoints -------------------
@app.post("/panic/on")
async def panic_on(request: Request, minutes: int = Form(60)):
    guard = _pin_guard(request)
    if guard:
        return guard
    global panic_until
    panic_until = _now() + max(1, minutes) * 60
    return RedirectResponse("/dashboard", status_code=302)

@app.post("/panic/off")
async def panic_off(request: Request):
    guard = _pin_guard(request)
    if guard:
        return guard
    global panic_until
    panic_until = 0.0
    return RedirectResponse("/dashboard", status_code=302)

@app.post("/focus/on")
async def focus_on(request: Request, minutes: int = Form(60), allow: str = Form("")):
    guard = _pin_guard(request)
    if guard:
        return guard
    allow_list = [x.strip().lower() for x in allow.split(",") if x.strip()]
    focus_state["active"] = True
    focus_state["end_ts"] = _now() + max(1, minutes) * 60
    focus_state["allow"]  = allow_list
    return RedirectResponse("/dashboard", status_code=302)

@app.post("/focus/off")
async def focus_off(request: Request):
    guard = _pin_guard(request)
    if guard:
        return guard
    focus_state["active"] = False
    focus_state["end_ts"] = 0.0
    focus_state["allow"]  = []
    return RedirectResponse("/dashboard", status_code=302)

# ------------------- приём событий от клиента -------------------
@app.post("/event")
async def event(request: Request):
    """
    Принимаем произвольный JSON от расширения/клиента.
    Пишем в лог и возвращаем решение (здесь по умолчанию "allow").
    """
    try:
        ev = await request.json()
    except Exception:
        return JSONResponse({"ok": False, "error": "bad json"}, status_code=400)

    # добавляем базовые поля, если не были переданы
    ev.setdefault("ts", time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()))
    ev.setdefault("source", "browser")

    try:
        add_event(ev)
    except Exception:
        pass

    # если есть настоящая политика — воспользуемся ею; иначе allow
    try:
        decision = check_event(ev, get_rules(), focus_state, _is_panic())
    except Exception:
        decision = {"action": "allow"}

    return {"ok": True, "decision": decision}
