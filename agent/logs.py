from __future__ import annotations
import sqlite3, json, time
from pathlib import Path
from typing import Any, Dict, List
from urllib.parse import urlparse
from collections import Counter, defaultdict
import datetime as dt

DB = Path("logs.db")

def _ensure():
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("""
      CREATE TABLE IF NOT EXISTS events(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts REAL,
        source TEXT,
        target TEXT,
        device TEXT,
        decision TEXT,
        actions TEXT
      )
    """)
    conn.commit(); conn.close()

def add_event(event: Dict[str,Any], decision: Dict[str,Any], actions: List[Dict[str,Any]]):
    _ensure()
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute(
        "INSERT INTO events(ts,source,target,device,decision,actions) VALUES(?,?,?,?,?,?)",
        (time.time(), event.get("source"), event.get("target"), event.get("device"),
         json.dumps(decision, ensure_ascii=False), json.dumps(actions, ensure_ascii=False))
    )
    conn.commit(); conn.close()

def list_events(limit: int = 200) -> List[Dict[str,Any]]:
    _ensure()
    conn = sqlite3.connect(DB); conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM events ORDER BY id DESC LIMIT ?", (limit,))
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return rows

def _domain(url: str) -> str:
    try:
        netloc = urlparse(url or "").netloc.lower()
        return netloc or (url or "")
    except Exception:
        return url or ""

def stats(days: int = 7) -> Dict[str,Any]:
    """Возвращает агрегированную статистику за N дней (по умолчанию 7)."""
    _ensure()
    since = time.time() - days*86400
    conn = sqlite3.connect(DB); conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM events WHERE ts >= ? ORDER BY ts ASC", (since,))
    rows = [dict(r) for r in c.fetchall()]
    conn.close()

    by_day = Counter()
    by_hour = Counter()
    by_source = Counter()
    by_device = Counter()
    by_domain = Counter()
    by_reason = Counter()

    for r in rows:
        t = dt.datetime.fromtimestamp(r["ts"])
        by_day[t.strftime("%Y-%m-%d")] += 1
        by_hour[t.strftime("%H:00")] += 1
        by_source[(r.get("source") or "unknown")] += 1
        by_device[(r.get("device") or "unknown")] += 1
        by_domain[_domain(r.get("target"))] += 1

        try:
            dec = json.loads(r.get("decision") or "{}")
            reasons = dec.get("reason") or []
            for x in reasons: by_reason[x] += 1
        except Exception:
            pass

    def top(counter: Counter, n=10):
        return [{"name": k, "value": v} for k, v in counter.most_common(n)]

    return {
        "range_days": days,
        "totals": {
            "events": len(rows),
            "sources": len(by_source),
            "devices": len(by_device),
            "domains": len(by_domain),
        },
        "by_day": [{"name": k, "value": v} for k, v in sorted(by_day.items())],
        "by_hour": [{"name": k, "value": v} for k, v in sorted(by_hour.items())],
        "top_domains": top(by_domain, 10),
        "top_sources": top(by_source, 5),
        "top_devices": top(by_device, 5),
        "reasons": top(by_reason, 10),
    }