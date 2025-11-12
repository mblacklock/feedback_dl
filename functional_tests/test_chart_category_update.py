from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from .base import FunctionalTestBase
import time


class ChartCategoryUpdateFT(FunctionalTestBase):
    """
    GIVEN a template edit page with a radar chart configured
    WHEN the user adds a new category via the UI
    THEN the radar chart's category selection list is refreshed to include the new category
    """

    def test_new_category_appears_in_radar_chart_options(self):
        # GIVEN: staff member opens the template builder
        self.navigate_to_home()
        self.create_new_template()

        # AND: fill required summary fields so autosave can proceed
        self.fill_template_fields(
            title="Chart Category Update",
            module_code="CS999",
            module_title="Chart Module",
            assessment_title="Test",
            weighting=10,
            max_marks=100,
            component=1
        )

        # Wait for autosave to stabilise
        self.wait_for_autosave()

        # WHEN: they add a radar chart
        add_chart_btn = self.browser.find_element(By.ID, "add-chart")
        # Use JS click to avoid interception by floating elements in headless mode
        self.browser.execute_script("arguments[0].scrollIntoView(true); arguments[0].click();", add_chart_btn)

        # Wait for a chart row to appear
        chart_row = self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "#charts .chart-row")))

        # Ensure the chart config initially reflects current categories
        # Capture existing category labels
        existing_labels = [el.text for el in chart_row.find_elements(By.CSS_SELECTOR, ".form-check-label")]

        # WHEN: they add a new category and fill it in
        new_label = f"NewCategory{int(time.time())}"
        self.add_category_row()
        # Fill the last category row with the new label
        rows = self.get_category_rows()
        new_index = len(rows) - 1
        self.fill_category(new_index, new_label, 10)

        # Wait for autosave and for chart config to be refreshed
        self.wait_for_autosave(1.5)

        # THEN: the radar chart config should include the new category label
        # Wait until a chart-category input with the new_label as value exists
        def checkbox_has_new_label(driver):
            try:
                chart_row_el = driver.find_element(By.CSS_SELECTOR, "#charts .chart-row")
                inputs = chart_row_el.find_elements(By.CSS_SELECTOR, "input.chart-category")
                return any(i.get_attribute('value') == new_label for i in inputs)
            except Exception:
                return False

        self.wait.until(checkbox_has_new_label)

        # Final assertion
        chart_row_el = self.browser.find_element(By.CSS_SELECTOR, "#charts .chart-row")
        inputs = chart_row_el.find_elements(By.CSS_SELECTOR, "input.chart-category")
        values = [i.get_attribute('value') for i in inputs]
        assert new_label in values, f"Expected new category '{new_label}' to appear in chart options, got {values}"

    def test_deleted_category_is_removed_from_radar_chart_options(self):
        # GIVEN: a template builder with a radar chart and one category
        self.navigate_to_home()
        self.create_new_template()
        self.fill_template_fields(
            title="Chart Category Delete",
            module_code="CS999",
            module_title="Chart Module",
            assessment_title="Test",
            weighting=10,
            max_marks=100,
            component=1
        )
        self.wait_for_autosave()

        # Add radar chart
        add_chart_btn = self.browser.find_element(By.ID, "add-chart")
        self.browser.execute_script("arguments[0].scrollIntoView(true); arguments[0].click();", add_chart_btn)
        chart_row = self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "#charts .chart-row")))

        # Add a category and ensure it appears in chart options
        unique_label = f"ToDelete{int(time.time())}"
        self.add_category_row()
        rows = self.get_category_rows()
        idx = len(rows) - 1
        self.fill_category(idx, unique_label, 10)
        self.wait_for_autosave(1.5)

        # Confirm the option exists
        def has_label(driver):
            try:
                cr = driver.find_element(By.CSS_SELECTOR, "#charts .chart-row")
                inputs = cr.find_elements(By.CSS_SELECTOR, "input.chart-category")
                return any(i.get_attribute("value") == unique_label for i in inputs)
            except Exception:
                return False
        self.wait.until(has_label)

        # WHEN: the user deletes the category
        remove_btn = rows[idx].find_element(By.CSS_SELECTOR, ".remove-category")
        self.browser.execute_script("arguments[0].scrollIntoView(true); arguments[0].click();", remove_btn)

        # Wait for autosave and chart refresh
        self.wait_for_autosave(1.5)

        # THEN: the chart config should no longer include the deleted label
        def no_label(driver):
            try:
                cr = driver.find_element(By.CSS_SELECTOR, "#charts .chart-row")
                inputs = cr.find_elements(By.CSS_SELECTOR, "input.chart-category")
                return not any(i.get_attribute("value") == unique_label for i in inputs)
            except Exception:
                return True
        self.wait.until(no_label)

        # Final assertion
        cr_el = self.browser.find_element(By.CSS_SELECTOR, "#charts .chart-row")
        values = [i.get_attribute('value') for i in cr_el.find_elements(By.CSS_SELECTOR, "input.chart-category")]
        assert unique_label not in values, f"Deleted category '{unique_label}' still present in chart options: {values}"
