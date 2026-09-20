import csv
import io

import streamlit as st

import api_client


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

st.markdown(
    """
    <style>
        .main-title {
            font-size: 2.5rem;
            font-weight: 750;
            margin-bottom: 0.1rem;
        }

        .subtitle {
            color: #8b949e;
            font-size: 1rem;
            margin-bottom: 1.5rem;
        }

        .decision-card {
            padding: 1.2rem;
            border-radius: 12px;
            margin-bottom: 1rem;
        }

        .block-card {
            background: rgba(255, 70, 70, 0.12);
            border: 1px solid rgba(255, 70, 70, 0.35);
        }

        .allow-card {
            background: rgba(40, 200, 120, 0.12);
            border: 1px solid rgba(40, 200, 120, 0.35);
        }

        .decision-title {
            font-size: 1.5rem;
            font-weight: 700;
        }

        .section-title {
            font-size: 1.35rem;
            font-weight: 650;
            margin-top: 0.7rem;
        }
    </style>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def decision_icon(decision):
    if decision == "ALLOW":
        return "✅"

    if decision == "BLOCK":
        return "⛔"

    return "⚠️"


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

    return output.getvalue().encode("utf-8")


# ============================================================
# LOAD DATA
# ============================================================

health = api_client.health()
stats = api_client.get_stats()
session = api_client.get_session("sess_demo")
decisions_data = api_client.get_decisions(limit=50)
scenarios_data = api_client.list_scenarios()


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
# HEADER
# ============================================================

st.markdown(
    '<div class="main-title">'
    "🔐 EVGuard — Charging Security Dashboard"
    "</div>",
    unsafe_allow_html=True,
)

st.markdown(
    '<div class="subtitle">'
    "EV charging command security gateway | "
    "Decision monitoring, session health and audit trail"
    "</div>",
    unsafe_allow_html=True,
)


# ============================================================
# SYSTEM STATUS
# ============================================================

status_col1, status_col2, status_col3 = st.columns(3)


with status_col1:
    if health and health.get("status") == "ok":
        st.success("🟢 EVGuard Gateway Online")
    else:
        st.error("🔴 EVGuard Gateway Offline")


with status_col2:
    contract_version = (
        health.get("contract_version", "unknown")
        if health
        else "unknown"
    )

    st.info(
        f"Contract Version: **{contract_version}**"
    )


with status_col3:
    if api_client.MOCK_MODE:
        st.info("Mode: **MOCK**")
    else:
        st.info("Mode: **LIVE**")


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

    if decision == "ALLOW":
        card_class = "allow-card"
    else:
        card_class = "block-card"

    st.markdown(
        f"""
        <div class="decision-card {card_class}">
            <div class="decision-title">
                {decision_icon(decision)} {decision}
            </div>
        </div>
        """,
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


    if decision == "BLOCK":
        st.error(
            f"**Block reason:** {reason}"
        )
    else:
        st.success(
            f"**Decision reason:** {reason}"
        )


    st.caption(
        f"Rule triggered: `{rule}` | "
        f"Command ID: `{command_id}` | "
        f"Session: `{session_id}` | "
        f"Received: `{received_at}`"
    )

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

    session_col1, session_col2 = st.columns(2)


    with session_col1:

        st.write(
            f"**Session:** "
            f"`{session.get('session_id', '—')}`"
        )

        st.write(
            f"**Vehicle:** "
            f"`{session.get('vehicle_id', '—')}`"
        )

        state = session.get(
            "state",
            "UNKNOWN",
        )

        if state == "CHARGING":
            st.success(
                f"⚡ State: **{state}**"
            )
        elif state == "STOPPED":
            st.warning(
                f"⏹️ State: **{state}**"
            )
        else:
            st.info(
                f"State: **{state}**"
            )

        st.write(
            f"**Maximum Power:** "
            f"{session.get('max_power_kw', '—')} kW"
        )

        st.write(
            f"**Maximum Current:** "
            f"{session.get('max_current_a', '—')} A"
        )


    with session_col2:

        physical = session.get(
            "physical",
            {},
        )

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
                f"{physical.get('power_kw', 0)} kW",
            )


        with p4:
            st.metric(
                "Current",
                f"{physical.get('current_a', 0)} A",
            )


        st.caption(
            f"Last command: "
            f"`{physical.get('last_command', '—')}`"
        )

else:
    st.warning(
        "Session information unavailable."
    )


st.divider()


# ============================================================
# SCENARIO TESTING
# ============================================================

st.markdown(
    '<div class="section-title">'
    "Scenario Testing"
    "</div>",
    unsafe_allow_html=True,
)

st.caption(
    "Run controlled security scenarios against the mock EVGuard gateway."
)


if scenarios_data:

    scenarios = scenarios_data.get(
        "items",
        [],
    )


    for start in range(
        0,
        len(scenarios),
        4,
    ):

        row = scenarios[
            start:start + 4
        ]

        columns = st.columns(4)


        for index, scenario in enumerate(row):

            name = scenario.get(
                "name",
                "",
            )

            title = scenario.get(
                "title",
                name,
            )


            with columns[index]:

                if st.button(
                    title,
                    key=f"scenario_{name}",
                    use_container_width=True,
                ):

                    with st.spinner(
                        f"Running {title}..."
                    ):

                        result = (
                            api_client.run_scenario(
                                name
                            )
                        )

                    st.session_state[
                        "scenario_result"
                    ] = result

                    st.session_state[
                        "scenario_name"
                    ] = name


    scenario_result = st.session_state.get(
        "scenario_result"
    )

    scenario_name = st.session_state.get(
        "scenario_name"
    )


    if scenario_result:

        st.markdown("---")

        st.write(
            f"**Last scenario:** "
            f"`{scenario_name}`"
        )

        passed = scenario_result.get(
            "passed",
            False,
        )


        if passed:
            st.success(
                "✅ Scenario completed successfully."
            )
        else:
            st.error(
                "⛔ Scenario failed."
            )


        results = scenario_result.get(
            "results",
            [],
        )


        if results:

            for result in results:

                expected = result.get(
                    "expect",
                    "—",
                )

                expected_rule = result.get(
                    "expect_rule",
                    "—",
                )

                result_passed = result.get(
                    "passed",
                    False,
                )


                if result_passed:
                    icon = "✅"
                else:
                    icon = "❌"


                st.write(
                    f"{icon} "
                    f"Step {result.get('step', '—')} "
                    f"| Expected: `{expected}` "
                    f"| Rule: `{expected_rule}`"
                )


                decision_data = result.get(
                    "decision",
                    {},
                )


                if decision_data:

                    st.caption(
                        f"Actual: "
                        f"`{decision_data.get('decision', '—')}` "
                        f"| "
                        f"`{decision_data.get('rule_triggered', '—')}` "
                        f"| "
                        f"{decision_data.get('reason', '')}"
                    )

else:
    st.info(
        "No scenarios available."
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

    st.dataframe(
        audit_rows,
        use_container_width=True,
        hide_index=True,
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
    "Mock data mode | "
    "Security decisions are fail-closed."
)
import io

import streamlit as st

import api_client


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

st.markdown(
    """
    <style>
        .main-title {
            font-size: 2.5rem;
            font-weight: 750;
            margin-bottom: 0.1rem;
        }

        .subtitle {
            color: #8b949e;
            font-size: 1rem;
            margin-bottom: 1.5rem;
        }

        .decision-card {
            padding: 1.2rem;
            border-radius: 12px;
            margin-bottom: 1rem;
        }

        .block-card {
            background: rgba(255, 70, 70, 0.12);
            border: 1px solid rgba(255, 70, 70, 0.35);
        }

        .allow-card {
            background: rgba(40, 200, 120, 0.12);
            border: 1px solid rgba(40, 200, 120, 0.35);
        }

        .decision-title {
            font-size: 1.5rem;
            font-weight: 700;
        }

        .section-title {
            font-size: 1.35rem;
            font-weight: 650;
            margin-top: 0.7rem;
        }
    </style>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def decision_icon(decision):
    if decision == "ALLOW":
        return "✅"

    if decision == "BLOCK":
        return "⛔"

    return "⚠️"


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

    return output.getvalue().encode("utf-8")


# ============================================================
# LOAD DATA
# ============================================================

health = api_client.health()
stats = api_client.get_stats()
session = api_client.get_session("sess_demo")
decisions_data = api_client.get_decisions(limit=50)
scenarios_data = api_client.list_scenarios()


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
# HEADER
# ============================================================

st.markdown(
    '<div class="main-title">'
    "🔐 EVGuard — Charging Security Dashboard"
    "</div>",
    unsafe_allow_html=True,
)

st.markdown(
    '<div class="subtitle">'
    "EV charging command security gateway | "
    "Decision monitoring, session health and audit trail"
    "</div>",
    unsafe_allow_html=True,
)


# ============================================================
# SYSTEM STATUS
# ============================================================

status_col1, status_col2, status_col3 = st.columns(3)


with status_col1:
    if health and health.get("status") == "ok":
        st.success("🟢 EVGuard Gateway Online")
    else:
        st.error("🔴 EVGuard Gateway Offline")


with status_col2:
    contract_version = (
        health.get("contract_version", "unknown")
        if health
        else "unknown"
    )

    st.info(
        f"Contract Version: **{contract_version}**"
    )


with status_col3:
    if api_client.MOCK_MODE:
        st.info("Mode: **MOCK**")
    else:
        st.info("Mode: **LIVE**")


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

    if decision == "ALLOW":
        card_class = "allow-card"
    else:
        card_class = "block-card"

    st.markdown(
        f"""
        <div class="decision-card {card_class}">
            <div class="decision-title">
                {decision_icon(decision)} {decision}
            </div>
        </div>
        """,
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


    if decision == "BLOCK":
        st.error(
            f"**Block reason:** {reason}"
        )
    else:
        st.success(
            f"**Decision reason:** {reason}"
        )


    st.caption(
        f"Rule triggered: `{rule}` | "
        f"Command ID: `{command_id}` | "
        f"Session: `{session_id}` | "
        f"Received: `{received_at}`"
    )

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

    session_col1, session_col2 = st.columns(2)


    with session_col1:

        st.write(
            f"**Session:** "
            f"`{session.get('session_id', '—')}`"
        )

        st.write(
            f"**Vehicle:** "
            f"`{session.get('vehicle_id', '—')}`"
        )

        state = session.get(
            "state",
            "UNKNOWN",
        )

        if state == "CHARGING":
            st.success(
                f"⚡ State: **{state}**"
            )
        elif state == "STOPPED":
            st.warning(
                f"⏹️ State: **{state}**"
            )
        else:
            st.info(
                f"State: **{state}**"
            )

        st.write(
            f"**Maximum Power:** "
            f"{session.get('max_power_kw', '—')} kW"
        )

        st.write(
            f"**Maximum Current:** "
            f"{session.get('max_current_a', '—')} A"
        )


    with session_col2:

        physical = session.get(
            "physical",
            {},
        )

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
                f"{physical.get('power_kw', 0)} kW",
            )


        with p4:
            st.metric(
                "Current",
                f"{physical.get('current_a', 0)} A",
            )


        st.caption(
            f"Last command: "
            f"`{physical.get('last_command', '—')}`"
        )

else:
    st.warning(
        "Session information unavailable."
    )


st.divider()


# ============================================================
# SCENARIO TESTING
# ============================================================

st.markdown(
    '<div class="section-title">'
    "Scenario Testing"
    "</div>",
    unsafe_allow_html=True,
)

st.caption(
    "Run controlled security scenarios against the mock EVGuard gateway."
)


if scenarios_data:

    scenarios = scenarios_data.get(
        "items",
        [],
    )


    for start in range(
        0,
        len(scenarios),
        4,
    ):

        row = scenarios[
            start:start + 4
        ]

        columns = st.columns(4)


        for index, scenario in enumerate(row):

            name = scenario.get(
                "name",
                "",
            )

            title = scenario.get(
                "title",
                name,
            )


            with columns[index]:

                if st.button(
                    title,
                    key=f"scenario_{name}",
                    use_container_width=True,
                ):

                    with st.spinner(
                        f"Running {title}..."
                    ):

                        result = (
                            api_client.run_scenario(
                                name
                            )
                        )

                    st.session_state[
                        "scenario_result"
                    ] = result

                    st.session_state[
                        "scenario_name"
                    ] = name


    scenario_result = st.session_state.get(
        "scenario_result"
    )

    scenario_name = st.session_state.get(
        "scenario_name"
    )


    if scenario_result:

        st.markdown("---")

        st.write(
            f"**Last scenario:** "
            f"`{scenario_name}`"
        )

        passed = scenario_result.get(
            "passed",
            False,
        )


        if passed:
            st.success(
                "✅ Scenario completed successfully."
            )
        else:
            st.error(
                "⛔ Scenario failed."
            )


        results = scenario_result.get(
            "results",
            [],
        )


        if results:

            for result in results:

                expected = result.get(
                    "expect",
                    "—",
                )

                expected_rule = result.get(
                    "expect_rule",
                    "—",
                )

                result_passed = result.get(
                    "passed",
                    False,
                )


                if result_passed:
                    icon = "✅"
                else:
                    icon = "❌"


                st.write(
                    f"{icon} "
                    f"Step {result.get('step', '—')} "
                    f"| Expected: `{expected}` "
                    f"| Rule: `{expected_rule}`"
                )


                decision_data = result.get(
                    "decision",
                    {},
                )


                if decision_data:

                    st.caption(
                        f"Actual: "
                        f"`{decision_data.get('decision', '—')}` "
                        f"| "
                        f"`{decision_data.get('rule_triggered', '—')}` "
                        f"| "
                        f"{decision_data.get('reason', '')}"
                    )

else:
    st.info(
        "No scenarios available."
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

    st.dataframe(
        audit_rows,
        use_container_width=True,
        hide_index=True,
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
    "Mock data mode | "
    "Security decisions are fail-closed."
)