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
        
        # THEN they see a grid with grade band cards (one card per main grade)
        grade_grid = self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".grade-bands-grid")))
        
        # AND the grid has cards for different main grades
        cards = grade_grid.find_elements(By.CSS_SELECTOR, ".card")
        card_text = " ".join([c.text for c in cards])
        # Should have main grades in cards
        self.assertIn("1st", card_text)
        self.assertIn("2:1", card_text)
        self.assertIn("Fail", card_text)
        
        # AND they can enter descriptions for each MAIN grade (not each subdivision)
        description_inputs = grade_grid.find_elements(By.TAG_NAME, "textarea")
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
        
        # AND the grade bands are displayed in a card grid format
        summary_grid = self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".grade-bands-grid")))
        
        # AND the descriptions they entered are visible
        grid_text = summary_grid.text
        self.assertIn("Complex engineering principles are creatively and critically applied", grid_text)
        self.assertIn("Well-founded engineering principles are soundly applied", grid_text)
        
        # AND the marks for each grade band are shown
        self.assertIn("30", grid_text)  # Maximum mark
        self.assertIn("27", grid_text)  # High 1st for 30 marks
    
    def test_descriptions_persist_when_changing_subdivision(self):
        # GIVEN a staff member creates a template with grade bands
        self.browser.get(self.live_server_url + "/feedback/")
        create_btn = self.wait.until(EC.presence_of_element_located((By.LINK_TEXT, "Create New Template")))
        create_btn.click()
        self.wait.until(EC.url_matches(r'/feedback/template/\d+/edit/'))
        
        add_btn = self.browser.find_element(By.ID, "add-category")
        add_btn.click()
        
        cat_rows = self.browser.find_elements(By.CSS_SELECTOR, ".category-row")
        cat_rows[0].find_element(By.CSS_SELECTOR, "input.cat-label").send_keys("Analysis")
        max_input = cat_rows[0].find_element(By.CSS_SELECTOR, "input.cat-max")
        max_input.clear()
        max_input.send_keys("20")
        
        grade_label = cat_rows[0].find_element(By.XPATH, ".//label[contains(text(), 'Grade')]")
        self.browser.execute_script("arguments[0].click();", grade_label)
        
        subdivision_btn = cat_rows[0].find_element(By.CSS_SELECTOR, "button[data-subdivision='none']")
        self.browser.execute_script("arguments[0].click();", subdivision_btn)
        
        time.sleep(0.5)
        
        # WHEN they enter descriptions for grade bands
        grade_grid = self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".grade-bands-grid")))
        description_inputs = grade_grid.find_elements(By.TAG_NAME, "textarea")
        
        first_desc_textarea = None
        two_one_desc_textarea = None
        for ta in description_inputs:
            if ta.get_attribute("data-grade") == "1st":
                first_desc_textarea = ta
                first_desc_textarea.send_keys("Excellent analysis with critical insight")
            elif ta.get_attribute("data-grade") == "2:1":
                two_one_desc_textarea = ta
                two_one_desc_textarea.send_keys("Good analysis with sound reasoning")
        
        self.assertIsNotNone(first_desc_textarea, "Should have textarea for 1st grade")
        self.assertIsNotNone(two_one_desc_textarea, "Should have textarea for 2:1 grade")
        
        # AND they change the subdivision
        cat_rows = self.browser.find_elements(By.CSS_SELECTOR, ".category-row")
        subdivision_btn_high_low = cat_rows[0].find_element(By.CSS_SELECTOR, "button[data-subdivision='high_low']")
        self.browser.execute_script("arguments[0].click();", subdivision_btn_high_low)
        
        time.sleep(0.5)
        
        # THEN the descriptions they entered should still be there
        grade_grid = self.browser.find_element(By.CSS_SELECTOR, ".grade-bands-grid")
        description_inputs = grade_grid.find_elements(By.TAG_NAME, "textarea")
        
        descriptions_text = []
        for ta in description_inputs:
            grade = ta.get_attribute("data-grade")
            value = ta.get_attribute("value")
            if grade == "1st":
                self.assertEqual(value, "Excellent analysis with critical insight", 
                               "1st grade description should persist after subdivision change")
                descriptions_text.append(value)
            elif grade == "2:1":
                self.assertEqual(value, "Good analysis with sound reasoning",
                               "2:1 grade description should persist after subdivision change")
                descriptions_text.append(value)
        
        self.assertEqual(len(descriptions_text), 2, "Both descriptions should be preserved")
    
    def test_descriptions_preserved_when_switching_to_numeric_and_back(self):
        # GIVEN a staff member creates a template with grade bands and descriptions
        self.browser.get(self.live_server_url + "/feedback/")
        create_btn = self.wait.until(EC.presence_of_element_located((By.LINK_TEXT, "Create New Template")))
        create_btn.click()
        self.wait.until(EC.url_matches(r'/feedback/template/\d+/edit/'))
        
        add_btn = self.browser.find_element(By.ID, "add-category")
        add_btn.click()
        
        cat_rows = self.browser.find_elements(By.CSS_SELECTOR, ".category-row")
        cat_rows[0].find_element(By.CSS_SELECTOR, "input.cat-label").send_keys("Methodology")
        max_input = cat_rows[0].find_element(By.CSS_SELECTOR, "input.cat-max")
        max_input.clear()
        max_input.send_keys("20")
        
        grade_label = cat_rows[0].find_element(By.XPATH, ".//label[contains(text(), 'Grade')]")
        self.browser.execute_script("arguments[0].click();", grade_label)
        
        subdivision_btn = cat_rows[0].find_element(By.CSS_SELECTOR, "button[data-subdivision='none']")
        self.browser.execute_script("arguments[0].click();", subdivision_btn)
        
        time.sleep(0.5)
        
        # WHEN they enter descriptions
        grade_grid = self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".grade-bands-grid")))
        description_inputs = grade_grid.find_elements(By.TAG_NAME, "textarea")
        
        for ta in description_inputs:
            if ta.get_attribute("data-grade") == "1st":
                ta.send_keys("Exceptional methodology with innovative approach")
            elif ta.get_attribute("data-grade") == "2:1":
                ta.send_keys("Strong methodology with clear justification")
        
        time.sleep(2)  # Wait for autosave
        
        # AND they switch to Numeric type
        cat_rows = self.browser.find_elements(By.CSS_SELECTOR, ".category-row")
        numeric_label = cat_rows[0].find_element(By.XPATH, ".//label[contains(text(), 'Numeric')]")
        self.browser.execute_script("arguments[0].click();", numeric_label)
        
        time.sleep(2)  # Wait for autosave
        
        # AND they navigate to view and back to edit
        view_btn = self.browser.find_element(By.ID, "view-template")
        view_btn.click()
        self.wait.until(EC.url_matches(r'/feedback/template/\d+/$'))
        
        edit_link = self.wait.until(EC.presence_of_element_located((By.LINK_TEXT, "Edit Template")))
        edit_link.click()
        self.wait.until(EC.url_matches(r'/feedback/template/\d+/edit/'))
        
        # AND they switch back to Grade type
        cat_rows = self.browser.find_elements(By.CSS_SELECTOR, ".category-row")
        grade_label = cat_rows[0].find_element(By.XPATH, ".//label[contains(text(), 'Grade')]")
        self.browser.execute_script("arguments[0].click();", grade_label)
        
        # Select subdivision to show grade bands
        subdivision_btn = cat_rows[0].find_element(By.CSS_SELECTOR, "button[data-subdivision='none']")
        self.browser.execute_script("arguments[0].click();", subdivision_btn)
        
        time.sleep(0.5)
        
        # THEN the descriptions they entered should still be there
        grade_grid = self.browser.find_element(By.CSS_SELECTOR, ".grade-bands-grid")
        description_inputs = grade_grid.find_elements(By.TAG_NAME, "textarea")
        
        found_first = False
        found_two_one = False
        for ta in description_inputs:
            grade = ta.get_attribute("data-grade")
            value = ta.get_attribute("value")
            if grade == "1st" and value == "Exceptional methodology with innovative approach":
                found_first = True
            elif grade == "2:1" and value == "Strong methodology with clear justification":
                found_two_one = True
        
        self.assertTrue(found_first, "1st grade description should be preserved after switching to numeric and back")
        self.assertTrue(found_two_one, "2:1 grade description should be preserved after switching to numeric and back")
