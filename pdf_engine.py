import os
import subprocess
from pypdf import PdfWriter, PdfReader
import html

def merge_pdfs(main_pdf_path, new_page_path):
    """Merges a new page into the main PDF."""
    try:
        if not os.path.exists(main_pdf_path):
            os.rename(new_page_path, main_pdf_path)
            return True

        writer = PdfWriter()
        reader_main = PdfReader(main_pdf_path)
        for page in reader_main.pages:
            writer.add_page(page)
            
        reader_new = PdfReader(new_page_path)
        for page in reader_new.pages:
            writer.add_page(page)
            
        with open(main_pdf_path, "wb") as f:
            writer.write(f)
        return True
    except Exception as e:
        print(f"Error merging PDFs: {e}")
        return False
    finally:
        if os.path.exists(new_page_path):
            os.remove(new_page_path)

def create_pdf_page(user_text, model_text, output_path, show_headings=True, user_heading="User Message", model_heading="Model Response"):
    """
    Creates a styled PDF page by calling the Puppeteer Node.js script.
    """
    temp_html_path = os.path.join(os.path.dirname(__file__), '_temp.html')
    
    try:
        # --- 1. Read CSS Content ---
        # By reading the CSS and embedding it directly, we ensure Puppeteer always has the styles.
        css_path = os.path.join(os.path.dirname(__file__), 'style.css')
        with open(css_path, 'r', encoding='utf-8') as f:
            css_content = f.read()

        # --- 2. Prepare HTML Content ---
        user_section = ""
        if user_text:
            if show_headings and user_heading:
                user_section += f"<h1>{html.escape(user_heading)}</h1>"
            # Escape text and convert newlines to <br> tags
            user_text_html = html.escape(user_text).replace('\n', '<br>')
            user_section += f"<p>{user_text_html}</p>"

        model_section = ""
        if model_text:
            if show_headings and model_heading:
                model_section += f"<h1>{html.escape(model_heading)}</h1>"
            model_text_html = html.escape(model_text).replace('\n', '<br>')
            model_section += f"<p>{model_text_html}</p>"

        # --- 3. Create the temporary HTML file with Embedded CSS ---
        # This is the key to making the fonts and emojis work perfectly.
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <title>PDF Page</title>
            <link rel="preconnect" href="https://fonts.googleapis.com">
            <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
            <link href="https://fonts.googleapis.com/css2?family=Noto+Color+Emoji&family=Roboto:wght@400;700&display=swap" rel="stylesheet">
            <style>
                {css_content}
            </style>
        </head>
        <body>
            {user_section}
            {model_section}
        </body>
        </html>
        """
        with open(temp_html_path, "w", encoding="utf-8") as f:
            f.write(html_content)

        # --- 3. Call the Puppeteer script ---
        # We run the Node.js script as a separate process.
        script_path = os.path.join(os.path.dirname(__file__), 'generate_pdf.js')
        subprocess.run(
            ['node', script_path],
            check=True,  # This will raise an error if the script fails
            cwd=os.path.dirname(__file__) # Ensure it runs in the correct directory
        )

        # The JS script creates '_temp_page.pdf', which we rename to the final output path
        os.rename(os.path.join(os.path.dirname(__file__), '_temp_page.pdf'), output_path)

        print(f"Successfully created PDF page at: {output_path}")
        return True

    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        print(f"Error calling Puppeteer script: {e}")
        return False
    except Exception as e:
        print(f"An error occurred: {e}")
        return False
    finally:
        # --- 4. Clean up the temporary HTML file ---
        if os.path.exists(temp_html_path):
            os.remove(temp_html_path)