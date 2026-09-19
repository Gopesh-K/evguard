"""Policy engine stub for EVGuard."""


def check_limits(command: dict, session: dict) -> tuple[bool, str, str]:
    """Returns (ok, rule_id, reason).

    SET_POWER vs max_power_kw; SET_CURRENT vs max_current_a.
    Other commands -> (True, "ok", "").
    """
    raise NotImplementedError("TODO: implement check_limits")

