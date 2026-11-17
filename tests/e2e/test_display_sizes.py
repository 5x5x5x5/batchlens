"""Every page of the app's menu fits at the five display sizes, on a small laptop and a large screen.

The display size (user menu, PlantCraft docs/brand.md) scales the type and spacing tokens; a page
written once at the default has to hold at all five. ``plantcraft_sdk.displayfit`` reads each page
as drawn and names any text a box cuts, or a page wider than the screen.
"""

import pytest
from plantcraft_sdk import displayfit


@pytest.mark.slow  # every page, 2 screens, 5 sizes
def test_every_page_fits_at_every_display_size(signed_in, app_url, screenshots):
    # The menu's pages and one batch page, the one with the most on it (flags, reasons, a
    # suspect transfer and split). The SDK's default follows the first two links of the list:
    # two batch pages of the same layout, which doubled the time for nothing new.
    urls = displayfit.menu_pages(signed_in, app_url)
    urls.append(f"{app_url.rstrip('/')}/batchlens/batches/BL-0005")
    displayfit.assert_fits(signed_in, app_url, urls=urls, screenshots=screenshots)
