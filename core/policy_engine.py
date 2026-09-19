"""Policy engine for EVGuard: checks requested values against session limits."""


def check_limits(command: dict, session: dict) -> tuple[bool, str, str]:
    """Returns (ok, rule_id, reason).

    SET_POWER vs max_power_kw; SET_CURRENT vs max_current_a.
    Other commands -> (True, "ok", "").
    """
    command_type = command.get("command_type")
    value = command.get("value")

    # Each command is compared only against its own limit, so kW and A never mix.
    if command_type == "SET_POWER" and value > session["max_power_kw"]:
        return (False, "policy.power_limit",
                f"Requested power {value} kW exceeds session maximum of "
                f"{session['max_power_kw']} kW")

    if command_type == "SET_CURRENT" and value > session["max_current_a"]:
        return (False, "policy.current_limit",
                f"Requested current {value} A exceeds session maximum of "
                f"{session['max_current_a']} A")

    return True, "ok", ""
