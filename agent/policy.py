from __future__ import annotations
from typing import Dict, Any, List
from pathlib import Path
import json, datetime as dt

RULES_PATH = Path("rules.json")
DEFAULT_RULES = {"blocked_services": ["telegram"], "time_windows": []}

def load_rules() -> Dict[str,Any]:
    if not RULES_PATH.exists():
        RULES_PATH.write_text(json.dumps(DEFAULT_RULES, ensure_ascii=False, indent=2), encoding="utf-8")
        return DEFAULT_RULES
    try:
        return json.loads(RULES_PATH.read_text(encoding="utf-8"))
    except Exception:
        return DEFAULT_RULES

def save_rules(rules: Dict[str,Any]) -> None:
    RULES_PATH.write_text(json.dumps(rules, ensure_ascii=False, indent=2), encoding="utf-8")

def in_quiet_window(now: dt.time, windows: List[Dict[str,str]]) -> bool:
    for w in windows or []:
        try:
            t1 = dt.datetime.strptime(w["start"], "%H:%M").time()
            t2 = dt.datetime.strptime(w["end"], "%H:%M").time()
        except Exception:
            continue
        if t1 <= t2:
            if t1 <= now <= t2: return True
        else:
            if now >= t1 or now <= t2: return True
    return False

def check_event(event: Dict[str,Any]) -> Dict[str,Any]:
    rules = load_rules()
    target = (event.get("target") or "").lower()
    blocked = any(key in target for key in rules.get("blocked_services", []))
    quiet = in_quiet_window(dt.datetime.now().time(), rules.get("time_windows", []))
    violation = blocked or quiet
    reason = []
    if blocked: reason.append("blocked_service")
    if quiet:   reason.append("quiet_window")
    return {"violation": violation, "reason": reason, "rules": rules}