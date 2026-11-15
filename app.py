import html
import os
import threading

import streamlit as st
from dotenv import load_dotenv

import languages as langs
import pipeline
import ui_adapter

load_dotenv()
st.set_page_config(page_title="OPT Check", page_icon="🎓")

# ---------- Settings (edit these) ----------
NAVY, BLUE, GRAY = "#1B2F5B", "#0B1FA8", "#5B6B8C"
SOFT, LINE = "#EEF1F8", "#C9D3EA"
CONFIG = pipeline.load_config()
# Language names come from languages.yaml: English, العربية, 中文, 繁體中文, Русский
LANGUAGES = list(langs.language_choices().values())
# Schools, offices and office links come from sources.yaml (one source of truth).
SCHOOLS = {s["name"]: {"key": key, "office": s["office"], "url": s["office_url"]}
           for key, s in CONFIG["schools"].items()}
# pill kind -> (background, text color). Same colors as before, plus Supported / Contradicted.
PILLS = {
    "supported": ("#E3F3EA", "#1A7F4B"),
    "contradicted": ("#FBE4E2", "#B3261E"),
    "unclear": (SOFT, GRAY),
    "in_effect": ("#E3F3EA", "#1A7F4B"),
    "proposed": ("#FDF1D6", "#9A6700"),
    "blocked": ("#FBE4E2", "#B3261E"),
}


def _load_key():
    """On a deployment the Gemini key lives in Streamlit secrets instead of .env."""
    try:
        if not os.environ.get("GEMINI_API_KEY") and "GEMINI_API_KEY" in st.secrets:
            os.environ["GEMINI_API_KEY"] = st.secrets["GEMINI_API_KEY"]
    except Exception:
        pass  # no secrets file: the key comes from the environment or .env


@st.cache_resource
def _warm():
    """Download the official pages in the background so the first check isn't slow."""
    threading.Thread(target=pipeline.warm_pages, daemon=True).start()
    return True


_load_key()
_warm()

# ---------- Styling ----------
st.markdown(f"""<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans:wght@400;600;700&family=Noto+Sans+Arabic:wght@400;600;700&family=Noto+Sans+SC:wght@400;600;700&family=Noto+Sans+TC:wght@400;600;700&display=swap');
html, body, [class*="css"] {{ font-family:'Noto Sans','Noto Sans Arabic','Noto Sans SC','Noto Sans TC',sans-serif; color:{NAVY}; }}
.block-container {{ max-width:480px; padding-top:1.5rem; }}
#MainMenu, footer, header {{ visibility:hidden; }}
.small {{ font-size:.75rem; color:{GRAY}; }}
.title {{ font-size:2rem; font-weight:700; line-height:1.15; margin:.2rem 0; }}
.label {{ font-weight:600; margin:1.2rem 0 .5rem; }}
.box {{ background:{SOFT}; border-radius:12px; padding:12px 16px; margin-top:.8rem; }}
.pill {{ display:inline-block; padding:4px 12px; border-radius:999px; font-weight:600; margin:0 6px 6px 0; }}
.card {{ border:1px solid {LINE}; border-radius:12px; padding:12px 16px; margin-bottom:10px; }}
.card a {{ color:{BLUE}; text-decoration:none; float:right; }}
.quote {{ direction:ltr; text-align:left; border-left:3px solid {LINE}; padding-left:10px; margin:8px 0 4px; font-size:.85rem; }}
.tr {{ font-size:.85rem; color:{GRAY}; }}
div.stButton > button {{ border-radius:10px; border:0; background:{SOFT}; color:{NAVY}; width:100%; }}
button[data-testid="stBaseButton-primary"] {{ background:{BLUE}; color:white; font-weight:600; }}
</style>""", unsafe_allow_html=True)

# ---------- State ----------
st.session_state.setdefault("screen", "home")
st.session_state.setdefault("language", "English")
st.session_state.setdefault("school", "Michigan State University")


def lang_code():
    return langs.resolve_language(st.session_state["language"])


def t(key, **kw):
    """An interface string in the chosen language (see languages.yaml)."""
    s = langs.ui_text(lang_code(), key)
    return s.format(**kw) if kw else s


def esc(text):
    return html.escape(text or "")


def direction_css():
    if langs.is_rtl(lang_code()):  # right-to-left layout for Arabic
        st.markdown("<style>.block-container{direction:rtl;text-align:right}</style>",
                    unsafe_allow_html=True)


def beta_notice():
    if not langs.is_reviewed(lang_code()):
        st.markdown(f'<div class="box small">{esc(t("beta"))}</div>', unsafe_allow_html=True)


def go(screen, claim=None):
    st.session_state["screen"] = screen
    if claim:
        st.session_state["claim"] = claim
    st.rerun()


def disclaimer():
    office = SCHOOLS[st.session_state["school"]]["office"]
    return f'<p class="small" style="margin-top:1.5rem">{esc(t("disclaimer", office=office))}</p>'


def pill_html(p):
    bg, color = PILLS[p["kind"]]
    return f'<span class="pill" style="background:{bg};color:{color}">{esc(p["text"])}</span>'


# ---------- Backend ----------
def check_claim(claim, language, school):
    """Run a real check. `language` and `school` are the names shown in the pickers."""
    key = SCHOOLS[school]["key"]
    result = pipeline.check_claim(claim, key, {}, language)
    return ui_adapter.to_ui(result, key, CONFIG)


# ---------- Screens ----------
def home():
    col1, col2 = st.columns([3, 2])
    col1.markdown("**OPT /**")
    st.session_state["language"] = col2.selectbox(
        "Language", LANGUAGES, label_visibility="collapsed",
        index=LANGUAGES.index(st.session_state["language"]))
    direction_css()
    schools = list(SCHOOLS)
    st.session_state["school"] = st.selectbox(
        t("school_label"), schools, index=schools.index(st.session_state["school"]))
    beta_notice()

    st.markdown(f'<p class="small">{esc(t("home_eyebrow"))}</p><div class="title">{esc(t("home_title"))}</div>'
                f'<span style="color:{GRAY}">{esc(t("home_subtitle"))}</span>'
                f'<div class="label">{esc(t("starters_label"))}</div>', unsafe_allow_html=True)
    for i, rumor in enumerate(langs.starters(lang_code())):
        if st.button(f"“{rumor}”", key=f"rumor{i}"):
            go("result", rumor)

    st.markdown(f'<div class="label">{esc(t("paste_label"))}</div>', unsafe_allow_html=True)
    text = st.text_area("claim", placeholder=t("placeholder"), label_visibility="collapsed",
                        max_chars=pipeline.MAX_CLAIM_CHARS)
    st.markdown(f'<p class="small">🔒 {esc(t("privacy_note"))}</p>', unsafe_allow_html=True)
    if st.button(t("check_button"), type="primary") and text.strip():
        go("result", text.strip())

    st.markdown(f'<p class="small">{esc(t("sources_note"))}</p>'
                f'<div class="box"><b>{esc(t("box_title"))}</b><br>'
                f'<span style="color:{GRAY}">{esc(t("box_body"))}</span></div>' + disclaimer(),
                unsafe_allow_html=True)


def result():
    direction_css()
    if st.button(t("new_check")):
        go("home")
    school = st.session_state["school"]
    claim = st.session_state["claim"]
    try:
        with st.spinner(t("progress")):
            res = check_claim(claim, st.session_state["language"], school)
    except pipeline.CheckError as e:  # empty claim, usage limit, service problem...
        st.error(str(e))
        st.markdown(disclaimer(), unsafe_allow_html=True)
        return
    beta_notice()

    parts = [f'<div class="box"><p class="small">{esc(t("your_question"))}</p>{esc(claim)}</div>']
    if res["claim_in_english"] and lang_code() != "en":
        parts.append(f'<p class="small">{esc(t("we_checked"))}: “{esc(res["claim_in_english"])}”</p>')
    parts.append(f'<p>{"".join(pill_html(p) for p in res["pills"])}</p>'
                 f'<div class="title">{esc(res["headline"])}</div>')
    if res["explanation"] and res["explanation"] != res["headline"]:
        parts.append(f'<p style="color:{GRAY}">{esc(res["explanation"])}</p>')
    for key, items in (("applies_to", res["applies_to"]), ("depends_on", res["exceptions"])):
        if items:
            lis = "".join(f"<li>{esc(i)}</li>" for i in items)
            parts.append(f'<p><b>{esc(t(key))}</b></p><ul>{lis}</ul>')
    if res["clarifying_question"]:
        parts.append(f'<div class="box">{esc(res["clarifying_question"])}</div>')
    if res["next_step"]:
        parts.append(f'<div class="box"><b>{esc(t("next_step"))}:</b> {esc(res["next_step"])}</div>')
    if res["sources"]:
        parts.append(f'<div class="label">{esc(t("sources"))} <span class="small" style="float:right">'
                     f'{esc(t("sources_found", n=len(res["sources"])))}</span></div>')
    st.markdown("".join(parts), unsafe_allow_html=True)

    for s in res["sources"]:
        when = esc(s["date_text"]) if not s["date"] else f'{esc(t("last_updated"))}: {esc(s["date"])}'
        card = (f'<div class="card"><a href="{html.escape(s["url"], quote=True)}" target="_blank">{esc(t("view"))}</a>'
                f'<p class="small">{esc(s["category"]).upper()}</p>'
                f'<b>{esc(s["title"])}</b><br>'
                f'<span style="color:{BLUE}">{esc(s["domain"])}</span><br>'
                f'<span class="small">{when}</span>'
                f'<div class="quote">{esc(s["quote"])}</div>')
        if s["quote_translation"]:
            card += f'<div class="tr">{esc(s["quote_translation"])}</div>'
        st.markdown(card + "</div>", unsafe_allow_html=True)

    if res["show_ask_office"]:
        if not res["out_of_scope"]:
            st.markdown(f'<div class="box"><b>{esc(t("unclear_title"))}</b><br>'
                        f'<span style="color:{GRAY}">{esc(t("unclear_body"))}</span></div>',
                        unsafe_allow_html=True)
        if res["question_for_office"]:  # always English: it is sent to the school's office
            st.markdown(f'**{t("office_question")}**')
            st.code(res["question_for_office"], language=None)
        st.link_button(t("ask_office_button"), res["office"]["url"], use_container_width=True)
    else:
        legend = ui_adapter.legend(lang_code())
        shown = legend["verdicts"] + (legend["rule_statuses"] if len(res["pills"]) > 1 else [])
        note = f'<p class="small">{esc(t("legend_note"))}</p>' if len(res["pills"]) > 1 else ""
        st.markdown(f'<div class="label">{esc(t("legend_title"))}</div>'
                    f'{"".join(pill_html(p) for p in shown)}{note}', unsafe_allow_html=True)
    st.markdown(disclaimer(), unsafe_allow_html=True)


# ---------- Run ----------
home() if st.session_state["screen"] == "home" else result()
