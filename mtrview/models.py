from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class ReadingView:
    receiver: str
    transmitter_id: str
    display_name: str
    location: str
    zone: str
    quantity: str
    description: str
    value: object | None
    unit: str
    measured_at: str | None
    updated_at: str | None
    status: str
    status_code: int | None
    battery: object | None
    age_seconds: int | None
    problem: bool
    status_label: str
    sort_key: str

    def to_dict(self) -> dict[str, object | None]:
        return asdict(self)
