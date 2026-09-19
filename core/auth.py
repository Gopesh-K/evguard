"""Authentication engine stub for EVGuard."""


def authenticate(command: dict) -> tuple[bool, str, str, str | None]:
    """Authenticate command sender and token.

    Returns (ok, rule_id, reason, role).
    """
    raise NotImplementedError("TODO: implement authenticate")

