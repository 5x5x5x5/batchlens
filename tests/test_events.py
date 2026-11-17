"""The one thing BatchLens tells PlantCraft on its own: which batch's phase is running on which
asset, as an interval event that opens when the phase is under way and closes when it is over."""

from __future__ import annotations

from datetime import timedelta

from batchlens.demo.generator import LIVE_BATCH, demo_campaign
from batchlens.demo.seed import seed_demo
from batchlens.meta import FILES
from batchlens.suite.events import PhasePublisher, catalog, publish
from tests.plant import APP_KEY

CAMPAIGN = {o.record.batch.batch_id: o for o in demo_campaign()[0]}


def service(fake):
    fake.declare_events(FILES.manifest())  # an event the manifest lacks is refused
    return fake.client(None, app="batchlens", key=APP_KEY)


def test_a_phase_opens_when_it_is_under_way_and_closes_when_it_is_over(seeded, fake):
    client, publisher = service(fake), PhasePublisher(catalog())
    culture = CAMPAIGN["BL-0006"].record.phase("production_culture")
    # In the middle of the last finished batch's culture: one phase is running in the plant.
    assert publish(publisher, seeded.batches, client, culture.start + timedelta(days=5)) == 1
    [started] = fake.links.events
    assert (started["kind"], started["subject"]) == ("batchlens.phase.running", "asset:BR-2001")
    assert (started["phase"], started["key"]) == ("start", culture.phase_id)
    assert started["summary"].startswith("BL-0006: production culture (began 2026-10-14T06:00")
    assert started["payload"] == {
        "batch": "BL-0006",
        "phase": culture.phase_id,
        "kind": "production_culture",
        "start": "2026-10-14T06:00:00.000Z",
        "end": None,  # not known while it runs
    }
    # Looking again while nothing changed writes nothing.
    assert publish(publisher, seeded.batches, client, culture.start + timedelta(days=6)) == 0
    # An hour into the harvest: the culture is closed, the harvest opened on its own asset.
    assert publish(publisher, seeded.batches, client, culture.end + timedelta(hours=1)) == 2
    ended, harvest = fake.links.events[1:]
    assert (ended["phase"], ended["key"], ended["severity"]) == ("end", culture.phase_id, "ok")
    assert ended["payload"]["end"] == "2026-10-28T12:00:00.000Z"
    assert (harvest["phase"], harvest["subject"]) == ("start", "asset:HV-2101")


def test_nothing_is_written_for_a_phase_that_was_over_before_the_app_looked(seeded, fake):
    client, publisher = service(fake), PhasePublisher(catalog())
    last = max(p.end for o in CAMPAIGN.values() for p in o.record.phases)
    # Every batch is finished: a start dated now for a culture of last month would be false.
    assert publish(publisher, seeded.batches, client, last + timedelta(days=30)) == 0
    assert fake.links.events == []


def test_a_restarted_app_does_not_open_a_running_phase_twice(runtime, fake):
    from datetime import UTC, datetime

    start = datetime(2027, 3, 1, 6, 0, tzinfo=UTC)
    now = start + timedelta(days=9, hours=1)
    seed_demo(runtime.batches, live_at=now)
    client = service(fake)
    assert publish(PhasePublisher(catalog()), runtime.batches, client, now) == 1
    # A new process has no memory and says start again; PlantCraft keeps the one it has.
    assert publish(PhasePublisher(catalog()), runtime.batches, client, now) == 0
    [event] = fake.links.events
    assert event["payload"]["batch"] == LIVE_BATCH and event["subject"] == "asset:BR-2001"
    # Solution lots are held in tanks all the while; only product batches' phases are told.
    assert "solution" not in event["payload"]["kind"]


def test_an_asset_plantcraft_does_not_hold_is_logged_and_the_rest_is_written(tmp_path, caplog):
    from tests.conftest import make_runtime
    from tests.plant import make_fake

    fake = make_fake(bioprocess=False)  # a PlantCraft before the synthetic plant is loaded
    runtime = make_runtime(tmp_path, fake)
    try:
        seed_demo(runtime.batches)
        culture = CAMPAIGN["BL-0006"].record.phase("production_culture")
        saved = publish(
            PhasePublisher(catalog()),
            runtime.batches,
            service(fake),
            culture.start + timedelta(days=5),
        )
        assert saved == 0 and fake.links.events == []
        assert "PlantCraft refused a phase event" in caplog.text
    finally:
        runtime.shutdown()
