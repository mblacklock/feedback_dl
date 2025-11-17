# functional_tests/base.py
"""
Base class for functional tests to reduce duplication.
Sets up Selenium WebDriver with Chrome in headless mode.
"""
import time
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

class FunctionalTestBase(StaticLiveServerTestCase):
    """Base class for all functional tests with common Selenium setup and helper methods."""

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
    
    # ===== Navigation Helpers =====
    
    def navigate_to_home(self):
        """Navigate to the feedback home page."""
        self.browser.get(f"{self.live_server_url}/feedback/")
    
    def create_new_template(self):
        """Click 'Create New Template' button and wait for edit page."""
        create_btn = self.wait.until(
            EC.presence_of_element_located((By.LINK_TEXT, "Create New Template"))
        )
        create_btn.click()
        self.wait_for_edit_page()
    
    def wait_for_edit_page(self):
        """Wait for the template edit page to load."""
        self.wait.until(EC.url_matches(r'/feedback/template/\d+/edit/'))
    
    def wait_for_rubric_page(self):
        """Wait for the template rubric page to load."""
        self.wait.until(EC.url_matches(r'/feedback/template/\d+/rubric/'))
    
    def wait_for_feedback_sheet_page(self):
        """Wait for the feedback sheet page to load."""
        self.wait.until(EC.url_matches(r'/feedback/template/\d+/feedback-sheet/'))
    
    def click_view_rubric(self):
        """Click 'View Rubric' button and wait for rubric page."""
        view_btn = self.wait.until(
            EC.presence_of_element_located((By.LINK_TEXT, "View Rubric"))
        )
        self.browser.execute_script("arguments[0].scrollIntoView(true);", view_btn)
        self.browser.execute_script("arguments[0].click();", view_btn)
        self.wait_for_rubric_page()
    
    def click_view_feedback_sheet(self):
        """Click 'View Feedback Sheet' button and wait for feedback sheet page."""
        view_btn = self.wait.until(
            EC.presence_of_element_located((By.LINK_TEXT, "View Feedback Sheet"))
        )
        self.browser.execute_script("arguments[0].scrollIntoView(true);", view_btn)
        self.browser.execute_script("arguments[0].click();", view_btn)
        self.wait_for_feedback_sheet_page()
    
    def click_edit_template(self):
        """Click 'Edit Template' link and wait for edit page."""
        edit_link = self.wait.until(
            EC.presence_of_element_located((By.LINK_TEXT, "Edit Template"))
        )
        edit_link.click()
        self.wait_for_edit_page()
    
    # ===== Form Field Helpers =====
    
    def fill_template_fields(
        self,
        title="Test Template",
        module_code="ABC123",
        module_title="Sample Module",
        assessment_title="Assessment Title",
        component=1,
        weighting=50,
        max_marks=100,
    ):
        # Fill everything unconditionally
        title_field = self.wait.until(EC.presence_of_element_located((By.NAME, "title")))
        title_field.clear()
        title_field.send_keys(title)

        module_code_field = self.browser.find_element(By.NAME, "module_code")
        module_code_field.clear()
        module_code_field.send_keys(module_code)

        module_title_field = self.browser.find_element(By.NAME, "module_title")
        module_title_field.clear()
        module_title_field.send_keys(module_title)

        assessment_field = self.browser.find_element(By.NAME, "assessment_title")
        assessment_field.clear()
        assessment_field.send_keys(assessment_title)

        component_field = self.browser.find_element(By.NAME, "component")
        component_field.clear()
        component_field.send_keys(str(component))

        weighting_field = self.browser.find_element(By.NAME, "weighting")
        weighting_field.clear()
        weighting_field.send_keys(str(weighting))

        max_marks_field = self.browser.find_element(By.NAME, "max_marks")
        max_marks_field.clear()
        max_marks_field.send_keys(str(max_marks))

    
    # ===== Category Helpers =====
    
    def add_category_row(self):
        """Click 'Add Category' button to add a new category row."""
        initial_count = len(self.get_category_rows())
        add_btn = self.browser.find_element(By.ID, "add-category")
        add_btn.click()
        # Wait for a new category row to appear
        self.wait.until(lambda driver: len(self.get_category_rows()) > initial_count)
    
    def get_category_rows(self):
        """Get all category rows currently on the page."""
        return self.browser.find_elements(By.CSS_SELECTOR, "#categories .category-row")
    
    def fill_category(self, row_index, label, max_marks, category_type='numeric', subdivision=None):
        """
        Fill in a category row with label, max marks, type, and optional subdivision.
        
        Args:
            row_index: Index of the category row (0-based)
            label: Category label text
            max_marks: Maximum marks for category
            category_type: 'numeric' or 'grade' (default: 'numeric')
            subdivision: 'none', 'high_low', 'high_mid_low', or 'thirds' (only for grade type)
        """
        cat_rows = self.get_category_rows()
        if row_index >= len(cat_rows):
            raise IndexError(f"Row index {row_index} out of range. Only {len(cat_rows)} rows exist.")
        
        row = cat_rows[row_index]
        
        # Fill label
        label_input = row.find_element(By.CSS_SELECTOR, "input.cat-label")
        label_input.clear()
        label_input.send_keys(label)
        
        # Fill max marks
        max_input = row.find_element(By.CSS_SELECTOR, "input.cat-max")
        max_input.clear()
        max_input.send_keys(str(max_marks))
        
        # Select type
        if category_type == 'grade':
            grade_label = row.find_element(By.XPATH, ".//label[contains(text(), 'Grade')]")
            self.browser.execute_script("arguments[0].click();", grade_label)
            
            # Select subdivision if provided
            if subdivision:
                # Wait for subdivision controls to appear
                subdivision_btn = self.wait.until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, f"button[data-subdivision='{subdivision}']"))
                )
                self.browser.execute_script("arguments[0].click();", subdivision_btn)
        else:
            numeric_label = row.find_element(By.XPATH, ".//label[contains(text(), 'Numeric')]")
            self.browser.execute_script("arguments[0].click();", numeric_label)
    
    def select_category_type(self, row_index, category_type):
        """
        Select numeric or grade type for a category.
        
        Args:
            row_index: Index of the category row (0-based)
            category_type: 'numeric' or 'grade'
        """
        cat_rows = self.get_category_rows()
        row = cat_rows[row_index]
        
        if category_type == 'grade':
            grade_label = row.find_element(By.XPATH, ".//label[contains(text(), 'Grade')]")
            self.browser.execute_script("arguments[0].click();", grade_label)
        else:
            numeric_label = row.find_element(By.XPATH, ".//label[contains(text(), 'Numeric')]")
            self.browser.execute_script("arguments[0].click();", numeric_label)
    
    def select_subdivision(self, row_index, subdivision):
        """
        Select subdivision for a grade category.
        
        Args:
            row_index: Index of the category row (0-based)
            subdivision: 'none', 'high_low', 'high_mid_low', or 'thirds'
        """
        cat_rows = self.get_category_rows()
        row = cat_rows[row_index]
        
        subdivision_btn = row.find_element(
            By.CSS_SELECTOR, f"button[data-subdivision='{subdivision}']"
        )
        self.browser.execute_script("arguments[0].click();", subdivision_btn)
    
    # ===== Grade Band Helpers =====
    
    def get_grade_bands_grid(self, row_index=None):
        """
        Get grade bands grid element.
        
        Args:
            row_index: If provided, get grid for specific category row.
                      If None, get the first grid on the page.
        """
        if row_index is not None:
            cat_rows = self.get_category_rows()
            row = cat_rows[row_index]
            return row.find_element(By.CSS_SELECTOR, ".grade-bands-grid")
        else:
            return self.wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, ".grade-bands-grid"))
            )
    
    def get_description_textareas(self, row_index=None):
        """
        Get all description textareas from a grade bands grid.
        
        Args:
            row_index: If provided, get textareas for specific category row.
                      If None, get textareas from first grid.
        """
        grid = self.get_grade_bands_grid(row_index)
        return grid.find_elements(By.TAG_NAME, "textarea")
    
    def set_grade_description(self, grade, description, row_index=None):
        """
        Set description for a specific grade band.
        
        Args:
            grade: Grade label (e.g., '1st', '2:1', 'Fail')
            description: Description text
            row_index: If provided, set description for specific category row.
        """
        textareas = self.get_description_textareas(row_index)
        for ta in textareas:
            if ta.get_attribute("data-grade") == grade:
                ta.clear()
                ta.send_keys(description)
                return
        raise ValueError(f"No textarea found for grade '{grade}'")
    
    # ===== Wait Helpers =====
    
    def wait_for_autosave(self, seconds=2):
        """Wait for autosave to complete. Uses time-based wait for reliability."""
        time.sleep(seconds)
    
    # ===== Test Data Helpers =====
    
    def create_test_template(self, **kwargs):
        """
        Create a test template with sensible defaults.
        
        Args:
            **kwargs: Override any default values. Common overrides:
                - title, module_code, module_title, assessment_title
                - component, weighting, max_marks
                - categories (list of dicts)
        
        Returns:
            AssessmentTemplate instance
        """
        from feedback.models import AssessmentTemplate
        
        defaults = {
            "component": 1,
            "title": "Software Engineering",
            "module_code": "CS301",
            "module_title": "Advanced Software Development",
            "assessment_title": "Coursework 1",
            "weighting": 40,
            "max_marks": 100,
            "categories": [
                {
                    "label": "Design",
                    "max": 30,
                    "type": "grade",
                    "subdivision": "high_low",
                    "grade_band_descriptions": {
                        "1st": "Excellent design with clear justification",
                        "2:1": "Good design with adequate justification"
                    }
                },
                {
                    "label": "Implementation",
                    "max": 40,
                    "type": "grade",
                    "subdivision": "none"
                },
                {
                    "label": "Testing",
                    "max": 30,
                    "type": "numeric"
                }
            ]
        }
        
        # Merge kwargs into defaults
        defaults.update(kwargs)
        return AssessmentTemplate.objects.create(**defaults)
