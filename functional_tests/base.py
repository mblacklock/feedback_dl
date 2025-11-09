# functional_tests/base.py
"""
Base class for functional tests to reduce duplication.
Sets up Selenium WebDriver with Chrome in headless mode.
"""
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager


class FunctionalTestBase(StaticLiveServerTestCase):
    """Base class for all functional tests with common Selenium setup."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        opts = Options()
        opts.add_argument("--headless=new")
        opts.add_argument("--window-size=1280,900")
        cls.browser = webdriver.Chrome(
            service=Service(ChromeDriverManager().install()), 
            options=opts
        )
        cls.wait = WebDriverWait(cls.browser, 10)

    @classmethod
    def tearDownClass(cls):
        cls.browser.quit()
        super().tearDownClass()
