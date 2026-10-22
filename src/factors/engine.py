"""Factor registry and dependency-bounded execution; no Investor routing."""

from __future__ import annotations

from src.factors.contracts import Factor, FactorCategory, FactorContext, FactorResult
from src.factors.definitions import builtins


class FactorRegistry:
    def __init__(self):
        self._factors: dict[str, Factor] = {}

    def register(self, factor: Factor) -> None:
        if not isinstance(factor, Factor):
            raise TypeError("factor must implement Factor")
        if factor.factor_id in self._factors:
            raise ValueError(f"duplicate factor_id: {factor.factor_id}")
        self._factors[factor.factor_id] = factor
        try:
            self._check_cycles()
        except ValueError:
            del self._factors[factor.factor_id]
            raise

    def get(self, factor_id: str) -> Factor:
        return self._factors[factor_id]

    def list(self, category: FactorCategory | None = None) -> tuple[Factor, ...]:
        return tuple(factor for factor in self._factors.values()
                     if category is None or factor.category is category)

    def _check_cycles(self) -> None:
        active, done = set(), set()
        def visit(factor_id):
            if factor_id in active:
                raise ValueError("factor dependency cycle")
            if factor_id in done:
                return
            active.add(factor_id)
            for dependency in self._factors[factor_id].dependencies:
                if dependency in self._factors:
                    visit(dependency)
            active.remove(factor_id)
            done.add(factor_id)
        for factor_id in self._factors:
            visit(factor_id)

    def validate_dependencies(self) -> None:
        missing = [(factor.factor_id, dependency)
                   for factor in self._factors.values()
                   for dependency in factor.dependencies if dependency not in self._factors]
        if missing:
            raise ValueError(f"unknown factor dependency: {missing}")
        self._check_cycles()


class FactorEngine:
    def __init__(self, registry: FactorRegistry | None = None):
        self.registry = registry or default_registry()
        self.registry.validate_dependencies()

    def evaluate(self, context: FactorContext, factor_ids: tuple[str, ...] | None = None) -> dict[str, FactorResult]:
        wanted = factor_ids or tuple(f.factor_id for f in self.registry.list())
        return {factor_id: self.registry.get(factor_id).evaluate(context) for factor_id in wanted}


def default_registry() -> FactorRegistry:
    registry = FactorRegistry()
    for factor in builtins():
        registry.register(factor)
    return registry
