from __future__ import annotations
import os, requests, json
from typing import Dict, Any, Optional
from dotenv import load_dotenv
load_dotenv()

def http_request(method: str, url: str, headers: Optional[Dict[str,str]]=None, json_body: Optional[Dict[str,Any]]=None, timeout: int=20) -> Dict[str,Any]:
    r = requests.request(method.upper(), url, headers=headers or {}, json=json_body, timeout=timeout)
    try: body = r.json()
    except Exception: body = {"raw": r.text}
    return {"status": r.status_code, "body": body}

def telegram_send_message(chat_id: str, text: str) -> Dict[str,Any]:
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token: return {"error":"TELEGRAM_BOT_TOKEN not configured"}
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    r = requests.post(url, json={"chat_id": chat_id, "text": text, "parse_mode":"HTML"}, timeout=20)
    try: return r.json()
    except Exception: return {"status": r.status_code, "raw": r.text}