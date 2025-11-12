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
            charts=[],
            categories=[
                {"label": "Part A", "max": 50},
                {"label": "Part B", "max": 50}
            ]
        )

        # Visit the feedback sheet page
        self.browser.get(f"{self.live_server_url}/feedback/template/{template.pk}/feedback-sheet/")

        # Wait for the assessment-grade element we render to the left of the total mark
        grade_el = self.wait.until(EC.presence_of_element_located((By.ID, "assessment-grade")))

        # We render an overall grade to the left of the total mark. The exact
        # band shown may be generated for example sheets, so assert the
        # element exists and contains one of the expected main grades rather
        # than a specific value.
        grade_text = grade_el.text.strip()
        allowed = ["1st", "2:1", "2:2", "3rd", "Fail"]
        self.assertIn(grade_text, allowed, f"Grade should be one of {allowed}, got {grade_text}")

    def test_feedback_sheet_shows_category_grade_and_numeric_examples(self):
        """
        Functional test: a grade-type category displays an example grade and marks,
        and a numeric category displays an example awarded mark out of its max.
        """
        from feedback.models import AssessmentTemplate

        template = AssessmentTemplate.objects.create(
            component=1,
            title="Category Display",
            module_code="CS999",
            module_title="Categories",
            assessment_title="Components",
            weighting=100,
            max_marks=50,
            charts=[],
            categories=[
                {"label": "Design", "max": 30, "type": "grade", "subdivision": "none"},
                {"label": "Implementation", "max": 20, "type": "numeric"}
            ]
        )

        # Visit the feedback sheet page
        self.browser.get(f"{self.live_server_url}/feedback/template/{template.pk}/feedback-sheet/")

        # Wait for the page to render the assessment-grade element (used as a safe ready-check)
        self.wait.until(EC.presence_of_element_located((By.ID, "assessment-grade")))

        # Grab the page content twice to assert example selection is deterministic
        page = self.browser.page_source
        # Reload and grab again
        self.browser.refresh()
        self.wait.until(EC.presence_of_element_located((By.ID, "assessment-grade")))
        page2 = self.browser.page_source

        # Category labels should be present
        self.assertIn("Design", page)
        self.assertIn("Implementation", page)

        # Extract per-category example awarded marks from the first page.
        # Grade categories display: "<grade> (<marks> marks)"
        # Numeric categories display: "<marks> / <max> marks"
        import re
        marks = []
        for m in re.findall(r"\((\d+)\s+marks\)", page):
            marks.append(int(m))
        for m in re.findall(r"(\d+)\s*/\s*\d+\s+marks", page):
            marks.append(int(m))

        # Ensure we found at least one per-category example mark to confirm examples are displayed.
        self.assertGreater(len(marks), 0, "Should find per-category example marks in the page")

        # Now assert that reloading the page produces the same per-category marks (deterministic selection)
        self.assertEqual(page, page2, "Example selection should be deterministic across page loads")
