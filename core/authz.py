"""Authorization for EVGuard: checks a role may issue a command."""

from contract.evguard_contract import ROLE_PERMISSIONS


def authorize(role: str, command_type: str) -> tuple[bool, str, str]:
    """Authorize role for command_type using ROLE_PERMISSIONS.

    Returns (ok, rule_id, reason).
    """
    if command_type in ROLE_PERMISSIONS.get(role, []):
        return True, "ok", ""
    return (False, "authz.command_not_permitted",
            f"Role '{role}' is not permitted to issue {command_type}")
