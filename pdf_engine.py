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
    Converts a Markdown string to HTML, with special handling for code blocks.

    This function finds all fenced code blocks, highlights them using Pygments,
    replaces them with placeholders, converts the remaining Markdown to HTML,
    and then re-injects the highlighted code blocks back into the HTML.

    Args:
        markdown_text (str): The Markdown text to convert.

    Returns:
        str: The fully-formatted HTML.
    """
    highlighted_blocks = []

    def _highlight_and_replace(match):
        language = match.group(1).strip()
        content = match.group(2).strip()
        if language.lower() == 'mermaid':
            placeholder = f"MERMAIDBLOCK{len(highlighted_blocks)}"
            highlighted_blocks.append(f'<pre class="mermaid">{content}</pre>')
            return placeholder

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
        # Handle both CODEBLOCK and MERMAIDBLOCK
        # The markdown processor might wrap the placeholder in <p> tags.
        for prefix in ["CODEBLOCK", "MERMAIDBLOCK"]:
            placeholder = f"{prefix}{i}"
            placeholder_p = f"<p>{placeholder}</p>"
            if placeholder_p in html_output:
                html_output = html_output.replace(placeholder_p, block_html)
            else:
                html_output = html_output.replace(placeholder, block_html)

    return html_output

def merge_pdfs(main_pdf_path, new_page_path):
    """Merges a new PDF page into a main PDF file.

    If the main PDF does not exist, the new page is renamed to become the main
    PDF. Otherwise, the new page is appended to the existing pages. The new
    page file is always deleted after the operation.

    Args:
        main_pdf_path (str): The file path for the primary PDF document.
        new_page_path (str): The file path for the new PDF page to be merged.

    Returns:
        bool: True if the merge was successful, False otherwise.
    """
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

def format_recovery_info(recovery_info):
    """Formats the recovery information dictionary into a styled HTML table.

    Args:
        recovery_info (dict or None): A dictionary containing the recovery
            metadata for a conversation file.

    Returns:
        str: A string of HTML representing the formatted table, or an empty
        string if `recovery_info` is None.
    """
    if not recovery_info:
        return ""

    # Start building the HTML content
    html_block = "<div class='recovery-info'><h2>Recovery Information</h2><table>"

    # Define the desired order and display names for keys
    key_map = {
        "chat_platform": "Chat Platform",
        "chat_link": "Chat Link",
        "chat_account": "Chat Account",
        "export_file_name": "Export File Name",
        "export_file_location": "Export File Location",
        "md_file_name": "MD File Name",
        "md_file_location": "MD File Location",
        "extra_notes": "Extra Notes"
    }

    for key, display_name in key_map.items():
        value = recovery_info.get(key)
        if value:  # Only add a row if the value exists
            # Escape the value to prevent HTML injection issues
            escaped_value = html.escape(str(value))
            html_block += f"<tr><td class='key'>{display_name}:</td><td class='value'>{escaped_value}</td></tr>"

    html_block += "</table></div>"
    return html_block

def create_pdf_page(user_text, model_text, output_path, model_image=None, show_headings=True, user_heading="User Message", model_heading="Model Response", user_response_num=None, model_response_num=None, recovery_info=None):
    """Creates a single, styled PDF page from text and optional image data.

    This function generates a temporary HTML file with embedded CSS, populates it
    with the provided conversation data and recovery information, and then calls
    a Node.js script which uses Puppeteer to render the HTML into a PDF file.

    Args:
        user_text (str): The text of the user's message.
        model_text (str): The text of the model's response.
        output_path (str): The file path where the generated PDF page will be saved.
        model_image (dict, optional): A dictionary containing 'mimeType' and base64
            'data' for an image. Defaults to None.
        show_headings (bool, optional): Whether to include headings for user/model
            sections. Defaults to True.
        user_heading (str, optional): The text for the user message heading.
            Defaults to "User Message".
        model_heading (str, optional): The text for the model response heading.
            Defaults to "Model Response".
        user_response_num (int, optional): The sequential number for the user's
            response. Defaults to None.
        model_response_num (int, optional): The sequential number for the model's
            response. Defaults to None.
        recovery_info (dict, optional): A dictionary of recovery metadata to be
            included at the top of the page. Defaults to None.

    Returns:
        bool: True if the PDF page was created successfully, False otherwise.
    """
    temp_html_path = os.path.join(os.path.dirname(__file__), '_temp.html')

    try:
        # --- 1. Read CSS Content ---
        css_path = os.path.join(os.path.dirname(__file__), 'style.css')
        with open(css_path, 'r', encoding='utf-8') as f:
            css_content = f.read()

        # --- 2. Prepare HTML Content ---
        recovery_section = format_recovery_info(recovery_info)

        user_section = ""
        if user_text:
            if show_headings and user_heading:
                heading_html = f"<span>{html.escape(user_heading)}</span>"
                # if user_response_num is not None:
                #     heading_html += f"<span class='response-number'>{user_response_num}</span>"
                user_section += f"<div class='heading-container'><h1>{heading_html}</h1></div>"
            user_text_html = markdown_to_html_final(user_text)
            user_section += f"<div class='content'>{user_text_html}</div>"

        model_section = ""
        if model_text or model_image:
            if show_headings and model_heading:
                if model_text or (model_image and not model_text):
                    heading_html = f"<span>{html.escape(model_heading)}</span>"
                    # if model_response_num is not None:
                    #     heading_html += f"<span class='response-number'>{model_response_num}</span>"
                    model_section += f"<div class='heading-container'><h1>{heading_html}</h1></div>"

            if model_text:
                model_text_html = markdown_to_html_final(model_text)
                model_section += f"<div class='content'>{model_text_html}</div>"

            if model_image:
                try:
                    mime_type = model_image.get("mimeType", "image/png")
                    data = model_image.get("data", "")
                    if not data:
                        raise ValueError("Image data is empty")
                    # The 'data' from the file is already base64, so we create a data URI
                    image_uri = f"data:{mime_type};base64,{data}"
                    model_section += f'<img src="{image_uri}" alt="Generated Image" style="max-width: 100%; height: auto;">'
                except Exception as e:
                    print(f"Warning: Could not process image. Error: {e}")
                    model_section += "<p><i>[Image could not be processed]</i></p>"

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
            <script id="MathJax-script" async src="https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-mml-chtml.js"></script>
            <script src="https://cdn.jsdelivr.net/npm/mermaid/dist/mermaid.min.js"></script>
            <script>
                mermaid.initialize({{ startOnLoad: true }});
            </script>
            <style>
                {css_content}
            </style>
        </head>
        <body>
            {recovery_section}
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
