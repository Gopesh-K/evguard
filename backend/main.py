"""FastAPI application for EVGuard security gateway."""

from fastapi import FastAPI, HTTPException, Query, status
from fastapi.responses import JSONResponse

from backend.schemas import CommandIn
from contract.evguard_contract import CONTRACT_VERSION
from core.decision import Gateway

app = FastAPI(
    title="EVGuard API",
    description="State-aware security gateway for EV charging commands",
    version=CONTRACT_VERSION,
)

gateway = Gateway()


@app.get("/health")
def get_health() -> dict:
    """Service health check and contract version verification."""
    return {"status": "ok", "contract_version": CONTRACT_VERSION}


@app.post("/command")
def post_command(cmd: CommandIn) -> dict:
    """Submit a command through EVGuard.

    Fails closed: returns 501 while engine is not implemented.
    """
    try:
        return gateway.handle(cmd.to_command())
    except NotImplementedError:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="engine not implemented",
        )


@app.get("/commands")
def get_commands(limit: int = Query(default=50, ge=1)) -> dict:
    """Retrieve recent decisions, newest first. Limit capped at 200."""
    capped_limit = min(limit, 200)
    try:
        items = gateway.recent_decisions(limit=capped_limit)
        return {"items": items}
    except NotImplementedError:
        return {"items": []}


@app.get("/commands/{command_id}")
def get_command(command_id: str) -> dict:
    """Retrieve a single decision by command_id."""
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Command not found",
    )


@app.get("/sessions/{session_id}")
def get_session(session_id: str) -> dict:
    """Retrieve session state and limits."""
    try:
        session = gateway.get_session(session_id)
        if session is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Session '{session_id}' not found",
            )
        return session
    except NotImplementedError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session '{session_id}' not found",
        )


@app.post("/sessions")
def post_session(session_def: dict) -> dict:
    """Create or reset a charging session.

    Fails closed: returns 501 while engine is not implemented.
    """
    try:
        return gateway.create_session(session_def)
    except NotImplementedError:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="engine not implemented",
        )


@app.get("/stats")
def get_stats() -> dict:
    """Retrieve global allow/block decision statistics."""
    try:
        return gateway.stats()
    except NotImplementedError:
        return {"total": 0, "allowed": 0, "blocked": 0}


@app.get("/scenarios")
def get_scenarios() -> dict:
    """List available demo scenarios."""
    return {"items": []}


@app.post("/scenarios/{name}")
def post_scenario(name: str) -> dict:
    """Run a named scenario against the simulator (stubs return 404)."""
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Scenario '{name}' not found",
    )


@app.post("/baseline/command")
def post_baseline_command(cmd: CommandIn) -> dict:
    """Send a command to the unprotected baseline controller.

    Fails closed: returns 501 while engine is not implemented.
    """
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="engine not implemented",
    )

