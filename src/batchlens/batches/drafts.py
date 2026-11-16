"""What a person may send to change a batch. Every limit is here; anything else is refused."""

from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class SampleTimeCorrection(BaseModel):
    """The body of ``PATCH /api/batches/{id}/samples/{sample_id}``: the collection time as it
    should have been recorded, and why it is being changed."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    # ISO 8601 text; without an offset it is UTC. Text, so a bare number is never read as a time.
    collected_at: str = Field(min_length=10, max_length=40)
    reason: str = Field(min_length=5, max_length=500)

    @field_validator("collected_at")
    @classmethod
    def _instant(cls, value: str) -> str:
        try:
            moment = datetime.fromisoformat(value.replace("Z", "+00:00"))
            (moment if moment.tzinfo else moment.replace(tzinfo=UTC)).astimezone(UTC)
        except (ValueError, OverflowError) as exc:
            raise ValueError("an ISO 8601 time, like 2026-07-06T06:00:00Z") from exc
        return value

    @property
    def instant(self) -> datetime:
        moment = datetime.fromisoformat(self.collected_at.replace("Z", "+00:00"))
        return (moment if moment.tzinfo else moment.replace(tzinfo=UTC)).astimezone(UTC)
