import os
from xhtml2pdf import pisa
import io

def create_debug_pdf(output_path):
    """
    A focused test to see if xhtml2pdf can render a color emoji
    from a local font file under ideal conditions.
    """
    try:
        # --- 1. Load the CSS content ---
        # We are using the exact same CSS file as our main app.
        css_path = os.path.join(os.path.dirname(__file__), 'style.css')
        with open(css_path, "r", encoding="utf-8") as f:
            css_content = f.read()

        # --- 2. Define the simplest possible HTML ---
        # This HTML contains only one thing: a paragraph with a test emoji.
        # This removes all other variables from the test.
        emoji_text = "This is a test: 😊"
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <style>{css_content}</style>
        </head>
        <body>
            <p>{emoji_text}</p>
        </body>
        </html>
        """

        # --- 3. Render the PDF ---
        with open(output_path, "w+b") as result_file:
            pisa_status = pisa.CreatePDF(
                io.StringIO(html_content),
                dest=result_file,
                encoding='utf-8'
            )

        if pisa_status.err:
            raise RuntimeError(f"PDF creation error: {pisa_status.err}")

        print(f"Debug PDF created successfully at: {output_path}")
        return True

    except Exception as e:
        print(f"An error occurred during the debug test: {e}")
        return False

if __name__ == '__main__':
    print("--- Running Emoji Debug Test ---")
    # Define the output file for our test
    debug_output_file = "debug_output.pdf"
    
    # Clean up any old test file
    if os.path.exists(debug_output_file):
        os.remove(debug_output_file)
        
    # Run the test
    success = create_debug_pdf(debug_output_file)
    
    if success:
        print(f"--- Test Complete ---")
        print(f"Please open the file '{debug_output_file}' and check if the emoji is in color.")
    else:
        print("--- Test Failed ---")