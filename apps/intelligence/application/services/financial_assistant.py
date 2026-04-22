"""
FinancialAssistant service — Phase 7.

This is the orchestrator for the AI financial assistant (Sprint 6).
It handles query intent parsing, data retrieval from selectors, optional
Claude API integration, and citation tracing.

Current state: functional stub that returns structured "not yet configured"
responses until the Claude API integration is wired up in Sprint 6.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass


class FinancialAssistant:
    """
    Answer natural-language financial questions using ERP data.

    Returns:
        (response_text, response_type, citations)
        where response_type is one of: factual / analytical / mixed / no_data
        and citations is a list of dicts describing data sources consulted.
    """

    def __init__(self, *, organization_id: int, user) -> None:
        self.organization_id = organization_id
        self.user = user

    def answer(self, query: str) -> tuple[str, str, list[dict]]:
        """
        Process a financial query and return a response.

        Sprint 6 will replace this with:
          1. Intent classification (revenue query / ratio / AR / etc.)
          2. Selector dispatch to retrieve live data
          3. Claude API call with structured context
          4. Citation extraction from tool calls / selector results
        """
        # Stub: return a placeholder until Sprint 6 integration
        response_text = (
            "The financial assistant is not yet fully configured. "
            "Please complete the Claude API integration in Sprint 6 to enable "
            "natural-language financial queries."
        )
        return response_text, "no_data", []
