"""Streamlit UI for "Is This Still True?". Run: streamlit run app.py"""
import html
from urllib.parse import urlparse

import streamlit as st
from dotenv import load_dotenv

import pipeline

load_dotenv()


@st.cache_data(ttl=3600, show_spinner=False)
def cached_check(claim, school_key, context_items, language):
    """Repeat checks of the same claim are instant; errors are not cached."""
    return pipeline.check_claim(claim, school_key, dict(context_items), language)

LANGUAGES = {
    "English": "English",
    "العربية (Arabic)": "Arabic",
    "中文 (Mandarin)": "Mandarin Chinese",
    "粵語／繁體中文 (Cantonese)": "Cantonese (Traditional Chinese)",
    "O'zbekcha (Uzbek)": "Uzbek",
}
RTL = {"Arabic"}

# Example claims are test inputs, not statements of fact. The OPT rumors come from
# the frontend teammate's mock UI.
STARTERS = {
    "Work": "F-1 students can work 30 hours per week on campus.",
    "SSN": "Every international student can get an SSN without a job.",
    "Taxes": "International students never need to file US tax forms.",
    "OPT cancelled?": "OPT is being cancelled",
    "OPT fee?": "OPT now costs $70,000",
    "STEM OPT?": "STEM OPT is ending",
}

# Colors from the teammate's mock, mapped onto the README verdicts.
VERDICT_COLOR = {"Supported": "#1a7f4b", "Contradicted": "#c0392b", "Unclear": "#5f6b7a"}
RULE_STATUS_COLOR = {"In effect": "#1a7f4b", "Proposed only": "#b7791f", "Blocked": "#c0392b"}

st.set_page_config(page_title="Is This Still True?", page_icon="✅", layout="centered")
st.markdown(
    """
<style>
.badge {display:inline-block; padding:6px 14px; border-radius:999px;
        color:white; font-weight:600; margin-right:8px;}
.card {border:1px solid rgba(128,128,128,.3); border-radius:12px;
       padding:12px 16px; margin-bottom:10px;}
.muted {opacity:.7; font-size:.85rem;}
</style>
""",
    unsafe_allow_html=True,
)
st.title("Is This Still True?")
st.caption("International Student Edition — check advice you heard against official sources.")

config = pipeline.load_config()
school_names = pipeline.schools(config)

if "claim" not in st.session_state:
    st.session_state.claim = ""

st.write("**Not sure what to ask?** Try an example:")
cols = st.columns(3)
for i, (label, text) in enumerate(STARTERS.items()):
    if cols[i % 3].button(label, key=f"starter{i}", use_container_width=True):
        st.session_state.claim = text

claim = st.text_area(
    "What did you hear?",
    key="claim",
    height=100,
    max_chars=pipeline.MAX_CLAIM_CHARS,
    help="You can paste a message from a group chat.",
)
st.caption("🔒 Don't enter passport, I-94, or immigration document numbers. Nothing you type is saved.")

c1, c2 = st.columns(2)
school_key = c1.selectbox("Your school", list(school_names), format_func=school_names.get)
language_label = c2.selectbox("Answer language", list(LANGUAGES))
language = LANGUAGES[language_label]

with st.expander("Tell us about your situation (optional, makes the answer more accurate)"):
    k1, k2 = st.columns(2)
    visa = k1.selectbox("Visa status", ["", "F-1", "J-1", "F-2 / J-2 (dependent)"])
    degree = k2.selectbox("Degree level", ["", "Undergraduate", "Master's", "PhD"])
    k3, k4 = st.columns(2)
    stem = k3.selectbox("STEM-designated degree?", ["", "Yes", "No", "Not sure"])
    timing = k4.selectbox("When?", ["", "During the semester", "Break / vacation", "After graduation"])
    assistantship = st.checkbox("I have an RA / TA assistantship")

if st.button("Check this claim", type="primary"):
    context = {
        "visa status": visa,
        "degree level": degree,
        "STEM-designated degree": stem,
        "timing": timing,
        "assistantship": "yes" if assistantship else "",
    }
    try:
        with st.status("Reading official government and university sources… (about 10 seconds)", expanded=False) as status:
            result = cached_check(claim, school_key, tuple(sorted(context.items())), language)
            status.update(label="Done", state="complete")
    except pipeline.CheckError as e:
        st.error(str(e))
        st.stop()

    badges = f'<span class="badge" style="background:{VERDICT_COLOR[result.verdict]}">{result.verdict}</span>'
    if result.rule_status in RULE_STATUS_COLOR:
        badges += (
            f'<span class="badge" style="background:{RULE_STATUS_COLOR[result.rule_status]}">'
            f"Rule: {result.rule_status}</span>"
        )
    st.markdown(badges, unsafe_allow_html=True)

    direction = "rtl" if language in RTL else "ltr"
    body = [f"<p>{html.escape(result.explanation)}</p>"]
    for title, items in (("Applies to", result.applies_to), ("It depends on", result.exceptions)):
        if items:
            lis = "".join(f"<li>{html.escape(i)}</li>" for i in items)
            body.append(f"<p><b>{title}</b></p><ul>{lis}</ul>")
    st.markdown(f"<div dir='{direction}'>{''.join(body)}</div>", unsafe_allow_html=True)

    if result.clarifying_question:
        st.info(f"To give a firmer answer: {result.clarifying_question}")
    if result.next_step:
        st.warning(f"**Next step:** {result.next_step}")
    if result.question_for_office:
        st.markdown("**Question to send your school's office (in English):**")
        st.code(result.question_for_office, language=None)

    if result.sources:
        st.subheader("Sources used")
        for s in result.sources:
            kind = f"{result.school} policy" if s.scope == "school" else "Federal"
            domain = urlparse(s.url).hostname or ""
            meta = f"{html.escape(domain)} · {html.escape(kind)}" + (f" · {html.escape(s.date)}" if s.date else "")
            st.markdown(
                f'<div class="card"><a href="{html.escape(s.url, quote=True)}">{html.escape(s.title or s.url)}</a>'
                f'<div class="muted">{meta}</div>'
                f'<blockquote>{html.escape(s.quote)}</blockquote></div>',
                unsafe_allow_html=True,
            )
    st.caption(f"Checked {result.checked_at}. A new search does not prove a page is current.")
    st.caption(f"This is not legal advice. Confirm with {config['schools'][school_key]['office']} before acting.")
