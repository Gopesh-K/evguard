"""Authentication for EVGuard: checks the source_id and token pair."""

import hmac

from contract.evguard_contract import DEMO_SOURCES


def _tokens_match(supplied: str, expected: str) -> bool:
    # Constant-time comparison so response timing does not leak the token.
    return hmac.compare_digest(supplied.encode("utf-8"), expected.encode("utf-8"))


def authenticate(command: dict) -> tuple[bool, str, str, str | None]:
    """Authenticate command sender and token.

    Returns (ok, rule_id, reason, role). The token is never logged or returned.
    """
    source_id = command.get("source_id")
    token = command.get("auth_token")

    if not isinstance(token, str) or not token:
        return False, "auth.missing_token", "No authentication token supplied", None

    source = DEMO_SOURCES.get(source_id)
    if source is None:
        return False, "auth.invalid_token", f"Unknown source '{source_id}' or invalid token", None

    if _tokens_match(token, source["token"]):
        return True, "ok", "", source["role"]

    # Token is wrong for this source; does it belong to some other source?
    for other_id, other in DEMO_SOURCES.items():
        if other_id != source_id and _tokens_match(token, other["token"]):
            return (False, "auth.source_mismatch",
                    f"Token does not belong to source '{source_id}'", None)

    return False, "auth.invalid_token", "Invalid authentication token", None
