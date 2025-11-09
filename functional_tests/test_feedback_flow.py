# functional_tests/test_feedback_flow.py
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from .base import FunctionalTestBase
from feedback.models import AssessmentTemplate


class FeedbackFT(FunctionalTestBase):
    def test_home_page_lists_templates_with_view_and_edit_buttons(self):
        """
        GIVEN: Multiple templates exist in the database
        WHEN: A staff member visits the home page
        THEN: They see all templates listed with View and Edit buttons
        """
        # GIVEN: Create some test templates
        template1 = AssessmentTemplate.objects.create(
            component=1,
            title="Introduction to Programming",
            module_code="CS101",
            assessment_title="Assignment 1",
            categories=[
                {"label": "Code Quality", "max": 30, "type": "grade", "subdivision": "high_low"},
                {"label": "Documentation", "max": 20, "type": "numeric"}
            ]
        )
        
        template2 = AssessmentTemplate.objects.create(
            component=1,
            title="Database Systems",
            module_code="CS202",
            assessment_title="Final Exam",
            categories=[
                {"label": "Theory", "max": 50, "type": "grade", "subdivision": "none"}
            ]
        )
        
        # WHEN: Staff member visits the home page
        self.browser.get(f"{self.live_server_url}/feedback/")
        
        # THEN: They see the page title
        page_heading = self.wait.until(
            EC.presence_of_element_located((By.TAG_NAME, "h1"))
        )
        self.assertIn("Feedback Templates", page_heading.text)
        
        # AND: They see a "Create New Template" button
        create_button = self.browser.find_element(By.LINK_TEXT, "Create New Template")
        self.assertIsNotNone(create_button)
        
        # AND: They see both templates listed
        list_items = self.browser.find_elements(By.CSS_SELECTOR, ".list-group-item")
        self.assertEqual(len(list_items), 2)
        
        # AND: First template shows correct information
        first_item = list_items[0]
        self.assertIn("Database Systems", first_item.text)  # Most recent first (order by -id)
        self.assertIn("CS202", first_item.text)
        self.assertIn("Component:", first_item.text)
        self.assertIn("Final Exam", first_item.text)
        self.assertIn("1 category", first_item.text)
        
        # AND: Second template shows correct information
        second_item = list_items[1]
        self.assertIn("Introduction to Programming", second_item.text)
        self.assertIn("CS101", second_item.text)
        self.assertIn("Component:", second_item.text)
        self.assertIn("Assignment 1", second_item.text)
        self.assertIn("2 categories", second_item.text)
        
        # AND: Each template has View and Edit buttons
        view_buttons = self.browser.find_elements(By.LINK_TEXT, "View")
        edit_buttons = self.browser.find_elements(By.LINK_TEXT, "Edit")
        self.assertEqual(len(view_buttons), 2)
        self.assertEqual(len(edit_buttons), 2)
        
        # WHEN: Staff member clicks View button on first template
        view_buttons[0].click()
        
        # THEN: They are taken to the template summary page
        self.wait.until(EC.url_contains(f"/feedback/template/{template2.pk}/"))
        self.assertIn("Database Systems", self.browser.page_source)
        
        # WHEN: They go back to home
        self.browser.get(f"{self.live_server_url}/feedback/")
        
        # AND: Click Edit button on second template
        edit_buttons = self.wait.until(
            EC.presence_of_all_elements_located((By.LINK_TEXT, "Edit"))
        )
        edit_buttons[1].click()
        
        # THEN: They are taken to the template edit page
        self.wait.until(EC.url_contains(f"/feedback/template/{template1.pk}/edit/"))
        self.assertIn("Introduction to Programming", self.browser.page_source)
    
    def test_home_page_shows_empty_state_when_no_templates(self):
        """
        GIVEN: No templates exist in the database
        WHEN: A staff member visits the home page
        THEN: They see an empty state with a call to action
        """
        # GIVEN: No templates (default state)
        
        # WHEN: Staff member visits the home page
        self.browser.get(f"{self.live_server_url}/feedback/")
        
        # THEN: They see the page title
        page_heading = self.wait.until(
            EC.presence_of_element_located((By.TAG_NAME, "h1"))
        )
        self.assertIn("Feedback Templates", page_heading.text)
        
        # AND: They see the empty state message
        page_content = self.browser.page_source
        self.assertIn("No templates yet", page_content)
        self.assertIn("Create your first feedback template", page_content)
        
        # AND: They see a "Create New Template" button
        create_buttons = self.browser.find_elements(By.LINK_TEXT, "Create New Template")
        self.assertGreaterEqual(len(create_buttons), 1)
        
        # WHEN: They click the create button
        create_buttons[0].click()
        
        # THEN: They are taken to the edit page for a new template
        self.wait.until(EC.url_contains("/feedback/template/"))
        self.wait.until(EC.url_contains("/edit/"))
    
    def test_user_can_delete_template_from_home_page(self):
        """
        GIVEN: A template exists
        WHEN: A staff member deletes it from the home page
        THEN: The template is removed from the list
        """
        # GIVEN: Create a test template
        template = AssessmentTemplate.objects.create(
            component=1,
            title="Test Template",
            module_code="TEST101",
            assessment_title="Test Assessment",
            categories=[{"label": "Quality", "max": 10}]
        )
        
        # WHEN: Staff member visits the home page
        self.browser.get(f"{self.live_server_url}/feedback/")
        
        # THEN: They see the template listed
        list_items = self.browser.find_elements(By.CSS_SELECTOR, ".list-group-item")
        self.assertEqual(len(list_items), 1)
        self.assertIn("Test Template", list_items[0].text)
        
        # AND: They see a Delete button
        delete_button = self.browser.find_element(By.CSS_SELECTOR, "button.delete-template")
        self.assertIsNotNone(delete_button)
        
        # WHEN: They click the Delete button
        delete_button.click()
        
        # AND: Confirm the deletion (browser's confirm dialog)
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.common.exceptions import TimeoutException
        try:
            # Wait for alert to appear
            WebDriverWait(self.browser, 2).until(EC.alert_is_present())
            alert = self.browser.switch_to.alert
            alert.accept()
        except TimeoutException:
            # No alert, continue
            pass
        
        # THEN: The template is removed from the list (wait for AJAX to complete)
        # Wait for the list item to be removed from the DOM
        self.wait.until(
            EC.invisibility_of_element_located((By.XPATH, "//h5[contains(text(), 'Test Template')]"))
        )
        
        # Verify template is gone
        page_content = self.browser.page_source
        self.assertNotIn("Test Template", page_content)
        
        # AND: Empty state is shown
        self.assertIn("No templates yet", page_content)

