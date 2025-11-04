import os, json, sqlite3
from pathlib import Path
from datetime import datetime, timedelta

from fastapi import FastAPI, Form
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from apscheduler.schedulers.background import BackgroundScheduler
from dotenv import load_dotenv
import requests

load_dotenv()
APP_NAME = os.getenv("APP_NAME", "Biotact Unified")
PORT = int(os.getenv("PORT", "18080"))
PRIVACY_STRICT = os.getenv("PRIVACY_STRICT", "1") in ("1","true","True")
LOG_RETENTION_DAYS = int(os.getenv("LOG_RETENTION_DAYS", "7"))
DATA_DIR = Path(os.getenv("DATA_DIR", "./data")); DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = Path("logs.db")
STATE_PATH = DATA_DIR / "state.json"
WEBUI_DIR = Path("webui")

N8N_WEBHOOK_FOCUS = os.getenv("N8N_WEBHOOK_FOCUS","").strip()
N8N_WEBHOOK_PANIC = os.getenv("N8N_WEBHOOK_PANIC","").strip()

DEFAULT_STATE = {"focus":{"until":None,"domains":[]},
                 "panic":{"until":None},
                 "rules":{"allow":[],"scope":[],"warn":[]}}

def load_state():
    if STATE_PATH.exists():
        try: return json.loads(STATE_PATH.read_text(encoding="utf-8"))
        except Exception: pass
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(DEFAULT_STATE, ensure_ascii=False, indent=2), encoding="utf-8")
    return DEFAULT_STATE

def save_state(st): STATE_PATH.write_text(json.dumps(st, ensure_ascii=False, indent=2), encoding="utf-8")

def is_active(until_iso):
    if not until_iso: return False
    try: return datetime.utcnow() < datetime.fromisoformat(until_iso)
    except Exception: return False

def db_connect():
    return sqlite3.connect(DB_PATH, timeout=5, check_same_thread=False)

def db_init():
    con = db_connect(); cur = con.cursor()
    cur.execute("""CREATE TABLE IF NOT EXISTS events(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        kind TEXT, source TEXT, target TEXT, level TEXT, created_at TEXT
    )""")
    con.commit()
    cur.execute("SELECT COUNT(*) FROM events")
    if (cur.fetchone() or [0])[0] == 0:
        cur.execute("INSERT INTO events(kind,source,target,level,created_at) VALUES(?,?,?,?,?)",
                    ("boot","server","startup","info",datetime.utcnow().isoformat()))
        con.commit()
    con.close()

def log_event(kind, source="", target="", level="info"):
    con = db_connect(); cur = con.cursor()
    cur.execute("INSERT INTO events(kind,source,target,level,created_at) VALUES(?,?,?,?,?)",
                (kind, source, target, level, datetime.utcnow().isoformat()))
    con.commit(); con.close()

def cleanup_logs():
    cutoff = datetime.utcnow() - timedelta(days=LOG_RETENTION_DAYS)
    con = db_connect(); cur = con.cursor()
    cur.execute("DELETE FROM events WHERE created_at < ?", (cutoff.isoformat(),))
    con.commit(); con.close()

def notify(url, payload):
    if not url: return
    try: requests.post(url, json=payload, timeout=5)
    except Exception: pass

db_init()

app = FastAPI(title=APP_NAME)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"], allow_credentials=True)

WEBUI_DIR.mkdir(exist_ok=True)
app.mount("/ui", StaticFiles(directory=str(WEBUI_DIR), html=True), name="ui")

CSS_RESET = """
<style>
body{font-family:system-ui;margin:0} .wrap{max-width:920px;margin:0 auto;padding:16px}
.card{border:1px solid #e6e6e6;border-radius:10px;padding:16px;margin:16px 0}
.btn{padding:8px 12px;border-radius:8px;border:1px solid #2156f5;background:#2156f5;color:#fff;cursor:pointer}
.btn.o{background:#fff;color:#2156f5}
input,textarea{padding:8px;border:1px solid #e6e6e6;border-radius:8px;width:100%}
h1::first-letter,h2::first-letter,p::first-letter,label::first-letter,a::first-letter,button::first-letter{all:unset!important}
.fx::before{content:"\\200A";}
</style>
"""

@app.get("/favicon.ico")
def favicon_redirect():
    return RedirectResponse(url="/ui/favicon.png")

@app.get("/health")
def health():
    return {"status":"ok","privacy_strict":PRIVACY_STRICT}

@app.get("/", response_class=RedirectResponse)
def root():
    return RedirectResponse("/dashboard")

@app.get("/dashboard", response_class=HTMLResponse)
def dashboard():
    st = load_state()
    html = f"""<!doctype html><html lang='ru'><head><meta charset='utf-8'><title>Biotact Dashboard</title>
    {CSS_RESET}</head><body>
    <div class='wrap'>
      <p class='fx'><a class='fx' href='/rules'>Правила</a> · <a class='fx' href='/logs/view'>Журнал</a> · <a class='fx' href='/ui/'>UI</a></p>
      <div class='card'>
        <h2 class='fx'>Паника: {"ON" if is_active(st["panic"]["until"]) else "OFF"}</h2>
        <form method='post' action='/panic/set'>
          <button name='btn' value='15m' class='btn fx'>Паника 15м</button>
          <button name='btn' value='1h' class='btn fx'>Паника 1ч</button>
          <button name='btn' value='24h' class='btn fx'>Паника 24ч</button>
          <button formaction='/panic/clear' class='btn o fx' type='submit'>Снять панику</button>
        </form>
        <p class='fx'>До: {st["panic"]["until"] or "-"}</p>
      </div>
      <div class='card'>
        <h2 class='fx'>Фокус-режим: {"ON" if is_active(st["focus"]["until"]) else "OFF"}</h2>
        <form method='post' action='/focus/on'>
          <label class='fx'>Минуты <input type='number' name='minutes' value='60' min='1'></label>
          <label class='fx'>Разрешить домены (через запятую) <input type='text' name='domains' value='{", ".join(st["focus"]["domains"])}'></label>
          <button class='btn fx' type='submit'>Включить фокус</button>
          <button class='btn o fx' type='submit' formaction='/focus/off'>Выключить фокус</button>
        </form>
        <p class='fx'>До: {st["focus"]["until"] or "-"}</p>
      </div>
    </div></body></html>"""
    return HTMLResponse(content=html)

@app.post("/focus/on")
def focus_on(minutes: int = Form(60), domains: str = Form("")):
    st = load_state()
    until = datetime.utcnow() + timedelta(minutes=max(1, int(minutes)))
    st["focus"]["until"] = until.isoformat()
    st["focus"]["domains"] = [d.strip() for d in domains.split(",") if d.strip()]
    save_state(st); log_event("focus_on", "dashboard", "focus")
    notify(N8N_WEBHOOK_FOCUS, {"event":"focus_on","until":st["focus"]["until"],"domains":st["focus"]["domains"]})
    return RedirectResponse("/dashboard", status_code=303)

@app.post("/focus/off")
def focus_off():
    st = load_state(); st["focus"] = {"until": None, "domains": []}
    save_state(st); log_event("focus_off", "dashboard", "focus")
    notify(N8N_WEBHOOK_FOCUS, {"event":"focus_off"})
    return RedirectResponse("/dashboard", status_code=303)

@app.post("/panic/set")
def panic_set(btn: str = Form("15m")):
    mapping = {"15m":15, "1h":60, "24h":24*60}
    st = load_state()
    until = datetime.utcnow() + timedelta(minutes=mapping.get(btn,15))
    st["panic"]["until"] = until.isoformat()
    save_state(st); log_event("panic_on", "dashboard", "panic")
    notify(N8N_WEBHOOK_PANIC, {"event":"panic_on","until":st["panic"]["until"]})
    return RedirectResponse("/dashboard", status_code=303)

@app.post("/panic/clear")
def panic_clear():
    st = load_state(); st["panic"]["until"] = None
    save_state(st); log_event("panic_off", "dashboard", "panic")
    notify(N8N_WEBHOOK_PANIC, {"event":"panic_off"})
    return RedirectResponse("/dashboard", status_code=303)

@app.get("/rules", response_class=HTMLResponse)
def rules_page():
    st = load_state()
    allow = "\n".join(st["rules"]["allow"]); scope = "\n".join(st["rules"]["scope"]); warn = "\n".join(st["rules"]["warn"])
    html = f"""<!doctype html><html lang='ru'><head><meta charset='utf-8'><title>Biotact правила</title>
    {CSS_RESET}</head><body>
    <div class='wrap'>
      <p class='fx'><a class='fx' href='/dashboard'>Dashboard</a> · <a class='fx' href='/logs/view'>Журнал</a> · <a class='fx' href='/ui/'>UI</a></p>
      <h1 class='fx'>Biotact правила</h1>
      <form method='post' action='/rules/save'>
        <label class='fx'>Разрешённые домены</label><textarea name='allow'></textarea>
        <label class='fx'>Доменная область (scope)</label><textarea name='scope'></textarea>
        <label class='fx'>Только предупреждать (warn-only)</label><textarea name='warn'></textarea>
        <p><button class='btn fx' type='submit'>Сохранить</button></p>
      </form>
      <script>
        // Подставим текущее состояние в текстовые поля без «первой буквы» проблем
        document.currentScript.previousElementSibling.previousElementSibling.value = `{warn}`;
      </script>
      <script>
        const areas = document.querySelectorAll("textarea");
        areas[0].value = `{allow}`;
        areas[1].value = `{scope}`;
        areas[2].value = `{warn}`;
      </script>
    </div></body></html>"""
    return HTMLResponse(content=html)

@app.post("/rules/save")
def rules_save(allow: str = Form(""), scope: str = Form(""), warn: str = Form("")):
    st = load_state()
    st["rules"]["allow"] = [l.strip() for l in allow.splitlines() if l.strip()]
    st["rules"]["scope"] = [l.strip() for l in scope.splitlines() if l.strip()]
    st["rules"]["warn"]  = [l.strip() for l in warn.splitlines()  if l.strip()]
    save_state(st); log_event("rules_update", "rules", "state")
    return RedirectResponse("/rules", status_code=303)

@app.get("/logs/view", response_class=HTMLResponse)
def logs_view():
    try:
        con = db_connect(); cur = con.cursor()
        cur.execute("SELECT kind,source,target,level,created_at FROM events ORDER BY id DESC LIMIT 200")
        rows = cur.fetchall(); con.close()
    except Exception:
        db_init()
        con = db_connect(); cur = con.cursor()
        cur.execute("SELECT kind,source,target,level,created_at FROM events ORDER BY id DESC LIMIT 200")
        rows = cur.fetchall(); con.close()

    trs = "\n".join([f"<tr><td class='fx'>{k}</td><td class='fx'>{s}</td><td class='fx'>{t}</td><td class='fx'>{lvl}</td><td>{ts}</td></tr>" for (k,s,t,lvl,ts) in rows]) or "<tr><td colspan='5' class='fx' style='color:#666'>Пока нет событий.</td></tr>"
    html = f"""<!doctype html><html lang='ru'><head><meta charset='utf-8'><title>Журнал</title>
    {CSS_RESET}</head><body>
    <div class='wrap'>
      <p class='fx'><a class='fx' href='/dashboard'>Dashboard</a> · <a class='fx' href='/rules'>Правила</a> · <a class='fx' href='/ui/'>UI</a></p>
      <h1 class='fx'>Журнал событий</h1>
      <table style="width:100%;border-collapse:collapse">
        <thead><tr><th>Событие</th><th>Источник</th><th>Цель</th><th>Уровень</th><th>Время (UTC)</th></tr></thead>
        <tbody>{trs}</tbody>
      </table>
    </div></body></html>"""
    return HTMLResponse(content=html)

scheduler = BackgroundScheduler()
scheduler.add_job(cleanup_logs, "interval", hours=12, id="cleanup")
scheduler.start()
