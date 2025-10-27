import os
import subprocess
from pypdf import PdfWriter, PdfReader
import html
import markdown
import re
from pygments import highlight
from pygments.lexers import get_lexer_by_name, TextLexer
from pygments.formatters import HtmlFormatter

def markdown_to_html_final(markdown_text):
    """
    Robustly converts Markdown to HTML by separating code blocks, processing them with
    Pygments, and then re-injecting them into the final HTML.
    """
    highlighted_blocks = []

    def _highlight_and_replace(match):
        language = match.group(1).strip()
        content = match.group(2).strip()
        placeholder = f"CODEBLOCK{len(highlighted_blocks)}"

        try:
            lexer = get_lexer_by_name(language)
        except Exception:
            lexer = TextLexer()

        formatter = HtmlFormatter(cssclass="codehilite")
        highlighted_code = highlight(content, lexer, formatter)
        highlighted_blocks.append(highlighted_code)

        # Return a simple placeholder that won't be altered by markdown processing
        return placeholder

    # 1. Find all code blocks, highlight them, and replace with a simple placeholder.
    pattern = re.compile(r"^[ \t]*```([^\n]*)\n(.*?)\n^[ \t]*```", re.DOTALL | re.MULTILINE)
    text_with_placeholders = pattern.sub(_highlight_and_replace, markdown_text)

    # 2. Process the main text (which now contains only placeholders).
    html_output = markdown.markdown(
        text_with_placeholders,
        extensions=['tables', 'nl2br', 'pymdownx.arithmatex'],
        extension_configs={
            'pymdownx.arithmatex': {'generic': True}
        }
    )

    # 3. Replace the placeholders with the fully rendered HTML for the code blocks.
    for i, block_html in enumerate(highlighted_blocks):
        # The markdown processor might wrap the placeholder in <p> tags.
        placeholder_p = f"<p>CODEBLOCK{i}</p>"
        if placeholder_p in html_output:
            html_output = html_output.replace(placeholder_p, block_html)
        else: # Fallback
            html_output = html_output.replace(f"CODEBLOCK{i}", block_html)

    return html_output

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
        css_path = os.path.join(os.path.dirname(__file__), 'style.css')
        with open(css_path, 'r', encoding='utf-8') as f:
            css_content = f.read()

        user_section = ""
        if user_text:
            if show_headings and user_heading:
                user_section += f"<h1>{html.escape(user_heading)}</h1>"
            user_text_html = markdown_to_html_final(user_text)
            user_section += f"<div class='content'>{user_text_html}</div>"

        model_section = ""
        if model_text:
            if show_headings and model_heading:
                model_section += f"<h1>{html.escape(model_heading)}</h1>"
            model_text_html = markdown_to_html_final(model_text)
            model_section += f"<div class='content'>{model_text_html}</div>"

        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <title>PDF Page</title>
            <link rel="preconnect" href="https://fonts.googleapis.com">
            <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
            <link href="https://fonts.googleapis.com/css2?family=Noto+Color+Emoji&family=Roboto:wght@400;700&display=swap" rel="stylesheet">
            <script id="MathJax-script" async src="https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-mml-chtml.js"></script>
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

        script_path = os.path.join(os.path.dirname(__file__), 'generate_pdf.js')
        subprocess.run(
            ['node', script_path],
            check=True,
            cwd=os.path.dirname(__file__)
        )

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
        if os.path.exists(temp_html_path):
            os.remove(temp_html_path)
