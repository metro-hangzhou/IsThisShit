from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter


@dataclass(frozen=True)
class ContextBudgetConfig:
    max_rounds: int = 4
    max_total_context_messages: int = 80
    max_total_asset_refs: int = 20
    max_runtime_s: float = 45.0


@dataclass(frozen=True)
class ContextBudgetSnapshot:
    rounds_used: int
    context_messages_used: int
    asset_refs_used: int
    runtime_s: float
    exhausted: bool
    exhaustion_reasons: tuple[str, ...]

    def model_dump(self) -> dict[str, object]:
        return {
            "rounds_used": self.rounds_used,
            "context_messages_used": self.context_messages_used,
            "asset_refs_used": self.asset_refs_used,
            "runtime_s": self.runtime_s,
            "exhausted": self.exhausted,
            "exhaustion_reasons": list(self.exhaustion_reasons),
        }


class ContextBudgetManager:
    def __init__(self, config: ContextBudgetConfig | None = None) -> None:
        self.config = config or ContextBudgetConfig()
        self._started_at = perf_counter()
        self._rounds_used = 0
        self._context_messages_used = 0
        self._asset_refs_used = 0

    def can_consume(
        self,
        *,
        round_cost: int = 1,
        message_cost: int = 0,
        asset_ref_cost: int = 0,
    ) -> bool:
        if self._rounds_used + round_cost > self.config.max_rounds:
            return False
        if self._context_messages_used + message_cost > self.config.max_total_context_messages:
            return False
        if self._asset_refs_used + asset_ref_cost > self.config.max_total_asset_refs:
            return False
        if self.runtime_s >= self.config.max_runtime_s:
            return False
        return True

    def consume(
        self,
        *,
        round_cost: int = 1,
        message_cost: int = 0,
        asset_ref_cost: int = 0,
    ) -> bool:
        if not self.can_consume(
            round_cost=round_cost,
            message_cost=message_cost,
            asset_ref_cost=asset_ref_cost,
        ):
            return False
        self._rounds_used += round_cost
        self._context_messages_used += message_cost
        self._asset_refs_used += asset_ref_cost
        return True

    @property
    def runtime_s(self) -> float:
        return perf_counter() - self._started_at

    def remaining(self) -> dict[str, float | int]:
        return {
            "remaining_rounds": max(self.config.max_rounds - self._rounds_used, 0),
            "remaining_context_messages": max(
                self.config.max_total_context_messages - self._context_messages_used,
                0,
            ),
            "remaining_asset_refs": max(
                self.config.max_total_asset_refs - self._asset_refs_used,
                0,
            ),
            "remaining_runtime_s": max(self.config.max_runtime_s - self.runtime_s, 0.0),
        }

    def snapshot(self) -> ContextBudgetSnapshot:
        reasons = self.exhaustion_reasons()
        return ContextBudgetSnapshot(
            rounds_used=self._rounds_used,
            context_messages_used=self._context_messages_used,
            asset_refs_used=self._asset_refs_used,
            runtime_s=round(self.runtime_s, 6),
            exhausted=bool(reasons),
            exhaustion_reasons=tuple(reasons),
        )

    def exhaustion_reasons(self) -> list[str]:
        reasons: list[str] = []
        if self._rounds_used >= self.config.max_rounds:
            reasons.append("max_rounds")
        if self._context_messages_used >= self.config.max_total_context_messages:
            reasons.append("max_total_context_messages")
        if self._asset_refs_used >= self.config.max_total_asset_refs:
            reasons.append("max_total_asset_refs")
        if self.runtime_s >= self.config.max_runtime_s:
            reasons.append("max_runtime_s")
        return reasons
