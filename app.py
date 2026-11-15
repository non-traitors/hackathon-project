import html
import os
import threading

import streamlit as st
from dotenv import load_dotenv

import backend
import languages as langs
import pipeline
import speech
import ui_adapter

load_dotenv()
st.set_page_config(page_title="OPT Check", page_icon="🎓")

# ---------- Settings (edit these) ----------
NAVY, BLUE, GRAY = "#1B2F5B", "#0B1FA8", "#5B6B8C"
SOFT, LINE = "#EEF1F8", "#C9D3EA"
MARK = "#FFF1A8"  # highlighter: marks the sentence copied from the official page
CONFIG = pipeline.load_config()
# Language names come from languages.yaml: English, العربية, 中文, 繁體中文, Русский
LANGUAGES = list(langs.language_choices().values())
# Schools, offices and office links come from sources.yaml (one source of truth).
SCHOOLS = {s["name"]: {"key": key, "office": s["office"], "url": s["office_url"]}
           for key, s in CONFIG["schools"].items()}
# pill kind -> (background, text color)
PILLS = {
    "supported": ("#E3F3EA", "#1A7F4B"),
    "contradicted": ("#FBE4E2", "#B3261E"),
    "unclear": (SOFT, GRAY),
    "in_effect": ("#E3F3EA", "#1A7F4B"),
    "proposed": ("#FDF1D6", "#9A6700"),
    "blocked": ("#FBE4E2", "#B3261E"),
}
# USE_AGENT=1 switches from the single-pass check to the agent (agent.py): it shows
# its steps while it works and answers every claim in a pasted message.
USE_AGENT = os.environ.get("USE_AGENT") == "1"
MAX_CHARS = backend.agent.MAX_TEXT_CHARS if USE_AGENT else pipeline.MAX_CLAIM_CHARS


def _load_key():
    """On a deployment the keys live in Streamlit secrets instead of .env."""
    for name in ("GEMINI_API_KEY", "ELEVENLABS_API_KEY"):
        try:
            if not os.environ.get(name) and name in st.secrets:
                os.environ[name] = st.secrets[name]
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
SANS = "'Noto Sans','Noto Sans Arabic','Noto Sans SC','Noto Sans TC',sans-serif"
SERIF = "'Noto Serif','Noto Sans Arabic','Noto Sans SC','Noto Sans TC',serif"
st.markdown(f"""<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans:wght@400;600;700&family=Noto+Serif:wght@400;600&family=Noto+Sans+Arabic:wght@400;600;700&family=Noto+Sans+SC:wght@400;600;700&family=Noto+Sans+TC:wght@400;600;700&display=swap');
html, body, [class*="css"] {{ font-family:{SANS}; color:{NAVY}; }}
.block-container {{ max-width:480px; padding-top:1.5rem; }}
#MainMenu, footer, header {{ visibility:hidden; }}
.small {{ font-size:.8rem; color:{GRAY}; }}
.title {{ font-size:2rem; font-weight:700; line-height:1.15; margin:.2rem 0; }}
.answer {{ font-family:{SERIF}; font-size:1.7rem; font-weight:600; line-height:1.25; margin:.4rem 0 .6rem; }}
.asked {{ color:{GRAY}; font-size:.9rem; margin-bottom:.6rem; }}
.label {{ font-weight:600; margin:1.2rem 0 .5rem; }}
.box {{ background:{SOFT}; border-radius:12px; padding:12px 16px; margin-top:.8rem; }}
.pill {{ display:inline-block; padding:4px 12px; border-radius:999px; font-weight:600; margin:0 6px 6px 0; }}
.card {{ border-top:1px solid {LINE}; padding:14px 0 6px; }}
.card a {{ color:{BLUE}; text-decoration:none; font-weight:600; }}
.card a:hover, .card a:focus-visible {{ text-decoration:underline; }}
/* The verified sentence, marked like a highlighter on a printed page. Always left-to-right English. */
.qwrap {{ direction:ltr; text-align:left; margin:0 0 8px; }}
.quote {{ display:inline; font-family:{SERIF}; font-size:1.05rem; line-height:1.75; background:{MARK};
          padding:.12em .3em; -webkit-box-decoration-break:clone; box-decoration-break:clone; }}
.tr {{ font-size:.9rem; color:{GRAY}; margin-bottom:8px; }}
.steps p {{ margin:.15rem 0; }}
div.stButton > button {{ border-radius:10px; border:0; background:{SOFT}; color:{NAVY}; width:100%; }}
div.stButton > button:focus-visible {{ outline:2px solid {BLUE}; outline-offset:2px; }}
div.stButton > button[kind="primary"], div.stButton > button[data-testid="stBaseButton-primary"] {{
  background:{BLUE}; color:white; font-weight:600; padding:.7rem 1rem; }}
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


def run_check(claim, language, school):
    """Answers for this claim, as a list. Shows progress while it works; raises CheckError."""
    if not USE_AGENT:
        with st.spinner(t("progress")):
            return [check_claim(claim, language, school)]
    results = []
    with st.status(t("progress"), expanded=True) as status:
        for item in backend.stream(claim, language, school):
            if "step" in item:
                step = item["step"]
                detail = "".join(f'<p class="small">{esc(d)}</p>' for d in step["detail"][:4])
                st.markdown(f'<div class="steps"><p><b>{esc(step["label"])}</b></p>{detail}</div>',
                            unsafe_allow_html=True)
            else:
                results = item["results"]
        status.update(state="complete", expanded=False)
    return results


def answers(claim, language, school):
    """The answers for this claim, checked once and kept for reruns (e.g. pressing Listen)."""
    key = (claim, language, school)
    kept = st.session_state.get("answers")
    if not kept or kept[0] != key:
        st.session_state["answers"] = kept = (key, run_check(claim, language, school))
    return kept[1]


# ---------- Screens ----------
def home():
    col1, col2 = st.columns([3, 2])
    st.session_state["language"] = col2.selectbox(
        "Language", LANGUAGES, label_visibility="collapsed",
        index=LANGUAGES.index(st.session_state["language"]))
    direction_css()
    col1.markdown(f'<div class="title">{esc(t("home_title"))}</div>', unsafe_allow_html=True)
    st.markdown(f'<span style="color:{GRAY}">{esc(t("home_subtitle"))}</span>', unsafe_allow_html=True)
    schools = list(SCHOOLS)
    st.session_state["school"] = st.selectbox(
        t("school_label"), schools, index=schools.index(st.session_state["school"]))
    beta_notice()

    st.markdown(f'<div class="label">{esc(t("starters_label"))}</div>', unsafe_allow_html=True)
    for i, rumor in enumerate(langs.starters(lang_code())):
        if st.button(f"“{rumor}”", key=f"rumor{i}"):
            go("result", rumor)

    st.markdown(f'<div class="label">{esc(t("paste_label"))}</div>', unsafe_allow_html=True)
    text = st.text_area("claim", placeholder=t("placeholder"), label_visibility="collapsed",
                        max_chars=MAX_CHARS)
    if st.button(t("check_button"), type="primary", use_container_width=True) and text.strip():
        go("result", text.strip())
    st.markdown(f'<p class="small">🔒 {esc(t("privacy_note"))}</p>', unsafe_allow_html=True)

    if speech.available():
        recording = st.audio_input(t("speak_label"))
        if recording is not None:
            audio = recording.getvalue()
            if hash(audio) != st.session_state.get("heard"):  # each recording is transcribed once
                st.session_state["heard"] = hash(audio)
                try:
                    with st.spinner(t("progress")):
                        go("result", speech.transcribe(audio))
                except pipeline.CheckError as e:
                    st.error(str(e))

    st.markdown(f'<p class="small">{esc(t("sources_note"))}</p>' + disclaimer(), unsafe_allow_html=True)


def source_html(s):
    """One official source: the copied sentence first, then where it comes from."""
    when = esc(s["date_text"]) if not s["date"] else f'{esc(t("last_updated"))}: {esc(s["date"])}'
    card = f'<div class="card"><div class="qwrap"><div class="quote">{esc(s["quote"])}</div></div>'
    if s["quote_translation"]:
        card += f'<div class="tr">{esc(s["quote_translation"])}</div>'
    return (card + f'<a href="{html.escape(s["url"], quote=True)}" target="_blank" rel="noopener">{esc(s["title"])}</a>'
            f'<p class="small">{esc(s["category"])}<br>{esc(s["domain"])}<br>{when}</p></div>')


def answer(res, claim, n):
    """Draw one answer: verdict and headline first, then the proof, then what to do next."""
    parts = [f'<p>{"".join(pill_html(p) for p in res["pills"])}</p>'
             f'<div class="answer">{esc(res["headline"])}</div>']
    if res["explanation"] and res["explanation"] != res["headline"]:
        parts.append(f'<p style="color:{GRAY}">{esc(res["explanation"])}</p>')
    st.markdown("".join(parts), unsafe_allow_html=True)

    if speech.available() and st.button(t("listen"), key=f"listen{n}", icon=":material/volume_up:"):
        try:
            st.audio(speech.speak(speech.script(res)), format="audio/mp3", autoplay=True)
        except pipeline.CheckError as e:
            st.error(str(e))

    parts = []
    if res["sources"]:
        parts.append(f'<div class="label">{esc(t("sources"))} <span class="small" style="float:right">'
                     f'{esc(t("sources_found", n=len(res["sources"])))}</span></div>')
        parts += [source_html(s) for s in res["sources"]]
    for key, items in (("applies_to", res["applies_to"]), ("depends_on", res["exceptions"])):
        if items:
            lis = "".join(f"<li>{esc(i)}</li>" for i in items)
            parts.append(f'<p><b>{esc(t(key))}</b></p><ul>{lis}</ul>')
    if res["clarifying_question"]:
        parts.append(f'<div class="box">{esc(res["clarifying_question"])}</div>')
    if res["next_step"]:
        parts.append(f'<div class="box"><b>{esc(t("next_step"))}:</b> {esc(res["next_step"])}</div>')
    parts.append(f'<p class="asked">{esc(t("you_asked"))}: “{esc(claim)}”</p>')
    if res["claim_in_english"] and lang_code() != "en":
        parts.append(f'<p class="small">{esc(t("we_checked"))}: “{esc(res["claim_in_english"])}”</p>')
    st.markdown("".join(parts), unsafe_allow_html=True)

    if res["show_ask_office"]:
        if not res["out_of_scope"]:
            st.markdown(f'<div class="box"><b>{esc(t("unclear_title"))}</b><br>'
                        f'<span style="color:{GRAY}">{esc(t("unclear_body"))}</span></div>',
                        unsafe_allow_html=True)
        if res["question_for_office"]:  # always English: it is sent to the school's office
            st.markdown(f'**{t("office_question")}**')
            st.code(res["question_for_office"], language=None)
        st.link_button(t("ask_office_button"), res["office"]["url"], use_container_width=True)


def result():
    direction_css()
    if st.button(t("new_check")):
        st.session_state.pop("answers", None)
        go("home")
    claim = st.session_state["claim"]
    waiting = st.empty()  # while the check runs, show what is being checked
    waiting.markdown(f'<p class="asked">{esc(t("you_asked"))}: “{esc(claim)}”</p>', unsafe_allow_html=True)
    try:
        results = answers(claim, st.session_state["language"], st.session_state["school"])
    except pipeline.CheckError as e:  # empty claim, usage limit, service problem...
        st.error(str(e))
        st.markdown(disclaimer(), unsafe_allow_html=True)
        return
    waiting.empty()
    beta_notice()

    for n, res in enumerate(results):
        if n:
            st.divider()
        answer(res, res.get("claim") or claim, n)

    if any(not r["show_ask_office"] for r in results):  # the legend only shows for firm answers
        legend = ui_adapter.legend(lang_code())
        rules = any(len(r["pills"]) > 1 for r in results)
        shown = legend["verdicts"] + (legend["rule_statuses"] if rules else [])
        note = f'<p class="small">{esc(t("legend_note"))}</p>' if rules else ""
        st.markdown(f'<div class="label">{esc(t("legend_title"))}</div>'
                    f'{"".join(pill_html(p) for p in shown)}{note}', unsafe_allow_html=True)
    st.markdown(disclaimer(), unsafe_allow_html=True)


# ---------- Run ----------
# Each screen is one container. The result screen first puts an empty element where
# the home screen was, so the home screen disappears at once instead of staying
# greyed out underneath while a check runs.
if st.session_state["screen"] == "home":
    with st.container():
        home()
else:
    st.empty()
    with st.container():
        result()
