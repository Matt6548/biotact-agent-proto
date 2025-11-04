import os, sys, subprocess, time, json, tempfile
from io import BytesIO
from pathlib import Path
from dotenv import load_dotenv, set_key
import streamlit as st
import pandas as pd

# РЅР°С€Рё РјРѕРґСѓР»Рё
from agent.llm_client import LLMClient
from agent.exporter import Exporter

load_dotenv()  # С‡РёС‚Р°РµРј .env

ROOT = Path(__file__).parent.resolve()
DEFAULT_PIPELINE = ROOT / "pipelines" / "example.yml"
OUTPUT_MD = ROOT / "samples" / "outputs" / "pipeline_markdown.md"

st.set_page_config(page_title="Agent Platform вЂ” Demo Web UI", layout="wide")
st.markdown("""
<style>
.stToolbar{position:sticky;top:0;z-index:999;background:#ffffffd9;padding:8px 0 6px;border-bottom:1px solid #eee;}
.stToolbar .btns{display:flex;gap:8px;align-items:center;}
</style>
""", unsafe_allow_html=True)

st.title("Agent Platform вЂ” Demo Web UI")

with st.sidebar:
    st.header("Run pipeline")
    st.text_input("YAML pipeline", str(DEFAULT_PIPELINE), key="pipepath")
    colA, colB = st.columns(2)
    gen_demo = colA.button("Generate demo")
    run_clicked = colB.button("Run")
    st.caption(f"Output в†’ {OUTPUT_MD}")

    st.divider()
    st.header("AI options")
    use_gpt = st.checkbox("Use GPT (append AI Add-on)", value=True)
    model = st.text_input("Model", os.getenv("OPENAI_MODEL", "gpt-4o-mini"))

    # РїРѕР»Рµ РґР»СЏ РІРІРѕРґР° Рё СЃРѕС…СЂР°РЅРµРЅРёСЏ РєР»СЋС‡Р° РїСЂСЏРјРѕ РІ UI
    st.subheader("OpenAI key")
    key_input = st.text_input("OPENAI_API_KEY", type="password", placeholder="sk-...", help="РЎРѕС…СЂР°РЅРёС‚СЃСЏ РІ .env Р»РѕРєР°Р»СЊРЅРѕ")
    if st.button("Save API key"):
        env_path = ROOT / ".env"
        if not env_path.exists():
            env_path.write_text("", encoding="utf-8")
        set_key(str(env_path), "OPENAI_API_KEY", key_input)
        os.environ["OPENAI_API_KEY"] = key_input
        st.success("API key СЃРѕС…СЂР°РЅС‘РЅ. РќР°Р¶РјРё Run.")

    have_key = bool(os.getenv("OPENAI_API_KEY"))
    st.write("API key:", "вњ… found" if have_key else "вќЊ not set")

    st.divider()
    export_docx = st.checkbox("Export DOCX after run", value=True)
    export_xlsx = st.checkbox("Export XLSX (plan table)", value=True)

def run_pipeline():
    OUTPUT_MD.parent.mkdir(parents=True, exist_ok=True)
    with st.spinner("Running pipelineвЂ¦"):
        result = subprocess.run([sys.executable, str(ROOT / "main.py")],
                                cwd=str(ROOT), capture_output=True, text=True)
    return result

def extract_plan_table(md_text: str):
    """РџСЂРѕР±СѓРµРј РІС‹С‚Р°С‰РёС‚СЊ markdown-С‚Р°Р±Р»РёС†Сѓ РїР»Р°РЅР° (Day|Channel|Theme|Goal) РІ DataFrame."""
    lines = md_text.splitlines()
    start = None
    for i, l in enumerate(lines):
        if "|" in l and ("Day" in l and "Channel" in l):
            start = i
            break
    if start is None:
        return None
    headers = [h.strip() for h in lines[start].split("|") if h.strip()]
    j = start + 1
    # РїСЂРѕРїСѓСЃРєР°РµРј Р»РёРЅРёСЋ-СЂР°Р·РґРµР»РёС‚РµР»СЊ |---|
    if j < len(lines) and set(lines[j].replace("|","").replace(" ","").replace("-","")) == set():
        j += 1
    rows = []
    for k in range(j, len(lines)):
        row = lines[k]
        if "|" not in row or not row.strip():
            break
        cells = [c.strip() for c in row.split("|") if c.strip() != ""]
        if len(cells) == len(headers):
            rows.append(cells)
        else:
            break
    if not rows:
        return None
    return pd.DataFrame(rows, columns=headers)

# РјР°Р»РµРЅСЊРєР°СЏ В«РїСЂРёР»РёРїР°СЋС‰Р°СЏВ» РїР°РЅРµР»СЊ СЃ РєРЅРѕРїРєР°РјРё СЃРєР°С‡РёРІР°РЅРёСЏ
st.markdown('<div class="stToolbar"><div class="btns">', unsafe_allow_html=True)
if OUTPUT_MD.exists():
    md_top = OUTPUT_MD.read_text(encoding="utf-8", errors="ignore")
    st.download_button("Download markdown", data=md_top.encode("utf-8"), file_name="pipeline_markdown.md")
st.markdown('</div></div>', unsafe_allow_html=True)

st.header("Content Plan")

if gen_demo:
    st.success("Demo inputs are ready. Press Run.")

if run_clicked:
    res = run_pipeline()
    if res.returncode != 0:
        st.error("РћС€РёР±РєР° РїСЂРё Р·Р°РїСѓСЃРєРµ main.py")
        st.code(res.stdout + "\n" + res.stderr)
    else:
        for _ in range(40):
            if OUTPUT_MD.exists() and OUTPUT_MD.stat().st_size > 0:
                break
            time.sleep(0.1)
        if not OUTPUT_MD.exists():
            st.warning("main.py Р·Р°РІРµСЂС€РёР»СЃСЏ, РЅРѕ С„Р°Р№Р» РЅРµ РЅР°Р№РґРµРЅ. РџСЂРѕРІРµСЂСЊ pipelines/example.yml.")
        else:
            st.success(f"Saved: {OUTPUT_MD}")

            # AI-РґРѕРіРµРЅРµСЂР°С†РёСЏ
            if use_gpt:
                md = OUTPUT_MD.read_text(encoding="utf-8", errors="ignore")
                llm = LLMClient(model=model)
                if not llm.available():
                    st.warning("OPENAI_API_KEY РЅРµ Р·Р°РґР°РЅ вЂ” РѕС„С„Р»Р°Р№РЅ СЂРµР¶РёРј, AI Add-on РїСЂРѕРїСѓС‰РµРЅ.")
                else:
                    prompt = f"""
РўС‹ вЂ” РјР°СЂРєРµС‚РѕР»РѕРі Р°РІС‚РѕРґРёР»РµСЂР°/Р°РІС‚РѕРёРјРїРѕСЂС‚Р°. РќР° РѕСЃРЅРѕРІРµ РєРѕРЅС‚РµРєСЃС‚Р° СЃС„РѕСЂРјРёСЂСѓР№:
1) РџР»Р°РЅ РїСѓР±Р»РёРєР°С†РёР№ РЅР° 7 РґРЅРµР№ (С‚Р°Р±Р»РёС†Р°: Р”РµРЅСЊ | Channel | Theme | Goal).
2) 5вЂ“7 РїРѕСЃС‚РѕРІ: Р—Р°РіРѕР»РѕРІРѕРє (60вЂ“80), РћСЃРЅРѕРІРЅРѕР№ С‚РµРєСЃС‚ (400вЂ“800), 8вЂ“15 С…СЌС€С‚РµРіРѕРІ.
3) ToR РґР»СЏ РІРёР·СѓР°Р»Р° Рє РєР°Р¶РґРѕРјСѓ РїРѕСЃС‚Сѓ (РєСЂР°С‚РєРѕ, РїРѕ РїСѓРЅРєС‚Р°Рј).
РљРѕРЅС‚РµРєСЃС‚ (Markdown):
---
{md}
---
Р’С‹РІРѕРґРё СЃС‚СЂРѕРіРѕ РІ Markdown СЃ Р·Р°РіРѕР»РѕРІРєРѕРј: "# AI Add-on".
"""
                    try:
                        with st.spinner("Generating AI Add-onвЂ¦"):
                            out = llm.complete(prompt, temperature=0.6)
                        if out:
                            new_md = md.rstrip() + "\n\n---\n\n" + out.strip() + "\n"
                            OUTPUT_MD.write_text(new_md, encoding="utf-8")
                            st.success("AI Add-on appended.")
                        else:
                            st.warning("LLM РІРµСЂРЅСѓР» РїСѓСЃС‚РѕР№ РѕС‚РІРµС‚.")
                    except Exception as e:
                        st.error(f"LLM error: {e}")

            # СЌРєСЃРїРѕСЂС‚
            md_final = OUTPUT_MD.read_text(encoding="utf-8", errors="ignore")
            if export_docx:
                try:
                    with tempfile.TemporaryDirectory() as td:
                        docx_path = Path(td) / "marketing_pack.docx"
                        Exporter.to_docx(md_final, str(docx_path))
                        st.download_button("Download DOCX", data=docx_path.read_bytes(), file_name="marketing_pack.docx")
                        st.toast("DOCX ready", icon="вњ…")
                except Exception as e:
                    st.warning(f"DOCX export error: {e}")

            if export_xlsx:
                try:
                    df = extract_plan_table(md_final)
                    if df is not None:
                        bio = BytesIO()
                        with pd.ExcelWriter(bio, engine="openpyxl") as w:
                            df.to_excel(w, index=False, sheet_name="Plan")
                        bio.seek(0)
                        st.download_button("Download XLSX plan", data=bio.getvalue(), file_name="content_plan.xlsx")
                    else:
                        st.info("РќРµ РЅР°С€С‘Р» С‚Р°Р±Р»РёС†Сѓ РїР»Р°РЅР° РІ AI Add-on вЂ” XLSX РїСЂРѕРїСѓС‰РµРЅ.")
                except Exception as e:
                    st.warning(f"XLSX export error: {e}")

# РїРѕРєР°Р·Р°С‚СЊ Markdown
if OUTPUT_MD.exists():
    md_show = OUTPUT_MD.read_text(encoding="utf-8", errors="ignore")
    st.markdown(md_show)
else:
    st.info("РџРѕРєР° РЅРµС‚ СЂРµР·СѓР»СЊС‚Р°С‚Р°. РќР°Р¶РјРё Run СЃР»РµРІР°.")
