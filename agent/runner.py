from __future__ import annotations
from typing import Dict, Any, List
import subprocess, sys
from agent.actions import http_request, telegram_send_message

def run_pipeline_yaml(pipeline_path: str="pipelines/example.yml") -> Dict[str,Any]:
    r = subprocess.run([sys.executable, "main.py"], capture_output=True, text=True)
    return {"ok": r.returncode == 0, "stdout": r.stdout, "stderr": r.stderr}

def run_steps(steps: List[Dict[str,Any]]) -> List[Dict[str,Any]]:
    out = []
    for s in steps:
        a = s.get("action")
        if a == "run_biotact":
            out.append({"action": a, "result": run_pipeline_yaml(s.get("pipeline","pipelines/example.yml"))})
        elif a == "http":
            out.append({"action": a, "result": http_request(s.get("method","GET"), s["url"], s.get("headers"), s.get("json"))})
        elif a == "telegram":
            out.append({"action": a, "result": telegram_send_message(s["chat_id"], s["text"])})
        else:
            out.append({"action": a, "error": "unknown action"})
    return out