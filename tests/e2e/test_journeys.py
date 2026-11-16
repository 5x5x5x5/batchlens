"""The journeys in a real browser: sign-in, then the batch list, one batch with its phases and
metrics, and a flagged metric that says why it has no value."""

from __future__ import annotations

import os
import re

import pytest

try:
    from playwright.sync_api import expect
except ImportError:
    if os.environ.get("BATCHLENS_E2E_REQUIRED") == "1":
        raise
    pytest.skip("Playwright is not installed", allow_module_level=True)


def _shot(page, screenshots, name):
    if screenshots:
        page.wait_for_timeout(800)
        page.screenshot(path=str(screenshots / f"{name}.png"), full_page=True)


def test_a_browser_without_a_token_is_sent_to_sign_in(anonymous, app_url):
    anonymous.goto(f"{app_url}/batchlens/")
    assert re.search(r"/login\?next=/batchlens/", anonymous.url), anonymous.url


BANNER = (
    "SYNTHETIC DATA · SIMULATED BATCHES · NOT FOR PROCESS CONTROL, RELEASE OR BATCH DISPOSITION"
)


def test_open_the_app_open_a_batch_and_see_its_phases_and_metrics(signed_in, app_url, screenshots):
    page = signed_in
    page.goto(f"{app_url}/batchlens/")
    expect(page.get_by_text(BANNER)).to_be_visible()
    expect(page.get_by_role("row", name=re.compile("BL-0001.*Reference"))).to_be_visible()
    expect(page.get_by_role("row", name=re.compile("BL-0004"))).to_be_visible()
    expect(page.get_by_text(re.compile("Times are shown in"))).to_be_visible()
    _shot(page, screenshots, "1-batches")

    page.get_by_role("link", name="BL-0003").click()
    expect(page.get_by_role("heading", name="Batch BL-0003")).to_be_visible()
    expect(page.get_by_text(BANNER)).to_be_visible()
    expect(page.get_by_text("Reference batch: BL-0001")).to_be_visible()
    phases = page.locator('[data-section="phases"]')
    for phase in ("Production culture", "Harvest", "Protein A capture", "UF/DF"):
        expect(phases.get_by_role("cell", name=phase, exact=True)).to_be_visible()
    expect(phases.get_by_text("Production bioreactor 2000 L")).to_be_visible()
    metrics = page.locator('[data-section="metrics"]')
    productivity = metrics.get_by_role("row", name=re.compile("Specific productivity"))
    expect(productivity).to_contain_text("pg/cell/day")
    expect(productivity).to_contain_text("Usable")
    expect(productivity).to_contain_text("-")  # lower than the reference batch
    expect(metrics.get_by_role("row", name=re.compile("^Product mass at harvest"))).to_contain_text(
        "Estimated from concentration × volume (Protein A HPLC)."
    )
    # The finding: an observation, a calculation, and no cause.
    findings = page.locator('[data-section="findings"]')
    expect(
        findings.get_by_role(
            "heading", name=re.compile("Titer left the reference batch at culture day")
        )
    ).to_be_visible()
    expect(findings).to_contain_text("BL-0001-S")
    expect(findings).to_contain_text(
        "Calculated: Product mass at harvest: 7,317 g against 10,170 g"
    )
    expect(findings).to_contain_text("No cause is attributed")
    expect(findings).to_contain_text("At the divergence: BL-0003-S09 against BL-0001-S09")
    expect(findings.get_by_role("row", name=re.compile("^Lactate")).first).to_be_visible()
    # The charts are drawn: the bioreactor's four signals, then VCD and titer.
    expect(page.locator('[data-section="trends"] .js-plotly-plot')).to_have_count(6)
    expect(
        page.locator('[data-section="results"]').get_by_text("Protein A HPLC").first
    ).to_be_visible()
    _shot(page, screenshots, "2-batch")


def test_a_batch_that_lost_product_in_the_capture_step_says_where(signed_in, app_url, screenshots):
    page = signed_in
    page.goto(f"{app_url}/batchlens/batches/BL-0004")
    findings = page.locator('[data-section="findings"]')
    expect(findings).to_contain_text("Titer stayed within 15 % of the reference batch")
    expect(findings).to_contain_text(
        "Harvest-to-load yield is within 10 points of the reference batch"
    )
    expect(
        findings.get_by_role(
            "heading", name=re.compile("Protein A recovery is 20 points below the reference batch")
        )
    ).to_be_visible()
    expect(findings).to_contain_text("Calculated: Protein A eluate mass: 7,410 g against 9,230 g")
    # The loss is in one step of the train, and it carries through to the drug substance.
    train = page.locator('[data-section="downstream"]')
    capture = train.get_by_role("row", name=re.compile("^Protein A capture"))
    expect(capture).to_contain_text("73.4 %")
    expect(capture).to_contain_text("-20.2")
    expect(train.get_by_role("row", name=re.compile("^UF.DF"))).to_contain_text("%")
    expect(train).to_contain_text(
        re.compile(r"From harvest to drug substance: \d+\.\d % \(reference batch: \d+\.\d %\)")
    )
    expect(
        train.get_by_role("row", name=re.compile("^Protein A eluate BL-0004-protein_a_eluate "))
    ).to_contain_text("BL-0004-protein_a_eluate_cycle_1, BL-0004-protein_a_eluate_cycle_2")
    # The reference batch is drawn over VCD and titer: two lines in each of those charts.
    expect(page.locator('[data-section="trends"] .js-plotly-plot')).to_have_count(6)
    expect(
        page.locator('[data-section="trends"]')
        .get_by_text("Reference batch BL-0001, same culture age")
        .first
    ).to_be_visible()
    _shot(page, screenshots, "4-recovery-finding")


def test_a_badly_recorded_batch_is_flagged_not_answered(signed_in, app_url, screenshots):
    page = signed_in
    page.goto(f"{app_url}/batchlens/")
    page.get_by_role("link", name="BL-0005").click()
    metrics = page.locator('[data-section="metrics"]')
    cells = metrics.get_by_role("row", name=re.compile("^Integral of viable cell density"))
    expect(cells).to_contain_text("Invalid")
    expect(cells).to_contain_text("No value")
    expect(cells).to_contain_text("Sample times are duplicated or out of order at BL-0005-S09-vcd.")
    harvest = metrics.get_by_role("row", name=re.compile("^Product mass at harvest"))
    expect(harvest).to_contain_text("Insufficient")
    expect(harvest).to_contain_text("No bioreactor volume value within")
    expect(metrics.get_by_role("row", name=re.compile("^Protein A recovery"))).to_contain_text(
        "Usable"
    )
    findings = page.locator('[data-section="findings"]')
    expect(findings).to_contain_text(
        "The titer could not be compared with the reference batch (Invalid)"
    )
    expect(findings).to_contain_text(
        "Harvest-to-load yield could not be compared with the reference batch"
    )
    _shot(page, screenshots, "5-bad-records")


def test_going_back_in_time_shows_only_what_was_known_then(signed_in, app_url, screenshots):
    page = signed_in
    page.goto(f"{app_url}/batchlens/batches/BL-0003")
    findings = page.locator('[data-section="findings"]')
    expect(findings).to_contain_text("Titer left the reference batch at culture day 7.9")
    expect(page.get_by_text("Showing everything recorded.")).to_be_visible()
    # Culture day 6 (24 steps of 6 hours): before the titer left the reference.
    page.get_by_label("What was known when").fill("24")
    expect(
        page.get_by_text(
            re.compile("Showing only what had been collected and reported by Aug 18, 2026")
        )
    ).to_be_visible()
    expect(findings).to_contain_text("Titer stayed within 15 % of the reference batch")
    expect(findings).not_to_contain_text("Titer left the reference batch")
    metrics = page.locator('[data-section="metrics"]')
    harvest = metrics.get_by_role("row", name=re.compile("^Product mass at harvest"))
    expect(harvest).to_contain_text("The production phase had not ended.")
    # Day 6's own titer was reported a day later: it is not in the list yet.
    results = page.locator('[data-section="results"]')
    expect(results.get_by_text(re.compile(r"1[–-]25 of \d+"))).to_be_visible()
    _shot(page, screenshots, "6-as-of-day-6")
    page.get_by_role("button", name="Show everything").click()
    expect(findings).to_contain_text("Titer left the reference batch at culture day 7.9")


def test_an_editor_corrects_the_mis_keyed_sample_time(signed_in_without_volume, screenshots):
    # On the second app of this run, so the other journeys keep the batch as it was recorded.
    page, url = signed_in_without_volume
    page.goto(f"{url}/batchlens/batches/BL-0005")
    metrics = page.locator('[data-section="metrics"]')
    cells = metrics.get_by_role("row", name=re.compile("^Integral of viable cell density"))
    expect(cells).to_contain_text("Invalid")
    samples = page.locator('[data-section="samples"]')
    samples.get_by_role("row", name=re.compile("BL-0005-S09")).get_by_role(
        "button", name="Correct the time"
    ).click()
    # Sample 9 was keyed in with sample 8's time, Sep 30; a daily sample belongs a day later.
    expect(samples.get_by_label("Collected")).to_have_value(re.compile("^2026-09-30T"))
    samples.get_by_label("Collected").fill("2026-10-01T05:00")
    samples.get_by_label("Reason").fill(
        "Keyed in with the previous sample's time; corrected from the label."
    )
    samples.get_by_role("button", name="Save the correction").click()
    expect(cells).to_contain_text("Usable")
    expect(cells).to_contain_text("1e6 cell-days/mL")
    expect(samples.get_by_role("row", name=re.compile("BL-0005-S09")).first).to_contain_text(
        "Corrected"
    )
    expect(samples).to_contain_text("corrected from the label")
    expect(samples).to_contain_text("engineer")
    _shot(page, screenshots, "7-corrected")


def test_a_metric_that_needs_a_missing_signal_says_why(signed_in_without_volume, screenshots):
    page, url = signed_in_without_volume
    page.goto(f"{url}/batchlens/batches/BL-0001")
    metrics = page.locator('[data-section="metrics"]')
    harvest = metrics.get_by_role("row", name=re.compile("^Product mass at harvest"))
    expect(harvest).to_contain_text("Insufficient")
    expect(harvest).to_contain_text("No value")
    expect(harvest).to_contain_text("BR-2001 has no volume signal in PlantCraft.")
    step_yield = metrics.get_by_role("row", name=re.compile("Harvest-to-load yield"))
    expect(step_yield).to_contain_text("Product mass at harvest has no value (Insufficient).")
    # What rests on the app's own records is still there.
    expect(metrics.get_by_role("row", name=re.compile("Protein A recovery"))).to_contain_text(
        "Usable"
    )
    trends = page.locator('[data-section="trends"]')
    expect(trends.get_by_text("BR-2001 has no volume signal in PlantCraft.")).to_be_visible()
    expect(trends.locator(".js-plotly-plot")).to_have_count(5)
    _shot(page, screenshots, "3-missing-signal")
