# Conversation Archiver

A powerful desktop application for archiving digital conversations into beautifully styled and organized PDF documents. Built with Python (PySide6) and Node.js (Puppeteer), this tool provides fine-grained control over the archiving process, from batch processing entire folders to selecting individual conversation chunks.

## Features

*   **Manual & Batch Processing**: Add single conversation entries manually or import and process an entire folder of conversation files at once.
*   **Selective Archiving**: For each file, a dialog allows you to select specific conversation chunks and even choose whether to include the user, model, or both parts of an exchange.
*   **File Reordering**: In batch mode, you can easily drag-and-drop files to control the order in which they are added to the PDF.
*   **Recovery Metadata**: Automatically generates a "Recovery Information" page for each file in a batch, detailing the source, account, and other important metadata.
*   **Image Support**: Renders inline images from conversation files directly into the PDF.
*   **Configuration Management**: Save and load multiple configurations for different projects or chat platforms. This includes settings like chat platform, account details, custom headings, and extra notes.
*   **Customizable Headings**: Set custom titles for "User" and "Model" sections.
*   **High-Quality PDFs**: Uses Puppeteer for superior rendering of HTML and CSS, ensuring that fonts, emojis, and markdown tables look great.
*   **Responsive UI**: A non-blocking interface, thanks to a multi-threaded architecture that handles PDF generation in the background.

## Project Structure

```
.
├── app.py                   # Main PySide6 application: UI, event handling, and thread management.
├── file_processor.py        # Logic for parsing the source conversation files.
├── pdf_engine.py            # Generates HTML and calls the Node.js script to create PDFs.
├── generate_pdf.js          # Node.js script that uses Puppeteer to convert HTML to a PDF page.
├── style.css                # CSS for styling the final PDF output.
├── requirements.txt         # Python dependencies.
├── package.json             # Node.js dependencies.
└── configs.json             # Stores saved user configurations.
```

## Technologies Used

*   **Python 3**: For the main application logic.
*   **PySide6**: For the graphical user interface.
*   **pypdf**: For merging PDF pages.
*   **markdown**: For converting markdown text to HTML.
*   **Node.js**: To run the Puppeteer script.
*   **Puppeteer**: For high-fidelity HTML-to-PDF rendering.

## Setup Instructions

1.  **Clone the repository:**
    ```bash
    git clone <your-repo-url>
    cd ConversationArchiver
    ```

2.  **Install Python dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

3.  **Install Node.js dependencies:**
    ```bash
    npm install
    ```

## Usage

### Manual Mode

1.  Run the application:
    ```bash
    python app.py
    ```
2.  Click **"Choose File..."** to select a destination PDF. This can be an existing PDF to append to or a new file name.
3.  Fill in the "User Message" and "Model Response" text boxes.
4.  Click **"Add to PDF"**. The content will be processed in the background and added to your chosen PDF.

### Batch Mode (Import from Folder)

1.  Run the application and select a destination PDF as in Manual Mode.
2.  Fill in all the fields under **"Recovery Information"** (Chat Platform, Chat Link, etc.). The "Import from Folder..." button will become enabled only when these are complete.
3.  Click **"Import from Folder..."** and select the directory containing your conversation files.
4.  A dialog will appear showing all files. Uncheck any you wish to exclude and drag-and-drop to reorder them. Click **OK**.
5.  For each file, a "Select Chunks" dialog will appear.
    *   Use the checkboxes to include or exclude entire chunks or just the user/model parts.
    *   Use the "Start from chunk" feature to quickly select all chunks from a certain point onwards.
    *   Click **OK** to confirm your selections for that file.
6.  All selected content will be queued and processed in the background, with progress updated in the status bar.
