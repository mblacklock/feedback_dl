# functional_tests/test_template_builder.py
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager


class TemplateBuilderFT(StaticLiveServerTestCase):
    """
    US-T1: As a staff member, I can create a feedback template by entering
    summary info and adding rubric categories, and then see a summary page.
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

    def test_staff_creates_template_and_sees_summary(self):
        # GIVEN a staff member visits the feedback portal home page
        self.browser.get(self.live_server_url + "/feedback/")
        
        # WHEN they click the "Create New Template" button
        create_btn = self.wait.until(EC.presence_of_element_located((By.LINK_TEXT, "Create New Template")))
        create_btn.click()
        
        # THEN they see a template form with summary fields
        form = self.wait.until(EC.presence_of_element_located((By.ID, "template-form")))
        title = form.find_element(By.NAME, "title")
        module_code = form.find_element(By.NAME, "module_code")
        assessment_title = form.find_element(By.NAME, "assessment_title")

        # AND they enter summary info
        title.send_keys("KB5031 – FEA Coursework")
        module_code.send_keys("KB5031")
        assessment_title.send_keys("Coursework 1: Truss Analysis")

        # AND they add three rubric categories
        add_btn = form.find_element(By.ID, "add-category")

        # Click twice to add two more rows (assume one empty row is present by default)
        add_btn.click()
        add_btn.click()

        # Fill the three visible category rows (inputs with classes .cat-label and .cat-max)
        cat_rows = self.browser.find_elements(By.CSS_SELECTOR, "#categories .category-row")
        assert len(cat_rows) >= 3, "Expected at least 3 category rows"

        labels = ["Introduction", "Method", "Design"]
        maxes = ["10", "20", "10"]
        for row, lab, mx in zip(cat_rows[:3], labels, maxes):
            row.find_element(By.CSS_SELECTOR, "input.cat-label").send_keys(lab)
            row.find_element(By.CSS_SELECTOR, "input.cat-max").clear()
            row.find_element(By.CSS_SELECTOR, "input.cat-max").send_keys(mx)

        # AND they submit the form
        submit_btn = form.find_element(By.CSS_SELECTOR, "button[type=submit]")
        # Scroll button into view and click with JavaScript to avoid interception
        self.browser.execute_script("arguments[0].scrollIntoView(true);", submit_btn)
        self.browser.execute_script("arguments[0].click();", submit_btn)

        # THEN they are taken to a summary page showing the new template title
        h1 = self.wait.until(EC.presence_of_element_located((By.TAG_NAME, "h1")))
        assert "KB5031 – FEA Coursework" in h1.text

        # AND the rubric categories appear in order
        cats_list = self.wait.until(EC.presence_of_element_located((By.ID, "cat-list")))
        items = cats_list.find_elements(By.TAG_NAME, "li")
        # Check that each label appears in the corresponding list item
        for idx, label in enumerate(labels):
            assert label in items[idx].text, f"Expected '{label}' in '{items[idx].text}'"
