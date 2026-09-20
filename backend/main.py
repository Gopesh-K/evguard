"""FastAPI application for EVGuard security gateway."""

import logging
from types import SimpleNamespace

from fastapi import FastAPI, HTTPException, Query, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from backend.schemas import CommandIn
from config.loader import load_policy
from contract.evguard_contract import CONTRACT_VERSION
from core.decision import Gateway

app = FastAPI(
    title="EVGuard API",
    description="State-aware security gateway for EV charging commands",
    version=CONTRACT_VERSION,
)


@app.exception_handler(RequestValidationError)
def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Return 422 with only type, loc and msg for each error.

    FastAPI's default response echoes the submitted input, which can hold the
    auth_token and crashes with a 500 on NaN. "input" and "ctx" are dropped.
    """
    errors = [{"type": e["type"], "loc": list(e["loc"]), "msg": e["msg"]} for e in exc.errors()]
    return JSONResponse(status_code=422, content={"detail": errors})


logger =logging.getLogger("uvicorn.error")

# Fail closed: an invalid config raises here and the app does not start.
policy = load_policy()


def load_simulator() -> tuple[SimpleNamespace | None, str]:
    """Try to import Role 2's simulator package.

    Returns (namespace, mode_message). The namespace is None when the import
    fails, and the app then runs standalone with the scenario and baseline
    endpoints stubbed.
    """
    try:
        from simulator.baseline import baseline_apply
        from simulator.ev_simulator import ChargerSimulator
        from simulator.scenarios import list_scenarios, run_scenario
    except ImportError as e:
        return None, f"standalone, no simulator ({e})"
    return SimpleNamespace(
        ChargerSimulator=ChargerSimulator,
        list_scenarios=list_scenarios,
        run_scenario=run_scenario,
        baseline_apply=baseline_apply,
    ), "integrated, simulator attached"


sim, _mode = load_simulator()
logger.info("EVGuard mode: %s", _mode)


def seed_demo_session(gw: Gateway) -> dict:
    """Create (or reset) the demo session sess_demo using the configured defaults."""
    return gw.create_session({
        "session_id": "sess_demo",
        "vehicle_id": "Vehicle-01",
        "max_power_kw": policy["defaults"]["max_power_kw"],
        "max_current_a": policy["defaults"]["max_current_a"],
    })


gateway = Gateway(simulator=sim.ChargerSimulator() if sim else None)
seed_demo_session(gateway)


@app.get("/health")
def get_health() -> dict:
    """Service health check and contract version verification."""
    return {"status": "ok", "contract_version": CONTRACT_VERSION}


@app.post("/command")
def post_command(cmd: CommandIn) -> dict:
    """Submit a command through EVGuard and return its decision."""
    return gateway.handle(cmd.to_command())


@app.get("/commands")
def get_commands(limit: int = Query(default=50, ge=1)) -> dict:
    """Retrieve recent decisions, newest first. Limit capped at 200."""
    return {"items": gateway.recent_decisions(limit=min(limit, 200))}


@app.get("/commands/{command_id}")
def get_command(command_id: str) -> dict:
    """Retrieve a single decision by command_id."""
    decision = gateway.get_decision(command_id)
    if decision is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Command not found",
        )
    return decision


@app.get("/sessions/{session_id}")
def get_session(session_id: str) -> dict:
    """Retrieve session state and limits."""
    session = gateway.get_session(session_id)
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session '{session_id}' not found",
        )
    return session


@app.post("/sessions")
def post_session(session_def: dict) -> dict:
    """Create or reset a charging session."""
    try:
        return gateway.create_session(session_def)
    except ValueError as e:
        raise HTTPException(
            status_code=422,
            detail=str(e),
        )


@app.get("/stats")
def get_stats() -> dict:
    """Retrieve global allow/block decision statistics."""
    return gateway.stats()


@app.get("/scenarios")
def get_scenarios() -> dict:
    """List available demo scenarios (empty until the simulator is integrated)."""
    if sim is None:
        return {"items": []}
    return {"items": sim.list_scenarios()}


@app.post("/scenarios/{name}")
def post_scenario(name: str) -> dict:
    """Run a named scenario through the gateway.

    404 if the name is unknown or there is no simulator; 422 if the scenario
    itself is invalid (ValueError while running).
    """
    if sim is None or name not in [s["name"] for s in sim.list_scenarios()]:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Scenario '{name}' not found",
        )
    try:
        return sim.run_scenario(name, gateway.handle, gateway.create_session)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


@app.post("/baseline/command")
def post_baseline_command(cmd: CommandIn) -> dict:
    """Send a command to the unprotected baseline controller (501 without a simulator)."""
    if sim is not None:
        return sim.baseline_apply(cmd.to_command())
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="engine not implemented",
    )
