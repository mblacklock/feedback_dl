from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from .base import FunctionalTestBase


class FeedbackSheetGradeFT(FunctionalTestBase):
    """
    Functional test: feedback sheet displays an overall grade to the left of the total mark.
    """

    def test_feedback_sheet_shows_overall_grade_next_to_total(self):
        # Create a template via ORM such that total category marks equal max_marks
        from feedback.models import AssessmentTemplate
        template = AssessmentTemplate.objects.create(
            component=1,
            title="Grade Display",
            module_code="CS900",
            module_title="Grading",
            assessment_title="Final",
            weighting=100,
            max_marks=100,
            categories=[
                {"label": "Part A", "max": 50},
                {"label": "Part B", "max": 50}
            ]
        )

        # Visit the feedback sheet page
        self.browser.get(f"{self.live_server_url}/feedback/template/{template.pk}/feedback-sheet/")

        # Wait for the assessment-grade element we render to the left of the total mark
        grade_el = self.wait.until(EC.presence_of_element_located((By.ID, "assessment-grade")))

        # The template we created has total_category_marks == max_marks (100/100)
        # so the overall grade should be '1st'
        self.assertEqual(grade_el.text.strip(), "1st")
