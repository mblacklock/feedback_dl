# functional_tests/test_feedback_flow.py
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager


class FeedbackFT(StaticLiveServerTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        opts = Options()
        # comment this out if you want to see the browser
        opts.add_argument("--headless=new")
        opts.add_argument("--window-size=1200,900")
        cls.browser = webdriver.Chrome(
            service=Service(ChromeDriverManager().install()),
            options=opts,
        )

    @classmethod
    def tearDownClass(cls):
        cls.browser.quit()
        super().tearDownClass()

    def test_student_can_see_feedback_homepage(self):
        """A student visits the feedback portal and sees a welcome message."""
        # GIVEN the student opens the feedback homepage
        self.browser.get(self.live_server_url + "/feedback/")

        # WHEN the page loads
        title = self.browser.title
        body = self.browser.find_element(By.TAG_NAME, "body").text

        # THEN they see that they are on the Feedback site
        self.assertIn("Feedback", title)
        self.assertIn("Welcome", body)

