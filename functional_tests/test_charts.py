# functional_tests/test_charts.py
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from .base import FunctionalTestBase


class ChartsFT(FunctionalTestBase):
    """
    US-C1: As a staff member, I can configure charts for the feedback sheet,
    so students can see their performance relative to the class.
    """

    def test_staff_can_configure_charts_for_feedback_sheet(self):
        """
        GIVEN: A staff member is editing a template
        WHEN: They add chart configurations
        THEN: The configured charts appear on the feedback sheet
        """
        # GIVEN: Navigate to home and create a new template
        self.navigate_to_home()
        self.create_new_template()
        
        # Fill in basic template info
        self.fill_template_fields()
        
        # Add categories
        self.add_category_row()
        self.fill_category(0, "Section 1", 30)
        self.add_category_row()
        self.fill_category(1, "Section 2", 30)
        self.add_category_row()
        self.fill_category(2, "Section 3", 40)
        
        self.wait_for_autosave()
        
        # WHEN: They configure charts
        # Look for "Add Chart" button or section
        chart_section = self.wait.until(
            EC.presence_of_element_located((By.ID, "charts"))
        )
        
        # Click "Add Chart" button
        add_chart_btn = self.browser.find_element(By.ID, "add-chart")
        self.browser.execute_script("arguments[0].scrollIntoView(true);", add_chart_btn)
        self.browser.execute_script("arguments[0].click();", add_chart_btn)
        
        # Wait for chart form to appear
        chart_row = self.wait.until(
            EC.presence_of_element_located((By.CSS_SELECTOR, ".chart-row"))
        )
        
        # Configure first chart: Radar chart of all categories
        chart_type_select = chart_row.find_element(By.CSS_SELECTOR, "select.chart-type")
        chart_type_select.send_keys("Radar")
        
        title_input = chart_row.find_element(By.CSS_SELECTOR, "input.chart-title")
        title_input.send_keys("Performance Breakdown")
        
        # Select all categories for radar chart
        category_checkboxes = chart_row.find_elements(By.CSS_SELECTOR, "input.chart-category")
        for checkbox in category_checkboxes:
            if not checkbox.is_selected():
                self.browser.execute_script("arguments[0].click();", checkbox)
        
        self.wait_for_autosave()
        
        # Add second chart: Histogram of overall marks
        add_chart_btn.click()
        chart_rows = self.browser.find_elements(By.CSS_SELECTOR, ".chart-row")
        second_chart = chart_rows[1]
        
        chart_type_select = second_chart.find_element(By.CSS_SELECTOR, "select.chart-type")
        chart_type_select.send_keys("Histogram")
        
        title_input = second_chart.find_element(By.CSS_SELECTOR, "input.chart-title")
        title_input.send_keys("Class Mark Distribution")
        
        data_source_select = second_chart.find_element(By.CSS_SELECTOR, "select.chart-data-source")
        data_source_select.send_keys("Overall")
        
        self.wait_for_autosave()
        
        # WHEN: They view the feedback sheet
        self.click_view_feedback_sheet()
        
        # THEN: They see the configured charts with Chart.js canvases
        feedback_content = self.browser.page_source
        
        # Should include Chart.js
        self.assertIn("chart.js", feedback_content.lower())
        
        # Should show canvas elements for charts
        canvases = self.browser.find_elements(By.TAG_NAME, "canvas")
        self.assertGreaterEqual(len(canvases), 2, "Should have at least 2 chart canvases")
        
        # Should show the configured titles
        self.assertIn("Performance Breakdown", feedback_content)
        self.assertIn("Class Mark Distribution", feedback_content)
    
    def test_select_all_button_for_radar_chart_categories(self):
        """
        GIVEN: A staff member is configuring a radar chart with multiple categories
        WHEN: They click the "Select All" button
        THEN: All category checkboxes are selected
        AND: The button text changes to "Deselect All"
        AND: Clicking again deselects all checkboxes
        """
        # GIVEN: Navigate to home and create a new template with categories
        self.navigate_to_home()
        self.create_new_template()
        
        self.fill_template_fields()
        
        # Add multiple categories
        self.add_category_row()
        self.fill_category(0, "Category A", 25)
        self.add_category_row()
        self.fill_category(1, "Category B", 25)
        self.add_category_row()
        self.fill_category(2, "Category C", 25)
        self.add_category_row()
        self.fill_category(3, "Category D", 25)
        
        self.wait_for_autosave()
        
        # Add a radar chart
        add_chart_btn = self.browser.find_element(By.ID, "add-chart")
        self.browser.execute_script("arguments[0].scrollIntoView(true);", add_chart_btn)
        self.browser.execute_script("arguments[0].click();", add_chart_btn)
        
        chart_row = self.wait.until(
            EC.presence_of_element_located((By.CSS_SELECTOR, ".chart-row"))
        )
        
        # Configure as radar chart
        chart_type_select = chart_row.find_element(By.CSS_SELECTOR, "select.chart-type")
        chart_type_select.send_keys("Radar")
        
        # Wait for chart config to render (category checkboxes should appear)
        self.wait.until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "input.chart-category"))
        )
        
        # WHEN: Look for the "(select all)" checkbox
        select_all_checkbox = self.wait.until(
            EC.presence_of_element_located((By.CSS_SELECTOR, ".select-all-categories"))
        )
        
        # Scroll to checkbox to ensure it's visible
        self.browser.execute_script("arguments[0].scrollIntoView(true);", select_all_checkbox)
        
        # THEN: Checkbox should be visible and initially unchecked
        self.assertTrue(select_all_checkbox.is_displayed())
        self.assertFalse(select_all_checkbox.is_selected())
        
        # Get all category checkboxes - initially should be unchecked
        category_checkboxes = chart_row.find_elements(By.CSS_SELECTOR, "input.chart-category")
        self.assertEqual(len(category_checkboxes), 4, "Should have 4 category checkboxes")
        
        initial_checked_count = sum(1 for cb in category_checkboxes if cb.is_selected())
        
        # WHEN: Click the "(select all)" checkbox
        self.browser.execute_script("arguments[0].click();", select_all_checkbox)
        self.wait_for_autosave()
        
        # THEN: All category checkboxes should be selected
        category_checkboxes = chart_row.find_elements(By.CSS_SELECTOR, "input.chart-category")
        checked_count = sum(1 for cb in category_checkboxes if cb.is_selected())
        self.assertEqual(checked_count, 4, "All category checkboxes should be selected")
        
        # AND: Select all checkbox should be checked
        self.assertTrue(select_all_checkbox.is_selected())
        
        # WHEN: Click the checkbox again
        self.browser.execute_script("arguments[0].click();", select_all_checkbox)
        self.wait_for_autosave()
        
        # THEN: All category checkboxes should be deselected
        category_checkboxes = chart_row.find_elements(By.CSS_SELECTOR, "input.chart-category")
        checked_count = sum(1 for cb in category_checkboxes if cb.is_selected())
        self.assertEqual(checked_count, 0, "All category checkboxes should be deselected")
        
        # AND: Select all checkbox should be unchecked
        self.assertFalse(select_all_checkbox.is_selected())
    
    def test_chart_title_updates_when_chart_type_changes(self):
        """
        GIVEN: A staff member is editing a template with a radar chart
        WHEN: They change the chart type to histogram
        THEN: The chart title updates to the default for that type
        """
        # GIVEN: Navigate to home and create a new template with categories
        self.navigate_to_home()
        self.create_new_template()
        
        self.fill_template_fields()
        
        # Add categories
        self.add_category_row()
        self.fill_category(0, "Category A", 50)
        self.add_category_row()
        self.fill_category(1, "Category B", 50)
        
        self.wait_for_autosave()
        
        # Add a radar chart (default)
        add_chart_btn = self.browser.find_element(By.ID, "add-chart")
        self.browser.execute_script("arguments[0].scrollIntoView(true);", add_chart_btn)
        self.browser.execute_script("arguments[0].click();", add_chart_btn)
        
        chart_row = self.wait.until(
            EC.presence_of_element_located((By.CSS_SELECTOR, ".chart-row"))
        )
        
        # THEN: Chart title should default to "Marks Breakdown" for radar
        title_input = chart_row.find_element(By.CSS_SELECTOR, "input.chart-title")
        self.assertEqual(title_input.get_attribute('value'), "Marks Breakdown")
        
        # WHEN: Change chart type to histogram
        chart_type_select = chart_row.find_element(By.CSS_SELECTOR, "select.chart-type")
        chart_type_select.send_keys("Histogram")
        
        # Give it a moment for the JavaScript to update
        import time
        time.sleep(0.5)
        
        # THEN: Chart title should update to "Distribution of class marks"
        self.assertEqual(title_input.get_attribute('value'), "Distribution of class marks")
    
    def test_staff_can_add_short_names_for_radar_chart_categories(self):
        """
        GIVEN: A staff member is configuring a radar chart
        WHEN: They add short names for categories with long labels
        THEN: The radar chart displays the short names instead of full labels
        """
        # GIVEN: Create template with categories that have long names
        self.navigate_to_home()
        self.create_new_template()
        
        self.fill_template_fields()
        
        # Add categories with long names
        self.add_category_row()
        self.fill_category(0, "Implementation and Code Quality", 40)
        self.add_category_row()
        self.fill_category(1, "Documentation and Comments", 30)
        self.add_category_row()
        self.fill_category(2, "Testing", 30)
        
        self.wait_for_autosave()
        
        # WHEN: They add a radar chart
        add_chart_btn = self.browser.find_element(By.ID, "add-chart")
        self.browser.execute_script("arguments[0].scrollIntoView(true);", add_chart_btn)
        import time
        time.sleep(0.2)
        self.browser.execute_script("arguments[0].click();", add_chart_btn)
        
        import time
        time.sleep(0.3)
        
        chart_rows = self.browser.find_elements(By.CSS_SELECTOR, ".chart-row")
        self.assertEqual(len(chart_rows), 1)
        
        # Select radar chart type
        chart_type = chart_rows[0].find_element(By.CSS_SELECTOR, ".chart-type")
        # Use JavaScript to set the value and trigger the change event
        self.browser.execute_script("arguments[0].value = 'radar'; arguments[0].dispatchEvent(new Event('change'));", chart_type)
        
        time.sleep(0.5)
        
        # Check some categories
        category_checkboxes = chart_rows[0].find_elements(By.CSS_SELECTOR, ".chart-category")
        self.assertGreater(len(category_checkboxes), 0, "Should have category checkboxes for radar chart")
        
        # Click first two category checkboxes
        self.browser.execute_script("arguments[0].click();", category_checkboxes[0])
        time.sleep(0.2)
        self.browser.execute_script("arguments[0].click();", category_checkboxes[1])
        time.sleep(0.2)
        
        # AND: They enter short names for the long category labels
        # Find short name inputs next to the checked categories
        short_name_inputs = chart_rows[0].find_elements(By.CSS_SELECTOR, "input.category-short-name")
        self.assertGreaterEqual(len(short_name_inputs), 2, "Should have short name inputs for checked categories")
        
        # Enter short names
        short_name_inputs[0].clear()
        short_name_inputs[0].send_keys("Code")
        short_name_inputs[1].clear()
        short_name_inputs[1].send_keys("Docs")
        
        self.wait_for_autosave(2)
        
        # WHEN: They view the feedback sheet
        view_feedback_btn = self.browser.find_element(By.LINK_TEXT, "View Feedback Sheet")
        self.browser.execute_script("arguments[0].scrollIntoView(true);", view_feedback_btn)
        time.sleep(0.2)
        self.browser.execute_script("arguments[0].click();", view_feedback_btn)
        
        self.wait.until(EC.url_contains("/feedback-sheet/"))
        
        # THEN: The radar chart should display the short names
        time.sleep(1)  # Wait for chart to render
        
        page_source = self.browser.page_source
        # Chart.js renders canvas, but we can check if the script has the short names
        # The labels should be in the JavaScript that configures the chart
        self.assertIn("Code", page_source, "Short name 'Code' should appear in chart config")
        self.assertIn("Docs", page_source, "Short name 'Docs' should appear in chart config")

    def test_short_names_persist_when_editing_from_feedback_sheet(self):
        """Full end-to-end: short names entered in the editor should be saved,
        visible on the feedback sheet, and pre-filled when returning to the editor."""
        import time
        # GIVEN: Create template and categories
        self.navigate_to_home()
        self.create_new_template()

        self.fill_template_fields()

        self.add_category_row()
        self.fill_category(0, "Design", 30)
        self.add_category_row()
        self.fill_category(1, "Implementation", 70)

        self.wait_for_autosave()

        # WHEN: Add a radar chart and set short names
        add_chart_btn = self.browser.find_element(By.ID, "add-chart")
        self.browser.execute_script("arguments[0].scrollIntoView(true);", add_chart_btn)
        time.sleep(0.2)
        self.browser.execute_script("arguments[0].click();", add_chart_btn)
        time.sleep(0.3)

        chart_row = self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".chart-row")))

        # Ensure radar type
        chart_type = chart_row.find_element(By.CSS_SELECTOR, ".chart-type")
        self.browser.execute_script("arguments[0].value = 'radar'; arguments[0].dispatchEvent(new Event('change'));", chart_type)
        time.sleep(0.3)

        # Select category checkboxes and add short names
        category_checkboxes = chart_row.find_elements(By.CSS_SELECTOR, "input.chart-category")
        for cb in category_checkboxes:
            if not cb.is_selected():
                self.browser.execute_script("arguments[0].click();", cb)
                time.sleep(0.1)

        short_name_inputs = chart_row.find_elements(By.CSS_SELECTOR, "input.category-short-name")
        self.assertGreaterEqual(len(short_name_inputs), 2)
        short_name_inputs[0].clear()
        short_name_inputs[0].send_keys("Dsg")
        short_name_inputs[1].clear()
        short_name_inputs[1].send_keys("Impl")

        self.wait_for_autosave(2)

        # WHEN: View feedback sheet then click Edit Template to return
        view_feedback_btn = self.browser.find_element(By.LINK_TEXT, "View Feedback Sheet")
        self.browser.execute_script("arguments[0].scrollIntoView(true);", view_feedback_btn)
        time.sleep(0.2)
        self.browser.execute_script("arguments[0].click();", view_feedback_btn)
        self.wait_for_feedback_sheet_page()

        # Click edit link to go back to editor
        self.click_edit_template()

        # THEN: On the edit page the chart short-name inputs should be pre-filled
        chart_row = self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".chart-row")))
        short_name_inputs = chart_row.find_elements(By.CSS_SELECTOR, "input.category-short-name")
        # Values should persist
        self.assertEqual(short_name_inputs[0].get_attribute('value'), "Dsg")
        self.assertEqual(short_name_inputs[1].get_attribute('value'), "Impl")
