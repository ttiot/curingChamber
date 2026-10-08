"""Persistence helpers built on Home Assistant's Store.

Persists user-defined programs, the running-program state (so a curing cycle
resumes transparently after a restart), per-actuator run-hour counters and the
product batches (with their weigh-in history and the designated reference batch)
and the last manually entered chamber weight (for setups without a scale).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.core import callback
from homeassistant.helpers.storage import Store

from .const import STORAGE_KEY_TEMPLATE, STORAGE_VERSION

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant


class CuringChamberStore:
    """Typed wrapper around a per-entry :class:`Store`."""

    def __init__(self, hass: HomeAssistant, entry_id: str) -> None:
        self._store: Store[dict[str, Any]] = Store(
            hass, STORAGE_VERSION, STORAGE_KEY_TEMPLATE.format(entry_id=entry_id)
        )
        self._data: dict[str, Any] = {}

    async def async_load(self) -> dict[str, Any]:
        """Load persisted data (returns an empty structure the first time)."""
        stored = await self._store.async_load()
        self._data = stored or {"programs": {}, "program_state": None, "counters": {}}
        self._data.setdefault("programs", {})
        self._data.setdefault("program_state", None)
        self._data.setdefault("counters", {})
        self._data.setdefault("batches", {})
        self._data.setdefault("reference_batch_id", None)
        self._data.setdefault("manual_weight", None)
        self._data.setdefault("weigh_in_reminders", {})
        return self._data

    @property
    def data(self) -> dict[str, Any]:
        return self._data

    @property
    def programs(self) -> dict[str, Any]:
        return self._data.setdefault("programs", {})

    @property
    def program_state(self) -> dict[str, Any] | None:
        return self._data.get("program_state")

    @property
    def counters(self) -> dict[str, float]:
        return self._data.setdefault("counters", {})

    @property
    def batches(self) -> dict[str, Any]:
        return self._data.setdefault("batches", {})

    @property
    def reference_batch_id(self) -> str | None:
        return self._data.get("reference_batch_id")

    @property
    def manual_weight(self) -> dict[str, float] | None:
        """Last hand-entered chamber weight: ``{"weight": ..., "timestamp": ...}``."""
        return self._data.get("manual_weight")

    @property
    def weigh_in_reminders(self) -> dict[str, float]:
        """Last weigh-in reminder sent per batch id (timestamp)."""
        return self._data.setdefault("weigh_in_reminders", {})

    def set_manual_weight(self, weight: float, timestamp: float) -> None:
        self._data["manual_weight"] = {"weight": weight, "timestamp": timestamp}

    def set_program_state(self, state: dict[str, Any] | None) -> None:
        self._data["program_state"] = state

    def upsert_program(self, program_id: str, program: dict[str, Any]) -> None:
        self.programs[program_id] = program

    def delete_program(self, program_id: str) -> bool:
        return self.programs.pop(program_id, None) is not None

    def set_counters(self, counters: dict[str, float]) -> None:
        self._data["counters"] = counters

    def upsert_batch(self, batch_id: str, batch: dict[str, Any]) -> None:
        self.batches[batch_id] = batch

    def delete_batch(self, batch_id: str) -> bool:
        removed = self.batches.pop(batch_id, None) is not None
        if removed and self._data.get("reference_batch_id") == batch_id:
            self._data["reference_batch_id"] = None
        return removed

    def set_reference_batch(self, batch_id: str | None) -> None:
        self._data["reference_batch_id"] = batch_id

    @callback
    def async_save(self) -> None:
        """Schedule a debounced save of the current data."""
        self._store.async_delay_save(lambda: self._data, delay=5.0)
