# functional_tests/test_grade_band_descriptions.py
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from .base import FunctionalTestBase
import time


class GradeBandDescriptionsFT(FunctionalTestBase):
    """
    US-T3: As a staff member, I can add descriptions for each grade band
    in a table format, so I can define criteria for each performance level.
    """

    def test_staff_can_add_grade_band_descriptions_in_table(self):
        # GIVEN a staff member creates a new template
        self.navigate_to_home()
        self.create_new_template()
        
        # WHEN they add a category with grade bands
        self.add_category_row()
        self.fill_category(0, "Comprehension", 30, category_type='grade', subdivision='none')
        
        # Wait for grade bands table to appear
        time.sleep(0.5)
        
        # THEN they see a grid with grade band cards (one card per main grade)
        grade_grid = self.get_grade_bands_grid()
        
        # AND the grid has cards for different main grades
        cards = grade_grid.find_elements(By.CSS_SELECTOR, ".card")
        card_text = " ".join([c.text for c in cards])
        # Should have main grades in cards
        self.assertIn("1st", card_text)
        self.assertIn("2:1", card_text)
        self.assertIn("Fail", card_text)
        
        # AND they can enter descriptions for each MAIN grade (not each subdivision)
        description_inputs = self.get_description_textareas()
        # Should have 5 textareas: one for each main grade (1st, 2:1, 2:2, 3rd, Fail)
        self.assertEqual(len(description_inputs), 5, "Should have 5 description fields for 5 main grades")
        
        # WHEN they enter a description for "1st" grade (spans all 1st subdivisions)
        self.set_grade_description("1st", "Complex engineering principles are creatively and critically applied")
        
        # AND they enter a description for "2:1" grade
        self.set_grade_description("2:1", "Well-founded engineering principles are soundly applied")
        
        # Wait for auto-save
        self.wait_for_autosave()
        
        # WHEN they click "View Rubric"
        self.click_view_rubric()
        
        # THEN the grade bands are displayed in a card grid format
        summary_grid = self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".grade-bands-grid")))
        
        # AND the descriptions they entered are visible
        grid_text = summary_grid.text
        self.assertIn("Complex engineering principles are creatively and critically applied", grid_text)
        self.assertIn("Well-founded engineering principles are soundly applied", grid_text)
        
        # AND the marks for each grade band are shown
        self.assertIn("30", grid_text)  # Maximum mark
        self.assertIn("27", grid_text)  # High 1st for 30 marks
    
    def test_descriptions_persist_when_changing_subdivision(self):
        # GIVEN a staff member creates a template with grade bands
        self.navigate_to_home()
        self.create_new_template()
        
        self.add_category_row()
        self.fill_category(0, "Analysis", 20, category_type='grade', subdivision='none')
        
        time.sleep(0.5)
        
        # WHEN they enter descriptions for grade bands
        self.set_grade_description("1st", "Excellent analysis with critical insight")
        self.set_grade_description("2:1", "Good analysis with sound reasoning")
        
        # AND they change the subdivision
        self.select_subdivision(0, 'high_low')
        
        time.sleep(0.5)
        
        # THEN the descriptions they entered should still be there
        description_inputs = self.get_description_textareas()
        
        descriptions_text = []
        for ta in description_inputs:
            grade = ta.get_attribute("data-grade")
            value = ta.get_attribute("value")
            if grade == "1st":
                self.assertEqual(value, "Excellent analysis with critical insight", 
                               "1st grade description should persist after subdivision change")
                descriptions_text.append(value)
            elif grade == "2:1":
                self.assertEqual(value, "Good analysis with sound reasoning",
                               "2:1 grade description should persist after subdivision change")
                descriptions_text.append(value)
        
        self.assertEqual(len(descriptions_text), 2, "Both descriptions should be preserved")
    
    def test_descriptions_preserved_when_switching_to_numeric_and_back(self):
        # GIVEN a staff member creates a template with grade bands and descriptions
        self.navigate_to_home()
        self.create_new_template()
        
        self.add_category_row()
        self.fill_category(0, "Methodology", 20, category_type='grade', subdivision='none')
        
        time.sleep(0.5)
        
        # WHEN they enter descriptions
        self.set_grade_description("1st", "Exceptional methodology with innovative approach")
        self.set_grade_description("2:1", "Strong methodology with clear justification")
        
        self.wait_for_autosave()
        
        # AND they switch to Numeric type
        self.select_category_type(0, 'numeric')
        
        self.wait_for_autosave()
        
        # AND they navigate to view and back to edit
        self.click_view_rubric()
        self.click_edit_template()
        
        # AND they switch back to Grade type
        self.select_category_type(0, 'grade')
        
        # Select subdivision to show grade bands
        self.select_subdivision(0, 'none')
        
        time.sleep(0.5)
        
        # THEN the descriptions they entered should still be there
        description_inputs = self.get_description_textareas()
        
        found_first = False
        found_two_one = False
        for ta in description_inputs:
            grade = ta.get_attribute("data-grade")
            value = ta.get_attribute("value")
            if grade == "1st" and value == "Exceptional methodology with innovative approach":
                found_first = True
            elif grade == "2:1" and value == "Strong methodology with clear justification":
                found_two_one = True
        
        self.assertTrue(found_first, "1st grade description should be preserved after switching to numeric and back")
        self.assertTrue(found_two_one, "2:1 grade description should be preserved after switching to numeric and back")
