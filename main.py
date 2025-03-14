import os
import json
import sys
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                            QHBoxLayout, QLabel, QLineEdit, QPushButton, 
                            QFrame, QScrollArea, QComboBox, QSizePolicy, QShortcut,
                            QCheckBox, QColorDialog, QMessageBox)
from PyQt5.QtGui import QPixmap, QImage, QKeySequence, QPainter, QColor, QPen, QBrush, QIntValidator
from PyQt5.QtCore import Qt, QRect, QPoint
from PIL import Image, ImageDraw
import shutil
from pathlib import Path

class DrawableImageLabel(QLabel):
    """Custom QLabel that allows drawing rectangles on the image"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMouseTracking(True)
        
        # Drawing state
        self.drawing_enabled = False
        self.drawing = False
        self.start_point = QPoint()
        self.end_point = QPoint()
        self.boxes = []  # List of QRect objects
        self.boxes_visible = True  # Whether to display the boxes
        self.current_scale = 1.0  # Current display scale
        self.original_boxes = []  # Original box coordinates at 100% scale
        
        # Appearance
        self.box_color = QColor(255, 0, 0, 128)  # Semi-transparent red
        
    def enable_drawing(self, enabled):
        """Enable or disable drawing mode"""
        self.drawing_enabled = enabled
        self.setCursor(Qt.CrossCursor if enabled else Qt.ArrowCursor)
    
    def set_boxes(self, boxes):
        """Set the list of boxes from metadata"""
        # Clear existing boxes
        self.boxes = []
        self.original_boxes = []
        
        # Add each box, ensuring they are valid QRect objects
        for box_data in boxes:
            if len(box_data) == 4:  # Ensure we have [x, y, width, height]
                x, y, width, height = box_data
                # Store original box coordinates (at 100% scale)
                self.original_boxes.append((int(x), int(y), int(width), int(height)))
        
        # Apply current scale to boxes
        self._update_scaled_boxes()
        
        # Force a repaint to show the boxes
        self.update()
    
    def _get_image_offset(self):
        """Calculate the offset of the image within the label"""
        if not self.pixmap():
            return 0, 0
            
        pixmap_width = self.pixmap().width()
        pixmap_height = self.pixmap().height()
        label_width = self.width()
        label_height = self.height()
        
        # Calculate the offset (if the image is centered)
        x_offset = max(0, (label_width - pixmap_width) // 2)
        y_offset = max(0, (label_height - pixmap_height) // 2)
        
        return x_offset, y_offset
    
    def screen_to_image_coords(self, screen_point):
        """Convert screen coordinates to image coordinates"""
        x_offset, y_offset = self._get_image_offset()
        
        # Adjust for the offset
        image_x = screen_point.x() - x_offset
        image_y = screen_point.y() - y_offset
        
        # Ensure we don't go negative
        image_x = max(0, image_x)
        image_y = max(0, image_y)
        
        # Convert to original scale
        orig_x = int(image_x / self.current_scale)
        orig_y = int(image_y / self.current_scale)
        
        return QPoint(orig_x, orig_y)
    
    def image_to_screen_coords(self, image_point, image_width, image_height):
        """Convert image coordinates to screen coordinates"""
        x_offset, y_offset = self._get_image_offset()
        
        # Scale the coordinates
        screen_x = int(image_point.x() * self.current_scale) + x_offset
        screen_y = int(image_point.y() * self.current_scale) + y_offset
        screen_width = int(image_width * self.current_scale)
        screen_height = int(image_height * self.current_scale)
        
        return QRect(screen_x, screen_y, screen_width, screen_height)
    
    def _update_scaled_boxes(self):
        """Update the boxes based on the current scale"""
        self.boxes = []
        
        if not self.pixmap():
            return
            
        x_offset, y_offset = self._get_image_offset()
        
        for x, y, width, height in self.original_boxes:
            # Apply current scale to box coordinates
            scaled_x = int(x * self.current_scale)
            scaled_y = int(y * self.current_scale)
            scaled_width = int(width * self.current_scale)
            scaled_height = int(height * self.current_scale)
            
            # Add the offset to position correctly within the label
            scaled_x += x_offset
            scaled_y += y_offset
            
            # Create a QRect with the scaled dimensions
            rect = QRect(scaled_x, scaled_y, scaled_width, scaled_height)
            # Only add if it has a reasonable size
            if rect.width() > 0 and rect.height() > 0:
                self.boxes.append(rect)
    
    def get_boxes(self):
        """Get the list of boxes as serializable data (at original scale)"""
        # Return the original box coordinates, not the scaled ones
        return self.original_boxes
    
    def clear_boxes(self):
        """Clear all boxes"""
        self.boxes = []
        self.original_boxes = []
        self.update()
    
    def remove_last_box(self):
        """Remove the last drawn box"""
        if self.boxes and self.original_boxes:
            self.boxes.pop()
            self.original_boxes.pop()
            self.update()
    
    def mousePressEvent(self, event):
        """Handle mouse press events for drawing"""
        if self.drawing_enabled and event.button() == Qt.LeftButton:
            self.drawing = True
            self.start_point = event.pos()
            self.end_point = event.pos()
            self.update()
        super().mousePressEvent(event)
    
    def mouseMoveEvent(self, event):
        """Handle mouse move events for drawing"""
        if self.drawing_enabled and self.drawing:
            self.end_point = event.pos()
            self.update()
        super().mouseMoveEvent(event)
    
    def mouseReleaseEvent(self, event):
        """Handle mouse release events for drawing"""
        if self.drawing_enabled and self.drawing and event.button() == Qt.LeftButton:
            self.drawing = False
            # Create a normalized rectangle (ensure width and height are positive)
            rect = QRect(self.start_point, self.end_point).normalized()
            
            # Only add if it has a reasonable size
            if rect.width() > 5 and rect.height() > 5:
                # Add to scaled boxes for display
                self.boxes.append(rect)
                
                # Convert screen coordinates to image coordinates
                start_image_point = self.screen_to_image_coords(rect.topLeft())
                end_image_point = self.screen_to_image_coords(rect.bottomRight())
                
                # Calculate width and height in image coordinates
                orig_width = end_image_point.x() - start_image_point.x()
                orig_height = end_image_point.y() - start_image_point.y()
                
                # Store the original coordinates
                self.original_boxes.append((
                    start_image_point.x(),
                    start_image_point.y(),
                    orig_width,
                    orig_height
                ))
            
            self.update()
        super().mouseReleaseEvent(event)
    
    def paintEvent(self, event):
        """Paint the image and the rectangles"""
        super().paintEvent(event)
        
        if self.pixmap() and self.boxes_visible:
            painter = QPainter(self)
            
            # Draw existing boxes
            for rect in self.boxes:
                painter.setPen(QPen(self.box_color, 2))
                painter.setBrush(QBrush(self.box_color))
                painter.drawRect(rect)
            
            # Draw the rectangle being created
            if self.drawing_enabled and self.drawing:
                painter.setPen(QPen(self.box_color, 2))
                painter.setBrush(QBrush(self.box_color))
                rect = QRect(self.start_point, self.end_point).normalized()
                painter.drawRect(rect)
            
            painter.end()

class SkiMapProcessor(QMainWindow):
    def __init__(self, files_dir="files"):
        super().__init__()
        
        self.setWindowTitle("Ski Map Processor")
        self.setGeometry(100, 100, 1200, 800)
        
        self.files_dir = files_dir
        self.folders = self.get_folders()
        self.current_folder_index = 0
        
        # Image display variables
        self.current_zoom = 1.0  # Current zoom level
        self.zoom_step = 0.1     # Zoom step size
        
        # Collect unique metadata values from existing files
        self.unique_values = self.collect_unique_metadata_values()
        
        # Create a mapping of country to regions
        self.country_to_regions = self.create_country_region_mapping()
        
        # Main widget and layout
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QHBoxLayout(main_widget)
        
        # Left side - Image display
        self.image_scroll = QScrollArea()
        self.image_scroll.setWidgetResizable(True)
        self.image_scroll.setAlignment(Qt.AlignCenter)
        self.image_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.image_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        
        # Create a container for the image area with controls
        image_area = QWidget()
        image_area_layout = QVBoxLayout(image_area)
        
        # Zoom controls
        zoom_controls = QHBoxLayout()
        
        self.zoom_out_btn = QPushButton("-")
        self.zoom_out_btn.setFixedSize(30, 30)
        self.zoom_out_btn.clicked.connect(self.zoom_out)
        zoom_controls.addWidget(self.zoom_out_btn)
        
        self.zoom_reset_btn = QPushButton("100%")
        self.zoom_reset_btn.clicked.connect(self.zoom_reset)
        zoom_controls.addWidget(self.zoom_reset_btn)
        
        self.zoom_in_btn = QPushButton("+")
        self.zoom_in_btn.setFixedSize(30, 30)
        self.zoom_in_btn.clicked.connect(self.zoom_in)
        zoom_controls.addWidget(self.zoom_in_btn)
        
        zoom_controls.addStretch()
        
        # Drawing controls
        self.draw_mode_checkbox = QCheckBox("Draw Mode")
        self.draw_mode_checkbox.toggled.connect(self.toggle_draw_mode)
        zoom_controls.addWidget(self.draw_mode_checkbox)
        
        self.undo_box_btn = QPushButton("Undo Box")
        self.undo_box_btn.clicked.connect(self.remove_last_box)
        zoom_controls.addWidget(self.undo_box_btn)
        
        self.clear_boxes_btn = QPushButton("Clear Boxes")
        self.clear_boxes_btn.clicked.connect(self.clear_boxes)
        zoom_controls.addWidget(self.clear_boxes_btn)
        
        # View toggle
        self.view_toggle_btn = QPushButton("View Redacted")
        self.view_toggle_btn.setCheckable(True)
        self.view_toggle_btn.clicked.connect(self.toggle_view)
        zoom_controls.addWidget(self.view_toggle_btn)
        
        image_area_layout.addLayout(zoom_controls)
        
        # Create a container widget for the image label to allow proper scrolling
        self.image_container = QWidget()
        self.image_container_layout = QVBoxLayout(self.image_container)
        
        self.image_label = DrawableImageLabel()
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.image_label.setMinimumSize(800, 600)  # Set minimum size to prevent tiny images
        
        # Enable mouse tracking for wheel events
        self.image_scroll.setMouseTracking(True)
        self.image_scroll.wheelEvent = self.wheel_event
        
        # Add keyboard shortcuts
        self.zoom_in_shortcut = QShortcut(QKeySequence("Ctrl++"), self)
        self.zoom_in_shortcut.activated.connect(self.zoom_in)
        
        self.zoom_out_shortcut = QShortcut(QKeySequence("Ctrl+-"), self)
        self.zoom_out_shortcut.activated.connect(self.zoom_out)
        
        self.zoom_reset_shortcut = QShortcut(QKeySequence("Ctrl+0"), self)
        self.zoom_reset_shortcut.activated.connect(self.zoom_reset)
        
        self.image_container_layout.addWidget(self.image_label)
        self.image_container_layout.addStretch()
        
        self.image_scroll.setWidget(self.image_container)
        image_area_layout.addWidget(self.image_scroll)
        
        main_layout.addWidget(image_area, 3)  # 3:1 ratio
        
        # Right side - Form
        form_widget = QWidget()
        form_layout = QVBoxLayout(form_widget)
        main_layout.addWidget(form_widget, 1)  # 3:1 ratio
        
        # Form title
        form_title = QLabel("Metadata")
        form_title.setStyleSheet("font-size: 18px; font-weight: bold;")
        form_layout.addWidget(form_title)
        
        # Resort name (text input only)
        form_layout.addWidget(QLabel("Resort Name:"))
        self.name_input = QLineEdit()
        form_layout.addWidget(self.name_input)
        
        # Country
        form_layout.addWidget(QLabel("Country:"))
        self.country_combo = QComboBox()
        self.country_combo.setEditable(True)
        self.country_combo.addItems([""] + self.unique_values.get("country", []) + ["Other"])
        self.country_combo.currentTextChanged.connect(self.on_country_changed)
        form_layout.addWidget(self.country_combo)
        self.country_input = QLineEdit()
        self.country_input.setVisible(False)
        form_layout.addWidget(self.country_input)
        
        # State/Region
        form_layout.addWidget(QLabel("State/Region:"))
        self.region_combo = QComboBox()
        self.region_combo.setEditable(True)
        self.region_combo.setEnabled(False)  # Disabled until country is selected
        self.region_combo.currentTextChanged.connect(self.on_region_changed)
        form_layout.addWidget(self.region_combo)
        self.region_input = QLineEdit()
        self.region_input.setVisible(False)
        form_layout.addWidget(self.region_input)
        
        # Parent Company
        form_layout.addWidget(QLabel("Parent Company:"))
        self.company_combo = QComboBox()
        self.company_combo.setEditable(True)
        self.company_combo.addItems([""] + self.unique_values.get("parent_company", []) + ["Other"])
        self.company_combo.currentTextChanged.connect(self.on_company_changed)
        form_layout.addWidget(self.company_combo)
        self.company_input = QLineEdit()
        self.company_input.setVisible(False)
        form_layout.addWidget(self.company_input)
        
        # Continent
        form_layout.addWidget(QLabel("Continent:"))
        self.continent_combo = QComboBox()
        self.continent_combo.setEditable(True)
        self.continent_combo.addItems([""] + self.unique_values.get("continent", []) + ["Other"])
        self.continent_combo.currentTextChanged.connect(self.on_continent_changed)
        form_layout.addWidget(self.continent_combo)
        self.continent_input = QLineEdit()
        self.continent_input.setVisible(False)
        form_layout.addWidget(self.continent_input)
        
        # Skiable Acreage
        form_layout.addWidget(QLabel("Skiable Acreage:"))
        self.acreage_input = QLineEdit()
        # Only allow numbers
        self.acreage_input.setValidator(QIntValidator(0, 999999))
        form_layout.addWidget(self.acreage_input)
        
        # Number of Lifts
        form_layout.addWidget(QLabel("Number of Lifts:"))
        self.lifts_input = QLineEdit()
        # Only allow numbers
        self.lifts_input.setValidator(QIntValidator(0, 999))
        form_layout.addWidget(self.lifts_input)
        
        # Latitude
        form_layout.addWidget(QLabel("Latitude:"))
        self.latitude_input = QLineEdit()
        # Use a validator that allows decimal numbers
        self.latitude_input.setPlaceholderText("e.g., 45.5017")
        form_layout.addWidget(self.latitude_input)
        
        # Longitude
        form_layout.addWidget(QLabel("Longitude:"))
        self.longitude_input = QLineEdit()
        # Use a validator that allows decimal numbers
        self.longitude_input.setPlaceholderText("e.g., -73.5673")
        form_layout.addWidget(self.longitude_input)
        
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
            
            # Create or update the index.json file
            self.update_index_json()
    
    def collect_unique_metadata_values(self):
        """Collect unique values for each metadata field from all metadata.json files"""
        unique_values = {
            "name": set(),
            "country": set(),
            "region": set(),
            "parent_company": set(),
            "continent": set()  # Add continent to unique values
        }
        
        for folder in self.folders:
            metadata_path = os.path.join(self.files_dir, folder, "metadata.json")
            if os.path.exists(metadata_path):
                try:
                    with open(metadata_path, 'r') as f:
                        metadata = json.load(f)
                    
                    # Add non-empty values to sets
                    if metadata.get("name"):
                        unique_values["name"].add(metadata["name"])
                    if metadata.get("country"):
                        unique_values["country"].add(metadata["country"])
                    if metadata.get("region"):
                        unique_values["region"].add(metadata["region"])
                    if metadata.get("parent_company"):
                        unique_values["parent_company"].add(metadata["parent_company"])
                    if metadata.get("continent"):
                        unique_values["continent"].add(metadata["continent"])
                except Exception as e:
                    print(f"Error reading metadata from {metadata_path}: {e}")
        
        # Convert sets to sorted lists
        return {k: sorted(list(v)) for k, v in unique_values.items()}
    
    def create_country_region_mapping(self):
        """Create a mapping of countries to their regions"""
        country_to_regions = {}
        
        for folder in self.folders:
            metadata_path = os.path.join(self.files_dir, folder, "metadata.json")
            if os.path.exists(metadata_path):
                try:
                    with open(metadata_path, 'r') as f:
                        metadata = json.load(f)
                    
                    country = metadata.get("country")
                    region = metadata.get("region")
                    
                    if country and region:
                        if country not in country_to_regions:
                            country_to_regions[country] = set()
                        country_to_regions[country].add(region)
                except Exception as e:
                    print(f"Error reading metadata from {metadata_path}: {e}")
        
        # Convert sets to sorted lists
        return {k: sorted(list(v)) for k, v in country_to_regions.items()}
    
    def on_country_changed(self, text):
        """Handle country dropdown change"""
        if text == "Other":
            self.country_input.setVisible(True)
            self.country_input.setFocus()
            # Disable region dropdown when "Other" is selected for country
            self.region_combo.setEnabled(False)
            self.region_combo.clear()
        else:
            self.country_input.setVisible(False)
            
            # Update region dropdown based on selected country
            self.region_combo.clear()
            if text in self.country_to_regions:
                self.region_combo.setEnabled(True)
                self.region_combo.addItems([""] + self.country_to_regions[text] + ["Other"])
            else:
                self.region_combo.setEnabled(False)
    
    def on_region_changed(self, text):
        """Handle region dropdown change"""
        self.region_input.setVisible(text == "Other")
        if text == "Other":
            self.region_input.setFocus()
    
    def on_company_changed(self, text):
        """Handle company dropdown change"""
        self.company_input.setVisible(text == "Other")
        if text == "Other":
            self.company_input.setFocus()
    
    def on_continent_changed(self, text):
        """Handle continent dropdown change"""
        self.continent_input.setVisible(text == "Other")
        if text == "Other":
            self.continent_input.setFocus()
    
    def disable_controls(self):
        """Disable all controls when no folders are found"""
        self.name_input.setEnabled(False)
        self.country_combo.setEnabled(False)
        self.country_input.setEnabled(False)
        self.region_combo.setEnabled(False)
        self.region_input.setEnabled(False)
        self.company_combo.setEnabled(False)
        self.company_input.setEnabled(False)
        self.continent_combo.setEnabled(False)
        self.continent_input.setEnabled(False)
        self.acreage_input.setEnabled(False)
        self.lifts_input.setEnabled(False)
        self.latitude_input.setEnabled(False)
        self.longitude_input.setEnabled(False)
        self.save_button.setEnabled(False)
        self.prev_button.setEnabled(False)
        self.next_button.setEnabled(False)
    
    def get_folders(self):
        """Get all folders in the files directory"""
        if not os.path.exists(self.files_dir):
            return []
        
        current_folders = [f for f in os.listdir(self.files_dir) 
                if os.path.isdir(os.path.join(self.files_dir, f))]
        
        # Check if the list of folders has changed
        if hasattr(self, 'folders') and set(current_folders) != set(self.folders):
            # Update the folders attribute
            self.folders = current_folders
            # Update the index.json file
            self.update_index_json()
            return self.sort_folders_by_name(current_folders)
        
        return self.sort_folders_by_name(current_folders)
    
    def sort_folders_by_name(self, folders):
        """Sort folders based on the resort names in their metadata files"""
        # Create a dictionary to map folders to their resort names
        folder_to_name = {}
        
        for folder in folders:
            metadata_path = os.path.join(self.files_dir, folder, "metadata.json")
            if os.path.exists(metadata_path):
                try:
                    with open(metadata_path, 'r') as f:
                        metadata = json.load(f)
                    
                    # Use the resort name if available, otherwise use the folder name
                    folder_to_name[folder] = metadata.get("name", folder).lower()
                except Exception as e:
                    print(f"Error reading metadata from {metadata_path}: {e}")
                    folder_to_name[folder] = folder.lower()
            else:
                folder_to_name[folder] = folder.lower()
        
        # Sort folders based on their associated names
        return sorted(folders, key=lambda folder: folder_to_name.get(folder, folder.lower()))
    
    def load_current_folder(self):
        """Load the current folder's image and metadata"""
        if not self.folders:
            return
        
        current_folder = self.folders[self.current_folder_index]
        folder_path = os.path.join(self.files_dir, current_folder)
        
        # Update folder label
        self.folder_label.setText(f"Folder: {current_folder} ({self.current_folder_index + 1}/{len(self.folders)})")
        
        # Clear any existing boxes
        self.image_label.clear_boxes()
        
        # Reset view toggle
        self.view_toggle_btn.setChecked(False)
        self.view_toggle_btn.setText("View Redacted")
        
        # Store paths for later use
        self.current_folder_path = folder_path
        self.original_image_path = os.path.join(folder_path, "ski_map_original.png")
        self.redacted_image_path = os.path.join(folder_path, "ski_map_redacted.png")
        
        # Load metadata first to get boxes
        metadata_path = os.path.join(folder_path, "metadata.json")
        if os.path.exists(metadata_path):
            with open(metadata_path, 'r') as f:
                metadata = json.load(f)
            
            # Set form values
            self.name_input.setText(metadata.get("name", ""))
            
            # Set country
            country = metadata.get("country", "")
            if country in self.unique_values["country"]:
                self.country_combo.setCurrentText(country)
                self.country_input.setVisible(False)
            else:
                self.country_combo.setCurrentText("Other")
                self.country_input.setText(country)
                self.country_input.setVisible(True)
            
            # Set region (will be updated by country change handler)
            region = metadata.get("region", "")
            if country in self.country_to_regions and region in self.country_to_regions[country]:
                self.region_combo.setCurrentText(region)
                self.region_input.setVisible(False)
            else:
                self.region_combo.setCurrentText("Other")
                self.region_input.setText(region)
                self.region_input.setVisible(True)
            
            # Set company
            company = metadata.get("parent_company", "")
            if company in self.unique_values["parent_company"]:
                self.company_combo.setCurrentText(company)
                self.company_input.setVisible(False)
            else:
                self.company_combo.setCurrentText("Other")
                self.company_input.setText(company)
                self.company_input.setVisible(True)
            
            # Set continent
            continent = metadata.get("continent", "")
            if continent in self.unique_values["continent"]:
                self.continent_combo.setCurrentText(continent)
                self.continent_input.setVisible(False)
            else:
                self.continent_combo.setCurrentText("Other")
                self.continent_input.setText(continent)
                self.continent_input.setVisible(True)
            
            # Set numeric fields
            self.acreage_input.setText(str(metadata.get("skiable_acreage", "")))
            self.lifts_input.setText(str(metadata.get("lifts", "")))
            
            # Set latitude and longitude
            self.latitude_input.setText(str(metadata.get("latitude", "")))
            self.longitude_input.setText(str(metadata.get("longitude", "")))
            
            # Load redaction boxes if they exist
            if "boxes" in metadata and isinstance(metadata["boxes"], list):
                # Store boxes for later use
                self.current_boxes = metadata["boxes"]
            else:
                self.current_boxes = []
        else:
            # Clear form
            self.name_input.setText("")
            self.country_combo.setCurrentText("")
            self.country_input.setText("")
            self.country_input.setVisible(False)
            self.region_combo.setCurrentText("")
            self.region_input.setText("")
            self.region_input.setVisible(False)
            self.company_combo.setCurrentText("")
            self.company_input.setText("")
            self.company_input.setVisible(False)
            self.continent_combo.setCurrentText("")
            self.continent_input.setText("")
            self.continent_input.setVisible(False)
            self.acreage_input.setText("")
            self.lifts_input.setText("")
            self.latitude_input.setText("")
            self.longitude_input.setText("")
            self.current_boxes = []
        
        # Now load the image
        if os.path.exists(self.original_image_path):
            # Reset zoom level when loading a new image
            self.current_zoom = 1.0
            self.zoom_reset_btn.setText("100%")
            
            # Display the image with high quality
            self.display_image(image_path=self.original_image_path)
            
            # After image is loaded, set the boxes with the current scale
            if hasattr(self, 'current_boxes') and self.current_boxes:
                self.image_label.set_boxes(self.current_boxes)
                self.image_label.boxes_visible = True
                self.image_label.current_scale = self.current_zoom
                self.image_label._update_scaled_boxes()
                self.image_label.update()  # Force a repaint
                self.statusBar().showMessage(f"Loaded folder: {current_folder} | Image: ski_map_original.png | Boxes: {len(self.current_boxes)}")
            else:
                self.statusBar().showMessage(f"Loaded folder: {current_folder} | Image: ski_map_original.png")
            
            # Enable/disable view toggle based on whether redacted image exists
            self.view_toggle_btn.setEnabled(os.path.exists(self.redacted_image_path))
        else:
            self.image_label.setText(f"Image not found: {self.original_image_path}")
            self.statusBar().showMessage(f"Error: Image not found in {current_folder}")
            self.view_toggle_btn.setEnabled(False)
    
    def display_image(self, image_path=None, pixmap=None):
        """Display the image in the GUI with high quality"""
        try:
            if image_path:
                # Open the image with PIL to get dimensions
                pil_img = Image.open(image_path)
                img_width, img_height = pil_img.size
                
                # Store original image for potential high-quality display
                self.original_pixmap = QPixmap(image_path)
                self.current_image_path = image_path
                self.current_zoom = 1.0  # Reset zoom when loading a new image
                
                # Store original dimensions for proper scaling
                self.original_width = self.original_pixmap.width()
                self.original_height = self.original_pixmap.height()
                
                # Get the available size for the image
                viewport_width = self.image_scroll.viewport().width()
                viewport_height = self.image_scroll.viewport().height()
                
                # Determine if we need to scale down (never scale up small images)
                if img_width > viewport_width or img_height > viewport_height:
                    # Scale down to fit viewport while maintaining aspect ratio
                    display_pixmap = self.original_pixmap.scaled(
                        viewport_width, 
                        viewport_height,
                        Qt.KeepAspectRatio,  # Maintain aspect ratio
                        Qt.SmoothTransformation  # High-quality scaling
                    )
                    
                    # Calculate the actual zoom level based on the scaling
                    if img_width > img_height:
                        self.current_zoom = display_pixmap.width() / self.original_width
                    else:
                        self.current_zoom = display_pixmap.height() / self.original_height
                else:
                    # Use original size for small images
                    display_pixmap = self.original_pixmap
                    self.current_zoom = 1.0
                
                # Update zoom indicator
                self.zoom_reset_btn.setText(f"{int(self.current_zoom * 100)}%")
                
                # If viewing redacted image, disable drawing controls
                if image_path.endswith("ski_map_redacted.png"):
                    self.draw_mode_checkbox.setEnabled(False)
                    self.undo_box_btn.setEnabled(False)
                    self.clear_boxes_btn.setEnabled(False)
                    # Note: We don't modify boxes_visible here, that's handled in toggle_view
                    self.image_label.drawing_enabled = False
                else:
                    self.draw_mode_checkbox.setEnabled(True)
                    self.undo_box_btn.setEnabled(True)
                    self.clear_boxes_btn.setEnabled(True)
                    # Note: We don't modify boxes_visible here, that's handled in toggle_view
            elif pixmap:
                # Use the provided pixmap (for zoom operations)
                display_pixmap = pixmap
                # Update zoom indicator
                self.zoom_reset_btn.setText(f"{int(self.current_zoom * 100)}%")
            else:
                return
            
            # Set the pixmap to the label
            self.image_label.setPixmap(display_pixmap)
            
            # Store the current display scale for box scaling
            self.image_label.current_scale = self.current_zoom
            
            # Resize the container to match the image size for proper scrolling
            # Make sure the image label is at least as big as the pixmap
            pixmap_width = display_pixmap.width()
            pixmap_height = display_pixmap.height()
            self.image_label.setMinimumSize(pixmap_width, pixmap_height)
            
            # Force a layout update to ensure proper positioning
            self.image_container_layout.update()
            self.image_scroll.update()
            
            # Update status bar with image info if we have the original image
            if hasattr(self, 'original_pixmap'):
                orig_width = self.original_pixmap.width()
                orig_height = self.original_pixmap.height()
                display_width = display_pixmap.width()
                display_height = display_pixmap.height()
                self.statusBar().showMessage(f"Image dimensions: {orig_width}x{orig_height} pixels | Display: {display_width}x{display_height} | Zoom: {int(self.current_zoom * 100)}%")
            
        except Exception as e:
            self.image_label.setText(f"Error displaying image: {e}")
            self.statusBar().showMessage(f"Error: {e}")
    
    def save_metadata(self):
        """Save the metadata to a JSON file and create redacted image"""
        if not self.folders:
            return
        
        current_folder = self.folders[self.current_folder_index]
        folder_path = os.path.join(self.files_dir, current_folder)
        metadata_path = os.path.join(folder_path, "metadata.json")
        
        # Get values from form
        name = self.name_input.text()
        country = self.country_input.text() if self.country_combo.currentText() == "Other" else self.country_combo.currentText()
        region = self.region_input.text() if self.region_combo.currentText() == "Other" else self.region_combo.currentText()
        company = self.company_input.text() if self.company_combo.currentText() == "Other" else self.company_combo.currentText()
        continent = self.continent_input.text() if self.continent_combo.currentText() == "Other" else self.continent_combo.currentText()
        
        # Get numeric values, defaulting to empty string if invalid
        try:
            acreage = int(self.acreage_input.text()) if self.acreage_input.text() else ""
        except ValueError:
            acreage = ""
        
        try:
            lifts = int(self.lifts_input.text()) if self.lifts_input.text() else ""
        except ValueError:
            lifts = ""
            
        # Get latitude and longitude, defaulting to empty string if invalid
        try:
            latitude = float(self.latitude_input.text()) if self.latitude_input.text() else ""
        except ValueError:
            latitude = ""
            
        try:
            longitude = float(self.longitude_input.text()) if self.longitude_input.text() else ""
        except ValueError:
            longitude = ""
        
        # Get boxes from image label
        boxes = self.image_label.get_boxes()
        
        # Store the current boxes for later use
        self.current_boxes = boxes
        
        metadata = {
            "name": name,
            "country": country,
            "region": region,
            "parent_company": company,
            "continent": continent,
            "skiable_acreage": acreage,
            "lifts": lifts,
            "latitude": latitude,
            "longitude": longitude,
            "boxes": boxes
        }
        
        # Save metadata
        with open(metadata_path, 'w') as f:
            json.dump(metadata, f, indent=4)
        
        # Create redacted image if we have boxes and an original image
        original_image_path = os.path.join(folder_path, "ski_map_original.png")
        redacted_image_path = os.path.join(folder_path, "ski_map_redacted.png")
        
        if boxes and os.path.exists(original_image_path):
            try:
                # Open the original image with PIL
                pil_img = Image.open(original_image_path)
                
                # Create a drawing context
                draw = ImageDraw.Draw(pil_img)
                
                # Draw filled rectangles for each box
                for box in boxes:
                    x, y, width, height = box
                    # Ensure coordinates are within image bounds
                    x = max(0, min(x, pil_img.width - 1))
                    y = max(0, min(y, pil_img.height - 1))
                    # Ensure width and height don't exceed image bounds
                    width = min(width, pil_img.width - x)
                    height = min(height, pil_img.height - y)
                    # Draw the rectangle
                    draw.rectangle([x, y, x + width, y + height], fill=(0, 0, 0))
                
                # Save the redacted image
                pil_img.save(redacted_image_path)
                
                # Enable the view toggle button
                self.view_toggle_btn.setEnabled(True)
                
                self.statusBar().showMessage(f"Metadata and redacted image saved for {current_folder}")
            except Exception as e:
                self.statusBar().showMessage(f"Error creating redacted image: {e}")
                print(f"Error creating redacted image: {e}")
        else:
            # If no boxes, remove any existing redacted image
            if os.path.exists(redacted_image_path):
                try:
                    os.remove(redacted_image_path)
                    self.view_toggle_btn.setEnabled(False)
                except Exception as e:
                    print(f"Error removing redacted image: {e}")
            
            self.statusBar().showMessage(f"Metadata saved for {current_folder}")
        
        print(f"Metadata saved for {current_folder}")
        
        # Update unique values with new entries
        if country and country not in self.unique_values["country"] and country != "Other":
            self.unique_values["country"].append(country)
            self.unique_values["country"].sort()
            self.update_combo_items(self.country_combo, self.unique_values["country"])
        
        # Update country-to-region mapping
        if country and region and region != "Other":
            if country not in self.country_to_regions:
                self.country_to_regions[country] = []
            
            if region not in self.country_to_regions[country]:
                self.country_to_regions[country].append(region)
                self.country_to_regions[country].sort()
        
        if company and company not in self.unique_values["parent_company"] and company != "Other":
            self.unique_values["parent_company"].append(company)
            self.unique_values["parent_company"].sort()
            self.update_combo_items(self.company_combo, self.unique_values["parent_company"])
            
        if continent and continent not in self.unique_values["continent"] and continent != "Other":
            self.unique_values["continent"].append(continent)
            self.unique_values["continent"].sort()
            self.update_combo_items(self.continent_combo, self.unique_values["continent"])
            
        # Update the index.json file
        self.update_index_json()
    
    def update_index_json(self):
        """Create or update the index.json file with a list of all ski resort folders and their names"""
        index_path = os.path.join(self.files_dir, "index.json")
        
        # Create the index data structure
        ski_resorts = []
        
        # Add each folder to the list with only the name
        for folder in self.folders:
            folder_path = os.path.join(self.files_dir, folder)
            metadata_path = os.path.join(folder_path, "metadata.json")
            
            resort_data = {"folderName": folder}
            
            # Add only the name if metadata exists
            if os.path.exists(metadata_path):
                try:
                    with open(metadata_path, 'r') as f:
                        metadata = json.load(f)
                    
                    # Add only the name to the index
                    if metadata.get("name"):
                        resort_data["name"] = metadata["name"]
                except Exception as e:
                    print(f"Error reading metadata from {metadata_path}: {e}")
            
            ski_resorts.append(resort_data)
        
        # Sort the ski resorts alphabetically by name
        ski_resorts.sort(key=lambda x: x.get("name", "").lower() if x.get("name") else x.get("folderName", "").lower())
        
        # Create the index object
        index_data = {
            "skiResorts": ski_resorts
        }
        
        # Save the index file
        try:
            with open(index_path, 'w') as f:
                json.dump(index_data, f, indent=4)
            print(f"Index file updated at {index_path}")
        except Exception as e:
            print(f"Error updating index file: {e}")
            self.statusBar().showMessage(f"Error updating index file: {e}")
    
    def update_combo_items(self, combo, items):
        """Update combo box items while preserving current selection"""
        current_text = combo.currentText()
        combo.clear()
        combo.addItems([""] + items + ["Other"])
        combo.setCurrentText(current_text)
    
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

    def zoom_out(self):
        """Zoom out the image"""
        if not hasattr(self, 'original_pixmap') or self.original_pixmap.isNull():
            return
            
        # Don't zoom out too far
        if self.current_zoom <= 0.2:
            return
            
        # Calculate new zoom level
        self.current_zoom = max(0.1, self.current_zoom - self.zoom_step)
        
        # Scale the pixmap
        scaled_pixmap = self.original_pixmap.scaled(
            int(self.original_width * self.current_zoom),
            int(self.original_height * self.current_zoom),
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation
        )
        
        # Update the display
        self.display_image(pixmap=scaled_pixmap)
        
        # Update the boxes with the new scale
        self.image_label.current_scale = self.current_zoom
        self.image_label._update_scaled_boxes()
        self.image_label.update()
    
    def zoom_reset(self):
        """Reset the image to original size"""
        if not hasattr(self, 'original_pixmap') or self.original_pixmap.isNull():
            return
            
        # Set zoom to 100%
        self.current_zoom = 1.0
        
        # Update the display with the original pixmap
        self.display_image(pixmap=self.original_pixmap)
        
        # Update the boxes with the new scale
        self.image_label.current_scale = self.current_zoom
        self.image_label._update_scaled_boxes()
        self.image_label.update()
    
    def zoom_in(self):
        """Zoom in the image"""
        if not hasattr(self, 'original_pixmap') or self.original_pixmap.isNull():
            return
            
        # Don't zoom in too far
        if self.current_zoom >= 5.0:
            return
            
        # Calculate new zoom level
        self.current_zoom = min(5.0, self.current_zoom + self.zoom_step)
        
        # Scale the pixmap
        scaled_pixmap = self.original_pixmap.scaled(
            int(self.original_width * self.current_zoom),
            int(self.original_height * self.current_zoom),
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation
        )
        
        # Update the display
        self.display_image(pixmap=scaled_pixmap)
        
        # Update the boxes with the new scale
        self.image_label.current_scale = self.current_zoom
        self.image_label._update_scaled_boxes()
        self.image_label.update()

    def wheel_event(self, event):
        """Handle wheel events for zooming"""
        # Check if Ctrl key is pressed for zooming
        modifiers = QApplication.keyboardModifiers()
        if modifiers == Qt.ControlModifier:
            # Zoom with Ctrl+wheel
            if event.angleDelta().y() > 0:
                self.zoom_in()
            elif event.angleDelta().y() < 0:
                self.zoom_out()
            event.accept()
        else:
            # Normal scrolling behavior
            QScrollArea.wheelEvent(self.image_scroll, event)

    def toggle_draw_mode(self, checked):
        """Toggle drawing mode"""
        self.image_label.enable_drawing(checked)
    
    def remove_last_box(self):
        """Remove the last drawn box"""
        self.image_label.remove_last_box()
    
    def clear_boxes(self):
        """Clear all drawn boxes"""
        self.image_label.clear_boxes()

    def toggle_view(self, checked):
        """Toggle between viewing the original and redacted image"""
        if not hasattr(self, 'original_image_path') or not hasattr(self, 'redacted_image_path'):
            return
            
        if checked:
            # Show redacted image if it exists
            if os.path.exists(self.redacted_image_path):
                # Hide boxes before switching to redacted image
                self.image_label.boxes_visible = False
                self.display_image(image_path=self.redacted_image_path)
                self.view_toggle_btn.setText("View Original")
                self.statusBar().showMessage(f"Viewing redacted image")
            else:
                self.view_toggle_btn.setChecked(False)
                self.statusBar().showMessage(f"Redacted image not found")
        else:
            # Show original image
            # First load the image
            self.display_image(image_path=self.original_image_path)
            
            # Then make boxes visible again and update them with the current scale
            self.image_label.boxes_visible = True
            self.image_label.current_scale = self.current_zoom
            self.image_label._update_scaled_boxes()
            self.image_label.update()  # Force a repaint to show the boxes
            
            self.view_toggle_btn.setText("View Redacted")
            self.statusBar().showMessage(f"Viewing original image")

def main():
    app = QApplication(sys.argv)
    window = SkiMapProcessor()
    window.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
