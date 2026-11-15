import html
import streamlit as st

st.set_page_config(page_title="OPT Check", page_icon="🎓")

# ---------- Settings (edit these) ----------
NAVY, BLUE, GRAY = "#1B2F5B", "#0B1FA8", "#5B6B8C"
SOFT, LINE = "#EEF1F8", "#C9D3EA"
LANGUAGES = ["English", "العربية", "中文", "繁體中文", "Русский"]
RUMORS = ["OPT now costs $70,000", "OPT has been cancelled",
          "OPT allows 12 months of work", "The STEM OPT extension is ending"]
SCHOOLS = {
    "Michigan State University": {
        "office": "MSU's Office for International Students and Scholars (OISS)",
        "url": "https://oiss.isp.msu.edu/students/current-students/employment"},
    "University of Chicago": {
        "office": "UChicago's Office of International Affairs (OIA)",
        "url": "https://internationalaffairs.uchicago.edu/"},
}
# label, background, text color
VERDICTS = {
    "In effect": ("✓ In effect", "#E3F3EA", "#1A7F4B"),
    "Proposed only": ("Proposed only", "#FDF1D6", "#9A6700"),
    "Blocked": ("Blocked", "#FBE4E2", "#B3261E"),
    "Unclear": ("— Unclear", SOFT, GRAY),
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
st.session_state.setdefault("school", "Michigan State University")

if st.session_state["language"] == "العربية":  # right-to-left
    st.markdown("<style>.block-container{direction:rtl;text-align:right}</style>",
                unsafe_allow_html=True)

def go(screen, claim=None):
    st.session_state["screen"] = screen
    if claim:
        st.session_state["claim"] = claim
    st.rerun()

def disclaimer():
    office = SCHOOLS[st.session_state["school"]]["office"]
    return f'<p class="small" style="margin-top:1.5rem">Not legal advice. Confirm with {office}.</p>'

# ---------- Backend (teammate replaces this) ----------
def check_claim(claim, language, school):
    return {
        "verdict": "In effect",
        "headline": "Yes, eligible students can apply for OPT.",
        "explanation": "F-1 students may be eligible for up to 12 months of work related to their major. You need authorization before you start.",
        "sources": [
            {"category": "U.S. Government", "domain": "uscis.gov", "url": "https://www.uscis.gov",
             "title": "Science, Technology, Engineering, and Mathematics Optional Practical Training",
             "date": "Aug 27, 2024"},
        ],
    }

# ---------- Screens ----------
def home():
    col1, col2 = st.columns([3, 2])
    col1.markdown("**OPT /**")
    st.session_state["language"] = col2.selectbox(
        "Language", LANGUAGES, label_visibility="collapsed",
        index=LANGUAGES.index(st.session_state["language"]))
    schools = list(SCHOOLS)
    st.session_state["school"] = st.selectbox(
        "Your school", schools, index=schools.index(st.session_state["school"]))

    st.markdown('<p class="small">CLARITY FOR F-1 STUDENTS</p><div class="title">OPT check</div>'
                f'<span style="color:{GRAY}">Clear answers to F-1 OPT rumors.</span>'
                '<div class="label">Heard something? Start here.</div>', unsafe_allow_html=True)
    for i, rumor in enumerate(RUMORS):
        if st.button(f"“{rumor}”", key=f"rumor{i}"):
            go("result", rumor)

    st.markdown('<div class="label">Or paste what you heard</div>', unsafe_allow_html=True)
    text = st.text_area("claim", placeholder='e.g. "Is OPT still available after graduation?"',
                        label_visibility="collapsed")
    if st.button("Check it", type="primary") and text.strip():
        go("result", text.strip())

    st.markdown('<p class="small">We look for government &amp; university sources.</p>'
                '<div class="box"><b>Less guesswork. More context.</b><br>'
                f'<span style="color:{GRAY}">See what the sources say, what is still uncertain, '
                'and where to go next.</span></div>' + disclaimer(), unsafe_allow_html=True)

def result():
    if st.button("← New check"):
        go("home")
    school = st.session_state["school"]
    with st.spinner("Searching official sources..."):
        res = check_claim(st.session_state["claim"], st.session_state["language"], school)

    label, bg, color = VERDICTS.get(res["verdict"], VERDICTS["Unclear"])
    st.markdown(
        f'<div class="box"><p class="small">YOUR QUESTION</p>{html.escape(st.session_state["claim"])}</div>'
        f'<p><span class="pill" style="background:{bg};color:{color}">{label}</span></p>'
        f'<div class="title">{html.escape(res["headline"])}</div>'
        f'<p style="color:{GRAY}">{html.escape(res["explanation"])}</p>'
        f'<div class="label">Sources <span class="small" style="float:right">{len(res["sources"])} found</span></div>',
        unsafe_allow_html=True)

    for s in res["sources"]:
        st.markdown(
            f'<div class="card"><a href="{s["url"]}" target="_blank">View</a>'
            f'<p class="small">{html.escape(s["category"]).upper()}</p>'
            f'<b>{html.escape(s["title"])}</b><br>'
            f'<span style="color:{BLUE}">{html.escape(s["domain"])}</span><br>'
            f'<span class="small">Published {html.escape(s["date"])}</span></div>',
            unsafe_allow_html=True)

    if res["verdict"] == "Unclear":
        st.markdown('<div class="box"><b>You don’t have to figure it out alone.</b><br>'
                    f'<span style="color:{GRAY}">Share this rumor with your school’s international '
                    'student office before you make plans or pay a fee.</span></div>',
                    unsafe_allow_html=True)
        st.link_button("Ask your student office", SCHOOLS[school]["url"], use_container_width=True)
    else:
        pills = "".join(f'<span class="pill" style="background:{b};color:{c}">'
                        f'{l.replace("✓ ", "").replace("— ", "")}</span>'
                        for l, b, c in VERDICTS.values())
        st.markdown(f'<div class="label">What each verdict means</div>{pills}'
                    '<p class="small">A proposal is not a rule in effect.</p>', unsafe_allow_html=True)
    st.markdown(disclaimer(), unsafe_allow_html=True)

# ---------- Run ----------
home() if st.session_state["screen"] == "home" else result()
