# Conversation Archiver

A desktop application built with PySide6 that allows users to archive conversations (e.g., AI model responses and user inputs) into a styled PDF document. It leverages Puppeteer (Node.js) for advanced PDF generation and `pypdf` for merging.

## Features

*   Input fields for user messages and model responses.
*   Option to include customizable headings for each section.
*   Generates styled PDF pages with embedded CSS and emoji support.
*   Merges new pages into an existing PDF or creates a new one.
*   Responsive UI using PySide6.

## Technologies Used

*   Python 3
*   PySide6
*   `pypdf`
*   Node.js
*   Puppeteer
*   HTML/CSS

## Setup Instructions

1.  **Clone the repository:**
    ```bash
    git clone [your-repo-url]
    ```
2.  **Navigate to the project directory:**
    ```bash
    cd ConversationArchiver
    ```
3.  **Install Python dependencies:**
    ```bash
    pip install -r requirements.txt
    ```
4.  **Install Node.js dependencies:**
    ```bash
    npm install
    ```

## Usage

1.  Run the application:
    ```bash
    python app.py
    ```
2.  Select an existing PDF or create a new one.
3.  Enter your user message and model response.
4.  Click "Add to PDF" to generate and merge the page.
