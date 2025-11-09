# functional_tests/test_template_autosave.py
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
import time


class TemplateAutoSaveFT(StaticLiveServerTestCase):
    """
    US-T2: As a staff member, I can create a template that auto-saves as I build it,
    so I don't lose my work.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        opts = Options()
        opts.add_argument("--headless=new")
        opts.add_argument("--window-size=1280,900")
        cls.browser = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=opts)
        cls.wait = WebDriverWait(cls.browser, 10)

    @classmethod
    def tearDownClass(cls):
        cls.browser.quit()
        super().tearDownClass()

    def test_template_autosaves_as_user_types(self):
        # GIVEN a staff member clicks "Create New Template"
        self.browser.get(self.live_server_url + "/feedback/")
        create_btn = self.wait.until(EC.presence_of_element_located((By.LINK_TEXT, "Create New Template")))
        create_btn.click()
        
        # THEN a template is created immediately and they're on the edit page
        self.wait.until(EC.url_matches(r'/feedback/template/\d+/edit/'))
        current_url = self.browser.current_url
        assert '/edit/' in current_url
        
        # AND they see a save status indicator
        save_status = self.wait.until(EC.presence_of_element_located((By.ID, "save-status")))
        
        # WHEN they enter a title
        title = self.browser.find_element(By.NAME, "title")
        title.clear()
        title.send_keys("KB5031 – FEA Coursework")
        
        # AND wait a moment for debounce
        time.sleep(1.5)
        
        # THEN they see "Saving..." or "Saved" indicator
        # (might be too fast to catch "Saving", so check for either)
        save_status = self.browser.find_element(By.ID, "save-status")
        self.assertIn("Sav", save_status.text)  # Catches both "Saving" and "Saved"
        
        # WHEN they click "View Template" button
        view_btn = self.browser.find_element(By.ID, "view-template")
        view_btn.click()
        
        # THEN they see the view page with their saved data
        self.wait.until(EC.url_matches(r'/feedback/template/\d+/$'))
        h1 = self.wait.until(EC.presence_of_element_located((By.TAG_NAME, "h1")))
        assert "KB5031 – FEA Coursework" in h1.text
