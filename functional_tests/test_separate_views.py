# functional_tests/test_separate_views.py
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from .base import FunctionalTestBase
from feedback.models import AssessmentTemplate


class SeparateViewsFT(FunctionalTestBase):
    """
    US-V1: As a staff member, I can view the rubric separately from the feedback sheet,
    so I can paste the rubric into assessment briefs and see what the student feedback will look like.
    """

    def test_staff_can_view_rubric_and_feedback_sheet_separately(self):
        """
        GIVEN: A template exists with categories and grade bands
        WHEN: A staff member navigates to the template
        THEN: They see options to view both Rubric and Feedback Sheet
        AND: Each view shows appropriate content for its purpose
        """
        # GIVEN: Create a template with grade bands
        template = self.create_test_template()
        
        # WHEN: Staff member visits the home page
        self.navigate_to_home()
        
        # THEN: They see buttons to view Rubric and Feedback Sheet for the template
        page_content = self.browser.page_source
        self.assertIn("Rubric", page_content)
        self.assertIn("Feedback Sheet", page_content)
        
        # WHEN: They click "Rubric" button
        rubric_buttons = self.browser.find_elements(By.LINK_TEXT, "Rubric")
        self.assertEqual(len(rubric_buttons), 1)
        rubric_buttons[0].click()
        
        # THEN: They see the rubric page with grade bands and descriptions
        self.wait.until(EC.url_contains("/rubric/"))
        
        rubric_content = self.browser.page_source
        # Should show module details
        self.assertIn("CS301", rubric_content)
        self.assertIn("Software Engineering", rubric_content)
        
        # Should show categories with grade bands
        self.assertIn("Design", rubric_content)
        self.assertIn("30 marks", rubric_content)
        self.assertIn("Implementation", rubric_content)
        self.assertIn("40 marks", rubric_content)
        self.assertIn("Testing", rubric_content)
        self.assertIn("Numeric scoring", rubric_content)
        
        # Should show grade band descriptions
        self.assertIn("Excellent design with clear justification", rubric_content)
        self.assertIn("High 1st", rubric_content)
        self.assertIn("Low 1st", rubric_content)
        
        # Should NOT show student name or marks awarded fields
        self.assertNotIn("Student Name", rubric_content)
        self.assertNotIn("Mark Awarded", rubric_content)
        
        # WHEN: They go back to home and click "Feedback Sheet"
        self.navigate_to_home()
        
        feedback_buttons = self.browser.find_elements(By.LINK_TEXT, "Feedback Sheet")
        self.assertEqual(len(feedback_buttons), 1)
        feedback_buttons[0].click()
        
        # THEN: They see an example feedback sheet
        self.wait.until(EC.url_contains("/feedback-sheet/"))
        
        feedback_content = self.browser.page_source
        # Should show template details
        self.assertIn("CS301", feedback_content)
        self.assertIn("Software Engineering", feedback_content)
        self.assertIn("Coursework 1", feedback_content)
        
        # Should show student name field (example)
        self.assertIn("Student Name", feedback_content)
        self.assertIn("Student ID", feedback_content)
        
        # Should show categories with mark/grade entry areas
        self.assertIn("Design", feedback_content)
        self.assertIn("Implementation", feedback_content)
        self.assertIn("Testing", feedback_content)
        
        # Should show areas for feedback comments
        self.assertIn("comments", feedback_content.lower())
        self.assertIn("feedback", feedback_content.lower())
        
        # Should show total marks
        self.assertIn("Total", feedback_content)
        self.assertIn("100", feedback_content)
    
    def test_marks_mismatch_warning_appears_on_rubric_page(self):
        """
        GIVEN: A template where category marks don't match max marks
        WHEN: Staff views the rubric page
        THEN: They see a warning about the mismatch
        """
        # GIVEN: Create a template with mismatched marks (100 category total vs 150 max)
        template = self.create_test_template()
        template.max_marks = 150
        template.save()
        
        # WHEN: Staff visits the rubric page
        self.browser.get(self.live_server_url + f'/feedback/template/{template.id}/rubric/')
        
        # THEN: They see a warning
        warning = self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, '.alert-warning')))
        warning_text = warning.text
        self.assertIn("100", warning_text, "Warning should show category total (100)")
        self.assertIn("150", warning_text, "Warning should show max marks (150)")
    
    def test_marks_mismatch_warning_appears_on_feedback_sheet_page(self):
        """
        GIVEN: A template where category marks don't match max marks
        WHEN: Staff views the feedback sheet page
        THEN: They see a warning about the mismatch
        """
        # GIVEN: Create a template with mismatched marks (100 category total vs 150 max)
        template = self.create_test_template()
        template.max_marks = 150
        template.save()
        
        # WHEN: Staff visits the feedback sheet page
        self.browser.get(self.live_server_url + f'/feedback/template/{template.id}/feedback-sheet/')
        
        # THEN: They see a warning
        warning = self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, '.alert-warning')))
        warning_text = warning.text
        self.assertIn("100", warning_text, "Warning should show category total (100)")
        self.assertIn("150", warning_text, "Warning should show max marks (150)")
