from django.test import override_settings
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from .base import FunctionalTestBase


class RubricModeFT(FunctionalTestBase):
    """
    Tests for UI behavior when RUBRIC_MODE is enabled.
    """

    def test_feedback_sheet_links_hidden_when_rubric_mode_true(self):
        """
        GIVEN: The application is running with RUBRIC_MODE = True
        WHEN: A staff member views the templates list and edit page
        THEN: The 'Feedback Sheet' link/button is not present
        """
        with override_settings(RUBRIC_MODE=True):
            # Create a template to appear on the home page
            tpl = self.create_test_template()

            # Visit the home page
            self.navigate_to_home()

            # The home page should not contain a 'Feedback Sheet' link
            page_source = self.browser.page_source
            self.assertNotIn('Feedback Sheet', page_source)

            # Click the edit link for the template and verify edit page loads
            edit_buttons = self.browser.find_elements(By.LINK_TEXT, 'Edit')
            self.assertGreaterEqual(len(edit_buttons), 1, 'Expected at least one Edit button')
            self.browser.execute_script('arguments[0].click();', edit_buttons[0])
            self.wait_for_edit_page()

            # On the edit page the 'View Feedback Sheet' control should be absent
            body_text = self.browser.find_element(By.TAG_NAME, 'body').text
            self.assertNotIn('View Feedback Sheet', body_text)

    def test_feedback_sheet_links_shown_when_rubric_mode_false(self):
        """
        GIVEN: The application is running with RUBRIC_MODE = False (or unset/default)
        WHEN: A staff member views the templates list and edit page
        THEN: The 'Feedback Sheet' link/button is present
        """
        # Ensure RUBRIC_MODE is False for this test
        # (explicit so test is deterministic regardless of global settings)
        with override_settings(RUBRIC_MODE=False):
            # Create a template to appear on the home page
            tpl = self.create_test_template()

            # Visit the home page
            self.navigate_to_home()

            # The home page should contain a 'Feedback Sheet' link
            page_source = self.browser.page_source
            self.assertIn('Feedback Sheet', page_source)

            # Click the edit link for the template and verify edit page loads
            edit_buttons = self.browser.find_elements(By.LINK_TEXT, 'Edit')
            self.assertGreaterEqual(len(edit_buttons), 1, 'Expected at least one Edit button')
            self.browser.execute_script('arguments[0].click();', edit_buttons[0])
            self.wait_for_edit_page()

            # On the edit page the 'View Feedback Sheet' control should be present
            body_text = self.browser.find_element(By.TAG_NAME, 'body').text
            self.assertIn('View Feedback Sheet', body_text)
