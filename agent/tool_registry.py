"""Simple registry for dynamically invoking platform tools."""

from __future__ import annotations

from typing import Callable, Dict


class ToolRegistry:
    """Registry mapping tool names to callables."""

    def __init__(self) -> None:
        self._tools: Dict[str, Callable[..., object]] = {}

    def register(self, name: str, func: Callable[..., object]) -> None:
        self._tools[name] = func

    def get(self, name: str) -> Callable[..., object]:
        if name not in self._tools:
            raise KeyError(f"Tool '{name}' is not registered")
        return self._tools[name]

    def available(self) -> Dict[str, Callable[..., object]]:
        return dict(self._tools)
