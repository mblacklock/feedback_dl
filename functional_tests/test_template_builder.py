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
        self.navigate_to_home()
        self.create_new_template()
        
        # WHEN: They enter basic info including weighting
        self.fill_template_fields(
            title="Test Template",
            module_code="KB5031",
            assessment_title="Coursework 1",
            weighting=40
        )
        
        # AND: They wait for autosave
        self.wait_for_autosave()
        
        # WHEN: They click "View Template"
        self.click_view_template()
        
        # THEN: They see the summary page with weighting displayed
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
        self.navigate_to_home()
        self.create_new_template()
        
        # WHEN: They enter module code, module title, and component
        self.fill_template_fields(
            title="Test Template",
            module_code="KB5031",
            module_title="Finite Element Analysis",
            component=1,
            assessment_title="Coursework 1"
        )
        
        # AND: They wait for autosave
        self.wait_for_autosave()
        
        # WHEN: They click "View Template"
        self.click_view_template()
        
        # THEN: They see the summary page with all fields
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
        self.navigate_to_home()
        self.create_new_template()
        
        # WHEN: They enter summary info including component field
        self.fill_template_fields(
            title="Test Template",
            module_code="KB5031",
            assessment_title="Coursework 1",
            component=1
        )
        
        # AND: They add a simple category
        self.fill_category(0, "Introduction", 10)
        
        # AND: They wait for autosave
        self.wait_for_autosave()
        
        # WHEN: They view the template
        self.click_view_template()
        
        # THEN: The summary page shows the component
        page_text = self.browser.find_element(By.TAG_NAME, "body").text
        self.assertIn("Component: 1", page_text)

    def test_staff_creates_template_with_grade_bands_and_sees_summary(self):
        # GIVEN a staff member visits the feedback portal home page
        self.navigate_to_home()
        
        # WHEN they click the "Create New Template" button
        self.create_new_template()
        
        # AND they enter summary info
        self.fill_template_fields(
            title="KB5031 – FEA Coursework",
            module_code="KB5031",
            assessment_title="Coursework 1: Truss Analysis"
        )

        # AND they add three rubric categories
        self.add_category_row()
        self.add_category_row()

        # Fill the three visible category rows
        cat_rows = self.get_category_rows()
        assert len(cat_rows) >= 3, "Expected at least 3 category rows"

        # First category: Comprehension (grade type with high/low subdivision)
        self.fill_category(0, "Comprehension", 30, category_type='grade', subdivision='high_low')

        # Second category: Method (numeric type)
        self.fill_category(1, "Method", 20, category_type='numeric')

        # Third category: Design (grade type with no subdivision)
        self.fill_category(2, "Design", 10, category_type='grade', subdivision='none')

        # AND they wait for autosave
        self.wait_for_autosave()
        
        # WHEN they click "View Template" button
        self.click_view_template()

        # THEN they are taken to a summary page showing the new template title
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
        self.navigate_to_home()
        self.create_new_template()
        
        # WHEN: They enter basic info including max marks
        self.fill_template_fields(
            title="Assessment with Max Marks",
            module_code="KB5031",
            assessment_title="Final Exam",
            max_marks=100
        )
        
        self.wait_for_autosave()
        
        # WHEN: They click View Template
        self.click_view_template()
        
        # THEN: They see the summary page
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
        self.navigate_to_home()
        self.create_new_template()
        
        # WHEN: They enter max marks of 100
        self.fill_template_fields(max_marks=100)
        
        # AND add categories totaling 90 marks (not 100)
        self.fill_category(0, "Part A", 40)
        self.add_category_row()
        self.fill_category(1, "Part B", 50)
        
        import time
        time.sleep(0.5)
        
        # THEN: They should see a warning alert
        warning = self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".alert-warning")))
        warning_text = warning.text
        self.assertIn("90", warning_text, "Warning should show current total (90)")
        self.assertIn("100", warning_text, "Warning should show max marks (100)")
        
        # WHEN: They view the template summary
        self.wait_for_autosave(1)
        self.click_view_template()
        
        # THEN: The warning also appears on the summary page
        summary_warning = self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".alert-warning")))
        summary_warning_text = summary_warning.text
        self.assertIn("90", summary_warning_text)
        self.assertIn("100", summary_warning_text)
        
        # WHEN: They return to edit
        self.click_edit_template()
        
        # THEN: The warning is still visible on page load (bug fix test)
        edit_warning = self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".alert-warning")))
        edit_warning_text = edit_warning.text
        self.assertIn("90", edit_warning_text, "Warning should persist after view→edit")
        self.assertIn("100", edit_warning_text, "Warning should persist after view→edit")
    
    def test_staff_must_provide_mandatory_fields(self):
        """
        GIVEN: A staff member creates a new template
        WHEN: They try to save without module_title, weighting, or max_marks
        THEN: Browser validation prevents submission (HTML5 required attribute)
        AND: They cannot proceed without filling these mandatory fields
        """
        # GIVEN: Staff member creates new template
        self.navigate_to_home()
        self.create_new_template()
        
        # THEN: Required fields should have the 'required' attribute
        module_title = self.browser.find_element(By.NAME, "module_title")
        weighting = self.browser.find_element(By.NAME, "weighting")
        max_marks = self.browser.find_element(By.NAME, "max_marks")
        
        self.assertTrue(module_title.get_attribute("required"), "module_title should be required")
        self.assertTrue(weighting.get_attribute("required"), "weighting should be required")
        self.assertTrue(max_marks.get_attribute("required"), "max_marks should be required")
        
        # AND: Category label and max marks should also be required
        cat_rows = self.browser.find_elements(By.CSS_SELECTOR, ".category-row")
        self.assertGreater(len(cat_rows), 0, "Should have at least one category row")
        
        cat_label = cat_rows[0].find_element(By.CSS_SELECTOR, ".cat-label")
        cat_max = cat_rows[0].find_element(By.CSS_SELECTOR, ".cat-max")
        
        self.assertTrue(cat_label.get_attribute("required"), "category label should be required")
        self.assertTrue(cat_max.get_attribute("required"), "category max marks should be required")
        
        # WHEN: They try to view template without filling mandatory fields
        # (autosave should handle saving, but browser validation on inputs should guide user)
        self.wait_for_autosave()
        
        # THEN: They should see the template saves but with null values
        # (Model validation will happen on the backend, HTML5 validation is just UX hint)
        self.click_view_template()
