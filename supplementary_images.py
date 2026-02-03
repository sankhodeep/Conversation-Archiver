import sys
import os
import json
import datetime
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTextEdit, QPushButton, QLabel, QTableWidget, QTableWidgetItem,
    QHeaderView, QMessageBox, QFileDialog, QScrollArea
)
from PySide6.QtGui import QPixmap, QImage, QClipboard, QKeySequence
from PySide6.QtCore import Qt

class ImagePasteCell(QWidget):
    """Custom widget for pasting and previewing images in a table cell."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(5, 5, 5, 5)
        
        self.preview_label = QLabel("Click 'Paste' or Press Ctrl+V")
        self.preview_label.setAlignment(Qt.AlignCenter)
        self.preview_label.setStyleSheet("border: 1px dashed #aaa; background: #f9f9f9;")
        self.preview_label.setMinimumHeight(120)
        self.preview_label.setScaledContents(True)
        self.layout.addWidget(self.preview_label)
        
        self.paste_btn = QPushButton("Paste Image")
        self.paste_btn.clicked.connect(self.paste_from_clipboard)
        self.layout.addWidget(self.paste_btn)
        
        self.image_path = None

    def paste_from_clipboard(self):
        clipboard = QApplication.clipboard()
        mime_data = clipboard.mimeData()
        
        if mime_data.hasImage():
            image = clipboard.image()
            if not image.isNull():
                # Create a unique filename for the cached image
                timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
                filename = f"cached_img_{timestamp}.png"
                path = os.path.join("supplemental_images", filename)
                
                # Ensure directory exists
                os.makedirs("supplemental_images", exist_ok=True)
                
                # Save high quality PNG
                if image.save(path, "PNG"):
                    self.image_path = path
                    self.preview_label.setPixmap(QPixmap.fromImage(image))
                    self.preview_label.setText("") # Clear text
                else:
                    QMessageBox.warning(self, "Error", "Failed to save cached image.")
        else:
            QMessageBox.information(self, "No Image", "No image found in clipboard!")

class SupplementaryImagesApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Supplementary Image Mapper")
        self.setGeometry(100, 100, 1100, 800)
        
        # Directories
        self.supplemental_dir = "supplemental_images"
        self.mappings_dir = "mappings"
        os.makedirs(self.supplemental_dir, exist_ok=True)
        os.makedirs(self.mappings_dir, exist_ok=True)

        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.main_layout = QVBoxLayout(self.central_widget)

        # Instructions
        instr = QLabel("<b>Instructions:</b> 1. Add a row. 2. Paste your image. 3. (Optional) Add a description. 4. Paste the full Model Response text (only needed for the first image in a group). 5. Click Save.")
        instr.setWordWrap(True)
        self.main_layout.addWidget(instr)

        # Table setup
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["Image (Screenshot)", "Description (Optional)", "Full Model Response Text"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Fixed)
        self.table.setColumnWidth(0, 250)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.table.verticalHeader().setDefaultSectionSize(180)
        self.main_layout.addWidget(self.table)

        # Control buttons
        self.btn_layout = QHBoxLayout()
        
        self.add_row_btn = QPushButton("➕ Add New Row")
        self.add_row_btn.clicked.connect(self.add_row)
        self.btn_layout.addWidget(self.add_row_btn)

        self.remove_row_btn = QPushButton("❌ Remove Selected Row")
        self.remove_row_btn.clicked.connect(self.remove_row)
        self.btn_layout.addWidget(self.remove_row_btn)

        self.save_btn = QPushButton("💾 Save All and Create Mapping")
        self.save_btn.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold; padding: 10px;")
        self.save_btn.clicked.connect(self.save_mapping)
        self.btn_layout.addWidget(self.save_btn)
        
        self.main_layout.addLayout(self.btn_layout)

        # Add initial row
        self.add_row()

    def add_row(self):
        row = self.table.rowCount()
        self.table.insertRow(row)
        
        # Col 0: Paste Area
        paste_cell = ImagePasteCell()
        self.table.setCellWidget(row, 0, paste_cell)
        
        # Col 1: Description
        desc_edit = QTextEdit()
        desc_edit.setPlaceholderText("Enter image caption (optional)...")
        self.table.setCellWidget(row, 1, desc_edit)
        
        # Col 2: Text Snippet
        snippet_edit = QTextEdit()
        snippet_edit.setPlaceholderText("Paste AI response here (Sticky Snippet logic applies)...")
        self.table.setCellWidget(row, 2, snippet_edit)

    def remove_row(self):
        current_row = self.table.currentRow()
        if current_row >= 0:
            self.table.removeRow(current_row)

    def save_mapping(self):
        mapping_data = []
        
        current_snippet = None
        current_images = [] # List of {"path": ..., "desc": ...}

        for row in range(self.table.rowCount()):
            paste_cell = self.table.cellWidget(row, 0)
            desc_edit = self.table.cellWidget(row, 1)
            snippet_edit = self.table.cellWidget(row, 2)
            
            image_path = paste_cell.image_path
            description = desc_edit.toPlainText().strip()
            text_content = snippet_edit.toPlainText().strip()
            
            if not image_path:
                continue

            img_obj = {"path": image_path, "desc": description}

            if text_content:
                # Save previous group
                if current_snippet and current_images:
                    mapping_data.append({
                        "text_snippet": current_snippet,
                        "images": current_images
                    })
                
                # Start new group
                current_snippet = text_content
                current_images = [img_obj]
            else:
                # Inherit snippet from above
                if current_snippet:
                    current_images.append(img_obj)
                else:
                    # Ignore first row if no snippet
                    pass

        # Add last group
        if current_snippet and current_images:
            mapping_data.append({
                "text_snippet": current_snippet,
                "images": current_images
            })

        if not mapping_data:
            QMessageBox.warning(self, "No Data", "Please add at least one image and its corresponding text.")
            return

        # Create timestamped mapping file
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"mapping_{timestamp}.json"
        filepath = os.path.join(self.mappings_dir, filename)
        
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(mapping_data, f, indent=4, ensure_ascii=False)
            
            QMessageBox.information(self, "Success", f"Mapping saved successfully!\nFile: {filename}\n\nYou can now run the Conversation Archiver.")
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save mapping: {e}")

def main():
    app = QApplication(sys.argv)
    window = SupplementaryImagesApp()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
