# functional_tests/test_template_autosave.py
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from .base import FunctionalTestBase
import time


class TemplateAutoSaveFT(FunctionalTestBase):
    """
    US-T2: As a staff member, I can create a template that auto-saves as I build it,
    so I don't lose my work.
    """

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
    
    def test_grade_bands_preview_appears_when_selecting_grade_type(self):
        # GIVEN a staff member is on the edit page
        self.browser.get(self.live_server_url + "/feedback/")
        create_btn = self.wait.until(EC.presence_of_element_located((By.LINK_TEXT, "Create New Template")))
        create_btn.click()
        self.wait.until(EC.url_matches(r'/feedback/template/\d+/edit/'))
        
        # WHEN they add a category
        add_btn = self.browser.find_element(By.ID, "add-category")
        add_btn.click()
        
        # AND they see at least one category row
        cat_rows = self.browser.find_elements(By.CSS_SELECTOR, ".category-row")
        assert len(cat_rows) >= 1
        
        # AND they enter a category with 30 marks
        cat_rows[0].find_element(By.CSS_SELECTOR, "input.cat-label").send_keys("Comprehension")
        max_input = cat_rows[0].find_element(By.CSS_SELECTOR, "input.cat-max")
        max_input.clear()
        max_input.send_keys("30")
        
        # WHEN they select grade type
        grade_label = cat_rows[0].find_element(By.XPATH, ".//label[contains(text(), 'Grade')]")
        self.browser.execute_script("arguments[0].click();", grade_label)
        
        # AND select a subdivision
        subdivision_btn = cat_rows[0].find_element(By.CSS_SELECTOR, "button[data-subdivision='high_low']")
        self.browser.execute_script("arguments[0].click();", subdivision_btn)
        
        # THEN they see the grade bands grid
        time.sleep(0.5)  # Wait for AJAX call
        preview = self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".grade-bands-grid")))
        
        # AND it contains grade information in cards
        preview_text = preview.text
        self.assertIn("Max", preview_text)
        self.assertIn("1st", preview_text)
        self.assertIn("Fail", preview_text)
        self.assertIn("30", preview_text)  # Maximum marks
    
    def test_multiple_categories_work_independently(self):
        # GIVEN a staff member is on the edit page
        self.browser.get(self.live_server_url + "/feedback/")
        create_btn = self.wait.until(EC.presence_of_element_located((By.LINK_TEXT, "Create New Template")))
        create_btn.click()
        self.wait.until(EC.url_matches(r'/feedback/template/\d+/edit/'))
        
        # WHEN they add one more category (one already exists by default)
        add_btn = self.browser.find_element(By.ID, "add-category")
        add_btn.click()
        
        cat_rows = self.browser.find_elements(By.CSS_SELECTOR, ".category-row")
        assert len(cat_rows) >= 2
        
        # AND set first category to Grade type with 30 marks
        cat_rows[0].find_element(By.CSS_SELECTOR, "input.cat-label").send_keys("Introduction")
        max_input1 = cat_rows[0].find_element(By.CSS_SELECTOR, "input.cat-max")
        max_input1.clear()
        max_input1.send_keys("30")
        
        grade_label1 = cat_rows[0].find_element(By.XPATH, ".//label[contains(text(), 'Grade')]")
        self.browser.execute_script("arguments[0].click();", grade_label1)
        
        subdivision_btn1 = cat_rows[0].find_element(By.CSS_SELECTOR, "button[data-subdivision='high_low']")
        self.browser.execute_script("arguments[0].click();", subdivision_btn1)
        
        # THEN first category shows grade bands
        time.sleep(0.5)
        previews = self.browser.find_elements(By.CSS_SELECTOR, ".grade-bands-grid")
        self.assertGreaterEqual(len(previews), 1, "First category should have grade bands")
        
        # WHEN they set second category to Numeric type with 10 marks
        cat_rows = self.browser.find_elements(By.CSS_SELECTOR, ".category-row")  # Re-fetch
        cat_rows[1].find_element(By.CSS_SELECTOR, "input.cat-label").send_keys("Methodology")
        max_input2 = cat_rows[1].find_element(By.CSS_SELECTOR, "input.cat-max")
        max_input2.clear()
        max_input2.send_keys("10")
        
        numeric_label2 = cat_rows[1].find_element(By.XPATH, ".//label[contains(text(), 'Numeric')]")
        self.browser.execute_script("arguments[0].click();", numeric_label2)
        
        # THEN second category does NOT show subdivision controls or grade bands
        time.sleep(0.3)
        subdivision_controls = cat_rows[1].find_elements(By.CSS_SELECTOR, ".subdivision-controls")
        for control in subdivision_controls:
            assert not control.is_displayed(), "Numeric category should not show subdivision controls"
        
        # AND first category still shows grade bands (not affected by second category)
        previews = self.browser.find_elements(By.CSS_SELECTOR, ".grade-bands-grid")
        self.assertGreaterEqual(len(previews), 1, "First category should still have grade bands")
        
        # WHEN they change second category back to Grade type
        cat_rows = self.browser.find_elements(By.CSS_SELECTOR, ".category-row")  # Re-fetch
        grade_label2 = cat_rows[1].find_element(By.XPATH, ".//label[contains(text(), 'Grade')]")
        self.browser.execute_script("arguments[0].click();", grade_label2)
        
        subdivision_btn2 = cat_rows[1].find_element(By.CSS_SELECTOR, "button[data-subdivision='high_mid_low']")
        self.browser.execute_script("arguments[0].click();", subdivision_btn2)
        
        # THEN second category now shows its own grade bands
        time.sleep(0.5)
        previews = self.browser.find_elements(By.CSS_SELECTOR, ".grade-bands-grid")
        self.assertGreaterEqual(len(previews), 2, "Both categories should now have grade bands")
        
        # WHEN they save and navigate to view and back to edit
        time.sleep(2)  # Wait for autosave
        view_btn = self.browser.find_element(By.ID, "view-template")
        self.browser.execute_script("arguments[0].scrollIntoView(true);", view_btn)
        self.browser.execute_script("arguments[0].click();", view_btn)
        self.wait.until(EC.url_matches(r'/feedback/template/\d+/$'))
        
        edit_link = self.wait.until(EC.presence_of_element_located((By.LINK_TEXT, "Edit Template")))
        edit_link.click()
        self.wait.until(EC.url_matches(r'/feedback/template/\d+/edit/'))
        
        # THEN both categories should still work independently
        cat_rows = self.browser.find_elements(By.CSS_SELECTOR, ".category-row")
        
        # First category should be Grade type
        grade_radio1 = cat_rows[0].find_element(By.CSS_SELECTOR, "input.cat-type-grade")
        self.assertTrue(grade_radio1.is_selected(), "First category should still be Grade type")
        
        # Second category should be Grade type
        grade_radio2 = cat_rows[1].find_element(By.CSS_SELECTOR, "input.cat-type-grade")
        self.assertTrue(grade_radio2.is_selected(), "Second category should still be Grade type")
        
        # AND clicking numeric on second category should NOT affect first
        numeric_label2 = cat_rows[1].find_element(By.XPATH, ".//label[contains(text(), 'Numeric')]")
        self.browser.execute_script("arguments[0].click();", numeric_label2)
        
        time.sleep(0.3)
        
        # Verify first category is still Grade
        cat_rows = self.browser.find_elements(By.CSS_SELECTOR, ".category-row")
        grade_radio1 = cat_rows[0].find_element(By.CSS_SELECTOR, "input.cat-type-grade")
        self.assertTrue(grade_radio1.is_selected(), "First category should remain Grade type after clicking second category's Numeric button")
    
    def test_category_data_persists_after_viewing_template(self):
        # GIVEN a staff member creates a template with a category
        self.browser.get(self.live_server_url + "/feedback/")
        create_btn = self.wait.until(EC.presence_of_element_located((By.LINK_TEXT, "Create New Template")))
        create_btn.click()
        self.wait.until(EC.url_matches(r'/feedback/template/\d+/edit/'))
        
        # WHEN they fill in first category details with NUMERIC type
        cat_rows = self.browser.find_elements(By.CSS_SELECTOR, ".category-row")
        cat_rows[0].find_element(By.CSS_SELECTOR, "input.cat-label").send_keys("Introduction")
        max_input = cat_rows[0].find_element(By.CSS_SELECTOR, "input.cat-max")
        max_input.clear()
        max_input.send_keys("15")
        
        # Set to Numeric type (should be default, but click to be sure)
        numeric_label = cat_rows[0].find_element(By.XPATH, ".//label[contains(text(), 'Numeric')]")
        self.browser.execute_script("arguments[0].click();", numeric_label)
        
        # Wait for autosave
        time.sleep(2)
        
        # WHEN they go to View Template
        view_btn = self.browser.find_element(By.ID, "view-template")
        view_btn.click()
        self.wait.until(EC.url_matches(r'/feedback/template/\d+/$'))
        
        # AND then go back to Edit
        edit_link = self.wait.until(EC.presence_of_element_located((By.LINK_TEXT, "Edit Template")))
        edit_link.click()
        self.wait.until(EC.url_matches(r'/feedback/template/\d+/edit/'))
        
        # THEN the first category should still have all its data
        cat_rows = self.browser.find_elements(By.CSS_SELECTOR, ".category-row")
        self.assertGreater(len(cat_rows), 0, "Should have at least one category")
        
        # Check label
        label_value = cat_rows[0].find_element(By.CSS_SELECTOR, "input.cat-label").get_attribute('value')
        self.assertEqual(label_value, "Introduction", "Label should be preserved")
        
        # Check max marks
        max_value = cat_rows[0].find_element(By.CSS_SELECTOR, "input.cat-max").get_attribute('value')
        self.assertEqual(max_value, "15", "Max marks should be preserved")
        
        # Check type is still Numeric
        numeric_radio = cat_rows[0].find_element(By.CSS_SELECTOR, "input.cat-type-numeric")
        self.assertTrue(numeric_radio.is_selected(), "Numeric type should be selected")
