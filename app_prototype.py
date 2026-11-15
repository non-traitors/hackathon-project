"""Standalone Streamlit UI wired to the backend. Run: streamlit run app_prototype.py

Every visible string comes from languages.yaml, and every answer goes through
ui_adapter.to_ui, so this file is also the reference for wiring any other frontend.
"""
import html
import os
import threading

import streamlit as st
from dotenv import load_dotenv

import languages as langs
import pipeline
import ui_adapter

load_dotenv()
st.set_page_config(page_title="Is This Still True?", page_icon="✅", layout="centered")


def _load_secrets() -> None:
    """On a deployment the key lives in Streamlit secrets instead of .env."""
    try:
        if not os.environ.get("GEMINI_API_KEY") and "GEMINI_API_KEY" in st.secrets:
            os.environ["GEMINI_API_KEY"] = st.secrets["GEMINI_API_KEY"]
    except Exception:
        pass  # no secrets file: the key comes from the environment or .env


@st.cache_resource
def _warm_pages() -> bool:
    """Download the official pages in the background so the first check isn't slow."""
    threading.Thread(target=pipeline.warm_pages, daemon=True).start()
    return True


_load_secrets()
_warm_pages()

PILL_COLORS = {  # kind -> (background, text)
    "supported": ("#E3F3EA", "#1A7F4B"),
    "contradicted": ("#FBE4E2", "#B3261E"),
    "unclear": ("#EEF1F8", "#5B6B8C"),
    "in_effect": ("#E3F3EA", "#1A7F4B"),
    "proposed": ("#FDF1D6", "#9A6700"),
    "blocked": ("#FBE4E2", "#B3261E"),
}

st.markdown(
    """
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans:wght@400;600;700&family=Noto+Sans+Arabic:wght@400;600;700&family=Noto+Sans+SC:wght@400;600;700&family=Noto+Sans+TC:wght@400;600;700&display=swap');
html, body, [class*="css"] {font-family:'Noto Sans','Noto Sans Arabic','Noto Sans SC','Noto Sans TC',sans-serif;}
.pill {display:inline-block; padding:6px 14px; border-radius:999px; font-weight:600; margin:0 8px 8px 0;}
.card {border:1px solid #C9D3EA; border-radius:12px; padding:12px 16px; margin-bottom:10px;}
.muted {opacity:.7; font-size:.85rem;}
.quote {direction:ltr; text-align:left; border-left:3px solid #C9D3EA; padding-left:10px; margin:6px 0;}
.headline {font-size:1.5rem; font-weight:700; line-height:1.25; margin:.3rem 0 .6rem;}
</style>
""",
    unsafe_allow_html=True,
)

st.session_state.setdefault("lang", "en")
st.session_state.setdefault("claim", "")
choices = langs.language_choices()
code = st.session_state["lang"]


def t(key: str) -> str:
    return langs.ui_text(code, key)


config = pipeline.load_config()
school_names = pipeline.schools(config)

top = st.columns([3, 2])
top[0].title(t("app_title"))
code = top[1].selectbox(
    t("language_label"), list(choices), format_func=choices.get, index=list(choices).index(code), key="lang"
)
if not langs.is_reviewed(code):
    st.info(t("beta"))
st.caption(t("tagline"))

st.write(f"**{t('starters_label')}**")
for i, claim_text in enumerate(langs.starters(code)):
    if st.button(claim_text, key=f"starter{i}", use_container_width=True):
        st.session_state["claim"] = claim_text

st.markdown(f"**{t('paste_label')}**")
claim = st.text_area(
    "claim", key="claim", height=100, max_chars=pipeline.MAX_CLAIM_CHARS,
    placeholder=t("placeholder"), label_visibility="collapsed",
)
st.caption(f"🔒 {t('privacy_note')}")

school_key = st.selectbox(t("school_label"), list(school_names), format_func=school_names.get)

with st.expander("Your situation (optional, makes the answer more accurate)"):
    k1, k2 = st.columns(2)
    visa = k1.selectbox("Visa status", ["", "F-1", "J-1", "F-2 / J-2 (dependent)"])
    degree = k2.selectbox("Degree level", ["", "Undergraduate", "Master's", "PhD"])
    k3, k4 = st.columns(2)
    stem = k3.selectbox("STEM-designated degree?", ["", "Yes", "No", "Not sure"])
    timing = k4.selectbox("When?", ["", "During the semester", "Break / vacation", "After graduation"])
    assistantship = st.checkbox("I have an RA / TA assistantship")

if st.button(t("check_button"), type="primary", use_container_width=True):
    context = {
        "visa status": visa, "degree level": degree, "STEM-designated degree": stem,
        "timing": timing, "assistantship": "yes" if assistantship else "",
    }
    try:
        with st.status(t("progress"), expanded=False) as status:
            result = pipeline.check_claim(claim, school_key, context, code)
            status.update(label="✓", state="complete")
    except pipeline.CheckError as e:
        st.error(str(e))
        st.stop()

    ui = ui_adapter.to_ui(result, school_key, config)
    direction = "rtl" if ui["rtl"] else "ltr"

    if ui["claim_in_english"]:
        st.caption(f"{t('we_checked')}: “{ui['claim_in_english']}”")
    pills = "".join(
        f'<span class="pill" style="background:{PILL_COLORS[p["kind"]][0]};color:{PILL_COLORS[p["kind"]][1]}">'
        f'{html.escape(p["text"])}</span>'
        for p in ui["pills"]
    )
    body = [f'<div class="headline">{html.escape(ui["headline"])}</div>']
    if ui["explanation"] and ui["explanation"] != ui["headline"]:
        body.append(f"<p>{html.escape(ui['explanation'])}</p>")
    for label_key, items in (("applies_to", ui["applies_to"]), ("depends_on", ui["exceptions"])):
        if items:
            lis = "".join(f"<li>{html.escape(i)}</li>" for i in items)
            body.append(f"<p><b>{html.escape(t(label_key))}</b></p><ul>{lis}</ul>")
    st.markdown(f'<div dir="{direction}">{pills}{"".join(body)}</div>', unsafe_allow_html=True)

    if ui["clarifying_question"]:
        st.info(ui["clarifying_question"])
    if ui["next_step"]:
        st.warning(f"**{t('next_step')}:** {ui['next_step']}")
    if ui["show_ask_office"] and not ui["out_of_scope"]:
        st.markdown(f"**{t('unclear_title')}** {t('unclear_body')}")
    if ui["question_for_office"]:
        st.markdown(f"**{t('office_question')}**")
        st.code(ui["question_for_office"], language=None)
    if ui["show_ask_office"]:
        st.link_button(ui["office"]["name"], ui["office"]["url"], use_container_width=True)

    if ui["sources"]:
        st.subheader(t("sources"))
        for s in ui["sources"]:
            card = (
                f'<div class="card"><a href="{html.escape(s["url"], quote=True)}" target="_blank">{html.escape(s["title"])}</a>'
                f'<div class="muted">{html.escape(s["domain"])} · {html.escape(s["category"])} · {html.escape(s["date_text"])}</div>'
                f'<div class="quote">{html.escape(s["quote"])}</div>'
            )
            if s["quote_translation"]:
                card += f'<div dir="{direction}" class="muted">{html.escape(s["quote_translation"])}</div>'
            st.markdown(card + "</div>", unsafe_allow_html=True)

    st.caption(f"{result.checked_at}" + (" · cached" if ui["cached"] else ""))
    st.caption(ui["disclaimer"])
