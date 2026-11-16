"""A batch's transfers, each with its balance against the vessel it went into.

Nothing here is stored. A transfer that had not begun at ``as_of`` does not exist yet and is
left out; one under way is listed without a balance.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timedelta
from typing import Any

from batchlens import calc
from batchlens.batches.models import BatchRecord
from batchlens.calc.mass import TRANSFER_VERSION

REACH = timedelta(seconds=calc.VOLUME_MAX_AGE_SECONDS)


def windows(
    record: BatchRecord, as_of: datetime | None = None
) -> dict[str, tuple[datetime, datetime]]:
    """For each asset something was transferred into: the stretch of its volume signal the
    balances need, cut at ``as_of``."""

    spans: dict[str, tuple[datetime, datetime]] = {}
    for transfer in record.transfers:
        if as_of is not None and transfer.start > as_of:
            continue
        start, end = transfer.start - REACH, transfer.end + REACH
        if as_of is not None:
            end = min(end, as_of)
        known = spans.get(transfer.to_asset_id)
        spans[transfer.to_asset_id] = (
            (start, end) if known is None else (min(known[0], start), max(known[1], end))
        )
    return spans


def transfers(
    record: BatchRecord,
    volumes: Mapping[str, calc.Online | calc.Reason],
    *,
    as_of: datetime | None = None,
) -> list[dict[str, Any]]:
    """Every transfer that had begun, oldest first, as plain data with its ``balance``.
    ``volumes`` holds, for each destination asset, its volume signal over ``windows`` or the
    reason it could not be read."""

    rows = []
    for transfer in record.transfers:
        if as_of is not None and transfer.start > as_of:
            continue
        volume = volumes.get(
            transfer.to_asset_id,
            calc.Reason("signal_not_found", {"asset_id": transfer.to_asset_id, "role": "volume"}),
        )
        if isinstance(volume, calc.Reason):
            balance = calc.insufficient("transfer_balance", "%", TRANSFER_VERSION, volume)
        else:
            balance = calc.transfer_balance(
                transfer.transfer_id,
                transfer.volume,
                transfer.volume_unit,
                volume,
                start=transfer.start,
                end=transfer.end,
                as_of=as_of,
            )
        ended = as_of is None or transfer.end <= as_of
        rows.append(
            {
                "transfer_id": transfer.transfer_id,
                "kind": transfer.kind,
                "from_asset_id": transfer.from_asset_id,
                "to_asset_id": transfer.to_asset_id,
                "from_lot_id": transfer.from_lot_id,
                "start": calc.results.iso(transfer.start),
                # Under way in an as-of view: its end and its volume were not known yet.
                "end": calc.results.iso(transfer.end) if ended else None,
                "volume": transfer.volume if ended else None,
                "volume_unit": transfer.volume_unit,
                "balance": balance.to_dict(),
            }
        )
    return rows


def hours_since_feed(record: BatchRecord, moment: datetime) -> float | None:
    """Hours from the end of the last feed before ``moment``; none before the first feed."""

    ends = [t.end for t in record.transfers if t.kind == "feed" and t.end <= moment]
    return (moment - max(ends)).total_seconds() / 3600 if ends else None
