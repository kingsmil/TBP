from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from app.homeos.framework.tool import ToolAdapter
from app.homeos.mock.tools import mock_transaction_data
from app.services.stats import summarize

if TYPE_CHECKING:
    from app.repositories.base import Repository


class TransactionsTool(ToolAdapter):
    name = "transactions"
    description = "Fetch recent HDB resale transactions for a block."

    def fetch(self, repo: "Repository", block_id: int | None, prefs: dict) -> dict[str, Any]:
        if self.mock:
            return mock_transaction_data(block_id or 0, prefs)
        txns = list(repo.transactions_for_block(block_id))
        flat_type = prefs.get("flat_type")
        if flat_type:
            txns = [t for t in txns if t.flat_type == flat_type]
        recent = sorted(txns, key=lambda t: t.transaction_month, reverse=True)[:6]
        summary = summarize(recent)
        max_price = prefs.get("max_price")
        median_price = round(summary.median_price, 2) if summary.median_price else None
        if max_price is None or median_price is None:
            budget_signal = "unknown"
        elif median_price <= max_price:
            budget_signal = "within_budget"
        else:
            budget_signal = "above_budget"
        return {
            "transaction_count": summary.txn_count,
            "median_price": median_price,
            "median_psf": round(summary.median_psf, 2) if summary.median_psf else None,
            "window_months": 6,
            "budget_signal": budget_signal,
            "confidence": "high" if summary.txn_count >= 6 else "medium" if summary.txn_count >= 3 else "low",
        }

    def as_tool(self, repo: "Repository", block_id: int | None, prefs: dict) -> Callable:
        _self = self
        _repo, _block_id, _prefs = repo, block_id, prefs

        def get_transactions(flat_type: str | None = None) -> dict[str, Any]:
            """Fetch recent HDB resale transactions for a block. Optionally filter by flat_type."""
            p = {**_prefs, **({"flat_type": flat_type} if flat_type else {})}
            return _self.fetch(repo=_repo, block_id=_block_id, prefs=p)

        return get_transactions
