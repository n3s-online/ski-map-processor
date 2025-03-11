import os
import json
import sys
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                            QHBoxLayout, QLabel, QLineEdit, QPushButton, 
                            QFrame, QScrollArea, QComboBox, QSizePolicy, QShortcut,
                            QCheckBox, QColorDialog, QMessageBox)
from PyQt5.QtGui import QPixmap, QImage, QKeySequence, QPainter, QColor, QPen, QBrush
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
    
    def _update_scaled_boxes(self):
        """Update the boxes based on the current scale"""
        self.boxes = []
        for x, y, width, height in self.original_boxes:
            # Apply current scale to box coordinates
            scaled_x = int(x * self.current_scale)
            scaled_y = int(y * self.current_scale)
            scaled_width = int(width * self.current_scale)
            scaled_height = int(height * self.current_scale)
            
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
                self.boxes.append(rect)
                
                # Convert to original scale and store
                orig_x = int(rect.x() / self.current_scale)
                orig_y = int(rect.y() / self.current_scale)
                orig_width = int(rect.width() / self.current_scale)
                orig_height = int(rect.height() / self.current_scale)
                self.original_boxes.append((orig_x, orig_y, orig_width, orig_height))
            
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
    
    def collect_unique_metadata_values(self):
        """Collect unique values for each metadata field from all metadata.json files"""
        unique_values = {
            "name": set(),
            "country": set(),
            "region": set(),
            "parent_company": set()
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
    
    def disable_controls(self):
        """Disable all controls when no folders are found"""
        self.name_input.setEnabled(False)
        self.country_combo.setEnabled(False)
        self.country_input.setEnabled(False)
        self.region_combo.setEnabled(False)
        self.region_input.setEnabled(False)
        self.company_combo.setEnabled(False)
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
            self.image_label.setMinimumSize(display_pixmap.width(), display_pixmap.height())
            
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
        
        # Get boxes from image label
        boxes = self.image_label.get_boxes()
        
        # Store the current boxes for later use
        self.current_boxes = boxes
        
        metadata = {
            "name": name,
            "country": country,
            "region": region,
            "parent_company": company,
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
            
        self.current_zoom = max(0.1, self.current_zoom - self.zoom_step)
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
            
        self.current_zoom = 1.0
        
        # Update the display
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
            
        self.current_zoom = min(5.0, self.current_zoom + self.zoom_step)
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
