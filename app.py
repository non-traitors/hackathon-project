import html
import streamlit as st

st.set_page_config(page_title="OPT check", page_icon="🎓", layout="centered")

NAVY, BLUE, MUTED, SOFT, LINE = "#1B2F5B", "#0B1FA8", "#5B6B8C", "#EEF1F8", "#C9D3EA"

LANGUAGES = ["English", "العربية", "中文", "繁體中文", "Русский"]

# Verify these domains in your browser before the demo
SCHOOLS = {
    "Michigan State University": {
        "domains": ["oiss.isp.msu.edu", "isp.msu.edu"],
        "office_url": "https://oiss.isp.msu.edu",
        "office_name": "MSU's international student office",
    },
    "University of Chicago": {
        "domains": ["internationalaffairs.uchicago.edu"],
        "office_url": "https://internationalaffairs.uchicago.edu",
        "office_name": "UChicago's international student office",
    },
}
FEDERAL_DOMAINS = ["uscis.gov", "ice.gov", "dhs.gov",
                   "studyinthestates.dhs.gov", "federalregister.gov"]

VERDICTS = {  # label, background, text
    "In effect":     ("✓ In effect", "#E3F3EA", "#1A7F4B"),
    "Proposed only": ("Proposed only", "#FDF1D6", "#9A6700"),
    "Blocked":       ("Blocked", "#FBE4E2", "#B3261E"),
    "Unclear":       ("— Unclear", SOFT, MUTED),
}

RUMORS = ["OPT now costs $70,000", "OPT has been cancelled",
          "OPT allows 12 months of work", "The STEM OPT extension is ending"]

st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans:wght@400;600;700&display=swap');
html, body, [class*="css"] {{ font-family:'Noto Sans',sans-serif; color:{NAVY}; }}
.block-container {{ max-width:480px; padding-top:1.5rem; }}
#MainMenu, footer, header {{ visibility:hidden; }}
.eyebrow {{ font-size:.7rem; font-weight:600; letter-spacing:.06em; text-transform:uppercase; }}
.h1 {{ font-size:2rem; font-weight:700; line-height:1.15; margin:.2rem 0; }}
.sub {{ color:{MUTED}; }}
.label {{ font-weight:600; margin:1.2rem 0 .5rem; }}
.quote {{ background:{SOFT}; border-radius:12px; padding:12px 16px; }}
.pill {{ display:inline-block; padding:4px 12px; border-radius:999px; font-size:.85rem; font-weight:600; margin:0 6px 6px 0; }}
.card {{ border:1px solid {LINE}; border-radius:12px; padding:12px 16px; margin-bottom:10px; }}
.card .row {{ display:flex; justify-content:space-between; font-size:.7rem; font-weight:600; text-transform:uppercase; }}
.card a {{ color:{BLUE}; text-decoration:none; }}
.ctitle {{ font-weight:700; margin:.3rem 0; }}
.dom {{ color:{BLUE}; font-size:.85rem; }}
.pub, .fine {{ color:{MUTED}; font-size:.75rem; }}
.info {{ background:{SOFT}; border-radius:12px; padding:14px 16px; margin-top:1rem; }}
div.stButton > button {{ border-radius:10px; border:0; background:{SOFT}; color:{NAVY};
    justify-content:flex-start; text-align:left; padding:.6rem 1rem; width:100%; }}
div.stButton > button[kind="primary"], button[data-testid="stBaseButton-primary"] {{
    background:{BLUE}; color:white; justify-content:center; font-weight:600; padding:.8rem 1rem; }}
textarea {{ border-radius:12px !important; }}
</style>
""", unsafe_allow_html=True)

# Right-to-left layout for Arabic
if st.session_state.get("language") == "العربية":
    st.markdown("<style>.block-container{direction:rtl;text-align:right}</style>",
                unsafe_allow_html=True)

st.session_state.setdefault("screen", "home")
st.session_state.setdefault("language", "English")
st.session_state.setdefault("school", "Michigan State University")


def disclaimer():
    office = SCHOOLS[st.session_state["school"]]["office_name"]
    return f"Not legal advice. Confirm with {office}."


def mock_check(claim, language, school):
    # TODO: replace with the backend's check_claim(claim, language, school)
    # Search domains = FEDERAL_DOMAINS + SCHOOLS[school]["domains"]
    return {
        "verdict": "In effect",
        "headline": "Yes, eligible students can apply for OPT.",
        "explanation": "F-1 students may be eligible for up to 12 months of work related to their major. You need authorization before you start.",
        "sources": [
            {"category": "U.S. Government",
             "title": "Science, Technology, Engineering, and Mathematics Optional Practical Training",
             "domain": "uscis.gov", "url": "https://www.uscis.gov", "date": "Aug 27, 2024"},
            {"category": "University",
             "title": "F-1 Students, OPT Application Season Begins Soon!",
             "domain": "oiss.tulane.edu", "url": "https://oiss.tulane.edu", "date": "Sep 10, 2025"},
        ],
    }


def home():
    c1, c2 = st.columns([3, 2])
    c1.markdown("**OPT /**")
    st.session_state["language"] = c2.selectbox(
        "Language", LANGUAGES, label_visibility="collapsed",
        index=LANGUAGES.index(st.session_state["language"]))

    schools = list(SCHOOLS.keys())
    st.session_state["school"] = st.selectbox(
        "Your school", schools, index=schools.index(st.session_state["school"]))

    st.markdown('<div class="eyebrow">Clarity for F-1 students</div>'
                '<div class="h1">OPT check</div>'
                '<div class="sub">Clear answers to F-1 OPT rumors.</div>'
                '<div class="label">Heard something? Start here.</div>',
                unsafe_allow_html=True)

    for i, r in enumerate(RUMORS):
        if st.button(f"“{r}”   →", key=f"r{i}"):
            st.session_state.update(claim=r, screen="result")
            st.rerun()

    st.markdown('<div class="label">Or paste what you heard</div>', unsafe_allow_html=True)
    text = st.text_area("claim", placeholder='e.g. "Is OPT still available after graduation?"',
                        label_visibility="collapsed")
    if st.button("Check it", type="primary", use_container_width=True) and text.strip():
        st.session_state.update(claim=text.strip(), screen="result")
        st.rerun()

    st.markdown('<div class="fine">We look for government &amp; university sources.</div>'
                '<div class="info"><b>Less guesswork. More context.</b><br>'
                '<span class="sub">See what the sources say, what is still uncertain, and where to go next.</span></div>'
                f'<p class="fine" style="margin-top:2rem">{disclaimer()}</p>',
                unsafe_allow_html=True)


def result():
    if st.button("← New check"):
        st.session_state["screen"] = "home"
        st.rerun()

    school = st.session_state["school"]
    with st.spinner("Searching official sources..."):
        res = mock_check(st.session_state["claim"], st.session_state["language"], school)

    label, bg, fg = VERDICTS.get(res["verdict"], VERDICTS["Unclear"])
    st.markdown(
        f'<div class="quote"><div class="eyebrow">Your question</div>'
        f'{html.escape(st.session_state["claim"])}</div>'
        f'<p><span class="pill" style="background:{bg};color:{fg}">{label}</span></p>'
        f'<div class="h1">{html.escape(res["headline"])}</div>'
        f'<p class="sub">{html.escape(res["explanation"])}</p>'
        f'<div class="label">Sources <span class="fine" style="float:right">{len(res["sources"])} sources</span></div>',
        unsafe_allow_html=True)

    for s in res["sources"]:
        st.markdown(
            f'<div class="card"><div class="row"><span>{html.escape(s["category"])}</span>'
            f'<a href="{s["url"]}" target="_blank">View</a></div>'
            f'<div class="ctitle">{html.escape(s["title"])}</div>'
            f'<div class="dom">{html.escape(s["domain"])}</div>'
            f'<div class="pub">Published {html.escape(s["date"])}</div></div>',
            unsafe_allow_html=True)

    if res["verdict"] == "Unclear":
        st.markdown('<div class="info"><b>You don’t have to figure it out alone.</b><br>'
                    '<span class="sub">Share this rumor with your school’s international student office before you make plans or pay a fee.</span></div>',
                    unsafe_allow_html=True)
        st.link_button("Ask your student office", SCHOOLS[school]["office_url"],
                       use_container_width=True)
    else:
        pills = "".join(
            f'<span class="pill" style="background:{b};color:{f}">'
            f'{l.replace("✓ ", "").replace("— ", "")}</span>'
            for l, b, f in VERDICTS.values())
        st.markdown(f'<div class="label">What each verdict means</div>{pills}'
                    '<p class="fine">A proposal is not a rule in effect.</p>',
                    unsafe_allow_html=True)

    st.markdown(f'<p class="fine" style="margin-top:1.5rem">{disclaimer()}</p>',
                unsafe_allow_html=True)


if st.session_state["screen"] == "home":
    home()
else:
    result()