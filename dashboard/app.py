import csv
import inspect
import io
import uuid
from datetime import datetime, timezone

import streamlit as st

import api_client
import styles


# ============================================================
# PAGE CONFIGURATION
# ============================================================

st.set_page_config(
    page_title="EVGuard — Charging Security Dashboard",
    page_icon="🔐",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ============================================================
# CUSTOM STYLING
# ============================================================

# All CSS lives in dashboard/styles.py; it is injected here, once.
st.markdown(styles.CSS, unsafe_allow_html=True)


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def decision_icon(decision):
    if decision == "ALLOW":
        return "✅"

    if decision == "BLOCK":
        return "⛔"

    return "⚠️"


def show(value):
    """Display text for a possibly empty value: None and "" become an em dash."""
    if value is None or value == "":
        return "—"

    return value


def number(value):
    """Compact number for display (20.0 -> 20); None becomes an em dash."""
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return f"{value:g}"

    return show(value)


MODE_LABEL = "Mock data mode" if api_client.MOCK_MODE else "Live mode"
GATEWAY_LABEL = "mock data" if api_client.MOCK_MODE else "the EVGuard gateway"


def build_csv(rows):
    if not rows:
        return b""

    output = io.StringIO()

    fieldnames = [
        "Time",
        "Command",
        "Value",
        "Decision",
        "Rule",
        "Reason",
    ]

    writer = csv.DictWriter(
        output,
        fieldnames=fieldnames,
    )

    writer.writeheader()
    writer.writerows(rows)

    return output.getvalue().encode("utf-8-sig")


# Streamlit renamed use_container_width to width="stretch"; support both.
STRETCH = (
    {"width": "stretch"}
    if "width" in inspect.signature(st.button).parameters
    else {"use_container_width": True}
)

NORMAL_SCENARIOS = ["normal_session", "full_lifecycle"]

ATTACK_SCENARIOS = [
    "excess_power",
    "invalid_state",
    "excess_current",
    "invalid_token",
    "unauthorized_role",
    "rate_burst",
]

# What each scenario should produce (CONTRACT section 4).
EXPECTED = {
    "normal_session": "ALLOW",
    "full_lifecycle": "ALLOW",
    "excess_power": "BLOCK (policy.power_limit)",
    "invalid_state": "BLOCK (state.invalid_transition)",
    "excess_current": "BLOCK (policy.current_limit)",
    "invalid_token": "BLOCK (auth.invalid_token)",
    "unauthorized_role": "BLOCK (authz.command_not_permitted)",
    "rate_burst": "BLOCK (sequence.rate_exceeded) after 10 commands",
}

# Used only when the scenario file carries no description.
FALLBACK_DESCRIPTIONS = {
    "normal_session": "A valid controller connects, authorizes, starts charging and sets 5 kW.",
    "full_lifecycle": "A complete charge from plug-in to unplug, all within limits.",
    "excess_power": "A valid controller asks for 20 kW on a 7 kW session.",
    "invalid_state": "A controller tries to start charging before connecting.",
    "excess_current": "A valid controller asks for 40 A on a 32 A session.",
    "invalid_token": "A controller connects with a forged authentication token.",
    "unauthorized_role": "A read-only monitor tries to send an active CONNECT.",
    "rate_burst": "A controller floods the charger with commands.",
}

DEMO_SESSION_ID = "sess_demo"
COMPARE_SESSION_ID = "sess_compare"
COMPARE_BASELINE_SESSION_ID = "sess_compare_baseline"
DEMO_SOURCE_ID = "controller_A"
DEMO_TOKEN = "demo-token-controller-A"

STATE_KEYS = ("scenario_result", "scenario_name", "active_session_id", "comparison")


def conclusion(result, session_info):
    """One plain-English sentence, built only from this run's decisions and the
    session's actual state afterwards. Nothing here is assumed about a scenario.
    """
    if not result.get("passed"):
        return (
            "At least one step did not behave as expected. "
            "The table above shows which step differs."
        )

    decisions = [step.get("decision") or {} for step in result.get("results", [])]
    blocked = [d for d in decisions if d.get("decision") == "BLOCK"]
    allowed_count = len(decisions) - len(blocked)

    power = ((session_info or {}).get("physical") or {}).get("power_kw")
    charger = (
        f" Charger power after the run: {number(power)} kW."
        if isinstance(power, (int, float)) and not isinstance(power, bool)
        else ""
    )

    if not blocked:
        return (
            f"All {len(decisions)} commands were allowed: each one was "
            f"authenticated, valid for the session state and within limits.{charger}"
        )

    first = blocked[0]
    earlier = decisions[:decisions.index(first)]
    authenticated_before = any(
        d.get("decision") == "ALLOW" and d.get("source_id") == first.get("source_id")
        for d in earlier
    )
    lead = (
        "The controller was authenticated (its earlier commands were allowed), "
        "but EVGuard blocked"
        if authenticated_before
        else "EVGuard blocked"
    )

    value = first.get("value")
    request = show(first.get("command_type"))
    if isinstance(value, (int, float)):
        request = f"{request} {number(value)} {first.get('unit') or ''}".strip()

    reason = str(show(first.get("reason"))).rstrip(".")
    text = f"{lead} {request} (rule {show(first.get('rule_triggered'))}). {reason}."

    if len(blocked) > 1:
        text += f" In total {allowed_count} commands were allowed and {len(blocked)} blocked."

    return text + charger


def compare_command(session_id, command_type, value=None, unit=None):
    return {
        "command_id": f"cmd_cmp_{uuid.uuid4().hex[:12]}",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "session_id": session_id,
        "source_id": DEMO_SOURCE_ID,
        "auth_token": DEMO_TOKEN,
        "command_type": command_type,
        "value": value,
        "unit": unit,
    }


def run_comparison():
    """Send the same 20 kW command to EVGuard and to the unprotected baseline.

    Both first reach a safe 5 kW. Returns None if any call fails.
    """
    setup = [
        ("CONNECT", None, None),
        ("AUTHORIZE_SESSION", None, None),
        ("START_CHARGING", None, None),
        ("SET_POWER", 5.0, "kW"),
    ]
    attack = ("SET_POWER", 20.0, "kW")

    if api_client.create_session(
        {"session_id": COMPARE_SESSION_ID, "vehicle_id": "Vehicle-01"}
    ) is None:
        return None

    for step in setup:
        if api_client.send_command(compare_command(COMPARE_SESSION_ID, *step)) is None:
            return None

    before_session = api_client.get_session(COMPARE_SESSION_ID)
    guarded = api_client.send_command(compare_command(COMPARE_SESSION_ID, *attack))
    guarded_session = api_client.get_session(COMPARE_SESSION_ID)

    baseline = None
    for step in setup + [attack]:
        baseline = api_client.baseline_command(
            compare_command(COMPARE_BASELINE_SESSION_ID, *step)
        )
        if baseline is None:
            return None

    if guarded is None or guarded_session is None or before_session is None:
        return None

    return {
        "decision": guarded.get("decision"),
        "rule": guarded.get("rule_triggered"),
        "evguard_power_before_kw": (before_session.get("physical") or {}).get("power_kw"),
        "evguard_power_kw": (guarded_session.get("physical") or {}).get("power_kw"),
        "baseline_power_kw": (baseline.get("snapshot") or {}).get("power_kw"),
    }


def run_and_store(name, title):
    """Run one scenario, remember its result and session, then redraw the page."""
    with st.spinner(f"Running {title}..."):
        result = api_client.run_scenario(name)

    st.session_state["scenario_result"] = result
    st.session_state["scenario_name"] = name

    if result and result.get("session_id"):
        st.session_state["active_session_id"] = result["session_id"]

    # Rerun so the session panel and metrics below show the new state.
    st.rerun()


def reset_demo():
    """Re-create sess_demo and clear everything the page remembers about a run."""
    reset = api_client.create_session(
        {"session_id": DEMO_SESSION_ID, "vehicle_id": "Vehicle-01"}
    )

    for key in STATE_KEYS:
        st.session_state.pop(key, None)

    st.session_state["notice"] = (
        "Demo reset: sess_demo is back to DISCONNECTED."
        if reset is not None
        else "Could not reset the demo session. Is the backend running?"
    )
    st.rerun()


def render_scenario_card(scenario):
    name = scenario.get("name", "")
    title = scenario.get("title") or name
    description = scenario.get("description") or FALLBACK_DESCRIPTIONS.get(name, "")

    with st.container(key=f"card_{name}"):
        st.markdown(f"**{title}**")
        st.write(description)
        st.markdown(
            styles.expected_badge(EXPECTED.get(name, "see the result")),
            unsafe_allow_html=True,
        )

        if st.button("▶ Run", key=f"scenario_{name}", **STRETCH):
            run_and_store(name, title)


def render_scenario_row(scenarios):
    for start in range(0, len(scenarios), 3):
        columns = st.columns(3)

        for column, scenario in zip(columns, scenarios[start:start + 3]):
            with column:
                render_scenario_card(scenario)


# ============================================================
# LOAD DATA
# ============================================================

health = api_client.health()
stats = api_client.get_stats()
active_session_id = st.session_state.get("active_session_id", DEMO_SESSION_ID)
session = api_client.get_session(active_session_id)
session_fallback = False

if session is None and active_session_id != DEMO_SESSION_ID:
    session = api_client.get_session(DEMO_SESSION_ID)
    session_fallback = True

decisions_data = api_client.get_decisions(limit=50)
scenarios_data = api_client.list_scenarios()


# ============================================================
# HEADER
# ============================================================


# ============================================================
# SYSTEM STATUS
# ============================================================

gateway_online = bool(health and health.get("status") == "ok")
contract_version = health.get("contract_version", "unknown") if health else "unknown"

st.markdown(
    styles.hero(
        [
            styles.pill("Gateway Online", "allow", "🟢")
            if gateway_online
            else styles.pill("Gateway Offline", "block", "🔴"),
            styles.pill(f"Contract v{contract_version}", "info"),
            styles.pill(MODE_LABEL, "warn" if api_client.MOCK_MODE else "info"),
        ]
    ),
    unsafe_allow_html=True,
)


# ============================================================
# BACKEND AVAILABILITY
# ============================================================

if not api_client.MOCK_MODE and health is None:
    st.error("**The EVGuard backend isn't running.**")

    st.markdown(
        "Start everything with one command from the repository folder:"
    )

    st.code(
        "./run.ps1      # Windows PowerShell\n"
        "./run.sh       # macOS / Linux",
        language="bash",
    )

    st.markdown("Or start only the backend yourself:")

    st.code(
        "python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000",
        language="bash",
    )

    st.caption(
        "Then reload this page. No backend? Run the no-browser demo "
        "with `python demo.py`."
    )
    st.stop()


if decisions_data is None:
    st.error("Unable to load EVGuard decisions.")
    st.stop()


decisions = decisions_data.get("items", [])


if stats is None:
    stats = {
        "total": len(decisions),
        "allowed": sum(
            item.get("decision") == "ALLOW"
            for item in decisions
        ),
        "blocked": sum(
            item.get("decision") == "BLOCK"
            for item in decisions
        ),
    }


# ============================================================
# WHAT IS EVGUARD / HOW TO USE
# ============================================================

with st.container(key="panel_what"):
    st.markdown(
        '<div class="section-title">What is EVGuard?</div>',
        unsafe_allow_html=True,
    )

    st.write(
        "Every EV charging command passes through EVGuard before it reaches "
        "the charger. Even a correctly authenticated command is **BLOCKED** if "
        "it is unsafe or invalid for the charger's current state. Every "
        "decision is explained and kept in an audit trail."
    )

    st.markdown(styles.pipeline(), unsafe_allow_html=True)


with st.container(key="panel_how"):
    st.markdown(
        '<div class="section-title">How to use this dashboard</div>',
        unsafe_allow_html=True,
    )

    how_steps = [
        "<b>Run the Normal charging session</b> below and watch every command get ALLOWED.",
        "<b>Run an attack</b>, for example the <i>Excess power attack</i>.",
        "<b>Watch the decision card and the charger's power</b> to see the attack stopped.",
        "<b>Check the audit trail</b> at the bottom of the page for the full record.",
    ]

    for number_, column, body in zip(range(1, 5), st.columns(4), how_steps):
        with column:
            st.markdown(styles.step_card(number_, body), unsafe_allow_html=True)


# ============================================================
# SCENARIO CARDS
# ============================================================

title_col, reset_col = st.columns([4, 1])

with title_col:
    st.markdown(
        '<div class="section-title">Try a scenario</div>',
        unsafe_allow_html=True,
    )

with reset_col:
    if st.button("🔄 Reset demo", key="reset_demo", **STRETCH):
        reset_demo()


notice = st.session_state.pop("notice", None)

if notice:
    st.info(notice)

st.caption(
    f"Each card runs a controlled scenario against {GATEWAY_LABEL}."
)


scenarios = (scenarios_data or {}).get("items", [])
by_name = {item.get("name"): item for item in scenarios}

normal_cards = [by_name[n] for n in NORMAL_SCENARIOS if n in by_name]
attack_cards = [by_name[n] for n in ATTACK_SCENARIOS if n in by_name]
attack_cards += [
    item
    for item in scenarios
    if item.get("name") not in NORMAL_SCENARIOS + ATTACK_SCENARIOS
]


if scenarios:
    st.markdown("#### ✅ Normal operation")
    render_scenario_row(normal_cards)

    st.markdown("#### ⚠️ Attacks")
    render_scenario_row(attack_cards)
else:
    st.info("No scenarios available.")


# ============================================================
# WHAT JUST HAPPENED
# ============================================================

scenario_result = st.session_state.get("scenario_result")
scenario_name = st.session_state.get("scenario_name")


if scenario_name and not scenario_result:
    st.error(
        f"✘ Scenario `{scenario_name}` could not be run."
    )


if scenario_result:

    with st.container(key="panel_happened"):
        st.markdown(
            '<div class="section-title">What just happened</div>',
            unsafe_allow_html=True,
        )

        st.write(f"**Scenario:** `{scenario_name}`")

        results = scenario_result.get("results", [])

        mismatch_step = next(
            (
                step_result.get("step", "—")
                for step_result in results
                if not step_result.get("passed", False)
            ),
            None,
        )

        with st.container(key="result_banner"):
            if scenario_result.get("passed") and mismatch_step is None:
                st.success("✔ Scenario matched expectations")
            elif mismatch_step is not None:
                st.error(f"✘ Mismatch at step {mismatch_step}")
            else:
                st.error("✘ Scenario did not match expectations")

        with st.container(key="conclusion"):
            st.info(
                conclusion(
                    scenario_result,
                    None if session_fallback else session,
                )
            )

        rows = []

        for step_result in results:
            decision_data = step_result.get("decision") or {}
            step_value = decision_data.get("value")

            rows.append(
                [
                    styles.esc(step_result.get("step")),
                    styles.esc(decision_data.get("command_type")),
                    styles.esc(
                        f"{step_value:g} {decision_data.get('unit') or ''}".strip()
                        if isinstance(step_value, (int, float))
                        else None
                    ),
                    styles.decision_pill(decision_data.get("decision")),
                    styles.code(decision_data.get("rule_triggered")),
                    styles.esc(decision_data.get("reason")),
                    f"{styles.esc(step_result.get('expect'))} "
                    f"({styles.esc(step_result.get('expect_rule'))})",
                    styles.pill("as expected", "allow", "✅")
                    if step_result.get("passed")
                    else styles.pill("mismatch", "block", "❌"),
                ]
            )

        if rows:
            st.markdown(
                styles.table(
                    [
                        "Step",
                        "Command",
                        "Value",
                        "Decision",
                        "Rule",
                        "Reason",
                        "Expected",
                        "Result",
                    ],
                    rows,
                ),
                unsafe_allow_html=True,
            )

        with st.expander("Technical details (raw JSON)"):
            st.json(scenario_result)


# ============================================================
# BASELINE VS EVGUARD
# ============================================================

with st.container(key="panel_compare"):
    st.markdown(
        '<div class="section-title">Baseline vs EVGuard</div>',
        unsafe_allow_html=True,
    )

    st.write(
        "Send the same 20 kW command to an unprotected controller and to "
        "EVGuard, on a session that is limited to 7 kW and already charging at 5 kW."
    )

    st.caption(
        "The baseline is a simulated unprotected controller, not a real charger."
    )

    if api_client.MOCK_MODE:
        st.info(
            "This comparison needs the live backend. Start it with "
            "`./run.ps1` or `./run.sh`."
        )

    if st.button(
        "⚡ Send 20 kW to both",
        key="run_comparison",
        disabled=api_client.MOCK_MODE,
    ):
        with st.spinner("Sending the same command to both..."):
            comparison_result = run_comparison()

        if comparison_result is None:
            st.session_state.pop("comparison", None)
            st.error("The comparison could not run. Is the backend running?")
        else:
            st.session_state["comparison"] = comparison_result

    comparison = st.session_state.get("comparison")

    if comparison:
        without_col, with_col = st.columns(2)

        with without_col:
            st.markdown(
                styles.compare_card(
                    "bad",
                    "🚫 Without EVGuard",
                    f"{number(comparison.get('baseline_power_kw'))} kW",
                    "The unprotected controller obeyed the command: "
                    "charger set to this power.",
                ),
                unsafe_allow_html=True,
            )

        with with_col:
            unchanged = (
                comparison.get("evguard_power_kw")
                == comparison.get("evguard_power_before_kw")
            )

            if comparison.get("decision") == "BLOCK":
                st.markdown(
                    styles.compare_card(
                        "good",
                        "🛡️ With EVGuard: ⛔ BLOCKED",
                        f"{number(comparison.get('evguard_power_kw'))} kW",
                        f"Rule {styles.code(comparison.get('rule'))}: the charger "
                        f"{'stays at' if unchanged else 'is now at'} this power.",
                    ),
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(
                    styles.compare_card(
                        "warn",
                        f"🛡️ With EVGuard: {styles.esc(comparison.get('decision'))}",
                        f"{number(comparison.get('evguard_power_kw'))} kW",
                        "The command was not blocked; this is the charger's power now.",
                    ),
                    unsafe_allow_html=True,
                )


st.divider()


# ============================================================
# TOP METRICS
# ============================================================

total = stats.get("total", 0)
allowed = stats.get("allowed", 0)
blocked = stats.get("blocked", 0)


metric1, metric2, metric3, metric4 = st.columns(4)


with metric1:
    st.metric(
        "Total Decisions",
        total,
    )


with metric2:
    st.metric(
        "Allowed",
        allowed,
    )


with metric3:
    st.metric(
        "Blocked",
        blocked,
    )


with metric4:
    block_rate = (
        (blocked / total) * 100
        if total
        else 0
    )

    st.metric(
        "Block Rate",
        f"{block_rate:.1f}%",
    )


# ============================================================
# LATEST SECURITY DECISION
# ============================================================

st.markdown(
    '<div class="section-title">'
    "Latest Security Decision"
    "</div>",
    unsafe_allow_html=True,
)


if decisions:

    latest = decisions[0]

    decision = latest.get(
        "decision",
        "UNKNOWN",
    )

    command = latest.get(
        "command_type",
        "UNKNOWN",
    )

    value = latest.get("value")
    unit = latest.get("unit") or ""

    reason = latest.get(
        "reason",
        "No reason provided",
    )

    rule = latest.get(
        "rule_triggered",
        "unknown",
    )

    state_before = latest.get(
        "state_before",
        "UNKNOWN",
    )

    state_after = latest.get(
        "state_after",
        "UNKNOWN",
    )

    command_id = latest.get(
        "command_id",
        "unknown",
    )

    source_id = latest.get(
        "source_id",
        "unknown",
    )

    session_id = latest.get(
        "session_id",
        "unknown",
    )

    received_at = latest.get(
        "received_at",
        "unknown",
    )

    st.markdown(
        styles.decision_hero(decision, reason, session_id),
        unsafe_allow_html=True,
    )


    col1, col2, col3, col4 = st.columns(4)


    with col1:
        st.metric(
            "Command",
            command,
        )


    with col2:
        if value is not None:
            requested_value = f"{value} {unit}"
        else:
            requested_value = "—"

        st.metric(
            "Requested Value",
            requested_value,
        )


    with col3:
        st.metric(
            "State",
            f"{state_before} → {state_after}",
        )


    with col4:
        st.metric(
            "Source",
            source_id,
        )


    with st.expander("Technical details"):
        st.caption(
            f"Rule triggered: `{rule}` | "
            f"Command ID: `{command_id}` | "
            f"Session: `{session_id}` | "
            f"Received: `{received_at}`"
        )

        st.json(latest)

else:
    st.warning(
        "No security decisions available."
    )


st.divider()


# ============================================================
# CHARGING SESSION HEALTH
# ============================================================

st.markdown(
    '<div class="section-title">'
    "Charging Session Health"
    "</div>",
    unsafe_allow_html=True,
)


if session:

    if session_fallback:
        st.caption(
            f"Session `{active_session_id}` is unavailable; "
            f"showing `{DEMO_SESSION_ID}`."
        )

    if not session_fallback:
        origin = (
            "from your last scenario run"
            if "active_session_id" in st.session_state
            else "default demo session"
        )
        st.caption(f"Showing session: `{show(session.get('session_id'))}` ({origin})")

    session_col1, session_col2 = st.columns(2)


    with session_col1:

        state = show(session.get("state"))

        st.markdown(
            '<div class="pills">'
            + styles.pill("Session: " + str(show(session.get("session_id"))), "info")
            + styles.pill("Vehicle: " + str(show(session.get("vehicle_id"))), "neutral")
            + styles.state_pill(state)
            + "</div>",
            unsafe_allow_html=True,
        )

        limit1, limit2 = st.columns(2)

        with limit1:
            st.metric(
                "Maximum Power",
                f"{show(session.get('max_power_kw'))} kW",
            )

        with limit2:
            st.metric(
                "Maximum Current",
                f"{show(session.get('max_current_a'))} A",
            )


    with session_col2:

        physical = session.get("physical") or {}

        p1, p2 = st.columns(2)


        with p1:
            st.metric(
                "Plugged In",
                "YES"
                if physical.get("plugged_in")
                else "NO",
            )


        with p2:
            st.metric(
                "Charging",
                "YES"
                if physical.get("charging")
                else "NO",
            )


        p3, p4 = st.columns(2)


        with p3:
            st.metric(
                "Current Power",
                f"{show(physical.get('power_kw'))} kW",
            )


        with p4:
            st.metric(
                "Current",
                f"{show(physical.get('current_a'))} A",
            )


        for label, used, limit, unit_label in (
            ("Power", physical.get("power_kw"), session.get("max_power_kw"), "kW"),
            ("Current", physical.get("current_a"), session.get("max_current_a"), "A"),
        ):
            if (
                isinstance(used, (int, float))
                and isinstance(limit, (int, float))
                and limit > 0
            ):
                st.progress(
                    min(max(used / limit, 0.0), 1.0),
                    text=f"{label}: {number(used)} of {number(limit)} {unit_label}",
                )


        st.caption(
            f"Last command: "
            f"`{show(physical.get('last_command'))}`"
        )

    with st.expander("Technical details"):
        st.json(session)

else:
    st.warning(
        "Session information unavailable."
    )


st.divider()


# ============================================================
# AUDIT FILTERS
# ============================================================

st.markdown(
    '<div class="section-title">'
    "Audit Trail"
    "</div>",
    unsafe_allow_html=True,
)

st.caption(
    "Filter security decisions by decision type, command and rule."
)


decision_options = [
    "ALL",
    "ALLOW",
    "BLOCK",
]


command_options = sorted(
    {
        item.get("command_type")
        for item in decisions
        if item.get("command_type")
    }
)

command_options = [
    "ALL"
] + command_options


rule_options = sorted(
    {
        item.get("rule_triggered")
        for item in decisions
        if item.get("rule_triggered")
    }
)

rule_options = [
    "ALL"
] + rule_options


filter1, filter2, filter3 = st.columns(3)


with filter1:
    selected_decision = st.selectbox(
        "Decision",
        decision_options,
    )


with filter2:
    selected_command = st.selectbox(
        "Command",
        command_options,
    )


with filter3:
    selected_rule = st.selectbox(
        "Rule",
        rule_options,
    )


filtered_decisions = []


for item in decisions:

    if (
        selected_decision != "ALL"
        and item.get("decision")
        != selected_decision
    ):
        continue


    if (
        selected_command != "ALL"
        and item.get("command_type")
        != selected_command
    ):
        continue


    if (
        selected_rule != "ALL"
        and item.get("rule_triggered")
        != selected_rule
    ):
        continue


    filtered_decisions.append(item)


# ============================================================
# AUDIT TABLE
# ============================================================

audit_rows = []


for item in filtered_decisions:

    value = item.get("value")
    unit = item.get("unit") or ""


    if value is not None:
        formatted_value = (
            f"{value} {unit}"
        )
    else:
        formatted_value = "—"


    audit_rows.append(
        {
            "Time": item.get(
                "received_at",
                "—",
            ),
            "Command": item.get(
                "command_type",
                "—",
            ),
            "Value": formatted_value,
            "Decision": item.get(
                "decision",
                "—",
            ),
            "Rule": item.get(
                "rule_triggered",
                "—",
            ),
            "Reason": item.get(
                "reason",
                "—",
            ),
        }
    )


if audit_rows:

    st.markdown(
        styles.table(
            ["Time", "Command", "Value", "Decision", "Rule", "Reason"],
            [
                [
                    styles.esc(row["Time"]),
                    styles.esc(row["Command"]),
                    styles.esc(row["Value"]),
                    styles.decision_pill(row["Decision"]),
                    styles.code(row["Rule"]),
                    styles.esc(row["Reason"]),
                ]
                for row in audit_rows
            ],
        ),
        unsafe_allow_html=True,
    )


    csv_data = build_csv(
        audit_rows
    )


    st.download_button(
        label="⬇️ Download Audit CSV",
        data=csv_data,
        file_name="evguard_audit.csv",
        mime="text/csv",
    )

else:

    st.info(
        "No audit events match the selected filters."
    )


# ============================================================
# FOOTER
# ============================================================

st.divider()

st.caption(
    "EVGuard Prototype | "
    f"{MODE_LABEL} | "
    "Security decisions are fail-closed."
)
