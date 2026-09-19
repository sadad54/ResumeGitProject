"""HTML -> PDF rendering via Playwright/Chromium (PRD §21, ADR-0009)."""

import os
from typing import Literal

from playwright.async_api import async_playwright

PageSize = Literal["Letter", "A4"]

# US Letter for US applications, A4 everywhere else. Getting this wrong doesn't
# fail loudly — it produces a document that prints with wrong margins or an
# extra near-empty page, which is exactly the kind of detail an ATS-targeted
# resume can't afford.
DEFAULT_PAGE_SIZE: PageSize = "Letter"


async def render_html_to_pdf(html: str, page_size: PageSize = DEFAULT_PAGE_SIZE) -> bytes:
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            executable_path=os.environ.get("PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH"),
        )
        try:
            page = await browser.new_page()
            await page.set_content(html, wait_until="networkidle")
            return await page.pdf(format=page_size, print_background=True)
        finally:
            await browser.close()


async def measure_rendered_pages(html: str, page_size: PageSize = DEFAULT_PAGE_SIZE) -> int:
    """Render and report how many pages the content actually occupies.

    Used for overflow detection: a resume silently spilling onto a second (or
    third) page is a real defect, and the only trustworthy way to know is to
    ask the same renderer that produces the export.
    """
    from proofhire_worker.render.parse_back import count_pdf_pages

    return count_pdf_pages(await render_html_to_pdf(html, page_size))

