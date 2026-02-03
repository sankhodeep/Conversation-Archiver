import sys
import os
import threading
import json
import queue
import difflib
import base64
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTextEdit, QPushButton, QLabel, QFileDialog, QMessageBox,
    QCheckBox, QLineEdit, QDialog, QListWidget, QListWidgetItem,
    QDialogButtonBox, QScrollArea, QComboBox, QFormLayout, QInputDialog
)
from PySide6.QtCore import Signal, QObject, Qt
from pdf_engine import create_pdf_page, merge_pdfs
from file_processor import process_conversation_file

# --- File Selection Dialog ---
class FileSelectionDialog(QDialog):
    """A dialog for selecting, unselecting, and reordering files for batch processing.

    This dialog displays a list of files found in a selected folder. Users can
    uncheck files to exclude them from the batch and use drag-and-drop to
    change the processing order.

    Attributes:
        list_widget (QListWidget): A widget to display the list of files.
    """
    def __init__(self, files, parent=None):
        """Initializes the FileSelectionDialog.

        Args:
            files (list[str]): A list of file names to display.
            parent (QWidget, optional): The parent widget. Defaults to None.
        """
        super().__init__(parent)
        self.setWindowTitle("Select and Order Files")
        self.setGeometry(200, 200, 500, 600)

        layout = QVBoxLayout(self)

        self.list_widget = QListWidget()
        self.list_widget.setDragDropMode(QListWidget.InternalMove)

        for file in files:
            item = QListWidgetItem(file)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Checked)
            self.list_widget.addItem(item)

        layout.addWidget(self.list_widget)

        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def get_selected_files_in_order(self):
        """Retrieves the list of files that are checked, in their current display order.

        Returns:
            list[str]: An ordered list of the selected file names.
        """
        selected_files = []
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            if item.checkState() == Qt.Checked:
                selected_files.append(item.text())
        return selected_files

# --- Chunk Widget for Selection Dialog ---
class ChunkWidgetItem(QWidget):
    """A custom widget to display a single conversation chunk in the selection dialog.

    This widget includes a main checkbox to include/exclude the entire chunk,
    and sub-checkboxes to include/exclude the user and model parts individually.
    It also shows a preview of the text content.

    Attributes:
        main_check (QCheckBox): The primary checkbox to toggle the whole chunk.
        user_check (QCheckBox): Checkbox to include the user's message.
        model_check (QCheckBox): Checkbox to include the model's response.
    """
    def __init__(self, chunk_number, user_text, model_text, has_image, parent=None):
        """Initializes the ChunkWidgetItem.

        Args:
            chunk_number (int): The sequential number of the chunk.
            user_text (str): The text from the user's part of the conversation.
            model_text (str): The text from the model's part of the conversation.
            has_image (bool): True if the model's response includes an image.
            parent (QWidget, optional): The parent widget. Defaults to None.
        """
        super().__init__(parent)
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(10, 10, 10, 10)

        # --- Main Checkbox and Title ---
        title_layout = QHBoxLayout()
        title = f"Chunk {chunk_number}"
        if has_image:
            title += " (Image)"
        self.main_check = QCheckBox(title)
        self.main_check.setChecked(True)
        self.main_check.stateChanged.connect(self.toggle_sub_checks)
        title_layout.addWidget(self.main_check)
        self.layout.addLayout(title_layout)

        # --- Sub-checkboxes and Text Previews ---
        self.user_check = QCheckBox("Include User")
        self.user_check.setChecked(True)
        self.user_text_preview = QLabel(f"<i>User:</i> {user_text[:100]}...")
        self.user_text_preview.setWordWrap(True)
        self.user_text_preview.setVisible(bool(user_text))

        self.model_check = QCheckBox("Include Model")
        self.model_check.setChecked(True)
        self.model_text_preview = QLabel(f"<i>Model:</i> {model_text[:100]}...")
        self.model_text_preview.setWordWrap(True)
        self.model_text_preview.setVisible(bool(model_text or has_image)) # Show if text or image

        sub_layout = QVBoxLayout()
        sub_layout.setContentsMargins(20, 0, 0, 0)
        sub_layout.addWidget(self.user_check)
        sub_layout.addWidget(self.user_text_preview)
        sub_layout.addWidget(self.model_check)
        sub_layout.addWidget(self.model_text_preview)
        self.layout.addLayout(sub_layout)

    def toggle_sub_checks(self, state):
        """Enables or disables sub-checkboxes based on the main checkbox's state.

        Args:
            state (int): The Qt.CheckState of the main checkbox.
        """
        is_checked = state == Qt.Checked
        self.user_check.setEnabled(is_checked)
        self.model_check.setEnabled(is_checked)

    def get_selection(self):
        """Gets the user's selection for this chunk.

        Returns:
            dict or None: A dictionary with 'include_user' and 'include_model'
            booleans if the main checkbox is checked, otherwise None.
        """
        if not self.main_check.isChecked():
            return None
        return {
            "include_user": self.user_check.isChecked(),
            "include_model": self.model_check.isChecked()
        }

# --- Chunk Selection Dialog ---
class ChunkSelectionDialog(QDialog):
    """A dialog for selecting which conversation chunks from a file to include in the PDF.

    This dialog displays a scrollable list of `ChunkWidgetItem` instances, allowing
    the user to make fine-grained selections. It also includes a feature to
    select all chunks from a certain number onwards.

    Attributes:
        chunks (list[dict]): The raw chunk data from the processed file.
        chunk_widgets (list[ChunkWidgetItem]): The list of widget instances created.
    """
    def __init__(self, chunks, file_name, parent=None):
        """Initializes the ChunkSelectionDialog.

        Args:
            chunks (list[dict]): A list of conversation chunks.
            file_name (str): The name of the file being processed.
            parent (QWidget, optional): The parent widget. Defaults to None.
        """
        super().__init__(parent)
        self.setWindowTitle(f"Select Chunks for: {file_name}")
        self.setGeometry(150, 150, 800, 700)

        self.chunks = chunks
        self.chunk_widgets = []

        main_layout = QVBoxLayout(self)

        # --- "Start From" Feature ---
        start_from_layout = QHBoxLayout()
        start_from_layout.addWidget(QLabel("Start from chunk:"))
        self.start_from_edit = QLineEdit()
        self.start_from_edit.setPlaceholderText("e.g., 23")
        start_from_layout.addWidget(self.start_from_edit)
        apply_button = QPushButton("Apply")
        apply_button.clicked.connect(self.apply_start_from)
        start_from_layout.addWidget(apply_button)

        select_all_button = QPushButton("Select All")
        select_all_button.clicked.connect(self.apply_select_all)
        start_from_layout.addWidget(select_all_button)

        model_only_button = QPushButton("Model Only")
        model_only_button.clicked.connect(self.apply_model_only)
        start_from_layout.addWidget(model_only_button)

        main_layout.addLayout(start_from_layout)

        # --- Scroll Area for Chunks ---
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_content = QWidget()
        self.list_layout = QVBoxLayout(scroll_content)
        scroll_area.setWidget(scroll_content)
        main_layout.addWidget(scroll_area)

        # --- Populate with Chunk Widgets ---
        for i, chunk in enumerate(self.chunks):
            widget = ChunkWidgetItem(
                i + 1,
                chunk.get("user_text", ""),
                chunk.get("model_text", ""),
                "model_image" in chunk
            )
            self.list_layout.addWidget(widget)
            self.chunk_widgets.append(widget)

        # --- Dialog Buttons ---
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        main_layout.addWidget(button_box)

    def apply_start_from(self):
        """Checks all chunks from the specified number onwards."""
        try:
            start_num = int(self.start_from_edit.text())
            for i, widget in enumerate(self.chunk_widgets):
                is_checked = (i + 1) >= start_num
                widget.main_check.setChecked(is_checked)
                # Also reset sub-checks to their default state
                widget.user_check.setChecked(True)
                widget.model_check.setChecked(True)

        except ValueError:
            QMessageBox.warning(self, "Invalid Input", "Please enter a valid number.")

    def apply_select_all(self):
        """Checks all chunks and all sub-boxes."""
        for widget in self.chunk_widgets:
            widget.main_check.setChecked(True)
            widget.user_check.setChecked(True)
            widget.model_check.setChecked(True)

    def apply_model_only(self):
        """Unchecks all User Message boxes and checks all Model Response boxes."""
        for widget in self.chunk_widgets:
            # Ensure the chunk itself is included
            widget.main_check.setChecked(True)
            # Exclude user, include model
            widget.user_check.setChecked(False)
            widget.model_check.setChecked(True)

    def get_selected_chunks(self):
        """Constructs a list of selected chunks based on the user's choices.

        Returns:
            list[dict]: A list of chunk dictionaries, formatted for the PDF
            worker. Each dictionary includes the original text/image data
            plus the user's include/exclude choices.
        """
        selected = []
        for i, widget in enumerate(self.chunk_widgets):
            selection_state = widget.get_selection()
            if selection_state:
                original_chunk = self.chunks[i]
                new_chunk = {
                    "user_text": original_chunk.get("user_text", ""),
                    "model_text": original_chunk.get("model_text", ""),
                    "include_user": selection_state["include_user"],
                    "include_model": selection_state["include_model"]
                }
                if "model_image" in original_chunk:
                    new_chunk["model_image"] = original_chunk["model_image"]
                selected.append(new_chunk)
        return selected

# --- Communication object for worker thread ---
class WorkerSignals(QObject):
    """Defines the signals available from a running worker thread.

    Attributes:
        finished (Signal): Emits a string message on completion or error.
        progress (Signal): Emits a string message for progress updates.
    """
    finished = Signal(str)
    progress = Signal(str)

class PdfWorker(QObject):
    """Worker thread for creating and merging PDFs to keep the UI responsive.

    This worker processes tasks from a queue in a separate thread, emitting
    signals to update the UI without freezing it.

    Attributes:
        signals (WorkerSignals): An object containing signals for communication.
        task_queue (queue.Queue): The queue from which to fetch PDF generation tasks.
        is_running (bool): A flag to control the execution loop.
    """
    def __init__(self, task_queue):
        """Initializes the PdfWorker.

        Args:
            task_queue (queue.Queue): The queue to process tasks from.
        """
        super().__init__()
        self.signals = WorkerSignals()
        self.task_queue = task_queue
        self.is_running = True

    def run(self):
        """The main execution loop for the worker thread.

        Continuously fetches tasks from the queue and processes them.
        Handles PDF page creation for recovery info and conversation chunks,
        then merges them into the main PDF. Exits when `is_running` is False.
        """
        while self.is_running:
            try:
                task = self.task_queue.get(timeout=1)
                if task is None:  # Sentinel value to stop
                    self.is_running = False
                    continue

                chunks, main_pdf_path, show_headings, user_heading, model_heading, recovery_info = task

                # --- Load Latest Mapping ---
                mappings_dir = "mappings"
                latest_mapping = []
                if os.path.exists(mappings_dir):
                    mapping_files = [f for f in os.listdir(mappings_dir) if f.startswith("mapping_") and f.endswith(".json")]
                    if mapping_files:
                        latest_mapping_file = sorted(mapping_files)[-1]
                        try:
                            with open(os.path.join(mappings_dir, latest_mapping_file), 'r', encoding='utf-8') as f:
                                latest_mapping = json.load(f)
                        except Exception as e:
                            print(f"Error loading mapping: {e}")

                # --- Handle Recovery Info ---
                if recovery_info:
                    self.signals.progress.emit(f"Creating recovery page for {recovery_info.get('export_file_name', 'file')}...")
                    recovery_page_path = "_temp_recovery_page.pdf"
                    create_pdf_page(
                        user_text="", model_text="",
                        output_path=recovery_page_path,
                        recovery_info=recovery_info
                    )
                    merge_pdfs(main_pdf_path, recovery_page_path)

                # --- Process Chunks ---
                total_chunks = len(chunks)
                for i, chunk in enumerate(chunks):
                    self.signals.progress.emit(f"Processing chunk {i + 1}/{total_chunks} for {recovery_info.get('export_file_name', 'file')}...")
                    user_text = chunk.get("user_text", "") if chunk.get("include_user", False) else ""
                    model_text = chunk.get("model_text", "") if chunk.get("include_model", False) else ""
                    
                    # Handle multiple images (existing + supplemental)
                    model_images = []
                    if chunk.get("include_model", False):
                        # Add existing image from export if any
                        existing_img = chunk.get("model_image")
                        if existing_img:
                            model_images.append(existing_img)
                        
                        # Add supplemental images via fuzzy matching
                        if model_text and latest_mapping:
                            for item in latest_mapping:
                                snippet = item.get("text_snippet", "")
                                if not snippet: continue
                                
                                # Use ratio for fuzzy match
                                ratio = difflib.SequenceMatcher(None, model_text, snippet).ratio()
                                if ratio > 0.9: # High confidence match
                                    img_paths = item.get("image_paths", [])
                                    # Fallback for old single image format
                                    if not img_paths and item.get("image_path"):
                                        img_paths = [item.get("image_path")]
                                    
                                    for img_path in img_paths:
                                        if img_path and os.path.exists(img_path):
                                            try:
                                                with open(img_path, "rb") as f:
                                                    data = base64.b64encode(f.read()).decode('utf-8')
                                                    model_images.append({"mimeType": "image/png", "data": data})
                                            except Exception as e:
                                                print(f"Error reading supplemental image: {e}")

                    user_response_num = chunk.get("user_response_num")
                    model_response_num = chunk.get("model_response_num")

                    if not user_text and not model_text and not model_images:
                        continue

                    temp_page_path = "_temp_page.pdf"
                    create_pdf_page(
                        user_text=user_text, model_text=model_text,
                        model_images=model_images, output_path=temp_page_path,
                        show_headings=show_headings, user_heading=user_heading,
                        model_heading=model_heading, user_response_num=user_response_num,
                        model_response_num=model_response_num, recovery_info=None
                    )
                    merge_pdfs(main_pdf_path, temp_page_path)

                self.task_queue.task_done()

            except queue.Empty:
                continue # Just check is_running again
            except Exception as e:
                self.signals.finished.emit(f"Error: {e}")
                self.task_queue.task_done()

        self.signals.finished.emit("All tasks completed successfully!")

    def stop(self):
        """Stops the worker thread's execution loop."""
        self.is_running = False

# --- Main Application Window ---
class MainWindow(QMainWindow):
    """The main application window for the Conversation Archiver.

    This class sets up the entire GUI, manages user interactions, handles
    configuration saving/loading, and coordinates the background PDF
    generation tasks with the `PdfWorker`.
    """
    def __init__(self):
        """Initializes the MainWindow, sets up the UI, and connects signals."""
        super().__init__()
        self.setWindowTitle("Conversation Archiver")
        self.setGeometry(100, 100, 700, 800)

        # --- Central Widget ---
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        # --- Scroll Area for Content ---
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        main_layout.addWidget(scroll_area)

        # This widget will contain all the scrollable content
        scroll_content_widget = QWidget()
        scroll_area.setWidget(scroll_content_widget)
        content_layout = QVBoxLayout(scroll_content_widget)

        # --- Recovery Information Section ---
        recovery_group = QWidget()
        recovery_group.setStyleSheet("border: 1px solid #ccc; border-radius: 5px; padding: 10px;")
        recovery_layout = QFormLayout(recovery_group)
        recovery_layout.addRow(QLabel("<h3>Recovery Information</h3>"))

        self.chat_platform_combo = QComboBox()
        self.chat_platform_combo.addItems(["ChatGPT", "Gemini", "Claude", "Qwen"])
        self.chat_platform_combo.setEditable(True)
        recovery_layout.addRow("Chat Platform:", self.chat_platform_combo)

        self.chat_link_entry = QLineEdit()
        recovery_layout.addRow("Chat Link:", self.chat_link_entry)

        self.chat_account_entry = QLineEdit()
        recovery_layout.addRow("Chat Account:", self.chat_account_entry)

        md_file_layout = QHBoxLayout()
        self.md_file_location_button = QPushButton("Choose MD File...")
        self.md_file_location_button.clicked.connect(self.choose_md_file)
        self.md_file_name_label = QLineEdit()
        self.md_file_name_label.setPlaceholderText("No file selected...")
        self.md_file_name_label.setReadOnly(True)
        md_file_layout.addWidget(self.md_file_location_button)
        md_file_layout.addWidget(self.md_file_name_label)
        recovery_layout.addRow("MD File:", md_file_layout)


        self.extra_notes_text = QTextEdit()
        self.extra_notes_text.setFixedHeight(80)
        recovery_layout.addRow("Extra Notes:", self.extra_notes_text)

        content_layout.addWidget(recovery_group)


        # --- Options ---
        self.show_headings_check = QCheckBox("Show Headings")
        self.show_headings_check.setChecked(True)
        content_layout.addWidget(self.show_headings_check)

        # --- User Message ---
        self.user_heading_entry = QLineEdit("User Message")
        content_layout.addWidget(self.user_heading_entry)
        self.user_text_box = QTextEdit()
        content_layout.addWidget(self.user_text_box)

        # --- Model Response ---
        self.model_heading_entry = QLineEdit("Model Response")
        content_layout.addWidget(self.model_heading_entry)
        self.model_text_box = QTextEdit()
        content_layout.addWidget(self.model_text_box)

        # --- File Chooser (Fixed at the bottom) ---
        file_layout = QHBoxLayout()
        self.pdf_path_label = QLineEdit("No file selected...")
        self.pdf_path_label.setReadOnly(True)
        file_layout.addWidget(self.pdf_path_label)
        choose_file_button = QPushButton("Choose File...")
        choose_file_button.clicked.connect(self.choose_file)
        file_layout.addWidget(choose_file_button)

        self.import_folder_button = QPushButton("Import from Folder...")
        self.import_folder_button.clicked.connect(self.choose_folder)
        file_layout.addWidget(self.import_folder_button)
        main_layout.addLayout(file_layout)

        # --- Config Management ---
        config_layout = QHBoxLayout()
        config_layout.addWidget(QLabel("Config:"))
        self.config_combo = QComboBox()
        self.config_combo.setPlaceholderText("Select a config...")
        self.config_combo.activated.connect(self.load_configuration)
        config_layout.addWidget(self.config_combo)

        self.save_config_button = QPushButton("Save Config")
        self.save_config_button.clicked.connect(self.save_configuration)
        config_layout.addWidget(self.save_config_button)

        self.delete_config_button = QPushButton("Delete Config")
        self.delete_config_button.clicked.connect(self.delete_configuration)
        config_layout.addWidget(self.delete_config_button)
        main_layout.addLayout(config_layout)


        # --- Bottom Bar ---
        bottom_layout = QHBoxLayout()
        self.add_button = QPushButton("Add to PDF")
        self.add_button.clicked.connect(self.process_and_add_pdf)
        bottom_layout.addWidget(self.add_button)
        self.status_label = QLabel("Status: Ready")
        bottom_layout.addWidget(self.status_label)
        main_layout.addLayout(bottom_layout)

        # --- Worker Thread and Queue Setup ---
        self.task_queue = queue.Queue()
        self.worker = PdfWorker(self.task_queue)
        self.thread = threading.Thread(target=self.worker.run, daemon=True)
        self.worker.signals.progress.connect(self.update_status)
        self.worker.signals.finished.connect(self.on_processing_finished)
        self.thread.start()

        self.configs = {}
        self.config_file = "configs.json"
        self._load_all_configs()
        self._populate_configs_combo()

        # --- Validation Signal Connections ---
        self.chat_platform_combo.currentTextChanged.connect(self._update_batch_button_state)
        self.chat_link_entry.textChanged.connect(self._update_batch_button_state)
        self.chat_account_entry.textChanged.connect(self._update_batch_button_state)
        self.md_file_name_label.textChanged.connect(self._update_batch_button_state)

        # Set initial state
        self._update_batch_button_state()


    def _load_all_configs(self):
        """Loads all named configurations from the JSON file."""
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r') as f:
                    self.configs = json.load(f)
            except (json.JSONDecodeError, IOError):
                self.configs = {}  # Start fresh if file is corrupt

    def _save_all_configs(self):
        """Saves all named configurations to the JSON file."""
        try:
            with open(self.config_file, 'w') as f:
                json.dump(self.configs, f, indent=4)
        except IOError as e:
            QMessageBox.critical(self, "Error", f"Could not save configs to file: {e}")

    def _populate_configs_combo(self):
        """Clears and repopulates the configurations dropdown."""
        self.config_combo.clear()
        self.config_combo.addItem("Select a config...")  # Placeholder
        self.config_combo.addItems(sorted(self.configs.keys()))

    def save_configuration(self):
        """Prompts the user for a name and saves the current UI settings as a configuration."""
        config_name, ok = QInputDialog.getText(self, "Save Configuration", "Enter a name for this configuration:")
        if ok and config_name:
            self.configs[config_name] = {
                "chat_platform": self.chat_platform_combo.currentText(),
                "chat_account": self.chat_account_entry.text(),
                "extra_notes": self.extra_notes_text.toPlainText(),
                "user_heading": self.user_heading_entry.text(),
                "model_heading": self.model_heading_entry.text()
            }
            self._save_all_configs()
            self._populate_configs_combo()
            self.config_combo.setCurrentText(config_name)
            QMessageBox.information(self, "Success", f"Configuration '{config_name}' saved.")

    def load_configuration(self):
        """Loads the selected configuration from the dropdown and applies its settings to the UI."""
        config_name = self.config_combo.currentText()
        if config_name and config_name != "Select a config...":
            config_data = self.configs.get(config_name)
            if config_data:
                self.chat_platform_combo.setCurrentText(config_data.get("chat_platform", ""))
                self.chat_account_entry.setText(config_data.get("chat_account", ""))
                self.extra_notes_text.setPlainText(config_data.get("extra_notes", ""))
                self.user_heading_entry.setText(config_data.get("user_heading", "User Message"))
                self.model_heading_entry.setText(config_data.get("model_heading", "Model Response"))

    def delete_configuration(self):
        """Deletes the currently selected configuration after confirming with the user."""
        config_name = self.config_combo.currentText()
        if config_name and config_name != "Select a config...":
            reply = QMessageBox.question(self, "Delete Configuration",
                                       f"Are you sure you want to delete '{config_name}'?",
                                       QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if reply == QMessageBox.Yes:
                if config_name in self.configs:
                    del self.configs[config_name]
                    self._save_all_configs()
                    self._populate_configs_combo()
                    QMessageBox.information(self, "Success", f"Configuration '{config_name}' deleted.")

    def choose_md_file(self):
        """Opens a file dialog for the user to select the single markdown file for a batch."""
        filepath, _ = QFileDialog.getOpenFileName(self, "Select Markdown File", "", "Markdown Files (*.md)")
        if filepath:
            self.md_file_name_label.setText(os.path.basename(filepath))
            # Store the full path to be used when creating recovery pages.
            self.md_full_path = filepath
        self._update_batch_button_state()

    def _update_batch_button_state(self):
        """Enables or disables the 'Import from Folder' button based on field content."""
        is_valid = all([
            self.chat_platform_combo.currentText().strip(),
            self.chat_link_entry.text().strip(),
            self.chat_account_entry.text().strip(),
            self.md_file_name_label.text().strip()
        ])
        self.import_folder_button.setEnabled(is_valid)

    def choose_file(self):
        """Opens a file dialog for the user to select the main destination PDF file."""
        filepath, _ = QFileDialog.getOpenFileName(self, "Select Your Main PDF File", "", "PDF Files (*.pdf)")
        if filepath:
            self.pdf_path_label.setText(filepath)

    def choose_folder(self):
        """Handles the 'Import from Folder' workflow.

        This method prompts the user to select a folder, then presents the
        `FileSelectionDialog` and `ChunkSelectionDialog` to let the user
        curate the content. It then queues all selected content for PDF
        generation by the worker thread.
        """
        folder_path = QFileDialog.getExistingDirectory(self, "Select Folder Containing Conversation Files")
        if not folder_path:
            return

        main_pdf_path = self.pdf_path_label.text()
        if "No file selected..." in main_pdf_path:
            QMessageBox.warning(self, "Warning", "Please choose a destination PDF file first.")
            return

        try:
            all_files = sorted([f for f in os.listdir(folder_path) if not f.startswith('.')])
            if not all_files:
                QMessageBox.information(self, "No Files Found", "The selected folder is empty.")
                return

            file_dialog = FileSelectionDialog(all_files, self)
            if not file_dialog.exec():
                return # User cancelled the file selection

            selected_files = file_dialog.get_selected_files_in_order()
            if not selected_files:
                return

            self.add_button.setEnabled(False)
            self.status_label.setText("Status: Processing folder...")
            QApplication.processEvents() # Update UI

            # Initialize a counter for the entire batch
            # response_counter = 1

            for file_name in selected_files:
                file_path = os.path.join(folder_path, file_name)
                self.status_label.setText(f"Status: Processing {file_name}...")
                QApplication.processEvents()

                try:
                    platform_name = self.chat_platform_combo.currentText()
                    chunks = process_conversation_file(file_path, platform_name)
                    if not chunks:
                        QMessageBox.warning(self, "No Content", f"No conversation chunks found in {file_name}.")
                        continue

                    chunk_dialog = ChunkSelectionDialog(chunks, file_name, self)
                    if not chunk_dialog.exec():
                        continue # User cancelled

                    selected_chunks = chunk_dialog.get_selected_chunks()

                    # Add numbering
                    # for chunk in selected_chunks:
                    #     if chunk.get("include_user") and chunk.get("user_text"):
                    #         chunk["user_response_num"] = response_counter
                    #         response_counter += 1
                    #     if chunk.get("include_model") and (chunk.get("model_text") or chunk.get("model_image")):
                    #         chunk["model_response_num"] = response_counter
                    #         response_counter += 1

                    # --- Gather Recovery Info for this specific file ---
                    recovery_info = {
                        "chat_platform": self.chat_platform_combo.currentText(),
                        "chat_link": self.chat_link_entry.text(),
                        "chat_account": self.chat_account_entry.text(),
                        "export_file_name": file_name,
                        "export_file_location": file_path,
                        "md_file_name": self.md_file_name_label.text(),
                        "md_file_location": getattr(self, 'md_full_path', ''),
                        "extra_notes": self.extra_notes_text.toPlainText()
                    }

                    # --- Add task to the queue ---
                    if selected_chunks or recovery_info:
                        task = (
                            selected_chunks,
                            main_pdf_path,
                            self.show_headings_check.isChecked(),
                            self.user_heading_entry.text().strip(),
                            self.model_heading_entry.text().strip(),
                            recovery_info
                        )
                        self.task_queue.put(task)

                except Exception as e:
                    QMessageBox.critical(self, "Error Processing File", f"Could not process {file_name}: {e}")

            self.status_label.setText("Status: All files have been queued for processing.")
            self.add_button.setEnabled(True)

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to read folder: {e}")
            self.status_label.setText("Status: Error.")
            self.add_button.setEnabled(True)


    def process_selected_chunks(self, chunks, recovery_info=None):
        """Adds a single PDF generation task to the worker queue.

        Args:
            chunks (list[dict]): A list of conversation chunks to be added to the PDF.
            recovery_info (dict, optional): A dictionary of recovery metadata.
                Defaults to None.
        """
        if not chunks and not recovery_info:
            return

        main_pdf_path = self.pdf_path_label.text()
        if "No file selected..." in main_pdf_path:
            QMessageBox.warning(self, "Warning", "Please choose a destination PDF file.")
            return

        self.add_button.setEnabled(False)
        self.status_label.setText("Status: Queuing task...")

        task = (
            chunks,
            main_pdf_path,
            self.show_headings_check.isChecked(),
            self.user_heading_entry.text().strip(),
            self.model_heading_entry.text().strip(),
            recovery_info
        )
        self.task_queue.put(task)


    def process_and_add_pdf(self):
        """Handles the 'Add to PDF' button click for single, manual entries.

        It takes the text from the main text boxes, packages it as a single
        "chunk," and queues it for processing.
        """
        user_text = self.user_text_box.toPlainText().strip()
        model_text = self.model_text_box.toPlainText().strip()

        if not user_text and not model_text:
            QMessageBox.warning(self, "Warning", "Both text boxes are empty.")
            return

        # --- Create a single chunk and process it ---
        single_chunk = [{
            "user_text": user_text,
            "model_text": model_text,
            "include_user": True,
            "include_model": True
        }]
        self.process_selected_chunks(single_chunk, recovery_info=None)


    def update_status(self, message):
        """Updates the status label with a message from the worker thread.

        Args:
            message (str): The status message to display.
        """
        self.status_label.setText(f"Status: {message}")

    def on_processing_finished(self, message):
        """Handles the 'finished' signal from the worker thread.

        It displays an error if one occurred, otherwise it clears the text boxes
        and updates the status. It re-enables the 'Add to PDF' button.

        Args:
            message (str): The final message from the worker.
        """
        if "Error" in message:
            QMessageBox.critical(self, "Error", message)
            self.status_label.setText("Status: Error!")
        else:
            # Check if queue is empty to show final message
            if self.task_queue.empty():
                self.status_label.setText(f"Status: {message}")
            self.user_text_box.clear()
            self.model_text_box.clear()

        self.add_button.setEnabled(True)

    def closeEvent(self, event):
        """Ensures the worker thread is stopped gracefully when the window is closed.

        Args:
            event (QCloseEvent): The close event.
        """
        self.worker.stop()
        self.task_queue.put(None)  # Sentinel to unblock the worker's get()
        self.thread.join()
        event.accept()


def main():
    """The main entry point for the application."""
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()