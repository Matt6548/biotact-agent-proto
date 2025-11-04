# --- real run_pipeline ---
from pathlib import Path
import json, yaml, re

def run_pipeline(pipeline: str) -> None:
    """
    РњРёРЅРёРјР°Р»СЊРЅР°СЏ СЂРµР°Р»СЊРЅР°СЏ СЃР±РѕСЂРєР° РѕС‚С‡С‘С‚Р°:
    - С‡РёС‚Р°РµС‚ inputs (brief/channels) Рё Р»РѕРєР°Р»СЊРЅС‹Р№ РєРѕСЂРїСѓСЃ,
    - С„РѕСЂРјРёСЂСѓРµС‚ markdown Рё СЃРѕС…СЂР°РЅСЏРµС‚ РІ samples/outputs/pipeline_markdown.md
    """
    out = Path("samples/outputs")
    out.mkdir(parents=True, exist_ok=True)
    md_path = out / "pipeline_markdown.md"

    # С‡РёС‚Р°РµРј pipeline (РµСЃР»Рё РЅСѓР¶РЅРѕ)
    try:
        _cfg = yaml.safe_load(Path(pipeline).read_text(encoding="utf-8"))
    except Exception:
        _cfg = {}

    # РёСЃС‚РѕС‡РЅРёРєРё
    brief_p = Path("samples/inputs/project_brief.md")
    channels_p = Path("samples/inputs/channels.json")
    brand_p = Path("data/corpus/brand_story.txt")
    kb_p = Path("data/corpus/knowledge_base.txt")

    brief = brief_p.read_text(encoding="utf-8") if brief_p.exists() else ""
    channels_raw = channels_p.read_text(encoding="utf-8") if channels_p.exists() else ""
    brand = brand_p.read_text(encoding="utf-8") if brand_p.exists() else ""
    kb = kb_p.read_text(encoding="utf-8") if kb_p.exists() else ""

    try:
        channels = json.loads(channels_raw) if channels_raw else {}
    except Exception:
        channels = {}

    # Р·Р°РіРѕР»РѕРІРѕРє РёР· brief (РїРµСЂРІР°СЏ СЃС‚СЂРѕРєР° '# ...') РёР»Рё РґРµС„РѕР»С‚
    m = re.search(r"^#\s*(.+)$", brief, re.M)
    title = m.group(1) if m else "Content Plan"

    # СЃРµРєС†РёРё
    def bullet_channels(obj):
        if isinstance(obj, list):
            return "\n".join(f"- {c.get('name', c)}" if isinstance(c, dict) else f"- {c}" for c in obj)
        if isinstance(obj, dict) and "channels" in obj:
            return "\n".join(f"- {c.get('name', c)}" if isinstance(c, dict) else f"- {c}" for c in obj["channels"])
        return "(no channels)"

    md_lines = [
        f"# {title}",
        "",
        "## Auto-assembled from local corpus",
        "",
        "### Brief (source)",
        f"```\n{brief.strip()}\n```" if brief else "(no brief)",
        "",
        "### Channels",
        bullet_channels(channels),
        "",
        "### Brand Story",
        brand.strip()[:2000] if brand else "(no brand story)",
        "",
        "### Knowledge Highlights",
        "\n".join(f"- {line}" for line in kb.splitlines()[:12]) if kb else "(no knowledge base)",
        "",
        "_Sources:_",
        f"- {brief_p.name if brief else 'вЂ”'}",
        f"- {channels_p.name if channels_raw else 'вЂ”'}",
        f"- {brand_p.name if brand else 'вЂ”'}",
        f"- {kb_p.name if kb else 'вЂ”'}",
        ""
    ]

    md_path.write_text("\n".join(md_lines), encoding="utf-8")
    print(f"Saved: {md_path}")
# --- end shim ---

