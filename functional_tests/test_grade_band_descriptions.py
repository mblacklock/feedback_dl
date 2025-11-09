# functional_tests/test_grade_band_descriptions.py
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from .base import FunctionalTestBase
import time


class GradeBandDescriptionsFT(FunctionalTestBase):
    """
    US-T3: As a staff member, I can add descriptions for each grade band
    in a table format, so I can define criteria for each performance level.
    """

    def test_staff_can_add_grade_band_descriptions_in_table(self):
        # GIVEN a staff member creates a new template
        self.browser.get(self.live_server_url + "/feedback/")
        create_btn = self.wait.until(EC.presence_of_element_located((By.LINK_TEXT, "Create New Template")))
        create_btn.click()
        self.wait.until(EC.url_matches(r'/feedback/template/\d+/edit/'))
        
        # WHEN they add a category with grade bands
        add_btn = self.browser.find_element(By.ID, "add-category")
        add_btn.click()
        
        cat_rows = self.browser.find_elements(By.CSS_SELECTOR, ".category-row")
        cat_rows[0].find_element(By.CSS_SELECTOR, "input.cat-label").send_keys("Comprehension")
        max_input = cat_rows[0].find_element(By.CSS_SELECTOR, "input.cat-max")
        max_input.clear()
        max_input.send_keys("30")
        
        # Select grade type
        grade_label = cat_rows[0].find_element(By.XPATH, ".//label[contains(text(), 'Grade')]")
        self.browser.execute_script("arguments[0].click();", grade_label)
        
        # Select subdivision
        subdivision_btn = cat_rows[0].find_element(By.CSS_SELECTOR, "button[data-subdivision='none']")
        self.browser.execute_script("arguments[0].click();", subdivision_btn)
        
        # Wait for grade bands table to appear
        time.sleep(0.5)
        
        # THEN they see a table with grade bands (subdivisions) and description fields (for main grades)
        grade_table = self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".grade-bands-table")))
        
        # AND the table has columns for different subdivisions
        headers = grade_table.find_elements(By.TAG_NAME, "th")
        header_text = " ".join([h.text for h in headers])
        # Should have subdivisions in headers
        self.assertIn("1st", header_text)
        self.assertIn("2:1", header_text)
        self.assertIn("Fail", header_text)
        
        # AND they can enter descriptions for each MAIN grade (not each subdivision)
        description_inputs = grade_table.find_elements(By.TAG_NAME, "textarea")
        # Should have 5 textareas: one for each main grade (1st, 2:1, 2:2, 3rd, Fail)
        self.assertEqual(len(description_inputs), 5, "Should have 5 description fields for 5 main grades")
        
        # WHEN they enter a description for "1st" grade (spans all 1st subdivisions)
        first_textareas = [ta for ta in description_inputs if ta.get_attribute("data-grade") == "1st"]
        self.assertGreater(len(first_textareas), 0, "Should have textarea for 1st grade")
        first_textareas[0].send_keys("Complex engineering principles are creatively and critically applied")
        
        # AND they enter a description for "2:1" grade
        two_one_textareas = [ta for ta in description_inputs if ta.get_attribute("data-grade") == "2:1"]
        if two_one_textareas:
            two_one_textareas[0].send_keys("Well-founded engineering principles are soundly applied")
        
        # Wait for auto-save
        time.sleep(2)
        
        # WHEN they click "View Template"
        view_btn = self.browser.find_element(By.ID, "view-template")
        self.browser.execute_script("arguments[0].scrollIntoView(true);", view_btn)
        self.browser.execute_script("arguments[0].click();", view_btn)
        
        # THEN they see the summary page
        self.wait.until(EC.url_matches(r'/feedback/template/\d+/$'))
        
        # AND the grade bands are displayed in a table format
        summary_table = self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".grade-bands-table")))
        
        # AND the descriptions they entered are visible
        table_text = summary_table.text
        self.assertIn("Complex engineering principles are creatively and critically applied", table_text)
        self.assertIn("Well-founded engineering principles are soundly applied", table_text)
        
        # AND the marks for each grade band are shown
        self.assertIn("30", table_text)  # Maximum mark
        self.assertIn("27", table_text)  # High 1st for 30 marks
