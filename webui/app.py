from pathlib import Path
import streamlit as st

# наш пайплайн-раннер (у тебя уже есть shim в agent/core.py)
from agent.core import run_pipeline

OUTPUT_MD = Path("samples/outputs/pipeline_markdown.md")

st.set_page_config(page_title="Agent Platform", layout="wide")
st.title("Agent Platform — Demo Web UI")

with st.sidebar:
    st.header("Run pipeline")
    pipeline_path = st.text_input("YAML pipeline", "pipelines/example.yml")
    run_btn = st.button("Run", type="primary")
    st.caption("Output → samples/outputs/pipeline_markdown.md")

if run_btn:
    with st.spinner("Running pipeline..."):
        try:
            run_pipeline(pipeline_path)
            st.success(f"Saved: {OUTPUT_MD}")
        except Exception as e:
            st.error("Pipeline failed")
            st.exception(e)

st.divider()
st.subheader("Output preview")

if OUTPUT_MD.exists():
    txt = OUTPUT_MD.read_text(encoding="utf-8")
    st.download_button("Download markdown", data=txt, file_name="pipeline_output.md")
    st.markdown(txt)
else:
    st.info("No output yet. Click **Run** in the sidebar.")
import json

# ...
# вместо: json.loads(INPUTS["channels"].read_text(encoding="utf-8"))
raw = INPUTS["channels"].read_text(encoding="utf-8-sig", errors="ignore")
# на случай, если попадётся \ufeff внутри:
raw = raw.lstrip("\ufeff")
data = json.loads(raw)
cnt = len(data) if isinstance(data, list) else len(data.get("channels", []))
st.write(f"Channels loaded: {cnt}")
