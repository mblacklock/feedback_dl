from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from .base import FunctionalTestBase


class DegreeLevelFT(FunctionalTestBase):
    """
    Functional tests for selecting degree level (BEng vs MEng/MSc)
    and ensuring grade bands update accordingly.
    """

    def test_degree_level_selector_changes_grade_bands_for_level7(self):
        """
        GIVEN: A staff member creates a new template and adds a grade category
        WHEN: They view the grade bands preview for a 100-mark category
        THEN: Default (BEng) bands include '3rd' and a 40 mark band
        WHEN: They switch the degree level to MEng/MSc
        THEN: The grade bands update to Distinction/Merit/Pass/Fail and include a 50 mark pass threshold, but do not include a 40 mark
        """
        # Arrange: create template and add a grade category
        self.navigate_to_home()
        self.create_new_template()

        # Add a category and set it to grade type with 'none' subdivision
        self.add_category_row()
        self.fill_category(0, "Module Knowledge", 100, category_type='grade', subdivision='none')

        # Wait for grade bands preview to appear and assert BEng defaults (3rd, 40)
        grid = self.get_grade_bands_grid()
        grid_text = grid.text
        self.assertIn('3rd', grid_text)
        # Expect a 40 mark badge for 3rd band on a 100-mark category for BEng
        self.assertIn('40', grid_text)

        # Action: attempt to switch degree level to MEng/MSc
        # The UI control is expected to have id 'degree_level' (select) with value 'MEng'
        # This is intentionally part of the FT; implementation will add this control.
        # Use select_box_action helper to select the visible option and wait
        try:
            self.select_box_action('degree_level', 'MEng/MSc')
        except Exception:
            self.fail('Degree level selector (id="degree_level") not found or selection failed')

        # Wait for preview to refresh and include Master-level terms and 50 mark pass
        def master_preview_ready(d):
            try:
                g = d.find_element(By.CSS_SELECTOR, '.grade-bands-grid')
                t = g.text
                return ('Merit' in t or 'Pass' in t) and '50' in t
            except Exception:
                return False

        self.wait.until(master_preview_ready)

        # Final assertions
        updated_grid = self.browser.find_element(By.CSS_SELECTOR, '.grade-bands-grid')
        updated_text = updated_grid.text
        self.assertIn('Merit', updated_text)
        self.assertIn('Pass', updated_text)
        self.assertIn('50', updated_text)
        self.assertNotIn('40', updated_text)


    def test_changing_degree_level_updates_each_category_preview(self):
        """
        GIVEN: A staff member creates a new template and adds two grade categories
        WHEN: They change the `degree_level` select from BEng to MEng/MSc
        THEN: Each category's grade-band preview should update to show M-level labels
        """
        self.navigate_to_home()
        self.create_new_template()

        # Add two grade categories
        self.add_category_row()
        self.fill_category(0, "Knowledge", 100, category_type='grade', subdivision='none')

        self.add_category_row()
        self.fill_category(1, "Application", 50, category_type='grade', subdivision='none')

        # Wait for both previews to render and assert BEng content appears
        g0 = self.get_grade_bands_grid(row_index=0)
        self.assertIn('1st', g0.text)
        self.assertIn('40', g0.text)  # 3rd band anchor for 100-mark BEng

        g1 = self.get_grade_bands_grid(row_index=1)
        # For 50-mark category, BEng pass/anchors will differ; ensure a known label present
        self.assertIn('1st', g1.text)

        # Switch degree level to M-level using the helper to ensure stable selection
        try:
            self.select_box_action('degree_level', 'MEng/MSc')
        except Exception:
            self.fail('Degree level selector (id="degree_level") not found or selection failed')

        # Wait for both previews to update with M-level labels (e.g., 'Merit' or 'Pass' and 50 pass threshold)
        def all_previews_updated(d):
            try:
                g0u = d.find_element(By.CSS_SELECTOR, '#categories .category-row:nth-of-type(1) .grade-bands-grid')
                g1u = d.find_element(By.CSS_SELECTOR, '#categories .category-row:nth-of-type(2) .grade-bands-grid')
                t0 = g0u.text
                t1 = g1u.text
                # Both previews should include M-level terms such as 'Merit' or 'Distinction'
                return (('Merit' in t0 or 'Pass' in t0 or 'Distinction' in t0) and
                        ('Merit' in t1 or 'Pass' in t1 or 'Distinction' in t1))
            except Exception:
                return False

        self.wait.until(all_previews_updated)

        # Final assertions: both grids include M-level labels and include a '50' anchor for pass when appropriate
        updated_g0 = self.get_grade_bands_grid(row_index=0)
        updated_g1 = self.get_grade_bands_grid(row_index=1)

        self.assertTrue(('Merit' in updated_g0.text) or ('Distinction' in updated_g0.text) or ('Pass' in updated_g0.text))
        self.assertTrue(('Merit' in updated_g1.text) or ('Distinction' in updated_g1.text) or ('Pass' in updated_g1.text))


    def test_degree_level_change_persists_after_reload(self):
        """
        GIVEN: A staff member creates a new template with a grade category
        WHEN: They change the `degree_level` select to MEng/MSc and wait for autosave
        THEN: After refreshing the page, the degree_level select should still be MEng/MSc
              and the grade-band previews should reflect M-level labels
        """
        self.navigate_to_home()
        self.create_new_template()
        self.fill_template_fields()

        # Add a grade category so preview exists
        self.add_category_row()
        self.fill_category(0, "Synthesis", 100, category_type='grade', subdivision='none')

        # Verify BEng preview present initially
        grid = self.get_grade_bands_grid(row_index=0)
        self.assertIn('1st', grid.text)

        # Change degree level to M-level using the Select helper which waits for selection
        try:
            self.select_box_action('degree_level', 'MEng/MSc')
        except Exception:
            self.fail('Degree level selector (id="degree_level") not found or selection failed')

        # Wait for the server-side persistence by polling the DB for the template
        # Extract the template PK from the current URL (/feedback/template/<pk>/edit/)
        import re, time
        m = re.search(r'/feedback/template/(\d+)/edit/', self.browser.current_url)
        if not m:
            self.fail('Could not determine template id from URL')
        tpl_pk = int(m.group(1))

        from feedback.models import AssessmentTemplate

        saved = False
        for _ in range(20):
            tpl = AssessmentTemplate.objects.get(pk=tpl_pk)
            if tpl.degree_level == 'MEng/MSc':
                saved = True
                break
            time.sleep(0.5)

        if not saved:
            self.fail('Template degree_level was not persisted to DB within timeout')

        # Now refresh the page and wait for the editor to re-initialize
        self.browser.refresh()
        self.wait.until(EC.presence_of_element_located((By.ID, 'degree_level')))

        # Assert the select retained the M-level value
        select_after = self.browser.find_element(By.ID, 'degree_level')
        self.assertEqual(select_after.get_attribute('value'), 'MEng/MSc')

        # Also assert the grade bands preview now shows M-level labels (e.g., Merit/Pass)
        updated_grid = self.get_grade_bands_grid(row_index=0)
        updated_text = updated_grid.text
        self.assertTrue(('Merit' in updated_text) or ('Pass' in updated_text) or ('Distinction' in updated_text))
