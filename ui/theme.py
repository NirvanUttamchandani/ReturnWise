"""Visual theme: one small CSS block + a few HTML helpers (all dynamic text is escaped)."""

import html
import streamlit as st

CSS = """
<style>
:root {
  --navy:#0b1f3a; --navy-2:#12305a; --teal:#0d9488; --teal-dk:#0f766e;
  --bg:#f5f7fa; --card:#ffffff; --line:#e2e8f0; --text:#0f172a; --muted:#64748b;
  --ok:#15803d; --ok-bg:#dcfce7; --warn:#b45309; --warn-bg:#fef3c7;
  --bad:#b91c1c; --bad-bg:#fee2e2; --info:#0f766e; --info-bg:#ccfbf1;
}
/* Font comes from .streamlit/config.toml; do not override font-family globally (it would break the icon font). */
.block-container { padding-top: 2rem; padding-bottom: 3rem; max-width: 1280px; }
h1, h2, h3 { color: var(--text); letter-spacing: -0.01em; }

/* Sidebar */
section[data-testid="stSidebar"] { background: var(--navy); border-right: 1px solid #0a1a31; }
section[data-testid="stSidebar"] * { color: #e2e8f0; }
section[data-testid="stSidebar"] .brand { font-size: 1.35rem; font-weight: 700; color: #fff; margin: .25rem 0 0 0; }
section[data-testid="stSidebar"] .brand span { color: #2dd4bf; }
section[data-testid="stSidebar"] .tagline { font-size: .78rem; color: #94a3b8; margin-bottom: 1rem; }
section[data-testid="stSidebar"] .foot { font-size: .74rem; color: #94a3b8; line-height: 1.5; }
section[data-testid="stSidebar"] button { justify-content: flex-start; border-radius: 8px; }
section[data-testid="stSidebar"] button[data-testid="stBaseButton-secondary"] { background: transparent; border: 1px solid transparent; color: #cbd5e1; }
section[data-testid="stSidebar"] button[data-testid="stBaseButton-secondary"]:hover { background: var(--navy-2); border-color: var(--navy-2); color: #fff; }
section[data-testid="stSidebar"] button[data-testid="stBaseButton-primary"] { background: var(--teal); border: 1px solid var(--teal); color: #fff; font-weight: 600; }

/* Cards / metrics */
div[data-testid="stMetric"] { background: var(--card); border: 1px solid var(--line); border-radius: 10px; padding: 14px 16px; }
div[data-testid="stMetricLabel"] p { color: var(--muted); font-size: .8rem; }
div[data-testid="stMetricValue"] { color: var(--text); font-weight: 700; }
div[data-testid="stVerticalBlockBorderWrapper"] { border-radius: 10px; }
.rw-header h1 { margin: 0; font-size: 1.7rem; }
.rw-header p { margin: .2rem 0 1.2rem 0; color: var(--muted); }
.rw-note { background: var(--info-bg); border: 1px solid #99f6e4; color: #134e4a; border-radius: 8px; padding: .6rem .9rem; font-size: .88rem; margin-bottom: 1rem; }
.rw-note.warn { background: var(--warn-bg); border-color: #fde68a; color: #78350f; }
.rw-note.bad { background: var(--bad-bg); border-color: #fecaca; color: #7f1d1d; }

/* Badges */
.badge { display:inline-block; padding: 2px 10px; border-radius: 999px; font-size: .75rem; font-weight: 600; white-space: nowrap; }
.badge.ok { background: var(--ok-bg); color: var(--ok); }
.badge.warn { background: var(--warn-bg); color: var(--warn); }
.badge.bad { background: var(--bad-bg); color: var(--bad); }
.badge.info { background: var(--info-bg); color: var(--info); }
.badge.muted { background: #e2e8f0; color: #475569; }
.chip { display:inline-block; padding: 1px 8px; border-radius: 6px; font-size: .72rem; background:#e0f2f1; color: var(--teal-dk); margin-left: .5rem; font-weight: 600; }

/* Timeline step header */
.step { display:flex; align-items:center; gap: .8rem; }
.step-num { width: 30px; height: 30px; border-radius: 50%; display:flex; align-items:center; justify-content:center; font-weight:700; color:#fff; background: var(--teal); flex: 0 0 30px; }
.step-num.bad { background: var(--bad); } .step-num.muted { background: #94a3b8; } .step-num.warn { background: var(--warn); }
.step-title { font-weight: 600; color: var(--text); }
.step-sub { color: var(--muted); font-size: .84rem; margin-top: 2px; }
.step-right { margin-left: auto; display:flex; gap:.4rem; align-items:center; }

/* Resolution banner */
.banner { border-radius: 12px; padding: 1.2rem 1.4rem; border: 1px solid var(--line); background: var(--card); border-left: 6px solid var(--teal); margin-bottom: 1rem; }
.banner.ok { border-left-color: var(--ok); } .banner.warn { border-left-color: var(--warn); } .banner.bad { border-left-color: var(--bad); }
.banner h2 { margin: 0 0 .2rem 0; font-size: 1.5rem; }
.banner p { margin: 0; color: var(--muted); font-size: .9rem; }
.kv { background: var(--card); border:1px solid var(--line); border-radius: 10px; padding: .7rem .9rem; }
.kv .k { color: var(--muted); font-size: .75rem; text-transform: uppercase; letter-spacing: .04em; }
.kv .v { font-size: 1.05rem; font-weight: 600; color: var(--text); word-break: break-word; }
</style>
"""


def inject() -> None:
    st.markdown(CSS, unsafe_allow_html=True)


def esc(value) -> str:
    return html.escape("" if value is None else str(value))


def badge(text: str, tone: str = "muted") -> str:
    return f'<span class="badge {esc(tone)}">{esc(text)}</span>'


def page_header(title: str, subtitle: str = "") -> None:
    st.markdown(
        f'<div class="rw-header"><h1>{esc(title)}</h1><p>{esc(subtitle)}</p></div>',
        unsafe_allow_html=True,
    )


def note(text: str, tone: str = "") -> None:
    st.markdown(f'<div class="rw-note {esc(tone)}">{esc(text)}</div>', unsafe_allow_html=True)


def kv(label: str, value) -> str:
    return f'<div class="kv"><div class="k">{esc(label)}</div><div class="v">{esc(value)}</div></div>'
