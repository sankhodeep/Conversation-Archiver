import sys
import os
import threading
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTextEdit, QPushButton, QLabel, QFileDialog, QMessageBox,
    QCheckBox, QLineEdit, QDialog, QListWidget, QListWidgetItem,
    QDialogButtonBox
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

# --- Communication object for worker thread ---
class WorkerSignals(QObject):
    finished = Signal(str)  # Emits a string message on completion or error
    progress = Signal(str) # Emits a progress update message

class BulkPdfWorker(QObject):
    """Worker thread for processing multiple files and adding them to a PDF."""
    def __init__(self, file_paths, main_pdf_path, show_headings, user_heading, model_heading):
        super().__init__()
        self.signals = WorkerSignals()
        self.file_paths = file_paths
        self.main_pdf_path = main_pdf_path
        self.show_headings = show_headings
        self.user_heading = user_heading
        self.model_heading = model_heading
        self.skipped_files = []

    def run(self):
        total_files = len(self.file_paths)
        for i, file_path in enumerate(self.file_paths):
            self.signals.progress.emit(f"Processing file {i + 1} of {total_files}: {os.path.basename(file_path)}")
            try:
                conversation_pairs = process_conversation_file(file_path)
                if not conversation_pairs:
                    self.skipped_files.append((os.path.basename(file_path), "No conversation content found."))
                    continue

                for pair in conversation_pairs:
                    temp_page_path = "_temp_page.pdf"
                    create_pdf_page(
                        pair["user_text"], pair["model_text"], temp_page_path,
                        self.show_headings, self.user_heading, self.model_heading
                    )
                    merge_pdfs(self.main_pdf_path, temp_page_path)

            except Exception as e:
                self.skipped_files.append((os.path.basename(file_path), str(e)))

        # --- Final report ---
        success_count = total_files - len(self.skipped_files)
        summary = f"Finished! Successfully processed {success_count} of {total_files} files."
        if self.skipped_files:
            summary += "\n\nSkipped files:\n"
            for name, reason in self.skipped_files:
                summary += f"- {name}: {reason}\n"
        self.signals.finished.emit(summary)


class PdfWorker(QObject):
    """Worker thread for creating and merging PDFs to keep the UI responsive."""
    def __init__(self, user_text, model_text, main_pdf_path, show_headings, user_heading, model_heading):
        super().__init__()
        self.signals = WorkerSignals()
        self.user_text = user_text
        self.model_text = model_text
        self.main_pdf_path = main_pdf_path
        self.show_headings = show_headings
        self.user_heading = user_heading
        self.model_heading = model_heading

    def run(self):
        try:
            temp_page_path = "_temp_page.pdf"
            
            success_create = create_pdf_page(
                self.user_text, self.model_text, temp_page_path,
                self.show_headings, self.user_heading, self.model_heading
            )
            if not success_create:
                raise RuntimeError("Failed to create the temporary PDF page.")

            success_merge = merge_pdfs(self.main_pdf_path, temp_page_path)
            if not success_merge:
                raise RuntimeError("Failed to merge the new page into the main PDF.")
                
            self.signals.finished.emit("Success! Page added.")
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
            files = sorted([f for f in os.listdir(folder_path) if not f.startswith('.')])
            if not files:
                QMessageBox.information(self, "No Files Found", "The selected folder is empty.")
                return

            dialog = FileSelectionDialog(files, self)
            if dialog.exec():
                selected_files = dialog.get_selected_files_in_order()
                if selected_files:
                    full_paths = [os.path.join(folder_path, f) for f in selected_files]
                    self.process_bulk_pdf(full_paths)

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to read folder: {e}")

    def process_bulk_pdf(self, file_paths):
        self.add_button.setEnabled(False)
        self.status_label.setText("Status: Starting bulk processing...")

        self.bulk_worker = BulkPdfWorker(
            file_paths,
            self.pdf_path_label.text(),
            self.show_headings_check.isChecked(),
            self.user_heading_entry.text().strip(),
            self.model_heading_entry.text().strip()
        )
        self.bulk_thread = threading.Thread(target=self.bulk_worker.run)
        self.bulk_worker.signals.progress.connect(self.update_status)
        self.bulk_worker.signals.finished.connect(self.on_bulk_processing_finished)
        self.bulk_thread.start()

    def on_bulk_processing_finished(self, summary):
        QMessageBox.information(self, "Bulk Processing Complete", summary)
        self.status_label.setText("Status: Bulk processing finished.")
        self.add_button.setEnabled(True)

    def update_status(self, message):
        self.status_label.setText(f"Status: {message}")

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

        self.add_button.setEnabled(False)
        self.status_label.setText("Status: Processing...")

        # --- Setup and run worker thread ---
        self.worker = PdfWorker(
            user_text, model_text, main_pdf_path,
            self.show_headings_check.isChecked(),
            self.user_heading_entry.text().strip(),
            self.model_heading_entry.text().strip()
        )
        self.thread = threading.Thread(target=self.worker.run)
        self.worker.signals.finished.connect(self.on_processing_finished)
        self.thread.start()

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