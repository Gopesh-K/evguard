"""Authorization engine stub for EVGuard."""


def authorize(role: str, command_type: str) -> tuple[bool, str, str]:
    """Authorize role for command_type using ROLE_PERMISSIONS.

    Returns (ok, rule_id, reason).
    """
    raise NotImplementedError("TODO: implement authorize")

