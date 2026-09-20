"""Visual styling for the EVGuard dashboard.

Everything visual lives here: one CSS block (injected once by app.py) and small
HTML helpers. Presentation only: no API calls, no decisions, no data flow.

Colour language, used everywhere:  green = ALLOW,  red = BLOCK,  amber = warning,
blue = neutral information. Colour is never the only signal: every pill and
badge keeps its icon and its word.

SECURITY: app.py passes API data (decision reasons, IDs, rule names ...) into
unsafe_allow_html markdown. Every dynamic value MUST go through esc() first.
The helpers below do that; never build HTML from raw values in app.py.
"""

import html

# ============================================================
# ESCAPING AND SMALL BUILDING BLOCKS
# ============================================================


def esc(value):
    """HTML-escape any value for safe use inside injected HTML.

    None becomes an em dash. "$" is escaped too, because Streamlit's markdown
    would otherwise treat $...$ as LaTeX.
    """
    if value is None or value == "":
        return "—"

    return html.escape(str(value), quote=True).replace("$", "&#36;")


_PILL_KINDS = {"allow", "block", "warn", "info", "neutral"}


def pill(text, kind="neutral", icon=""):
    """A rounded badge. `kind` is chosen by code, never by data."""
    kind = kind if kind in _PILL_KINDS else "neutral"
    label = f"{icon} {esc(text)}".strip() if icon else esc(text)

    return f'<span class="pill pill-{kind}">{label}</span>'


def decision_pill(decision):
    """ALLOW / BLOCK badge with icon and word (never colour alone)."""
    if decision == "ALLOW":
        return pill("ALLOW", "allow", "✅")

    if decision == "BLOCK":
        return pill("BLOCK", "block", "⛔")

    return pill(decision, "warn", "⚠️")


def state_pill(state):
    """Session state badge: charging = green, stopped = amber, others = blue."""
    if state == "CHARGING":
        return pill(state, "allow", "⚡")

    if state == "STOPPED":
        return pill(state, "warn", "⏹️")

    return pill(state, "info")


def expected_badge(expected):
    """'Expected: ALLOW' (green) or 'Expected: BLOCK (rule)' (red)."""
    text = str(expected)
    kind = "allow" if text.startswith("ALLOW") else "block" if text.startswith("BLOCK") else "neutral"

    return f'<span class="badge badge-{kind}">Expected: {esc(text)}</span>'


# ============================================================
# PAGE SECTIONS (HTML)
# ============================================================


def hero(pills):
    """Product name, tagline and status pills. `pills` are already-safe HTML."""
    return (
        '<div class="hero">'
        '<div class="hero-title">🔐 EVGuard</div>'
        '<div class="hero-tag">State-aware security gateway for EV charging commands</div>'
        f'<div class="pills">{"".join(pills)}</div>'
        "</div>"
    )


def pipeline():
    """Authentication → ... → ALLOW / BLOCK as connected chips (wraps on small screens)."""
    steps = [
        "Authentication",
        "Authorization",
        "Session state",
        "Safety limits",
        "Rate limit",
    ]
    chips = '<span class="pipe-arrow">→</span>'.join(
        f'<span class="chip"><span class="chip-n">{index}</span>{label}</span>'
        for index, label in enumerate(steps, start=1)
    )

    return (
        f'<div class="pipeline">{chips}<span class="pipe-arrow">→</span>'
        '<span class="chip chip-end">'
        '<span class="end-allow">ALLOW</span> / <span class="end-block">BLOCK</span>'
        "</span></div>"
    )


def step_card(number, body_html):
    """A numbered 'how to use' card. `body_html` is static, code-written HTML."""
    return (
        '<div class="step-card">'
        f'<div class="step-num">{int(number)}</div>'
        f'<div class="step-text">{body_html}</div>'
        "</div>"
    )


def table(headers, rows):
    """A readable table. Every cell in `rows` must already be safe HTML."""
    head = "".join(f"<th>{esc(h)}</th>" for h in headers)
    body = "".join(
        "<tr>" + "".join(f"<td>{cell}</td>" for cell in row) + "</tr>"
        for row in rows
    )

    return (
        '<div class="evtable-wrap"><table class="evtable">'
        f"<thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>"
    )


def code(text):
    return f"<code>{esc(text)}</code>"


def compare_card(kind, label, big, sub):
    """Baseline-vs-EVGuard card. kind: 'bad' (red) or 'good' (green) or 'warn'."""
    kind = kind if kind in {"bad", "good", "warn"} else "warn"

    return (
        f'<div class="cmp-card cmp-{kind}">'
        f'<div class="cmp-label">{label}</div>'
        f'<div class="cmp-big">{esc(big)}</div>'
        f'<div class="cmp-sub">{sub}</div>'
        "</div>"
    )


def decision_hero(decision, reason, session_id):
    """Big ALLOW/BLOCK block: the reason is the headline, session label beneath."""
    kind = "allow" if decision == "ALLOW" else "block" if decision == "BLOCK" else "warn"
    icon = {"allow": "✅", "block": "⛔"}.get(kind, "⚠️")

    return (
        f'<div class="decision-hero decision-{kind}">'
        f'<div class="decision-word">{icon} {esc(decision)}</div>'
        f'<div class="decision-reason">{esc(reason)}</div>'
        f'<div class="decision-meta">{pill("Session: " + str(session_id), "info")}</div>'
        "</div>"
    )


# ============================================================
# THE CSS (injected once by app.py)
# ============================================================

CSS = """
<style>
/* ---------- design tokens ---------- */
:root {
    --ev-bg: #0b1220;
    --ev-panel: #111a2e;
    --ev-panel-2: #16213a;
    --ev-line: #2a3a5c;
    --ev-text: #e5e9f0;
    --ev-muted: #a3b3cc;
    --ev-accent: #38bdf8;
    --ev-allow: #34d399;
    --ev-allow-bg: rgba(52, 211, 153, 0.14);
    --ev-block: #f87171;
    --ev-block-bg: rgba(248, 113, 113, 0.14);
    --ev-warn: #fbbf24;
    --ev-warn-bg: rgba(251, 191, 36, 0.14);
    --ev-info-bg: rgba(56, 189, 248, 0.14);
    --ev-radius: 14px;
}

/* ---------- page frame: comfortable on a 1366x768 laptop ---------- */
.block-container {
    max-width: 1200px;
    padding-top: 3.6rem;   /* clears Streamlit's fixed toolbar */
    padding-bottom: 3rem;
}

h4 {
    margin-top: 1.1rem;
    letter-spacing: 0.01em;
}

/* ---------- hero ---------- */
.hero {
    background: linear-gradient(135deg, #111a2e 0%, #0f2440 100%);
    border: 1px solid var(--ev-line);
    border-left: 5px solid var(--ev-accent);
    border-radius: var(--ev-radius);
    padding: 1.1rem 1.5rem;
    margin-bottom: 1rem;
}
.hero-title { font-size: 2.1rem; font-weight: 800; line-height: 1.15; }
.hero-tag   { color: var(--ev-muted); font-size: 1.05rem; margin: 0.15rem 0 0.7rem; }
.pills      { display: flex; flex-wrap: wrap; gap: 0.5rem; }

/* ---------- pills and badges ---------- */
.pill, .badge {
    display: inline-flex;
    align-items: center;
    gap: 0.3rem;
    border-radius: 999px;
    border: 1px solid var(--ev-line);
    padding: 0.22rem 0.75rem;
    font-size: 0.85rem;
    font-weight: 600;
    white-space: nowrap;
}
.pill-allow, .badge-allow { color: #6ee7b7; background: var(--ev-allow-bg); border-color: rgba(52, 211, 153, 0.45); }
.pill-block, .badge-block { color: #fca5a5; background: var(--ev-block-bg); border-color: rgba(248, 113, 113, 0.5); }
.pill-warn                { color: #fcd34d; background: var(--ev-warn-bg);  border-color: rgba(251, 191, 36, 0.5); }
.pill-info                { color: #7dd3fc; background: var(--ev-info-bg);  border-color: rgba(56, 189, 248, 0.45); }
.pill-neutral, .badge-neutral { color: var(--ev-text); background: var(--ev-panel-2); }
.badge { border-radius: 8px; margin-top: 0.15rem; white-space: normal; overflow-wrap: anywhere; }

/* ---------- section titles ---------- */
.section-title {
    font-size: 1.25rem;
    font-weight: 700;
    padding-left: 0.7rem;
    border-left: 4px solid var(--ev-accent);
    margin: 0.9rem 0 0.6rem;
}

/* ---------- panels and cards (st.container(key="panel_..."/"card_...")) ---------- */
[class*="st-key-panel_"] {
    background: var(--ev-panel);
    border: 1px solid var(--ev-line);
    border-radius: var(--ev-radius);
    padding: 0.4rem 1.3rem 1.1rem;
    margin-bottom: 0.9rem;
}
[class*="st-key-card_"] {
    background: var(--ev-panel-2);
    border: 1px solid var(--ev-line);
    border-radius: var(--ev-radius);
    padding: 0.9rem 1.1rem 1rem;
    height: 100%;
    transition: transform 0.15s ease, border-color 0.15s ease, box-shadow 0.15s ease;
}
[class*="st-key-card_"]:hover {
    transform: translateY(-2px);
    border-color: var(--ev-accent);
    box-shadow: 0 6px 18px rgba(0, 0, 0, 0.35);
}

/* ---------- pipeline chips ---------- */
.pipeline { display: flex; flex-wrap: wrap; align-items: center; gap: 0.35rem 0.25rem; margin: 0.4rem 0 0.3rem; }
.chip {
    display: inline-flex; align-items: center; gap: 0.45rem;
    background: var(--ev-panel-2);
    border: 1px solid var(--ev-line);
    border-radius: 10px;
    padding: 0.4rem 0.8rem;
    font-weight: 600;
}
.chip-n {
    display: inline-flex; align-items: center; justify-content: center;
    width: 1.35rem; height: 1.35rem; border-radius: 50%;
    background: var(--ev-info-bg); color: #7dd3fc; font-size: 0.78rem;
}
.chip-end { border-color: var(--ev-line); }
.end-allow { color: #6ee7b7; }
.end-block { color: #fca5a5; }
.pipe-arrow { color: var(--ev-muted); font-weight: 700; padding: 0 0.1rem; }

/* ---------- how-to step cards ---------- */
.step-card {
    display: flex; gap: 0.75rem; align-items: flex-start;
    background: var(--ev-panel-2);
    border: 1px solid var(--ev-line);
    border-radius: 12px;
    padding: 0.8rem 0.9rem;
}
@media (min-width: 901px) { .step-card { min-height: 7.2rem; } }
.step-num {
    flex: 0 0 auto;
    display: inline-flex; align-items: center; justify-content: center;
    width: 1.9rem; height: 1.9rem; border-radius: 50%;
    background: var(--ev-accent); color: #04121f; font-weight: 800;
}
.step-text { line-height: 1.4; font-size: 0.95rem; }

/* ---------- result banner and conclusion (st.container(key="result_banner"/"conclusion")) ---------- */
[class*="st-key-result_banner"] [data-testid="stAlert"] { padding: 0.9rem 1.2rem; }
[class*="st-key-result_banner"] [data-testid="stAlert"] p {
    font-size: 1.45rem;
    font-weight: 800;
}
[class*="st-key-conclusion"] [data-testid="stAlert"] { padding: 0.9rem 1.2rem; }
[class*="st-key-conclusion"] [data-testid="stAlert"] p {
    font-size: 1.12rem;
    line-height: 1.5;
}

/* ---------- tables ---------- */
.evtable-wrap {
    max-height: 430px;
    overflow: auto;
    border: 1px solid var(--ev-line);
    border-radius: 12px;
    margin: 0.5rem 0 0.8rem;
}
.evtable { width: 100%; border-collapse: collapse; font-size: 0.9rem; }
.evtable th {
    position: sticky; top: 0;
    background: var(--ev-panel-2);
    color: var(--ev-muted);
    text-align: left;
    font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.05em;
    padding: 0.55rem 0.75rem;
    border-bottom: 1px solid var(--ev-line);
}
.evtable td { padding: 0.5rem 0.75rem; border-bottom: 1px solid rgba(42, 58, 92, 0.6); vertical-align: top; }
.evtable td:first-child, .evtable td:nth-child(3) { white-space: nowrap; }
.evtable tr:hover td { background: rgba(56, 189, 248, 0.05); }
.evtable code { background: transparent; color: #7dd3fc; padding: 0; }

/* ---------- baseline vs EVGuard cards ---------- */
.cmp-card { border-radius: var(--ev-radius); padding: 1rem 1.3rem; border: 1px solid var(--ev-line); height: 100%; }
.cmp-bad  { background: var(--ev-block-bg); border-color: rgba(248, 113, 113, 0.55); }
.cmp-good { background: var(--ev-allow-bg); border-color: rgba(52, 211, 153, 0.55); }
.cmp-warn { background: var(--ev-warn-bg);  border-color: rgba(251, 191, 36, 0.55); }
.cmp-label { font-weight: 700; font-size: 1.05rem; }
.cmp-big   { font-size: 3rem; font-weight: 800; line-height: 1.1; margin: 0.25rem 0; }
.cmp-bad  .cmp-big { color: #fca5a5; }
.cmp-good .cmp-big { color: #6ee7b7; }
.cmp-warn .cmp-big { color: #fcd34d; }
.cmp-sub   { color: var(--ev-text); font-size: 0.98rem; }

/* ---------- latest decision hero ---------- */
.decision-hero { border-radius: var(--ev-radius); padding: 1.1rem 1.4rem; margin-bottom: 0.9rem; border: 1px solid var(--ev-line); }
.decision-allow { background: var(--ev-allow-bg); border-color: rgba(52, 211, 153, 0.55); }
.decision-block { background: var(--ev-block-bg); border-color: rgba(248, 113, 113, 0.55); }
.decision-warn  { background: var(--ev-warn-bg);  border-color: rgba(251, 191, 36, 0.55); }
.decision-word   { font-size: 2.2rem; font-weight: 800; line-height: 1.1; }
.decision-allow .decision-word { color: #6ee7b7; }
.decision-block .decision-word { color: #fca5a5; }
.decision-warn  .decision-word { color: #fcd34d; }
.decision-reason { font-size: 1.2rem; font-weight: 600; margin: 0.4rem 0 0.7rem; line-height: 1.4; }
.decision-meta   { display: flex; flex-wrap: wrap; gap: 0.5rem; }

/* ---------- Streamlit widgets ---------- */
[data-testid="stMetric"] {
    background: var(--ev-panel-2);
    border: 1px solid var(--ev-line);
    border-radius: 12px;
    padding: 0.7rem 1rem;
}
[data-testid="stMetricLabel"] { color: var(--ev-muted); }
[data-testid="stMetricValue"] { font-size: 1.35rem; }
[data-testid="stMetricValue"] > div { white-space: normal; overflow: visible; text-overflow: clip; overflow-wrap: anywhere; }
[data-testid="stAlert"]       { border-radius: 12px; }
[data-testid="stExpander"]    { border-radius: 12px; border-color: var(--ev-line); }

.stButton > button, .stDownloadButton > button {
    border-radius: 10px;
    font-weight: 600;
    border: 1px solid var(--ev-accent);
    transition: background 0.15s ease;
}
.stButton > button:hover, .stDownloadButton > button:hover {
    background: var(--ev-info-bg);
    border-color: var(--ev-accent);
}

/* ---------- small screens and reduced motion ---------- */
@media (max-width: 900px) {
    .hero-title { font-size: 1.7rem; }
    .cmp-big    { font-size: 2.3rem; }
    .decision-word { font-size: 1.8rem; }
}
@media (prefers-reduced-motion: reduce) {
    * { transition: none !important; }
}
</style>
"""
