"""EFP reservation tools — wrap the Flask API via HTTP.

Architectural Guardrail #2: Tools wrap the Flask API; they never bypass it.
These tools call the existing /api/reservations/* endpoints over HTTP.
They never re-implement capacity validation, block checking, or room
assignment — all business rules live in the Flask app + utils.

Each tool returns a dict (success or error) that the LLM can use to
compose its response. The tool definitions (JSON schema) are exported
as EFP_TOOLS for the Ollama /api/chat "tools" parameter.
"""
from __future__ import annotations

import logging
import os
from typing import Any

import requests

logger = logging.getLogger(__name__)

# The Flask app runs on port 5000 in development.
FLASK_BASE_URL = os.environ.get("FLASK_BASE_URL", "http://localhost:5000")
FLASK_TIMEOUT = int(os.environ.get("FLASK_TIMEOUT", "30"))


# ---------------------------------------------------------------------------
# Tool definitions (JSON schema for Ollama /api/chat "tools" parameter)
# ---------------------------------------------------------------------------

EFP_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_locations",
            "description": (
                "Get all EFP restaurant locations with their IDs, codes (JPN, ITA, ESP), "
                "names, and guest/reservation limits. Call this first when a guest wants to "
                "make a reservation but hasn't specified which location."
            ),
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "check_availability",
            "description": (
                "Check available dining time slots for a specific location and date. "
                "Returns each time slot with availability status, slots left, and guests "
                "available. Use this when a guest asks about availability for a given date "
                "and location."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "location_id": {
                        "type": "integer",
                        "description": "The numeric ID of the location (from get_locations).",
                    },
                    "date": {
                        "type": "string",
                        "description": "The date to check, in YYYY-MM-DD format.",
                    },
                },
                "required": ["location_id", "date"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_reservation",
            "description": (
                "Create a new reservation. Call this ONLY after confirming all required "
                "details with the guest: location, date, time, party size, name, and email. "
                "Party size must be between 1 and 12. If party size > 12, do NOT call this "
                "tool — tell the guest to call the restaurant instead."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "location_id": {
                        "type": "integer",
                        "description": "The numeric ID of the location.",
                    },
                    "date": {
                        "type": "string",
                        "description": "Reservation date in YYYY-MM-DD format.",
                    },
                    "time": {
                        "type": "string",
                        "description": "Reservation time in HH:MM format (24-hour).",
                    },
                    "party_size": {
                        "type": "integer",
                        "description": "Number of guests (1-12). Must NOT exceed 12.",
                    },
                    "name": {
                        "type": "string",
                        "description": "Guest's full name.",
                    },
                    "email": {
                        "type": "string",
                        "description": "Guest's email address.",
                    },
                    "phone": {
                        "type": "string",
                        "description": "Guest's phone number (optional).",
                    },
                    "special_requests": {
                        "type": "string",
                        "description": "Any special requests (optional).",
                    },
                },
                "required": ["location_id", "date", "time", "party_size", "name", "email"],
            },
        },
    },
]


# ---------------------------------------------------------------------------
# Tool implementations (call Flask API over HTTP)
# ---------------------------------------------------------------------------


def get_locations() -> dict[str, Any]:
    """Get all EFP locations via GET /api/reservations/locations."""
    try:
        resp = requests.get(
            f"{FLASK_BASE_URL}/api/reservations/locations",
            timeout=FLASK_TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()
        locations = data.get("locations", [])
        return {
            "success": True,
            "locations": [
                {
                    "id": loc["id"],
                    "code": loc["code"],
                    "name": loc["name"],
                    "timezone": loc["timezone"],
                    "max_guests_per_slot": loc["max_guests_per_slot"],
                    "max_reservations_per_slot": loc["max_reservations_per_slot"],
                }
                for loc in locations
            ],
        }
    except requests.RequestException as exc:
        logger.error("get_locations failed: %s", exc)
        return {"success": False, "error": f"Could not reach the reservation system: {exc}"}


def check_availability(location_id: int, date: str) -> dict[str, Any]:
    """Check availability via GET /api/reservations/availability."""
    try:
        resp = requests.get(
            f"{FLASK_BASE_URL}/api/reservations/availability",
            params={"location_id": location_id, "date": date},
            timeout=FLASK_TIMEOUT,
        )
        if resp.status_code == 400:
            return {"success": False, "error": resp.json().get("error", "Invalid request")}
        resp.raise_for_status()
        data = resp.json()
        slots = data.get("slots", [])
        # Summarize: only show available slots, with a count
        available_slots = [s for s in slots if s.get("available")]
        return {
            "success": True,
            "date": data.get("date", date),
            "total_slots": len(slots),
            "available_count": len(available_slots),
            "available_slots": [
                {
                    "time": s["time"],
                    "slots_left": s.get("slotsLeft", 0),
                    "guests_available": s.get("guestsAvailable", 0),
                }
                for s in available_slots
            ],
        }
    except requests.RequestException as exc:
        logger.error("check_availability failed: %s", exc)
        return {"success": False, "error": f"Could not check availability: {exc}"}


def create_reservation(
    location_id: int,
    date: str,
    time: str,
    party_size: int,
    name: str,
    email: str,
    phone: str | None = None,
    special_requests: str | None = None,
) -> dict[str, Any]:
    """Create a reservation via POST /api/reservations/."""
    # Client-side guardrail: never send party_size > 12 to the API.
    if party_size > 12:
        return {
            "success": False,
            "error": "Party size exceeds 12. The guest must call the restaurant directly.",
            "requires_call": True,
        }

    payload: dict[str, Any] = {
        "location_id": location_id,
        "date": date,
        "time": time,
        "party_size": party_size,
        "name": name,
        "email": email,
    }
    if phone:
        payload["phone"] = phone
    if special_requests:
        payload["special_requests"] = special_requests

    try:
        resp = requests.post(
            f"{FLASK_BASE_URL}/api/reservations/",
            json=payload,
            timeout=FLASK_TIMEOUT,
        )
        if resp.status_code == 201:
            data = resp.json()
            return {
                "success": True,
                "reservation_id": data.get("id"),
                "reservation_number": data.get("reservationNumber"),
                "message": data.get("message"),
                "room": data.get("room"),
            }
        else:
            error_data = resp.json()
            return {
                "success": False,
                "error": error_data.get("error", "Reservation failed"),
                "requires_call": error_data.get("requiresCall", False),
            }
    except requests.RequestException as exc:
        logger.error("create_reservation failed: %s", exc)
        return {"success": False, "error": f"Could not create reservation: {exc}"}


# ---------------------------------------------------------------------------
# Tool dispatcher — maps tool name to function
# ---------------------------------------------------------------------------

TOOL_FUNCTIONS = {
    "get_locations": get_locations,
    "check_availability": check_availability,
    "create_reservation": create_reservation,
}


def execute_tool(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    """Execute a tool by name with the given arguments. Returns a result dict."""
    func = TOOL_FUNCTIONS.get(name)
    if func is None:
        return {"success": False, "error": f"Unknown tool: {name}"}
    import time as _time
    t0 = _time.time()
    try:
        result = func(**arguments)
        latency = int((_time.time() - t0) * 1000)
        # Trace the tool call.
        try:
            from tracing import get_tracer
            get_tracer().trace_tool_call(
                name=name,
                arguments=arguments,
                success=result.get("success", True),
                latency_ms=latency,
                result_summary=str(result.get("error", "")) if not result.get("success", True) else "",
            )
        except Exception:
            pass
        return result
    except TypeError as exc:
        return {"success": False, "error": f"Invalid arguments for {name}: {exc}"}
    except Exception as exc:
        logger.error("Tool %s raised: %s", name, exc, exc_info=True)
        return {"success": False, "error": f"Tool {name} failed: {exc}"}