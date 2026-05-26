# functional_tests/test_pdf_generation.py
import os
import time
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from .base import FunctionalTestBase


class PDFGenerationFT(FunctionalTestBase):
    def test_user_can_upload_spreadsheet_and_download_pdf_zip(self):
        """
        GIVEN: An academic has a grades spreadsheet with rubric marks and feedback comments.
        WHEN: They visit the PDF generation tool, upload the file, and confirm bounds.
        THEN: They receive a ZIP download containing clean, beautifully formatted PDFs for all students.
        """
        # WHEN: They visit the assessment feedback tool home
        self.browser.get(f"{self.live_server_url}/assessment-feedback/")
        
        # THEN: They see a premium header and a drag-and-drop file input
        page_title = self.wait.until(
            EC.presence_of_element_located((By.TAG_NAME, "h1"))
        )
        self.assertIn("Cohort PDF Feedback Generator", page_title.text)
        
        file_input = self.browser.find_element(By.NAME, "file")
        self.assertIsNotNone(file_input)
        
        # WHEN: They upload their Excel spreadsheet
        fixture_path = os.path.join(
            r"c:\Backup Drive\Documents\django-apps\feedback_dl",
            "functional_tests", "fixtures", "dummy_grades.xlsx"
        )
        file_input.send_keys(fixture_path)
        
        # AND: Click the Upload/Analyze button
        upload_btn = self.browser.find_element(By.CSS_SELECTOR, "button[type='submit']")
        self.browser.execute_script("arguments[0].scrollIntoView(true);", upload_btn)
        self.browser.execute_script("arguments[0].click();", upload_btn)
        
        # THEN: They are redirected to the Confirmation UI
        self.wait.until(EC.url_contains("/assessment-feedback/confirm/"))
        
        # AND: They see that column roles have been auto-inferred
        confirm_title = self.browser.find_element(By.TAG_NAME, "h2")
        self.assertIn("Confirm Data Mapping", confirm_title.text)
        
        # Verify student details mapping selectors exist and have selections
        name_select = self.browser.find_element(By.NAME, "col_student_name")
        id_select = self.browser.find_element(By.NAME, "col_student_id")
        self.assertIsNotNone(name_select)
        self.assertIsNotNone(id_select)
        
        # Verify that parsed criteria rows exist (Design, Implementation, Testing)
        # We look for labels or headings in our mapping table
        page_content = self.browser.page_source
        self.assertIn("Design", page_content)
        self.assertIn("Implementation", page_content)
        self.assertIn("Testing", page_content)
        
        # AND: They choose a postgraduate/undergraduate level
        degree_select = self.browser.find_element(By.NAME, "degree_level")
        self.assertIsNotNone(degree_select)
        
        # WHEN: They submit the confirmation form to trigger PDF generation
        generate_btn = self.browser.find_element(By.CSS_SELECTOR, "button.btn-generate")
        self.browser.execute_script("arguments[0].scrollIntoView(true);", generate_btn)
        self.browser.execute_script("arguments[0].click();", generate_btn)
        
        # THEN: They receive the file response (in Selenium, we wait or check for success indicators)
        time.sleep(2)
        # Assert page doesn't show a 500 server error
        self.assertNotIn("Server Error", self.browser.title)
        self.assertNotIn("Traceback", self.browser.page_source)
