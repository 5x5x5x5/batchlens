"""E2E fixtures: FakePlantCraft and BatchLens served over HTTP, and a headless Chromium
(``plantcraft_sdk.e2e``: the fake in a forked server, the app in a uvicorn thread with the built
interface, the browser signed in with PlantCraft's cookie). ``BATCHLENS_E2E_REQUIRED=1`` makes a
missing tool a failure; ``BATCHLENS_E2E_SCREENSHOTS`` names a folder for screenshots.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import httpx
import pytest
from plantcraft_sdk import e2e
from plantcraft_sdk.auth import TokenVerifier
from plantcraft_sdk.client import PlantCraftClient
from plantcraft_sdk.contract import TOKEN_COOKIE

from batchlens import APP_ID
from batchlens.api.app import create_app, ui_folder
from batchlens.api.runtime import Runtime
from batchlens.config import Settings
from batchlens.demo.generator import BIOREACTOR
from batchlens.demo.seed import seed_demo
from tests.plant import APP_KEY, make_fake


@contextmanager
def _app(fake, data_dir) -> Iterator[str]:
    """BatchLens with the demo batches, served against ``fake``; yields its URL."""

    if ui_folder() is None:
        e2e.unavailable(
            APP_ID, "The interface is not built: run `npm ci && npm run build` in frontend/"
        )
    with e2e.served(fake.app) as processcraft_url:
        http = httpx.Client(timeout=30)
        runtime = Runtime(
            Settings(processcraft_url=processcraft_url, data_dir=data_dir),
            verifier=TokenVerifier(processcraft_url, APP_ID, http_client=http),
            service_client=PlantCraftClient(
                processcraft_url, app=APP_ID, key=APP_KEY, http_client=http
            ),
            http_client=http,
        )
        seed_demo(runtime.batches)
        runtime.start()
        try:
            with e2e.serving(create_app(runtime), "BatchLens") as url:
                yield url
        finally:
            runtime.shutdown()
            http.close()


@pytest.fixture(scope="session")
def fake():
    return make_fake()


@pytest.fixture(scope="session")
def app_url(fake, tmp_path_factory):
    with _app(fake, tmp_path_factory.mktemp("e2e")) as url:
        yield url


@pytest.fixture(scope="session")
def app_without_volume_url(tmp_path_factory):
    """The app against a PlantCraft whose bioreactor has no volume signal bound: what a metric
    that needs a missing signal looks like to a person."""

    fake = make_fake()
    del next(asset for asset in fake.assets if asset["id"] == BIOREACTOR)["signals"]["volume"]
    with _app(fake, tmp_path_factory.mktemp("e2e-no-volume")) as url:
        yield url, fake.token("engineer")


@pytest.fixture(scope="session")
def browser():
    with e2e.chromium(APP_ID) as instance:
        yield instance


@pytest.fixture
def anonymous(browser):
    with e2e.page(browser) as page:
        yield page


@pytest.fixture
def signed_in(browser, fake, app_url):
    """A page whose browser holds a PlantCraft token for an editor."""

    cookie = {"name": TOKEN_COOKIE, "value": fake.token("engineer"), "url": app_url}
    with e2e.page(browser, [cookie]) as page:
        yield page


@pytest.fixture(scope="session")
def screenshots() -> Path | None:
    return e2e.screenshots(APP_ID)


@pytest.fixture
def signed_in_without_volume(browser, app_without_volume_url):
    url, token = app_without_volume_url
    with e2e.page(browser, [{"name": TOKEN_COOKIE, "value": token, "url": url}]) as page:
        yield page, url
