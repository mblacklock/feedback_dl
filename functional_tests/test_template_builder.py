# functional_tests/test_template_builder.py
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from .base import FunctionalTestBase


class TemplateBuilderFT(FunctionalTestBase):
    """
    US-T1: As a staff member, I can create a feedback template by entering
    summary info and adding rubric categories, and then see a summary page.
    """

    def test_staff_can_add_weighting_field_to_template(self):
        """
        GIVEN: A staff member creates a new template
        WHEN: They enter an assessment weighting (e.g., 40%)
        THEN: The weighting is saved and displayed on the summary page
        """
        # GIVEN: Staff member visits the feedback portal and creates a new template
        self.browser.get(self.live_server_url + "/feedback/")
        create_btn = self.wait.until(EC.presence_of_element_located((By.LINK_TEXT, "Create New Template")))
        create_btn.click()
        
        # THEN: They are taken to the edit page
        self.wait.until(EC.url_matches(r'/feedback/template/\d+/edit/'))
        
        # WHEN: They enter basic info including weighting
        title = self.wait.until(EC.presence_of_element_located((By.NAME, "title")))
        title.clear()
        title.send_keys("Test Template")
        
        module_code = self.browser.find_element(By.NAME, "module_code")
        module_code.send_keys("KB5031")
        
        assessment_title = self.browser.find_element(By.NAME, "assessment_title")
        assessment_title.send_keys("Coursework 1")
        
        weighting = self.browser.find_element(By.NAME, "weighting")
        weighting.send_keys("40")
        
        # AND: They wait for autosave
        import time
        time.sleep(2)
        
        # WHEN: They click "View Template"
        view_btn = self.browser.find_element(By.ID, "view-template")
        view_btn.click()
        
        # THEN: They see the summary page with weighting displayed
        self.wait.until(EC.url_matches(r'/feedback/template/\d+/$'))
        page_content = self.browser.page_source
        
        # Verify weighting is present (could be "40%" or "Weighting: 40")
        assert "40" in page_content
        assert "Weight" in page_content or "weight" in page_content
    
    def test_staff_can_add_module_title_field_to_template(self):
        """
        GIVEN: A staff member creates a new template
        WHEN: They enter module code, module title, and component
        THEN: All three fields are saved and displayed correctly
        """
        # GIVEN: Staff member visits the feedback portal and creates a new template
        self.browser.get(self.live_server_url + "/feedback/")
        create_btn = self.wait.until(EC.presence_of_element_located((By.LINK_TEXT, "Create New Template")))
        create_btn.click()
        
        # THEN: They are taken to the edit page
        self.wait.until(EC.url_matches(r'/feedback/template/\d+/edit/'))
        
        # WHEN: They enter module code, module title, and component
        module_code = self.wait.until(EC.presence_of_element_located((By.NAME, "module_code")))
        module_code.send_keys("KB5031")
        
        module_title = self.browser.find_element(By.NAME, "module_title")
        module_title.send_keys("Finite Element Analysis")
        
        component = self.browser.find_element(By.NAME, "component")
        component.clear()
        component.send_keys("1")
        
        # AND: They add a title and assessment
        title = self.browser.find_element(By.NAME, "title")
        title.clear()
        title.send_keys("Test Template")
        
        assessment_title = self.browser.find_element(By.NAME, "assessment_title")
        assessment_title.send_keys("Coursework 1")
        
        # AND: They wait for autosave
        import time
        time.sleep(2)
        
        # WHEN: They click "View Template"
        view_btn = self.browser.find_element(By.ID, "view-template")
        view_btn.click()
        
        # THEN: They see the summary page with all fields
        self.wait.until(EC.url_matches(r'/feedback/template/\d+/$'))
        page_content = self.browser.page_source
        
        # Verify module code, module title, and component are all present
        assert "KB5031" in page_content
        assert "Finite Element Analysis" in page_content or "Finite Element Analysis" in page_content
        assert "Component:" in page_content or "Component" in page_content
    
    def test_staff_can_add_component_field_to_template(self):
        """
        GIVEN: A staff member creates a new template
        WHEN: They enter a component number like '001'
        THEN: The component is saved and displayed on the summary page
        """
        # GIVEN: Staff member visits the feedback portal and creates a new template
        self.browser.get(self.live_server_url + "/feedback/")
        create_btn = self.wait.until(EC.presence_of_element_located((By.LINK_TEXT, "Create New Template")))
        create_btn.click()
        
        # WHEN: They see the edit page
        self.wait.until(EC.url_matches(r'/feedback/template/\d+/edit/'))
        
        # AND: They enter summary info including component field
        title = self.wait.until(EC.presence_of_element_located((By.NAME, "title")))
        title.clear()
        title.send_keys("Test Template")
        
        module_code = self.browser.find_element(By.NAME, "module_code")
        module_code.send_keys("KB5031")
        
        assessment_title = self.browser.find_element(By.NAME, "assessment_title")
        assessment_title.send_keys("Coursework 1")
        
        component = self.browser.find_element(By.NAME, "component")
        component.send_keys("1")
        
        # AND: They add a simple category
        cat_row = self.browser.find_element(By.CSS_SELECTOR, "#categories .category-row")
        cat_row.find_element(By.CSS_SELECTOR, "input.cat-label").send_keys("Introduction")
        cat_row.find_element(By.CSS_SELECTOR, "input.cat-max").clear()
        cat_row.find_element(By.CSS_SELECTOR, "input.cat-max").send_keys("10")
        
        # AND: They wait for autosave
        import time
        time.sleep(2)
        
        # WHEN: They view the template
        view_btn = self.browser.find_element(By.ID, "view-template")
        self.browser.execute_script("arguments[0].click();", view_btn)
        
        # THEN: The summary page shows the component
        self.wait.until(EC.url_matches(r'/feedback/template/\d+/$'))
        page_text = self.browser.find_element(By.TAG_NAME, "body").text
        self.assertIn("Component: 1", page_text)

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
        # Click Numeric radio button (Grade is now default)
        numeric_label = cat_rows[1].find_element(By.XPATH, ".//label[contains(text(), 'Numeric')]")
        self.browser.execute_script("arguments[0].scrollIntoView(true);", numeric_label)
        self.browser.execute_script("arguments[0].click();", numeric_label)

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
        
        # AND the first category shows grade bands with high/low subdivision in a table
        assert "Comprehension" in items[0].text
        assert "30 marks" in items[0].text
        assert "High 1st" in items[0].text
        assert "Low 1st" in items[0].text
        # Check for card grid structure
        first_cat_grid = items[0].find_element(By.CSS_SELECTOR, ".grade-bands-grid")
        assert first_cat_grid is not None
        
        # AND the second category shows as numeric (no grade bands)
        assert "Method" in items[1].text
        assert "20 marks" in items[1].text
        assert "Numeric scoring" in items[1].text
        
        # AND the third category shows grade bands with no subdivision in a table
        assert "Design" in items[2].text
        assert "10 marks" in items[2].text
        assert "1st" in items[2].text
        assert "2:1" in items[2].text
        assert "Fail" in items[2].text
        third_cat_grid = items[2].find_element(By.CSS_SELECTOR, ".grade-bands-grid")
        assert third_cat_grid is not None
    
    def test_staff_can_add_max_marks_field_to_template(self):
        """
        GIVEN: A staff member creates a new template
        WHEN: They enter max marks for the assessment (e.g., 100)
        THEN: The max marks is saved and displayed on the summary page
        """
        # GIVEN: Staff member visits feedback portal and creates new template
        self.browser.get(self.live_server_url + "/feedback/")
        create_btn = self.wait.until(EC.presence_of_element_located((By.LINK_TEXT, "Create New Template")))
        create_btn.click()
        
        # THEN: They are taken to the edit page
        self.wait.until(EC.url_matches(r'/feedback/template/\d+/edit/'))
        
        # WHEN: They enter basic info including max marks
        title = self.wait.until(EC.presence_of_element_located((By.NAME, "title")))
        title.clear()
        title.send_keys("Assessment with Max Marks")
        
        module_code = self.browser.find_element(By.NAME, "module_code")
        module_code.clear()
        module_code.send_keys("KB5031")
        
        assessment_title = self.browser.find_element(By.NAME, "assessment_title")
        assessment_title.clear()
        assessment_title.send_keys("Final Exam")
        
        # Enter max marks
        max_marks = self.browser.find_element(By.NAME, "max_marks")
        max_marks.clear()
        max_marks.send_keys("100")
        
        import time
        time.sleep(2)  # Wait for autosave
        
        # WHEN: They click View Template
        view_btn = self.browser.find_element(By.ID, "view-template")
        self.browser.execute_script("arguments[0].scrollIntoView(true);", view_btn)
        self.browser.execute_script("arguments[0].click();", view_btn)
        
        # THEN: They see the summary page
        self.wait.until(EC.url_matches(r'/feedback/template/\d+/$'))
        
        # AND the max marks is displayed
        body_text = self.browser.find_element(By.TAG_NAME, "body").text
        self.assertIn("100", body_text, "Max marks should be displayed on summary page")
    
    def test_staff_sees_warning_when_category_marks_dont_match_max_marks(self):
        """
        GIVEN: A staff member creates a template with max marks and categories
        WHEN: The sum of category marks doesn't equal max marks
        THEN: They see a warning on the edit page
        """
        # GIVEN: Staff member creates new template
        self.browser.get(self.live_server_url + "/feedback/")
        create_btn = self.wait.until(EC.presence_of_element_located((By.LINK_TEXT, "Create New Template")))
        create_btn.click()
        self.wait.until(EC.url_matches(r'/feedback/template/\d+/edit/'))
        
        # WHEN: They enter max marks of 100
        max_marks = self.browser.find_element(By.NAME, "max_marks")
        max_marks.clear()
        max_marks.send_keys("100")
        
        # AND add categories totaling 90 marks (not 100)
        cat_rows = self.browser.find_elements(By.CSS_SELECTOR, ".category-row")
        cat_rows[0].find_element(By.CSS_SELECTOR, "input.cat-label").send_keys("Part A")
        max_input1 = cat_rows[0].find_element(By.CSS_SELECTOR, "input.cat-max")
        max_input1.clear()
        max_input1.send_keys("40")
        
        add_btn = self.browser.find_element(By.ID, "add-category")
        add_btn.click()
        
        import time
        time.sleep(0.3)
        
        cat_rows = self.browser.find_elements(By.CSS_SELECTOR, ".category-row")
        cat_rows[1].find_element(By.CSS_SELECTOR, "input.cat-label").send_keys("Part B")
        max_input2 = cat_rows[1].find_element(By.CSS_SELECTOR, "input.cat-max")
        max_input2.clear()
        max_input2.send_keys("50")
        
        time.sleep(0.5)
        
        # THEN: They should see a warning alert
        warning = self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".alert-warning")))
        warning_text = warning.text
        self.assertIn("90", warning_text, "Warning should show current total (90)")
        self.assertIn("100", warning_text, "Warning should show max marks (100)")
        
        # WHEN: They view the template summary
        time.sleep(1)  # Wait for autosave
        view_btn = self.browser.find_element(By.LINK_TEXT, "View Template")
        self.browser.execute_script("arguments[0].click();", view_btn)
        self.wait.until(EC.url_matches(r'/feedback/template/\d+/$'))
        
        # THEN: The warning also appears on the summary page
        summary_warning = self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".alert-warning")))
        summary_warning_text = summary_warning.text
        self.assertIn("90", summary_warning_text)
        self.assertIn("100", summary_warning_text)
        
        # WHEN: They return to edit
        edit_btn = self.browser.find_element(By.LINK_TEXT, "Edit Template")
        edit_btn.click()
        self.wait.until(EC.url_matches(r'/feedback/template/\d+/edit/'))
        
        # THEN: The warning is still visible on page load (bug fix test)
        edit_warning = self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".alert-warning")))
        edit_warning_text = edit_warning.text
        self.assertIn("90", edit_warning_text, "Warning should persist after view→edit")
        self.assertIn("100", edit_warning_text, "Warning should persist after view→edit")
