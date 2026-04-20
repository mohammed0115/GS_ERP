"""drf-spectacular customizations."""
from __future__ import annotations

# Shared OpenAPI response shape that matches our exception handler envelope.
ERROR_RESPONSE_SCHEMA: dict = {
    "type": "object",
    "required": ["error"],
    "properties": {
        "error": {
            "type": "object",
            "required": ["code", "message"],
            "properties": {
                "code": {"type": "string"},
                "message": {"type": "string"},
                "details": {"type": "object"},
            },
        }
    },
}
