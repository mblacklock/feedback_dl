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

    def test_staff_creates_template_with_grade_bands_and_sees_summary(self):
        # GIVEN a staff member visits the feedback portal home page
        self.browser.get(self.live_server_url + "/feedback/")
        
        # WHEN they click the "Create New Template" button
        create_btn = self.wait.until(EC.presence_of_element_located((By.LINK_TEXT, "Create New Template")))
        create_btn.click()
        
        # THEN they're redirected to the edit page
        self.wait.until(EC.url_matches(r'/feedback/template/\d+/edit/'))
        
        # AND they see the edit page with summary fields
        title = self.wait.until(EC.presence_of_element_located((By.NAME, "title")))
        module_code = self.browser.find_element(By.NAME, "module_code")
        assessment_title = self.browser.find_element(By.NAME, "assessment_title")

        # AND they enter summary info
        title.clear()
        title.send_keys("KB5031 – FEA Coursework")
        module_code.send_keys("KB5031")
        assessment_title.send_keys("Coursework 1: Truss Analysis")

        # AND they add three rubric categories
        add_btn = self.browser.find_element(By.ID, "add-category")

        # Click twice to add two more rows (assume one empty row is present by default)
        add_btn.click()
        add_btn.click()

        # Fill the three visible category rows
        cat_rows = self.browser.find_elements(By.CSS_SELECTOR, "#categories .category-row")
        assert len(cat_rows) >= 3, "Expected at least 3 category rows"

        # First category: Comprehension (grade type with high/low subdivision)
        cat_rows[0].find_element(By.CSS_SELECTOR, "input.cat-label").send_keys("Comprehension")
        cat_rows[0].find_element(By.CSS_SELECTOR, "input.cat-max").clear()
        cat_rows[0].find_element(By.CSS_SELECTOR, "input.cat-max").send_keys("30")
        # Select grade type by clicking the label (like a real user would)
        grade_label = cat_rows[0].find_element(By.XPATH, ".//label[contains(text(), 'Grade')]")
        self.browser.execute_script("arguments[0].scrollIntoView(true);", grade_label)
        self.browser.execute_script("arguments[0].click();", grade_label)
        # Select high_low subdivision button
        subdivision_btn = cat_rows[0].find_element(By.CSS_SELECTOR, "button[data-subdivision='high_low']")
        self.browser.execute_script("arguments[0].click();", subdivision_btn)

        # Second category: Method (numeric type)
        cat_rows[1].find_element(By.CSS_SELECTOR, "input.cat-label").send_keys("Method")
        cat_rows[1].find_element(By.CSS_SELECTOR, "input.cat-max").clear()
        cat_rows[1].find_element(By.CSS_SELECTOR, "input.cat-max").send_keys("20")
        # Numeric is default, no need to click

        # Third category: Design (grade type with no subdivision)
        cat_rows[2].find_element(By.CSS_SELECTOR, "input.cat-label").send_keys("Design")
        cat_rows[2].find_element(By.CSS_SELECTOR, "input.cat-max").clear()
        cat_rows[2].find_element(By.CSS_SELECTOR, "input.cat-max").send_keys("10")
        grade_label2 = cat_rows[2].find_element(By.XPATH, ".//label[contains(text(), 'Grade')]")
        self.browser.execute_script("arguments[0].scrollIntoView(true);", grade_label2)
        self.browser.execute_script("arguments[0].click();", grade_label2)
        subdivision_btn2 = cat_rows[2].find_element(By.CSS_SELECTOR, "button[data-subdivision='none']")
        self.browser.execute_script("arguments[0].click();", subdivision_btn2)

        # AND they wait for autosave
        import time
        time.sleep(2)
        
        # WHEN they click "View Template" button
        view_btn = self.browser.find_element(By.ID, "view-template")
        self.browser.execute_script("arguments[0].scrollIntoView(true);", view_btn)
        self.browser.execute_script("arguments[0].click();", view_btn)

        # THEN they are taken to a summary page showing the new template title
        self.wait.until(EC.url_matches(r'/feedback/template/\d+/$'))
        h1 = self.wait.until(EC.presence_of_element_located((By.TAG_NAME, "h1")))
        assert "KB5031 – FEA Coursework" in h1.text

        # AND the rubric categories appear in order
        cats_list = self.wait.until(EC.presence_of_element_located((By.ID, "cat-list")))
        items = cats_list.find_elements(By.TAG_NAME, "li")
        
        # AND the first category shows grade bands with high/low subdivision
        assert "Comprehension" in items[0].text
        assert "30 marks" in items[0].text
        assert "High 1st:" in items[0].text
        assert "Low 1st:" in items[0].text
        
        # AND the second category shows as numeric (no grade bands)
        assert "Method" in items[1].text
        assert "20 marks" in items[1].text
        assert "Numeric scoring" in items[1].text
        
        # AND the third category shows grade bands with no subdivision
        assert "Design" in items[2].text
        assert "10 marks" in items[2].text
        assert "1st:" in items[2].text
        assert "2:1:" in items[2].text
        assert "Fail:" in items[2].text
