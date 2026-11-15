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

# Web fonts first, then fonts already on the device, so a weak connection still reads well.
SANS = ("'Noto Sans','Noto Sans Arabic','Noto Sans SC','Noto Sans TC',system-ui,-apple-system,"
        "'Segoe UI',Roboto,'Helvetica Neue',Arial,sans-serif")
SERIF = ("'Noto Serif','Noto Sans Arabic','Noto Sans SC','Noto Sans TC',Georgia,'Times New Roman',serif")
FONTS_URL = ("https://fonts.googleapis.com/css2?family=Noto+Sans:wght@400;600;700&family=Noto+Serif:wght@400;600"
             "&family=Noto+Sans+Arabic:wght@400;600;700&family=Noto+Sans+SC:wght@400;600;700"
             "&family=Noto+Sans+TC:wght@400;600;700&display=swap")


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
.stone-wait .asked {{ font-family:{SERIF}; font-size:1.15rem; color:{NAVY}; max-width:22em; }}
"""


def css() -> str:
    """The stylesheet for the whole app."""
    return f"""
@import url('{FONTS_URL}');
html, body, [class*="css"] {{ font-family:{SANS}; color:{NAVY}; }}
.block-container {{ max-width:480px; padding-top:1.5rem; }}
#MainMenu, footer, header {{ visibility:hidden; }}
.small {{ font-size:.85rem; color:{GRAY}; }}
.sr {{ position:absolute; width:1px; height:1px; overflow:hidden; clip:rect(0 0 0 0); white-space:nowrap; }}
.block-container h1.title {{ font-family:{SANS}; font-size:2rem; font-weight:700; line-height:1.15;
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
{_stone_css()}"""
