"""The look of the interface: colors, type, styles and the stone.

One idea carries the design. The page is quiet paper and ink; the single bold
element is the stone, a dark polished circle you bring a rumor to. While a check
runs, a light turns inside it. When the answer is ready it clears to the color of
the verdict. The light is the same yellow that marks the sentence copied from the
official page, so the eye connects the stone to the proof.

Everything here is plain data and strings, so it can be tested without running
the app (tests/test_theme.py checks every text color against WCAG AA).
"""
from __future__ import annotations

import html
from typing import Optional

NAVY, BLUE, GRAY = "#1B2F5B", "#0B1FA8", "#5B6B8C"
SOFT, LINE = "#EEF1F8", "#C9D3EA"
MARK = "#FFF1A8"  # highlighter: marks the sentence copied from the official page

# pill kind -> (background, text). Every pair is at least 4.5:1.
PILLS = {
    "supported": ("#E3F3EA", "#146C3F"),
    "contradicted": ("#FBE4E2", "#B3261E"),
    "unclear": (SOFT, "#56668A"),
    "in_effect": ("#E3F3EA", "#146C3F"),
    "proposed": ("#FDF1D6", "#855900"),
    "blocked": ("#FBE4E2", "#B3261E"),
}

# stone kind -> (light, body, shadow) of the sphere once it has cleared to a verdict
STONES = {
    "supported": ("#BFE6CF", "#1A7F4B", "#0D4628"),
    "contradicted": ("#F6C1BC", "#B3261E", "#5E120D"),
    "unclear": ("#D3DAEA", "#5B6B8C", "#2B3650"),
    "in_effect": ("#BFE6CF", "#1A7F4B", "#0D4628"),
    "proposed": ("#F7DFA3", "#9A6700", "#4F3500"),
    "blocked": ("#F6C1BC", "#B3261E", "#5E120D"),
}

# Latin text uses Noto Sans and Noto Serif from static/fonts (bundled, SIL Open Font
# License), so the interface looks right with no network. Arabic and Chinese faces
# are too large to bundle: they load from Google Fonts, and fall back to the fonts
# already on the device.
SANS = ("'Noto Sans','Noto Sans Arabic','Noto Sans SC','Noto Sans TC',system-ui,-apple-system,"
        "'Segoe UI',Roboto,'Helvetica Neue',Arial,sans-serif")
# A device serif comes before the Arabic and Chinese faces: those include Latin letters, so
# they would otherwise turn a headline sans whenever Noto Serif is missing.
SERIF = ("'Noto Serif',Georgia,'Times New Roman','Noto Sans Arabic','Noto Sans SC','Noto Sans TC',serif")
FONTS_URL = ("https://fonts.googleapis.com/css2?family=Noto+Sans+Arabic:wght@400;600;700"
             "&family=Noto+Sans+SC:wght@400;600;700&family=Noto+Sans+TC:wght@400;600;700&display=swap")
LOCAL_FONTS = """
@font-face { font-family:'Noto Sans'; font-style:normal; font-weight:400 700; font-display:swap;
  src:url('app/static/fonts/noto-sans-latin.woff2') format('woff2'); }
@font-face { font-family:'Noto Serif'; font-style:normal; font-weight:400 600; font-display:swap;
  src:url('app/static/fonts/noto-serif-latin.woff2') format('woff2'); }
"""


def _luminance(hex_color: str) -> float:
    def channel(v: float) -> float:
        v /= 255
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4

    r, g, b = (channel(int(hex_color[i : i + 2], 16)) for i in (1, 3, 5))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(foreground: str, background: str) -> float:
    """WCAG contrast ratio of two #RRGGBB colors, from 1 to 21."""
    a, b = _luminance(foreground), _luminance(background)
    return (max(a, b) + 0.05) / (min(a, b) + 0.05)


def stone(kind: Optional[str], size: int) -> str:
    """The stone as HTML. `kind` is None (at rest), "reading", or a pill kind (cleared to a verdict)."""
    cls = "stone" if not kind else f"stone {kind}"
    return f'<div class="{cls}" style="--s:{size}px" aria-hidden="true"></div>'


def waiting(claim: str, steps: list[str], note: str) -> str:
    """The waiting screen: the stone with the light inside, the claim, and what happens meanwhile."""
    rows = "".join(f'<li>{html.escape(step)}</li>' for step in steps)
    return (f'<div class="stone-wait" role="status">{stone("reading", 176)}'
            f'<div class="asked">“{html.escape(claim)}”</div>'
            f'<ul class="stages">{rows}</ul><p class="small">{html.escape(note)}</p></div>')


def _stone_css() -> str:
    cleared = "".join(
        f".stone.{kind} {{ background:radial-gradient(circle at 32% 28%, {light} 0%, {body} 46%, {shadow} 88%); }}\n"
        for kind, (light, body, shadow) in STONES.items()
    )
    return f"""
.stone {{ width:var(--s); height:var(--s); flex:none; border-radius:50%; position:relative; overflow:hidden;
  background:radial-gradient(circle at 32% 28%, {GRAY} 0%, {NAVY} 40%, #0A1330 84%);
  box-shadow:inset -.08em -.1em .22em rgba(0,0,0,.45), inset .05em .06em .1em rgba(255,255,255,.14),
             0 .06em .16em rgba(27,47,91,.28);
  font-size:var(--s); }}
/* the glint on the polished surface */
.stone::after {{ content:""; position:absolute; top:14%; left:19%; width:27%; height:16%; border-radius:50%;
  background:rgba(255,255,255,.34); filter:blur(.03em); transform:rotate(-24deg); }}
/* the light that turns inside while it reads: the same yellow as the highlighted quote */
.stone::before {{ content:""; position:absolute; inset:-45%; opacity:0; filter:blur(.09em);
  background:conic-gradient(from 0deg, transparent 0 52%, {MARK} 70%, transparent 88%); }}
.stone.reading::before {{ opacity:.55; animation:stone-turn 3.4s linear infinite; }}
@keyframes stone-turn {{ to {{ transform:rotate(360deg); }} }}
@media (prefers-reduced-motion: reduce) {{ .stone.reading::before {{ animation:none; opacity:.4; }} }}
{cleared}
.stone-row {{ display:flex; align-items:center; gap:14px; margin:.2rem 0 .4rem; }}
.stone-wait {{ display:flex; flex-direction:column; align-items:center; text-align:center; gap:18px;
  margin:2.2rem 0 1rem; }}
.stone-wait .asked {{ font-family:{SERIF}; font-size:1.35rem; line-height:1.35; color:{NAVY}; max-width:20em; }}
.stone-wait .stages {{ list-style:none; margin:.6rem 0 0; padding:0; text-align:start; align-self:stretch; }}
.stone-wait .stages li {{ position:relative; padding-inline-start:1.5rem; margin:.7rem 0; color:{NAVY}; }}
.stone-wait .stages li::before {{ content:""; position:absolute; inset-inline-start:0; top:.5em; width:10px; height:10px;
  border-radius:50%; background:{NAVY}; }}
.hero {{ display:flex; flex-direction:column; align-items:center; text-align:center; gap:14px; margin:.4rem 0 1.2rem; }}
.hero .lead {{ color:{GRAY}; max-width:21em; margin:0; }}
"""


def css() -> str:
    """The stylesheet for the whole app."""
    return f"""
@import url('{FONTS_URL}');
{LOCAL_FONTS}
html, body, [class*="css"] {{ font-family:{SANS}; color:{NAVY}; }}
.block-container {{ max-width:680px; padding:1.5rem 1rem 3rem; }}
/* A website reads on any screen: a comfortable column on a laptop, the whole width on a phone. */
@media (min-width: 720px) {{
  .block-container {{ padding-top:2.5rem; }}
  .hero .lead {{ max-width:30em; }}
  .st-key-examples.stVerticalBlock {{ display:grid; grid-template-columns:1fr 1fr; gap:.6rem 1rem; }}
}}
#MainMenu, footer, header {{ visibility:hidden; }}
.small {{ font-size:.85rem; color:{GRAY}; }}
.sr {{ position:absolute; width:1px; height:1px; overflow:hidden; clip:rect(0 0 0 0); white-space:nowrap; }}
.block-container h1.title {{ font-family:{SERIF}; font-size:2rem; font-weight:600; line-height:1.2;
  margin:0; padding:0; color:{NAVY}; }}
.block-container h1.answer, .block-container h2.answer {{ font-family:{SERIF}; font-size:1.7rem; font-weight:600;
  line-height:1.25; margin:.4rem 0 .6rem; padding:0; color:{NAVY}; }}
.asked {{ color:{GRAY}; font-size:.9rem; margin-bottom:.4rem; }}
.label {{ font-weight:600; margin:1.2rem 0 .5rem; }}
.box {{ background:{SOFT}; border-radius:12px; padding:12px 16px; margin-top:.8rem; }}
.pill {{ display:inline-block; padding:4px 12px; border-radius:999px; font-weight:600; margin:0 6px 6px 0; }}
.pill.mini {{ font-size:.8rem; padding:2px 10px; }}
details.legend {{ margin-top:1.2rem; color:{GRAY}; }}
details.legend summary {{ cursor:pointer; min-height:44px; display:flex; align-items:center; font-size:.9rem; }}
.card {{ border-top:1px solid {LINE}; padding:14px 0 6px; }}
.card a {{ display:inline-block; padding:12px 0; color:{BLUE}; text-decoration:none; font-weight:600; }}
.card a:hover, .card a:focus-visible {{ text-decoration:underline; }}
/* The verified sentence, marked like a highlighter on a printed page. Always left-to-right English. */
.qwrap {{ direction:ltr; text-align:left; margin:0 0 4px; }}
.quote {{ display:inline; font-family:{SERIF}; font-size:1.05rem; line-height:1.75; background:{MARK};
  padding:.12em .3em; -webkit-box-decoration-break:clone; box-decoration-break:clone; }}
.tr {{ font-size:.9rem; color:{GRAY}; margin:4px 0; }}
.steps p {{ margin:.15rem 0; }}
div.stButton > button {{ min-height:44px; border-radius:10px; border:0; background:{SOFT}; color:{NAVY}; width:100%; }}
div.stButton > button:focus-visible {{ outline:2px solid {BLUE}; outline-offset:2px; }}
div.stButton > button[kind="primary"], div.stButton > button[data-testid="stBaseButton-primary"] {{
  background:{BLUE}; color:white; font-weight:600; padding:.7rem 1rem; }}
[data-testid="stAudioInput"] button {{ min-width:44px; min-height:44px; }}
/* The microphone and the main button share one row at every width, as in the design. */
.st-key-actions [data-testid="stHorizontalBlock"] {{ flex-wrap:nowrap; gap:12px; align-items:stretch; }}
.st-key-actions [data-testid="stColumn"] {{ min-width:0; }}
.st-key-actions [data-testid="stColumn"]:first-child {{ flex:0 0 52px; width:52px; }}
.st-key-actions button {{ min-height:48px; }}
.st-key-actions div.stButton > button {{ background:{SOFT}; border:0; }}
.st-key-actions div.stButton > button[kind="primary"], .st-key-actions div.stButton > button[data-testid="stBaseButton-primary"] {{
  background:{BLUE}; }}
/* The microphone shows only its icon; its label stays for screen readers. */
.st-key-mic, .st-key-mic div.stButton {{ width:100%; }}
.st-key-mic button [data-testid="stMarkdownContainer"] {{ position:absolute; width:1px; height:1px; overflow:hidden;
  clip:rect(0 0 0 0); white-space:nowrap; }}
/* School and language share the top row at every width. */
.st-key-topbar [data-testid="stHorizontalBlock"] {{ flex-wrap:nowrap; gap:10px; }}
.st-key-topbar [data-testid="stColumn"] {{ min-width:0; }}
/* Example claims read as full-width rows that wrap, not as centred buttons. */
.st-key-examples [data-testid="stElementContainer"], .st-key-examples div.stButton {{ width:100%; }}
.st-key-examples div.stButton > button {{ justify-content:flex-start; text-align:start; padding:.7rem 1rem; }}
.st-key-examples div.stButton > button > div {{ justify-content:flex-start; }}
.st-key-examples div.stButton > button p {{ text-align:start; }}
/* The recorder opens right under the microphone, as one soft panel. */
.st-key-recorder:has([data-testid="stAudioInput"]) {{ background:{SOFT}; border-radius:12px; padding:12px 14px; gap:.5rem; }}
.st-key-recorder p.small {{ margin:0 0 .6rem; color:{NAVY}; }}
/* When the browser blocks the microphone, the recorder explains how to allow it. On a phone that
   message is taller than the recorder, so the recorder grows instead of cutting it off. */
.st-key-recorder [data-testid="stAudioInput"] > div {{ height:auto; min-height:68px; background:white; }}
.st-key-recorder [data-testid="stAudioInput"] > div > div > div:first-child {{ font-size:.85rem; line-height:1.4; padding:8px 0; }}
{_stone_css()}"""
