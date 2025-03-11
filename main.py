import os
import json
import sys
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                            QHBoxLayout, QLabel, QLineEdit, QPushButton, 
                            QFrame, QScrollArea)
from PyQt5.QtGui import QPixmap, QImage
from PyQt5.QtCore import Qt
from PIL import Image
import shutil
from pathlib import Path

class SkiMapProcessor(QMainWindow):
    def __init__(self, files_dir="files"):
        super().__init__()
        
        self.setWindowTitle("Ski Map Processor")
        self.setGeometry(100, 100, 1200, 800)
        
        self.files_dir = files_dir
        self.folders = self.get_folders()
        self.current_folder_index = 0
        
        # Main widget and layout
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QHBoxLayout(main_widget)
        
        # Left side - Image display
        self.image_scroll = QScrollArea()
        self.image_scroll.setWidgetResizable(True)
        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_scroll.setWidget(self.image_label)
        main_layout.addWidget(self.image_scroll, 3)  # 3:1 ratio
        
        # Right side - Form
        form_widget = QWidget()
        form_layout = QVBoxLayout(form_widget)
        main_layout.addWidget(form_widget, 1)  # 3:1 ratio
        
        # Form title
        form_title = QLabel("Metadata")
        form_title.setStyleSheet("font-size: 18px; font-weight: bold;")
        form_layout.addWidget(form_title)
        
        # Resort name
        form_layout.addWidget(QLabel("Resort Name:"))
        self.name_input = QLineEdit()
        form_layout.addWidget(self.name_input)
        
        # Country
        form_layout.addWidget(QLabel("Country:"))
        self.country_input = QLineEdit()
        form_layout.addWidget(self.country_input)
        
        # State/Region
        form_layout.addWidget(QLabel("State/Region:"))
        self.region_input = QLineEdit()
        form_layout.addWidget(self.region_input)
        
        # Parent Company
        form_layout.addWidget(QLabel("Parent Company:"))
        self.company_input = QLineEdit()
        form_layout.addWidget(self.company_input)
        
        # Add some spacing
        form_layout.addSpacing(20)
        
        # Save button
        self.save_button = QPushButton("Save")
        self.save_button.clicked.connect(self.save_metadata)
        form_layout.addWidget(self.save_button)
        
        # Navigation buttons
        nav_layout = QHBoxLayout()
        self.prev_button = QPushButton("Previous")
        self.prev_button.clicked.connect(self.previous_folder)
        nav_layout.addWidget(self.prev_button)
        
        self.next_button = QPushButton("Next")
        self.next_button.clicked.connect(self.next_folder)
        nav_layout.addWidget(self.next_button)
        
        form_layout.addLayout(nav_layout)
        
        # Current folder display
        self.folder_label = QLabel()
        form_layout.addWidget(self.folder_label)
        
        # Add stretch to push everything up
        form_layout.addStretch()
        
        # Check if we have folders
        if not self.folders:
            self.image_label.setText("No folders found in the 'files' directory!")
            self.disable_controls()
        else:
            # Load the first folder
            self.load_current_folder()
    
    def disable_controls(self):
        """Disable all controls when no folders are found"""
        self.name_input.setEnabled(False)
        self.country_input.setEnabled(False)
        self.region_input.setEnabled(False)
        self.company_input.setEnabled(False)
        self.save_button.setEnabled(False)
        self.prev_button.setEnabled(False)
        self.next_button.setEnabled(False)
    
    def get_folders(self):
        """Get all folders in the files directory"""
        if not os.path.exists(self.files_dir):
            return []
        
        return [f for f in os.listdir(self.files_dir) 
                if os.path.isdir(os.path.join(self.files_dir, f))]
    
    def load_current_folder(self):
        """Load the current folder's image and metadata"""
        if not self.folders:
            return
        
        current_folder = self.folders[self.current_folder_index]
        folder_path = os.path.join(self.files_dir, current_folder)
        
        # Update folder label
        self.folder_label.setText(f"Folder: {current_folder} ({self.current_folder_index + 1}/{len(self.folders)})")
        
        # Load image
        image_path = os.path.join(folder_path, "ski_map_original.png")
        if os.path.exists(image_path):
            self.display_image(image_path)
        else:
            self.image_label.setText(f"Image not found: {image_path}")
        
        # Load metadata
        metadata_path = os.path.join(folder_path, "metadata.json")
        if os.path.exists(metadata_path):
            with open(metadata_path, 'r') as f:
                metadata = json.load(f)
            
            self.name_input.setText(metadata.get("name", ""))
            self.country_input.setText(metadata.get("country", ""))
            self.region_input.setText(metadata.get("region", ""))
            self.company_input.setText(metadata.get("parent_company", ""))
        else:
            # Clear form if no metadata exists
            self.name_input.setText("")
            self.country_input.setText("")
            self.region_input.setText("")
            self.company_input.setText("")
    
    def display_image(self, image_path):
        """Display the image in the GUI"""
        try:
            # Open the image with PIL to get dimensions
            pil_img = Image.open(image_path)
            img_width, img_height = pil_img.size
            
            # Convert to QPixmap for display
            pixmap = QPixmap(image_path)
            
            # Scale if needed
            if pixmap.width() > 800 or pixmap.height() > 600:
                pixmap = pixmap.scaled(800, 600, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            
            self.image_label.setPixmap(pixmap)
            
        except Exception as e:
            self.image_label.setText(f"Error displaying image: {e}")
    
    def save_metadata(self):
        """Save the metadata to a JSON file"""
        if not self.folders:
            return
        
        current_folder = self.folders[self.current_folder_index]
        folder_path = os.path.join(self.files_dir, current_folder)
        metadata_path = os.path.join(folder_path, "metadata.json")
        
        metadata = {
            "name": self.name_input.text(),
            "country": self.country_input.text(),
            "region": self.region_input.text(),
            "parent_company": self.company_input.text()
        }
        
        with open(metadata_path, 'w') as f:
            json.dump(metadata, f, indent=4)
        
        print(f"Metadata saved for {current_folder}")
    
    def next_folder(self):
        """Move to the next folder"""
        if not self.folders:
            return
        
        self.current_folder_index = (self.current_folder_index + 1) % len(self.folders)
        self.load_current_folder()
    
    def previous_folder(self):
        """Move to the previous folder"""
        if not self.folders:
            return
        
        self.current_folder_index = (self.current_folder_index - 1) % len(self.folders)
        self.load_current_folder()

def main():
    app = QApplication(sys.argv)
    window = SkiMapProcessor()
    window.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
