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

    def test_feedback_sheet_shows_category_grade_and_numeric_examples(self):
        """
        Functional test: a grade-type category displays an example grade and marks,
        and a numeric category displays an example awarded mark out of its max.
        This test checks textual content only (no exact HTML structure assertions).
        """
        from feedback.models import AssessmentTemplate

        template = AssessmentTemplate.objects.create(
            component=1,
            title="Category Display",
            module_code="CS999",
            module_title="Categories",
            assessment_title="Components",
            weighting=100,
            max_marks=0,  # ensure example-mode is used so per-category examples are shown
            categories=[
                {"label": "Design", "max": 30, "type": "grade", "subdivision": "none"},
                {"label": "Implementation", "max": 20, "type": "numeric"}
            ]
        )

        # Visit the feedback sheet page
        self.browser.get(f"{self.live_server_url}/feedback/template/{template.pk}/feedback-sheet/")

        # Wait for the page to render the assessment-grade element (used as a safe ready-check)
        self.wait.until(EC.presence_of_element_located((By.ID, "assessment-grade")))

        page = self.browser.page_source

        # Category labels should be present
        self.assertIn("Design", page)
        self.assertIn("Implementation", page)

        # Extract per-category example awarded marks from the page and sum them.
        # Grade categories display: "<grade> (<marks> marks)"
        # Numeric categories display: "<marks> / <max> marks"
        import re
        marks = []
        for m in re.findall(r"\((\d+)\s+marks\)", page):
            marks.append(int(m))
        for m in re.findall(r"(\d+)\s*/\s*\d+\s+marks", page):
            marks.append(int(m))

        self.assertGreater(len(marks), 0, "Should find per-category example marks in the page")
        page_total = sum(marks)

        # The page header shows the example total as "( <example_awarded> / <total_marks> )" when in example-mode
        m = re.search(r"\(\s*(\d+)\s*/\s*(\d+)\s*\)", page)
        self.assertIsNotNone(m, "Page should show the example total in the header")
        displayed_example_awarded = int(m.group(1))
        displayed_total_marks = int(m.group(2))

        # The displayed example awarded total should equal the sum of per-category example marks
        self.assertEqual(displayed_example_awarded, page_total)
        # And the displayed total marks should equal the sum of category maxima
        self.assertEqual(displayed_total_marks, 30 + 20)
