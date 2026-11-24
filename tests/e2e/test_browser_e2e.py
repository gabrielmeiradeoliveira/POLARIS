import unittest
from playwright.sync_api import sync_playwright


class TestPolarisBrowserE2E(unittest.TestCase):
    def test_frontend_real_backend_navigation(self) -> None:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto("http://127.0.0.1:5173/#/", wait_until="networkidle")
            self.assertIn("POLARIS", page.content())

            page.click('a[href="#/status"]')
            page.wait_for_timeout(300)
            status_text = page.inner_text("main")
            self.assertIn("Estado do Servidor", status_text)
            self.assertIn("Liveness:", status_text)

            page.click('a[href="#/projects"]')
            page.wait_for_timeout(300)
            proj_text = page.inner_text("main")
            self.assertIn("Projetos", proj_text)

            page.goto("http://127.0.0.1:5173/#/rota-inexistente", wait_until="networkidle")
            self.assertIn("404", page.inner_text("main"))
            browser.close()


if __name__ == "__main__":
    unittest.main()
