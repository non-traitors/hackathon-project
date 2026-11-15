import html
from urllib.parse import urlparse

import streamlit as st
from dotenv import load_dotenv

import pipeline

load_dotenv()
st.set_page_config(page_title="OPT check", page_icon="🎓")

# ---------- Settings (edit these) ----------
NAVY, BLUE, GRAY = "#1B2F5B", "#0B1FA8", "#5B6B8C"
SOFT, LINE = "#EEF1F8", "#C9D3EA"
LANGUAGES = {"English": "English", "العربية": "Arabic", "中文": "Mandarin Chinese",
             "繁體中文": "Traditional Chinese", "Русский": "Russian"}
RUMORS = ["OPT now costs $70,000", "OPT has been cancelled",
          "OPT allows 12 months of work", "The STEM OPT extension is ending"]
CONFIG = pipeline.load_config()
SCHOOLS = pipeline.schools(CONFIG)  # {"msu": "Michigan State University", ...}

# label, background, text color
VERDICTS = {
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
st.markdown(f"""<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans:wght@400;600;700&display=swap');
html, body, [class*="css"] {{ font-family:'Noto Sans',sans-serif; color:{NAVY}; }}
.block-container {{ max-width:480px; padding-top:1.5rem; }}
#MainMenu, footer, header {{ visibility:hidden; }}
.small {{ font-size:.75rem; color:{GRAY}; }}
.title {{ font-size:2rem; font-weight:700; line-height:1.15; margin:.2rem 0; }}
.label {{ font-weight:600; margin:1.2rem 0 .5rem; }}
.box {{ background:{SOFT}; border-radius:12px; padding:12px 16px; margin-top:.8rem; }}
.pill {{ display:inline-block; padding:4px 12px; border-radius:999px; font-weight:600; margin:0 6px 6px 0; }}
.card {{ border:1px solid {LINE}; border-radius:12px; padding:12px 16px; margin-bottom:10px; }}
.card a {{ color:{BLUE}; text-decoration:none; float:right; }}
div.stButton > button {{ border-radius:10px; border:0; background:{SOFT}; color:{NAVY}; width:100%; }}
button[data-testid="stBaseButton-primary"] {{ background:{BLUE}; color:white; font-weight:600; }}
</style>""", unsafe_allow_html=True)

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
    return f'<p class="small" style="margin-top:1.5rem">Not legal advice. Confirm with {html.escape(office())}.</p>'

@st.cache_data(ttl=3600, show_spinner=False)  # same claim again = instant
def cached_check(claim, school_key, language):
    return pipeline.check_claim(claim, school_key, {}, language)

# ---------- Screens ----------
def home():
    col1, col2 = st.columns([3, 2])
    col1.markdown("**OPT /**")
    st.session_state["language"] = col2.selectbox(
        "Language", list(LANGUAGES), label_visibility="collapsed",
        index=list(LANGUAGES).index(st.session_state["language"]))
    keys = list(SCHOOLS)
    st.session_state["school"] = st.selectbox(
        "Your school", keys, format_func=SCHOOLS.get, index=keys.index(st.session_state["school"]))

    st.markdown('<p class="small">CLARITY FOR F-1 STUDENTS</p><div class="title">OPT check</div>'
                f'<span style="color:{GRAY}">Clear answers to F-1 OPT rumors.</span>'
                '<div class="label">Heard something? Start here.</div>', unsafe_allow_html=True)
    for i, rumor in enumerate(RUMORS):
        if st.button(f"“{rumor}”", key=f"rumor{i}"):
            go("result", rumor)

    st.markdown('<div class="label">Or paste what you heard</div>', unsafe_allow_html=True)
    text = st.text_area("claim", placeholder='e.g. "Is OPT still available after graduation?"',
                        max_chars=pipeline.MAX_CLAIM_CHARS, label_visibility="collapsed")
    if st.button("Check it", type="primary") and text.strip():
        go("result", text.strip())

    st.markdown('<p class="small">We look for government &amp; university sources. '
                'Don’t enter passport or immigration document numbers.</p>'
                '<div class="box"><b>Less guesswork. More context.</b><br>'
                f'<span style="color:{GRAY}">See what the sources say, what is still uncertain, '
                'and where to go next.</span></div>' + disclaimer(), unsafe_allow_html=True)

def result():
    if st.button("← New check"):
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

    label, bg, color = VERDICTS[res.verdict]
    badges = f'<span class="pill" style="background:{bg};color:{color}">{label}</span>'
    if res.rule_status in RULES:
        rl, rbg, rc = RULES[res.rule_status]
        badges += f'<span class="pill" style="background:{rbg};color:{rc}">{rl}</span>'
    st.markdown(
        f'<div class="box"><p class="small">YOUR QUESTION</p>{html.escape(claim)}</div>'
        f'<p style="margin-top:1rem">{badges}</p>'
        f'<div class="title">{HEADLINES[res.verdict]}</div>'
        f'<p style="color:{GRAY}">{html.escape(res.explanation)}</p>', unsafe_allow_html=True)

    for title, items in (("Applies to", res.applies_to), ("It depends on", res.exceptions)):
        if items:
            lis = "".join(f"<li>{html.escape(i)}</li>" for i in items)
            st.markdown(f"<p><b>{title}</b></p><ul>{lis}</ul>", unsafe_allow_html=True)
    if res.clarifying_question:
        st.info(f"To give a firmer answer: {res.clarifying_question}")
    if res.next_step:
        st.warning(f"**Next step:** {res.next_step}")

    if res.sources:
        st.markdown(f'<div class="label">Sources <span class="small" style="float:right">'
                    f'{len(res.sources)} used</span></div>', unsafe_allow_html=True)
        for s in res.sources:
            kind = "University" if s.scope == "school" else "U.S. Government"
            date = f'<br><span class="small">Published {html.escape(s.date)}</span>' if s.date else ""
            st.markdown(
                f'<div class="card"><a href="{html.escape(s.url, quote=True)}" target="_blank">View</a>'
                f'<p class="small">{kind.upper()}</p><b>{html.escape(s.title or s.url)}</b><br>'
                f'<span style="color:{BLUE}">{html.escape(urlparse(s.url).hostname or "")}</span>{date}'
                f'<p class="small" style="margin-top:.5rem">“{html.escape(s.quote)}”</p></div>',
                unsafe_allow_html=True)

    if res.question_for_office:
        st.markdown("**Question to send your school’s office (in English):**")
        st.code(res.question_for_office, language=None)
    if res.verdict == "Unclear":
        st.markdown('<div class="box"><b>You don’t have to figure it out alone.</b><br>'
                    f'<span style="color:{GRAY}">Share this rumor with your school’s international '
                    'student office before you make plans or pay a fee.</span></div>',
                    unsafe_allow_html=True)
        st.link_button("Ask your student office", CONFIG["schools"][school]["office_url"],
                       use_container_width=True)
    else:
        pills = "".join(f'<span class="pill" style="background:{b};color:{c}">'
                        f'{l.replace("✓ ", "")}</span>' for l, b, c in VERDICTS.values())
        st.markdown(f'<div class="label">What each verdict means</div>{pills}'
                    '<p class="small">A proposal is not a rule in effect.</p>', unsafe_allow_html=True)
    st.caption(f"Checked {res.checked_at}. A new search does not prove a page is current.")
    st.markdown(disclaimer(), unsafe_allow_html=True)

# ---------- Run ----------
home() if st.session_state["screen"] == "home" else result()