import streamlit as st

st.set_page_config(page_title="OPT Reality Check", page_icon="🎓", layout="centered")

COLORS = {
    "In effect": "#1a7f4b",
    "Proposed only": "#b7791f",
    "Blocked": "#c0392b",
    "Unclear": "#5f6b7a",
}

st.markdown("""
<style>
.badge {display:inline-block; padding:6px 14px; border-radius:999px;
        color:white; font-weight:600;}
.card {border:1px solid rgba(128,128,128,.3); border-radius:12px;
       padding:12px 16px; margin-bottom:10px;}
.muted {opacity:.7; font-size:.85rem;}
</style>
""", unsafe_allow_html=True)

def mock_check(claim, language):
    return {
        "verdict": "Proposed only",
        "explanation": "A rule was proposed but is not in effect. Current OPT rules still apply.",
        "sources": [{"title": "DHS proposed rule", "url": "https://www.dhs.gov",
                     "date": "2026-10-08", "domain": "dhs.gov"}],
    }

st.title("OPT Reality Check")
st.caption("Is that OPT rumor true? Checked against official sources.")

language = st.selectbox("Answer in", ["English", "العربية", "中文", "繁體中文", "Русский"])

if language == "العربية":
    st.markdown("<style>.block-container{direction:rtl;text-align:right}</style>",
                unsafe_allow_html=True)

st.write("Try a common rumor:")
rumors = ["OPT is being cancelled", "OPT now costs $70,000",
          "STEM OPT is ending", "I can start working once OPT is approved"]
cols = st.columns(2)
for i, r in enumerate(rumors):
    if cols[i % 2].button(r, key=f"r{i}", use_container_width=True):
        st.session_state["claim"] = r

claim = st.text_input("Or paste your own claim", key="claim")

if st.button("Check it", type="primary") and claim:
    with st.spinner("Searching official sources..."):
        result = mock_check(claim, language)

    color = COLORS.get(result["verdict"], COLORS["Unclear"])
    st.markdown(f'<span class="badge" style="background:{color}">{result["verdict"]}</span>',
                unsafe_allow_html=True)
    st.write(result["explanation"])

    st.subheader("Sources")
    for s in result["sources"]:
        st.markdown(
            f'<div class="card"><a href="{s["url"]}">{s["title"]}</a>'
            f'<div class="muted">{s["domain"]} · {s["date"]}</div></div>',
            unsafe_allow_html=True)

st.divider()
st.caption("Not legal advice. Confirm with MSU's international student office or an immigration attorney.")
