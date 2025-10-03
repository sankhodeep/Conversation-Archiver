import sys
import os
import threading
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTextEdit, QPushButton, QLabel, QFileDialog, QMessageBox,
    QCheckBox, QLineEdit, QDialog, QListWidget, QListWidgetItem,
    QDialogButtonBox, QScrollArea
)
from PySide6.QtCore import Signal, QObject, Qt
from pdf_engine import create_pdf_page, merge_pdfs
from file_processor import process_conversation_file

# --- File Selection Dialog ---
class FileSelectionDialog(QDialog):
    def __init__(self, files, parent=None):
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
        selected_files = []
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            if item.checkState() == Qt.Checked:
                selected_files.append(item.text())
        return selected_files

# --- Chunk Widget for Selection Dialog ---
class ChunkWidgetItem(QWidget):
    def __init__(self, chunk_number, user_text, model_text, parent=None):
        super().__init__(parent)
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(10, 10, 10, 10)

        # --- Main Checkbox and Title ---
        title_layout = QHBoxLayout()
        self.main_check = QCheckBox(f"Chunk {chunk_number}")
        self.main_check.setChecked(True)
        self.main_check.stateChanged.connect(self.toggle_sub_checks)
        title_layout.addWidget(self.main_check)
        self.layout.addLayout(title_layout)

        # --- Sub-checkboxes and Text Previews ---
        self.user_check = QCheckBox("Include User")
        self.user_check.setChecked(True)
        self.user_text_preview = QLabel(f"<i>User:</i> {user_text[:100]}...")
        self.user_text_preview.setWordWrap(True)

        self.model_check = QCheckBox("Include Model")
        self.model_check.setChecked(True)
        self.model_text_preview = QLabel(f"<i>Model:</i> {model_text[:100]}...")
        self.model_text_preview.setWordWrap(True)

        sub_layout = QVBoxLayout()
        sub_layout.setContentsMargins(20, 0, 0, 0)
        sub_layout.addWidget(self.user_check)
        sub_layout.addWidget(self.user_text_preview)
        sub_layout.addWidget(self.model_check)
        sub_layout.addWidget(self.model_text_preview)
        self.layout.addLayout(sub_layout)

    def toggle_sub_checks(self, state):
        is_checked = state == Qt.Checked
        self.user_check.setEnabled(is_checked)
        self.model_check.setEnabled(is_checked)

    def get_selection(self):
        if not self.main_check.isChecked():
            return None
        return {
            "include_user": self.user_check.isChecked(),
            "include_model": self.model_check.isChecked()
        }

# --- Chunk Selection Dialog ---
class ChunkSelectionDialog(QDialog):
    def __init__(self, chunks, file_name, parent=None):
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
            widget = ChunkWidgetItem(i + 1, chunk["user_text"], chunk["model_text"])
            self.list_layout.addWidget(widget)
            self.chunk_widgets.append(widget)

        # --- Dialog Buttons ---
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        main_layout.addWidget(button_box)

    def apply_start_from(self):
        try:
            start_num = int(self.start_from_edit.text())
            for i, widget in enumerate(self.chunk_widgets):
                is_checked = (i + 1) >= start_num
                widget.main_check.setChecked(is_checked)
                widget.user_check.setChecked(True)
                widget.model_check.setChecked(True)

        except ValueError:
            QMessageBox.warning(self, "Invalid Input", "Please enter a valid number.")

    def get_selected_chunks(self):
        selected = []
        for i, widget in enumerate(self.chunk_widgets):
            selection_state = widget.get_selection()
            if selection_state:
                selected.append({
                    "user_text": self.chunks[i]["user_text"],
                    "model_text": self.chunks[i]["model_text"],
                    "include_user": selection_state["include_user"],
                    "include_model": selection_state["include_model"]
                })
        return selected

# --- Communication object for worker thread ---
class WorkerSignals(QObject):
    finished = Signal(str)  # Emits a string message on completion or error
    progress = Signal(str) # Emits a progress update message

class PdfWorker(QObject):
    """Worker thread for creating and merging PDFs to keep the UI responsive."""
    def __init__(self, chunks, main_pdf_path, show_headings, user_heading, model_heading):
        super().__init__()
        self.signals = WorkerSignals()
        self.chunks = chunks
        self.main_pdf_path = main_pdf_path
        self.show_headings = show_headings
        self.user_heading = user_heading
        self.model_heading = model_heading

    def run(self):
        try:
            total_chunks = len(self.chunks)
            for i, chunk in enumerate(self.chunks):
                self.signals.progress.emit(f"Processing chunk {i + 1} of {total_chunks}...")

                user_text = chunk.get("user_text", "") if chunk.get("include_user", False) else ""
                model_text = chunk.get("model_text", "") if chunk.get("include_model", False) else ""

                if not user_text and not model_text:
                    continue

                temp_page_path = "_temp_page.pdf"
                create_pdf_page(
                    user_text, model_text, temp_page_path,
                    self.show_headings, self.user_heading, self.model_heading
                )
                merge_pdfs(self.main_pdf_path, temp_page_path)

            self.signals.finished.emit(f"Success! {total_chunks} chunk(s) added.")
        except Exception as e:
            self.signals.finished.emit(f"Error: {e}")

# --- Main Application Window ---
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Conversation Archiver")
        self.setGeometry(100, 100, 700, 800)

        # --- Central Widget and Layout ---
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        # --- Options ---
        self.show_headings_check = QCheckBox("Show Headings")
        self.show_headings_check.setChecked(True)
        main_layout.addWidget(self.show_headings_check)

        # --- User Message ---
        self.user_heading_entry = QLineEdit("User Message")
        main_layout.addWidget(self.user_heading_entry)
        self.user_text_box = QTextEdit()
        main_layout.addWidget(self.user_text_box)

        # --- Model Response ---
        self.model_heading_entry = QLineEdit("Model Response")
        main_layout.addWidget(self.model_heading_entry)
        self.model_text_box = QTextEdit()
        main_layout.addWidget(self.model_text_box)

        # --- File Chooser ---
        file_layout = QHBoxLayout()
        self.pdf_path_label = QLineEdit("No file selected...")
        self.pdf_path_label.setReadOnly(True)
        file_layout.addWidget(self.pdf_path_label)
        choose_file_button = QPushButton("Choose File...")
        choose_file_button.clicked.connect(self.choose_file)
        file_layout.addWidget(choose_file_button)

        import_folder_button = QPushButton("Import from Folder...")
        import_folder_button.clicked.connect(self.choose_folder)
        file_layout.addWidget(import_folder_button)
        main_layout.addLayout(file_layout)

        # --- Bottom Bar ---
        bottom_layout = QHBoxLayout()
        self.add_button = QPushButton("Add to PDF")
        self.add_button.clicked.connect(self.process_and_add_pdf)
        bottom_layout.addWidget(self.add_button)
        self.status_label = QLabel("Status: Ready")
        bottom_layout.addWidget(self.status_label)
        main_layout.addLayout(bottom_layout)

    def choose_file(self):
        filepath, _ = QFileDialog.getOpenFileName(self, "Select Your Main PDF File", "", "PDF Files (*.pdf)")
        if filepath:
            self.pdf_path_label.setText(filepath)

    def choose_folder(self):
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

            for file_name in selected_files:
                file_path = os.path.join(folder_path, file_name)
                self.status_label.setText(f"Status: Processing {file_name}...")
                QApplication.processEvents()

                try:
                    chunks = process_conversation_file(file_path)
                    if not chunks:
                        QMessageBox.warning(self, "No Content", f"No conversation chunks found in {file_name}.")
                        continue

                    chunk_dialog = ChunkSelectionDialog(chunks, file_name, self)
                    if chunk_dialog.exec():
                        selected_chunks = chunk_dialog.get_selected_chunks()
                        self.process_selected_chunks(selected_chunks)

                except Exception as e:
                    QMessageBox.critical(self, "Error Processing File", f"Could not process {file_name}: {e}")

            self.status_label.setText("Status: Folder processing complete.")
            self.add_button.setEnabled(True)

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to read folder: {e}")
            self.status_label.setText("Status: Error.")
            self.add_button.setEnabled(True)


    def process_selected_chunks(self, chunks):
        """Processes a list of chunks selected by the user in a worker thread."""
        if not chunks:
            return

        self.add_button.setEnabled(False)
        self.status_label.setText("Status: Starting PDF generation...")

        self.worker = PdfWorker(
            chunks,
            self.pdf_path_label.text(),
            self.show_headings_check.isChecked(),
            self.user_heading_entry.text().strip(),
            self.model_heading_entry.text().strip()
        )
        self.thread = threading.Thread(target=self.worker.run)
        self.worker.signals.progress.connect(self.update_status)
        self.worker.signals.finished.connect(self.on_processing_finished)
        self.thread.start()


    def process_and_add_pdf(self):
        user_text = self.user_text_box.toPlainText().strip()
        model_text = self.model_text_box.toPlainText().strip()
        main_pdf_path = self.pdf_path_label.text()

        if not user_text and not model_text:
            QMessageBox.warning(self, "Warning", "Both text boxes are empty.")
            return
        if "No file selected..." in main_pdf_path:
            QMessageBox.warning(self, "Warning", "Please choose a destination PDF file.")
            return

        # --- Create a single chunk and process it ---
        single_chunk = {
            "user_text": user_text,
            "model_text": model_text,
            "include_user": True,
            "include_model": True
        }
        self.process_selected_chunks([single_chunk])


    def update_status(self, message):
        self.status_label.setText(f"Status: {message}")


    def on_processing_finished(self, message):
        if message.startswith("Error"):
            QMessageBox.critical(self, "Error", message)
            self.status_label.setText("Status: Error!")
        else:
            self.status_label.setText(f"Status: {message}")
            self.user_text_box.clear()
            self.model_text_box.clear()
        self.add_button.setEnabled(True)

def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()