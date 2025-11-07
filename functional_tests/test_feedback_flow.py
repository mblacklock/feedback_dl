import time
import unittest
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

class FeedbackFT(unittest.TestCase):
    def setUp(self):
        self.browser = webdriver.Chrome(service=Service(ChromeDriverManager().install()))
        self.addCleanup(self.browser.quit)

    def test_student_can_see_feedback_homepage(self):
        # The student visits the portal
        self.browser.get("http://localhost:8000/feedback/")

        # They see the site title or a welcome message
        self.assertIn("Feedback", self.browser.title)

        # Optional: check visible text
        body_text = self.browser.find_element("tag name", "body").text
        self.assertIn("Welcome", body_text)

if __name__ == "__main__":
    unittest.main(warnings="ignore")
