import html
from urllib.parse import urlparse

import streamlit as st
from dotenv import load_dotenv

import pipeline

load_dotenv()
st.set_page_config(page_title="OPT check", page_icon="🎓", layout="wide")

# ---------- Settings (edit these) ----------
NAVY, BLUE, GRAY = "#1B2F5B", "#0B1FA8", "#5B6B8C"
SOFT, LINE = "#EEF1F8", "#C9D3EA"
LANGUAGES = {"English": "English", "العربية": "Arabic", "中文": "Mandarin Chinese",
             "繁體中文": "Traditional Chinese", "Русский": "Russian"}
RUMORS = ["OPT now costs $70,000", "OPT has been cancelled",
          "OPT allows 12 months of work", "The STEM OPT extension is ending"]
CONFIG = pipeline.load_config()
SCHOOLS = pipeline.schools(CONFIG)  # {"msu": "Michigan State University", ...}

VERDICTS = {  # label, background, text color
    "Supported": ("✓ Supported", "#E3F3EA", "#1A7F4B"),
    "Contradicted": ("Contradicted", "#FBE4E2", "#B3261E"),
    "Unclear": ("— Unclear", SOFT, GRAY),
}
RULES = {
    "In effect": ("Rule: In effect", "#E3F3EA", "#1A7F4B"),
    "Proposed only": ("Rule: Proposed only", "#FDF1D6", "#9A6700"),
    "Blocked": ("Rule: Blocked", "#FBE4E2", "#B3261E"),
}
HEADLINES = {
    "Supported": "The official sources support this.",
    "Contradicted": "The official sources say otherwise.",
    "Unclear": "Not enough evidence. Let’s not guess.",
}

# ---------- Styling ----------
CSS = """
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans:wght@400;600;700&display=swap');
html, body, [class*="css"] { font-family:'Noto Sans',sans-serif; color:NAVY; }
.block-container { max-width:1100px; padding-top:1rem; padding-bottom:3rem; }
#MainMenu, footer, header { visibility:hidden; }
.brand { font-weight:700; font-size:1.4rem; padding-top:.4rem; }
.eyebrow { font-size:.8rem; font-weight:600; letter-spacing:.08em; color:GRAY; margin-top:2rem; }
.hero { font-size:3.2rem; font-weight:700; line-height:1.1; margin:.3rem 0 .8rem; }
.lead { font-size:1.15rem; color:GRAY; margin-bottom:1.5rem; }
.title { font-size:2.2rem; font-weight:700; line-height:1.15; margin:.4rem 0; }
.small { font-size:.8rem; color:GRAY; }
.label { font-weight:600; margin:1rem 0 .5rem; }
.box { background:SOFT; border-radius:12px; padding:14px 18px; margin-top:.8rem; }
.pill { display:inline-block; padding:4px 12px; border-radius:999px; font-weight:600; margin:0 6px 6px 0; }
.card { border:1px solid LINE; border-radius:12px; padding:14px 18px; margin-bottom:12px; }
.card a { color:BLUE; text-decoration:none; float:right; }
.btn { display:block; text-align:center; background:BLUE; color:white !important;
       padding:.8rem 1rem; border-radius:10px; font-weight:600; text-decoration:none; margin-top:.8rem; }
[data-testid="stButton"] { width:100%; }
[data-testid="stButton"] button { width:100%; justify-content:flex-start; text-align:left;
       border:0; border-radius:10px; background:SOFT; color:NAVY; padding:.7rem 1rem; }
[data-testid="stButton"] button:hover { background:LINE; color:NAVY; }
[data-testid="stButton"] button[kind="primary"],
[data-testid="stButton"] button[data-testid="stBaseButton-primary"] {
       background:BLUE; color:white; justify-content:center; font-weight:600; padding:.85rem 1rem; }
[data-testid="stButton"] button[kind="primary"] p,
[data-testid="stButton"] button[data-testid="stBaseButton-primary"] p { color:white; }
textarea { border-radius:12px !important; }
"""
for name, value in (("NAVY", NAVY), ("GRAY", GRAY), ("BLUE", BLUE), ("SOFT", SOFT), ("LINE", LINE)):
    CSS = CSS.replace(name, value)
st.markdown(f"<style>{CSS}</style>", unsafe_allow_html=True)

# ---------- State ----------
st.session_state.setdefault("screen", "home")
st.session_state.setdefault("language", "English")
st.session_state.setdefault("school", list(SCHOOLS)[0])

if LANGUAGES[st.session_state["language"]] == "Arabic":  # right-to-left
    st.markdown("<style>.block-container{direction:rtl;text-align:right}</style>",
                unsafe_allow_html=True)


def go(screen, claim=None):
    st.session_state["screen"] = screen
    if claim:
        st.session_state["claim"] = claim
    st.rerun()


def office():
    return CONFIG["schools"][st.session_state["school"]]["office"]


def disclaimer():
    return (f'<p class="small" style="margin-top:2rem;text-align:center">'
            f'Not legal advice. Confirm with {html.escape(office())}.</p>')


@st.cache_data(ttl=3600, show_spinner=False)  # same claim again = instant
def cached_check(claim, school_key, language):
    return pipeline.check_claim(claim, school_key, {}, language)


def top_bar():
    brand, lang, school = st.columns([4, 1.5, 2.5])
    brand.markdown('<div class="brand">OPT /</div>', unsafe_allow_html=True)
    st.session_state["language"] = lang.selectbox(
        "Language", list(LANGUAGES), label_visibility="collapsed",
        index=list(LANGUAGES).index(st.session_state["language"]))
    keys = list(SCHOOLS)
    st.session_state["school"] = school.selectbox(
        "School", keys, format_func=SCHOOLS.get, label_visibility="collapsed",
        index=keys.index(st.session_state["school"]))


# ---------- Screens ----------
def home():
    top_bar()
    left, right = st.columns([3, 2], gap="large")
    with left:
        st.markdown('<div class="eyebrow">CLARITY FOR F-1 STUDENTS</div>'
                    '<div class="hero">Is that OPT rumor true?</div>'
                    '<div class="lead">Paste what you heard. We check it against official '
                    'government and university sources.</div>', unsafe_allow_html=True)
        text = st.text_area("claim", height=140, max_chars=pipeline.MAX_CLAIM_CHARS,
                            placeholder='e.g. "Is OPT still available after graduation?"',
                            label_visibility="collapsed")
        if st.button("Check it", type="primary") and text.strip():
            go("result", text.strip())
        st.markdown('<p class="small">Don’t enter passport or immigration document numbers.</p>',
                    unsafe_allow_html=True)
    with right:
        st.markdown('<div class="label" style="margin-top:2.5rem">Heard something? Start here.</div>',
                    unsafe_allow_html=True)
        for i, rumor in enumerate(RUMORS):
            if st.button(f"“{rumor}”", key=f"rumor{i}"):
                go("result", rumor)
        st.markdown('<div class="box"><b>Less guesswork. More context.</b><br>'
                    f'<span style="color:{GRAY}">See what the sources say, what is still '
                    'uncertain, and where to go next.</span></div>', unsafe_allow_html=True)
    st.markdown(disclaimer(), unsafe_allow_html=True)


def result():
    top_bar()
    back, _ = st.columns([1, 5])
    if back.button("← New check"):
        go("home")
    claim, school = st.session_state["claim"], st.session_state["school"]
    try:
        with st.spinner("Reading official sources… (about 10–15 seconds)"):
            res = cached_check(claim, school, LANGUAGES[st.session_state["language"]])
    except pipeline.CheckError as e:
        st.error(str(e))
        return
    except Exception:
        st.error("Something went wrong while checking. Please try again in a moment.")
        return

    left, right = st.columns([3, 2], gap="large")
    with left:
        label, bg, color = VERDICTS[res.verdict]
        badges = f'<span class="pill" style="background:{bg};color:{color}">{label}</span>'
        if res.rule_status in RULES:
            rl, rbg, rc = RULES[res.rule_status]
            badges += f'<span class="pill" style="background:{rbg};color:{rc}">{rl}</span>'
        st.markdown(
            f'<div class="box"><p class="small">YOUR QUESTION</p>{html.escape(claim)}</div>'
            f'<p style="margin-top:1rem">{badges}</p>'
            f'<div class="title">{HEADLINES[res.verdict]}</div>'
            f'<p style="color:{GRAY};font-size:1.05rem">{html.escape(res.explanation)}</p>',
            unsafe_allow_html=True)
        for title, items in (("Applies to", res.applies_to), ("It depends on", res.exceptions)):
            if items:
                lis = "".join(f"<li>{html.escape(i)}</li>" for i in items)
                st.markdown(f"<p><b>{title}</b></p><ul>{lis}</ul>", unsafe_allow_html=True)
        if res.clarifying_question:
            st.info(f"To give a firmer answer: {res.clarifying_question}")
        if res.next_step:
            st.warning(f"**Next step:** {res.next_step}")
        if res.question_for_office:
            st.markdown("**Question to send your school’s office (in English):**")
            st.code(res.question_for_office, language=None)
        if res.verdict == "Unclear":
            url = CONFIG["schools"][school]["office_url"]
            st.markdown('<div class="box"><b>You don’t have to figure it out alone.</b><br>'
                        f'<span style="color:{GRAY}">Share this rumor with your school’s '
                        'international student office before you make plans or pay a fee.</span></div>'
                        f'<a class="btn" href="{html.escape(url, quote=True)}" target="_blank">'
                        'Ask your student office</a>', unsafe_allow_html=True)
    with right:
        st.markdown(f'<div class="label" style="margin-top:0">Sources '
                    f'<span class="small" style="float:right">{len(res.sources)} used</span></div>',
                    unsafe_allow_html=True)
        if not res.sources:
            st.markdown('<div class="box">No verified sources for this answer.</div>',
                        unsafe_allow_html=True)
        for s in res.sources:
            kind = "University" if s.scope == "school" else "U.S. Government"
            date = f'<br><span class="small">Published {html.escape(s.date)}</span>' if s.date else ""
            st.markdown(
                f'<div class="card"><a href="{html.escape(s.url, quote=True)}" target="_blank">View</a>'
                f'<p class="small">{kind.upper()}</p><b>{html.escape(s.title or s.url)}</b><br>'
                f'<span style="color:{BLUE}">{html.escape(urlparse(s.url).hostname or "")}</span>{date}'
                f'<p class="small" style="margin-top:.5rem">“{html.escape(s.quote)}”</p></div>',
                unsafe_allow_html=True)
        pills = "".join(f'<span class="pill" style="background:{b};color:{c}">'
                        f'{l.replace("✓ ", "")}</span>' for l, b, c in VERDICTS.values())
        st.markdown(f'<div class="label">What each verdict means</div>{pills}'
                    '<p class="small">A proposal is not a rule in effect.</p>'
                    f'<p class="small">Checked {html.escape(res.checked_at)}. '
                    'A new search does not prove a page is current.</p>', unsafe_allow_html=True)
    st.markdown(disclaimer(), unsafe_allow_html=True)


# ---------- Run ----------
if st.session_state["screen"] == "home":
    home()
else:
    result()