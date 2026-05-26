"""PDF rendering engine with WeasyPrint and robust xhtml2pdf pure-python fallback."""
import logging
from io import BytesIO
from xhtml2pdf import pisa

logger = logging.getLogger(__name__)


def render_html_to_pdf(html_content, base_url=None):
    """
    Render HTML/CSS document string into raw PDF bytes.
    
    Tries to use the premium WeasyPrint engine. If GTK system libraries
    (glib/pango) are missing (highly common on Windows environments),
    it gracefully and transparently falls back to the pure-Python xhtml2pdf engine.
    
    Args:
        html_content (str): The complete HTML/CSS source text of the page.
        base_url (str, optional): Base URL/directory path for resolving relative asset links.
        
    Returns:
        bytes: Raw PDF document binary bytes.
    """
    try:
        import sys
        import io
        import contextlib
        import logging
        
        # Temporarily silence weasyprint logging to avoid noisy debug dumps
        logging.getLogger("weasyprint").setLevel(logging.CRITICAL)
        
        # Suppress stderr and stdout to silence the FFI loader's library warning blocks
        dummy = io.StringIO()
        with contextlib.redirect_stderr(dummy), contextlib.redirect_stdout(dummy):
            from weasyprint import HTML
            
        logger.info("Attempting PDF rendering using WeasyPrint...")
        html = HTML(string=html_content, base_url=base_url)
        return html.write_pdf()
    except (OSError, ImportError) as e:
        logger.info(
            "WeasyPrint is not configured on this host (missing system GTK dependencies). "
            "Using xhtml2pdf pure-python renderer."
        )
        
        pdf_buffer = BytesIO()
        # Renders the HTML directly to PDF bytes
        pisa_status = pisa.CreatePDF(html_content, dest=pdf_buffer)
        
        if pisa_status.err:
            raise Exception(f"PDF generation failed inside xhtml2pdf: {pisa_status.err}")
            
        return pdf_buffer.getvalue()
