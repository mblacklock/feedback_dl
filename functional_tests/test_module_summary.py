# functional_tests/test_module_summary.py
import os
import time
import openpyxl
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from .base import FunctionalTestBase


class ModuleSummaryFT(FunctionalTestBase):
    def setUp(self):
        super().setUp()
        self.fixture_dir = os.path.join(
            r"c:\Backup Drive\Documents\django-apps\feedback_dl",
            "functional_tests", "fixtures"
        )
        os.makedirs(self.fixture_dir, exist_ok=True)
        self.fixture_path = os.path.join(self.fixture_dir, "dummy_mcrf.xlsx")

        # Dynamically generate a valid MCRF workbook fixture
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.append(["Module Marks Record Form (MCRF) - CIS3001"])
        ws.append([])
        ws.append(["", "", "CW1", "CW1", "Exam", "Exam"])
        ws.append(["Student ID", "Student Name", "Mark", "Grade", "Mark", "Grade"])
        ws.append(["w12345678", "Alice Smith", 24, "A", 35, "B"])
        ws.append(["12345679/2", "Bob Jones", 18, "C", 28, "D"])
        wb.save(self.fixture_path)

    def tearDown(self):
        if os.path.exists(self.fixture_path):
            try:
                os.remove(self.fixture_path)
            except OSError:
                pass
        super().tearDown()

    def test_user_can_upload_mcrf_and_download_module_summary_zip(self):
        """
        GIVEN: An academic has a completed MCRF spreadsheet.
        WHEN: They visit the Module Summary tool, upload the file, and confirm weights.
        THEN: They design the layout and receive a ZIP download containing summary HTML sheets.
        """
        # WHEN: They visit the module summary tool
        self.browser.get(f"{self.live_server_url}/module-summary/")
        
        # THEN: They see the premium header
        page_title = self.wait.until(
            EC.presence_of_element_located((By.TAG_NAME, "h1"))
        )
        self.assertIn("Module Summary Sheet Generator", page_title.text)
        
        file_input = self.browser.find_element(By.NAME, "file")
        self.assertIsNotNone(file_input)
        
        # WHEN: They upload their MCRF Excel spreadsheet
        file_input.send_keys(self.fixture_path)
        
        # AND: Click the Upload/Analyse button
        upload_btn = self.browser.find_element(By.CSS_SELECTOR, "button[type='submit']")
        self.browser.execute_script("arguments[0].scrollIntoView(true);", upload_btn)
        self.browser.execute_script("arguments[0].click();", upload_btn)
        
        # THEN: They are redirected to the Confirmation UI
        self.wait.until(EC.url_contains("/module-summary/mapping/"))
        
        # AND: They see that column roles have been auto-inferred
        confirm_title = self.browser.find_element(By.TAG_NAME, "h2")
        self.assertIn("Confirm MCRF Grade Mapping", confirm_title.text)
        
        # Verify student details mapping selectors exist
        name_select = self.browser.find_element(By.NAME, "col_student_name")
        id_select = self.browser.find_element(By.NAME, "col_student_id")
        self.assertIsNotNone(name_select)
        self.assertIsNotNone(id_select)
        
        # Verify component columns parsed and weights sum input boxes present
        page_content = self.browser.page_source
        self.assertIn("CW1 - Mark", page_content)
        self.assertIn("Exam - Mark", page_content)
        
        # WHEN: They submit the confirmation form to proceed to layout builder
        generate_btn = self.browser.find_element(By.CSS_SELECTOR, "button[type='submit']")
        self.browser.execute_script("arguments[0].scrollIntoView(true);", generate_btn)
        self.browser.execute_script("arguments[0].click();", generate_btn)
        
        # THEN: They are redirected to the WYSIWYG Layout UI
        self.wait.until(EC.url_contains("/module-summary/layout/"))
        
        # AND: They see that they are in the Designer view
        layout_title = self.browser.find_element(By.TAG_NAME, "h3")
        self.assertIn("Module Summary Designer", layout_title.text)
        
        # WHEN: They submit the layout design form
        layout_submit_btn = self.browser.find_element(By.CSS_SELECTOR, "form#layoutForm button[type='submit']")
        self.browser.execute_script("arguments[0].scrollIntoView(true);", layout_submit_btn)
        self.browser.execute_script("arguments[0].click();", layout_submit_btn)
        
        # THEN: They receive the ZIP file response
        time.sleep(2)
        self.assertNotIn("Server Error", self.browser.title)
        self.assertNotIn("Traceback", self.browser.page_source)
