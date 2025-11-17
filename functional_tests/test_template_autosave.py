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
        self.navigate_to_home()
        self.create_new_template()
        
        # THEN they're on the edit page
        current_url = self.browser.current_url
        assert '/edit/' in current_url
        
        # AND they see a save status indicator
        save_status = self.wait.until(EC.presence_of_element_located((By.ID, "save-status")))
        
        # WHEN they enter a title
        self.fill_template_fields(title="KB5031 – FEA Coursework")
        
        # AND wait a moment for debounce
        time.sleep(1.5)
        
        # THEN they see "Saving..." or "Saved" indicator
        # (might be too fast to catch "Saving", so check for either)
        save_status = self.browser.find_element(By.ID, "save-status")
        self.assertIn("Sav", save_status.text)  # Catches both "Saving" and "Saved"
        
        # WHEN they click "View Template" button
        self.click_view_rubric()
        
        # THEN they see the view page with their saved data
        h1 = self.wait.until(EC.presence_of_element_located((By.TAG_NAME, "h1")))
        assert "KB5031 – FEA Coursework" in h1.text
    
    def test_grade_bands_preview_appears_when_selecting_grade_type(self):
        # GIVEN a staff member is on the edit page
        self.navigate_to_home()
        self.create_new_template()
        
        # WHEN they add a category
        self.add_category_row()
        
        # AND they see at least one category row
        cat_rows = self.get_category_rows()
        assert len(cat_rows) >= 1
        
        # AND they enter a category with grade type and subdivision
        self.fill_category(0, "Comprehension", 30, category_type='grade', subdivision='high_low')
        
        # THEN they see the grade bands grid
        time.sleep(0.5)  # Wait for AJAX call
        preview = self.get_grade_bands_grid()
        
        # AND it contains grade information in cards
        preview_text = preview.text
        self.assertIn("Max", preview_text)
        self.assertIn("1st", preview_text)
        self.assertIn("Fail", preview_text)
        self.assertIn("30", preview_text)  # Maximum marks
    
    def test_multiple_categories_work_independently(self):
        # GIVEN a staff member is on the edit page
        self.navigate_to_home()
        self.create_new_template()
        self.fill_template_fields()
        
        # WHEN they add one more category (one already exists by default)
        self.add_category_row()
        
        cat_rows = self.get_category_rows()
        assert len(cat_rows) >= 2
        
        # AND set first category to Grade type with 30 marks
        self.fill_category(0, "Introduction", 30, category_type='grade', subdivision='high_low')
        
        # THEN first category shows grade bands
        time.sleep(0.5)
        previews = self.browser.find_elements(By.CSS_SELECTOR, ".grade-bands-grid")
        self.assertGreaterEqual(len(previews), 1, "First category should have grade bands")
        
        # WHEN they set second category to Numeric type with 10 marks
        self.fill_category(1, "Methodology", 10, category_type='numeric')
        
        # THEN second category does NOT show subdivision controls or grade bands
        time.sleep(0.3)
        cat_rows = self.get_category_rows()
        subdivision_controls = cat_rows[1].find_elements(By.CSS_SELECTOR, ".subdivision-controls")
        for control in subdivision_controls:
            assert not control.is_displayed(), "Numeric category should not show subdivision controls"
        
        # AND first category still shows grade bands (not affected by second category)
        previews = self.browser.find_elements(By.CSS_SELECTOR, ".grade-bands-grid")
        self.assertGreaterEqual(len(previews), 1, "First category should still have grade bands")
        
        # WHEN they change second category back to Grade type
        self.select_category_type(1, 'grade')
        self.select_subdivision(1, 'high_mid_low')
        
        # THEN second category now shows its own grade bands
        time.sleep(0.5)
        previews = self.browser.find_elements(By.CSS_SELECTOR, ".grade-bands-grid")
        self.assertGreaterEqual(len(previews), 2, "Both categories should now have grade bands")
        
        # WHEN they save and navigate to view and back to edit
        self.wait_for_autosave()
        self.click_view_rubric()
        self.click_edit_template()
        
        # THEN both categories should still work independently
        cat_rows = self.get_category_rows()
        
        # First category should be Grade type
        grade_radio1 = cat_rows[0].find_element(By.CSS_SELECTOR, "input.cat-type-grade")
        self.assertTrue(grade_radio1.is_selected(), "First category should still be Grade type")
        
        # Second category should be Grade type
        grade_radio2 = cat_rows[1].find_element(By.CSS_SELECTOR, "input.cat-type-grade")
        self.assertTrue(grade_radio2.is_selected(), "Second category should still be Grade type")
        
        # AND clicking numeric on second category should NOT affect first
        self.select_category_type(1, 'numeric')
        
        time.sleep(0.3)
        
        # Verify first category is still Grade
        cat_rows = self.get_category_rows()
        grade_radio1 = cat_rows[0].find_element(By.CSS_SELECTOR, "input.cat-type-grade")
        self.assertTrue(grade_radio1.is_selected(), "First category should remain Grade type after clicking second category's Numeric button")
    
    def test_category_data_persists_after_viewing_template(self):
        # GIVEN a staff member creates a template with a category
        self.navigate_to_home()
        self.create_new_template()
        self.fill_template_fields()
        
        # WHEN they fill in first category details with NUMERIC type
        self.fill_category(0, "Introduction", 15, category_type='numeric')
        
        # Wait for autosave
        self.wait_for_autosave()
        
        # WHEN they go to View Template and back to Edit
        self.click_view_rubric()
        self.click_edit_template()
        
        # THEN the first category should still have all its data
        cat_rows = self.get_category_rows()
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
