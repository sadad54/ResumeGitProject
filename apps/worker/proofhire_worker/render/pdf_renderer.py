"""HTML -> PDF rendering via Playwright/Chromium (PRD §21, ADR-0009)."""

from playwright.async_api import async_playwright


async def render_html_to_pdf(html: str) -> bytes:
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        try:
            page = await browser.new_page()
            await page.set_content(html, wait_until="networkidle")
            pdf_bytes = await page.pdf(format="Letter", print_background=True)
            return pdf_bytes
        finally:
            await browser.close()
