import html
import os
import threading

import streamlit as st
from dotenv import load_dotenv

import backend
import languages as langs
import pipeline
import speech
import theme
import ui_adapter

load_dotenv()
st.set_page_config(page_title="Is This Still True?", page_icon="🎓")

# ---------- Settings (edit these) ----------
# Colors, type and the stone live in theme.py.
CONFIG = pipeline.load_config()
# Language names come from languages.yaml: English, العربية, 中文, 繁體中文, Русский
LANGUAGES = list(langs.language_choices().values())
# Schools, offices and office links come from sources.yaml (one source of truth).
SCHOOLS = {s["name"]: {"key": key, "office": s["office"], "url": s["office_url"]}
           for key, s in CONFIG["schools"].items()}
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
st.markdown(f"<style>{theme.css()}</style>", unsafe_allow_html=True)

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


def pill_html(p, mini=False):
    bg, color = theme.PILLS[p["kind"]]
    cls = "pill mini" if mini else "pill"
    return f'<span class="{cls}" style="background:{bg};color:{color}">{esc(p["text"])}</span>'


# ---------- Backend ----------
def check_claim(claim, language, school):
    """Run a real check. `language` and `school` are the names shown in the pickers."""
    key = SCHOOLS[school]["key"]
    result = pipeline.check_claim(claim, key, {}, language)
    return ui_adapter.to_ui(result, key, CONFIG)


def run_check(claim, language, school):
    """Answers for this claim, as a list. Raises CheckError. The agent also shows each step as it happens."""
    if not USE_AGENT:
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
    if kept and kept[0] == key:
        return kept[1]
    # While it reads: the stone with the light turning inside it, the claim, and what happens meanwhile.
    waiting = st.empty()
    stages = [t("step_read"), t("step_compare"), t("step_verify")]
    waiting.markdown(theme.waiting(claim, stages, t("progress")), unsafe_allow_html=True)
    try:
        results = run_check(claim, language, school)
    finally:
        waiting.empty()
    st.session_state["answers"] = (key, results)
    return results



def _spoken_language():
    """The language to expect when the student speaks: the one they picked (繁體中文 is
    Cantonese). English is left to auto-detect, since an English-interface student may
    well speak another language."""
    code = lang_code()
    return None if code == "en" else code


def listen_to_question():
    """Voice in: put what the student said into the text box, for them to correct before checking."""
    st.markdown(f'<p class="small">{esc(t("speak_how"))}</p>', unsafe_allow_html=True)
    recording = st.audio_input(t("speak_label"), label_visibility="collapsed")
    if recording is None:
        return
    audio = recording.getvalue()
    if hash(audio) == st.session_state.get("heard"):  # each recording is transcribed once
        return
    st.session_state["heard"] = hash(audio)
    try:
        with st.spinner(t("transcribing")):
            said = speech.transcribe(audio, language=_spoken_language())
    except pipeline.CheckError as e:  # the recorder stays open for another try
        st.error(t("not_heard") if str(e) == speech.NOT_HEARD else str(e))
        return
    typed = st.session_state.get("draft", "").strip()
    st.session_state["draft"] = f"{typed} {said}".strip()[:MAX_CHARS]
    st.session_state["heard_note"] = True
    st.session_state["recording"] = False  # the transcript is in the box: put the recorder away
    st.rerun()


# ---------- Screens ----------
def home():
    with st.container(key="topbar"):
        school_col, language_col = st.columns([3, 2])
    st.session_state["language"] = language_col.selectbox(
        langs.ui_text(lang_code(), "language_label"), LANGUAGES, label_visibility="collapsed",
        index=LANGUAGES.index(st.session_state["language"]))
    direction_css()
    schools = list(SCHOOLS)
    st.session_state["school"] = school_col.selectbox(
        t("school_label"), schools, label_visibility="collapsed", index=schools.index(st.session_state["school"]))
    st.markdown(f'<div class="hero">{theme.stone(None, 112)}<h1 class="title">{esc(t("app_title"))}</h1>'
                f'<p class="lead">{esc(t("tagline"))}</p></div>', unsafe_allow_html=True)
    beta_notice()

    recording = speech.available() and st.session_state.get("recording")
    asking, recorder, after = st.container(), st.container(key="recorder"), st.container()
    with recorder:  # runs first so a transcript can fill the text box above it
        if recording:
            listen_to_question()
    with asking:
        if st.session_state.get("heard_note"):
            st.markdown(f'<p class="small">{esc(t("we_heard"))}</p>', unsafe_allow_html=True)
        text = st.text_area(t("paste_label"), key="draft", placeholder=t("paste_label"),
                            label_visibility="collapsed", max_chars=MAX_CHARS)
        with st.container(key="actions"):  # microphone and main button side by side
            if speech.available():
                mic_col, check_col = st.columns([1, 5])
                label, icon = (("speak_close", ":material/close:") if recording
                               else ("speak_label", ":material/mic:"))
                if mic_col.button(t(label), key="mic", icon=icon):  # opens the recorder, or puts it away
                    st.session_state["recording"] = not recording
                    st.rerun()
            else:
                check_col = st.container()
            if check_col.button(t("check_button"), type="primary", use_container_width=True):
                if text.strip():
                    go("result", text.strip())
                st.warning(t("empty_claim"))
    after.markdown(f'<p class="small">🔒 {esc(t("privacy_note"))}</p>', unsafe_allow_html=True)

    st.markdown(f'<div class="label">{esc(t("starters_label"))}</div>', unsafe_allow_html=True)
    with st.container(key="examples"):
        for i, rumor in enumerate(langs.starters(lang_code())):
            if st.button(f"“{rumor}”", key=f"rumor{i}"):
                go("result", rumor)

    st.markdown(f'<p class="small">{esc(t("sources_note"))}</p>' + disclaimer(), unsafe_allow_html=True)


def source_html(s):
    """One official source: the copied sentence first, then where it comes from."""
    when = esc(s["date_text"]) if not s["date"] else f'{esc(t("last_updated"))}: {esc(s["date"])}'
    card = f'<div class="card"><div class="qwrap" lang="en"><div class="quote">{esc(s["quote"])}</div></div>'
    if s["quote_translation"]:
        card += f'<div class="tr">{esc(s["quote_translation"])}</div>'
    return (card + f'<a href="{html.escape(s["url"], quote=True)}" target="_blank" rel="noopener">{esc(s["title"])}'
            f'<span class="sr"> ({esc(t("new_tab"))})</span></a>'
            f'<p class="small">{esc(s["category"])}<br>{esc(s["domain"])}<br>{when}</p></div>')


def answer(res, claim, n):
    """Draw one answer: verdict and headline first, then the proof, then what to do next."""
    tag = "h1" if n == 0 else "h2"
    head = (f'<div role="status" lang="{lang_code()}"><div class="stone-row">{theme.stone(res["pills"][0]["kind"], 48)}'
            f'<div>{"".join(pill_html(p) for p in res["pills"])}</div></div>'
            f'<{tag} class="answer">{esc(res["headline"])}</{tag}>')
    if res["explanation"] and res["explanation"] != res["headline"]:
        head += f'<p style="color:{theme.GRAY}">{esc(res["explanation"])}</p>'
    st.markdown(head + "</div>", unsafe_allow_html=True)

    if speech.available() and st.button(t("listen"), key=f"listen{n}", icon=":material/volume_up:"):
        try:
            st.audio(speech.speak(speech.script(res), language=res["language"]), format="audio/mp3", autoplay=True)
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
    if res.get("checked_at"):  # when the check ran, which is not when a page was last updated
        when = f'{res["checked_at"][:10]} {res["checked_at"][11:16]} UTC'
        parts.append(f'<p class="small">{esc(t("checked_at", when=when))}</p>')
    st.markdown("".join(parts), unsafe_allow_html=True)

    if res["show_ask_office"]:
        if not res["out_of_scope"]:
            st.markdown(f'<div class="box"><b>{esc(t("unclear_title"))}</b><br>'
                        f'<span style="color:{theme.GRAY}">{esc(t("unclear_body"))}</span></div>',
                        unsafe_allow_html=True)
        if res["question_for_office"]:  # always English: it is sent to the school's office
            st.markdown(f'**{t("office_question")}**')
            st.code(res["question_for_office"], language=None)
        st.link_button(t("ask_office_button"), res["office"]["url"], use_container_width=True)


def result():
    direction_css()
    if st.button(t("new_check")):
        for key in ("answers", "draft", "heard_note", "recording"):
            st.session_state.pop(key, None)
        go("home")
    claim = st.session_state["claim"]
    try:
        results = answers(claim, st.session_state["language"], st.session_state["school"])
    except pipeline.CheckError as e:  # empty claim, usage limit, service problem...
        st.error(str(e))
        if st.button(t("try_again")):
            st.rerun()
        st.markdown(disclaimer(), unsafe_allow_html=True)
        return
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
        st.markdown(f'<details class="legend"><summary>{esc(t("legend_title"))}</summary>'
                    f'{"".join(pill_html(p, mini=True) for p in shown)}{note}</details>', unsafe_allow_html=True)
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
