"""Data types for the batch-tracking layer.

A :class:`Batch` is one product curing in a chamber. It carries a reference
weight (its weight when curing started), a target weight loss and an ordered
history of :class:`WeightSample` weigh-ins. Weigh-ins may come from a scale
entity or be entered by hand (optionally with a photo), so the whole model is
serialisable and independent of Home Assistant.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class BatchStatus(StrEnum):
    """Lifecycle status of a batch."""

    ACTIVE = "active"
    COMPLETED = "completed"
    ARCHIVED = "archived"


@dataclass(frozen=True)
class WeightSample:
    """A single weigh-in: a weight at a point in time, plus optional context."""

    timestamp: float
    weight: float
    note: str | None = None
    photo_url: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "timestamp": self.timestamp,
            "weight": self.weight,
            "note": self.note,
            "photo_url": self.photo_url,
        }

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> WeightSample:
        return cls(
            timestamp=float(_req_float(data.get("timestamp"))),
            weight=float(_req_float(data.get("weight"))),
            note=_opt_str(data.get("note")),
            photo_url=_opt_str(data.get("photo_url")),
        )


#: Suggested journal event kinds (the UI offers them; any short text is accepted).
EVENT_KINDS: tuple[str, ...] = (
    "note",
    "salting",
    "hung",
    "turned",
    "washed",
    "tasting",
    "other",
)


@dataclass(frozen=True)
class BatchEvent:
    """A journal entry: something done to or observed on the batch."""

    timestamp: float
    kind: str
    note: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {"timestamp": self.timestamp, "kind": self.kind, "note": self.note}

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> BatchEvent:
        return cls(
            timestamp=float(_req_float(data.get("timestamp"))),
            kind=str(data.get("kind") or "note"),
            note=_opt_str(data.get("note")),
        )


@dataclass
class Batch:
    """A product being cured, with its weigh-in history and journal (mutable, persisted)."""

    id: str
    name: str
    product: str | None = None
    program_id: str | None = None
    reference_weight: float | None = None
    target_loss_pct: float | None = None
    created_at: float = 0.0
    status: BatchStatus = BatchStatus.ACTIVE
    samples: list[WeightSample] = field(default_factory=list)
    events: list[BatchEvent] = field(default_factory=list)

    @property
    def latest_sample(self) -> WeightSample | None:
        """Return the most recent weigh-in (samples are kept time-ordered)."""
        return self.samples[-1] if self.samples else None

    @property
    def latest_weight(self) -> float | None:
        sample = self.latest_sample
        return sample.weight if sample is not None else None

    @property
    def effective_reference(self) -> float | None:
        """Reference weight to measure loss against.

        Falls back to the first weigh-in when no explicit reference was set, so
        a chamber without a scale still tracks loss from the first manual entry.
        """
        if self.reference_weight is not None and self.reference_weight > 0:
            return self.reference_weight
        if self.samples:
            first = self.samples[0].weight
            return first if first > 0 else None
        return None

    def add_sample(self, sample: WeightSample) -> None:
        """Insert a weigh-in, keeping ``samples`` sorted by timestamp."""
        self.samples.append(sample)
        self.samples.sort(key=lambda s: s.timestamp)

    def add_event(self, event: BatchEvent) -> None:
        """Insert a journal entry, keeping ``events`` sorted by timestamp."""
        self.events.append(event)
        self.events.sort(key=lambda e: e.timestamp)

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "name": self.name,
            "product": self.product,
            "program_id": self.program_id,
            "reference_weight": self.reference_weight,
            "target_loss_pct": self.target_loss_pct,
            "created_at": self.created_at,
            "status": self.status.value,
            "samples": [s.to_dict() for s in self.samples],
            "events": [e.to_dict() for e in self.events],
        }

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> Batch:
        raw_samples = data.get("samples", [])
        samples_iter = raw_samples if isinstance(raw_samples, list) else []
        samples = [WeightSample.from_dict(_as_mapping(s)) for s in samples_iter]
        samples.sort(key=lambda s: s.timestamp)
        raw_events = data.get("events", [])
        events_iter = raw_events if isinstance(raw_events, list) else []
        events = [BatchEvent.from_dict(_as_mapping(e)) for e in events_iter]
        events.sort(key=lambda e: e.timestamp)
        return cls(
            id=str(data["id"]),
            name=str(data["name"]),
            product=_opt_str(data.get("product")),
            program_id=_opt_str(data.get("program_id")),
            reference_weight=_opt_float(data.get("reference_weight")),
            target_loss_pct=_opt_float(data.get("target_loss_pct")),
            created_at=_opt_float(data.get("created_at")) or 0.0,
            status=BatchStatus(str(data.get("status", "active"))),
            samples=samples,
            events=events,
        )


def _opt_float(value: object) -> float | None:
    if value is None or isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def _req_float(value: object) -> float:
    number = _opt_float(value)
    if number is None:
        raise TypeError("expected a number")
    return number


def _opt_str(value: object) -> str | None:
    if value is None:
        return None
    return str(value)


def _as_mapping(value: object) -> dict[str, object]:
    if not isinstance(value, dict):
        raise TypeError("expected a mapping for a weigh-in")
    return value
