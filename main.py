import argparse
import cv2
import numpy as np
import math
import os
import platform

class RectangleEditor:
    def __init__(self, image_path, output_path):
        self.original_image = cv2.imread(image_path)
        if self.original_image is None:
            raise ValueError(f"Could not load image from {image_path}")
        
        self.output_path = output_path
        self.image = self.original_image.copy()
        self.window_name = "Rectangle Editor"
        self.rectangles = []  # List of (x, y, w, h, angle) tuples
        self.current_rect = None
        self.dragging = False
        self.rotating = False
        self.selected_rect_idx = -1
        self.start_point = None
        self.rotation_origin = None
        
        # Zoom and pan variables
        self.zoom_scale = 1.0
        self.zoom_center = None
        self.pan_start = None
        self.offset_x = 0
        self.offset_y = 0
        
        # Constants
        self.HANDLE_RADIUS = 5
        self.HANDLE_COLOR = (0, 255, 255)  # Yellow
        self.RECT_COLOR = (0, 0, 0)  # Black
        self.RECT_THICKNESS = -1  # Filled rectangle
        self.OUTLINE_COLOR = (0, 255, 0)  # Green
        self.OUTLINE_THICKNESS = 2
        self.ROTATION_HANDLE_COLOR = (255, 0, 255)  # Magenta
        self.ZOOM_FACTOR = 1.1  # Zoom in/out factor
        self.MIN_ZOOM = 0.1  # Minimum zoom level
        self.MAX_ZOOM = 10.0  # Maximum zoom level
        
        # Default window size
        self.window_width = 1200
        self.window_height = 800
        
        # Check if running on macOS
        self.is_macos = platform.system() == 'Darwin'
        
        # Instructions
        self.instructions = [
            "Left click and drag: Draw new rectangle",
            "Right click on rectangle: Select for editing",
            "Left click and drag on selected rectangle: Move rectangle",
            "Left click and drag on rotation handle: Rotate rectangle",
        ]
        
        # Add platform-specific zoom instructions
        if self.is_macos:
            self.instructions.append("Trackpad pinch or + and - keys: Zoom in/out")
        else:
            self.instructions.append("Mouse wheel: Zoom in/out")
            
        self.instructions.extend([
            "Middle mouse button drag: Pan image",
            "Delete key: Remove selected rectangle",
            "S key: Save and exit",
            "Esc key: Exit without saving"
        ])
    
    def draw_rectangle(self, img, rect, color, thickness, draw_handles=False):
        x, y, w, h, angle = rect
        
        # Create a rotation matrix
        center = (int(x + w/2), int(y + h/2))
        rotation_matrix = cv2.getRotationMatrix2D(center, angle, 1)
        
        # Define the four corners of the rectangle
        corners = np.array([
            [x, y],
            [x + w, y],
            [x + w, y + h],
            [x, y + h]
        ], dtype=np.float32)
        
        # Apply rotation to the corners
        ones = np.ones(shape=(len(corners), 1))
        corners_homogeneous = np.hstack([corners, ones])
        rotated_corners = rotation_matrix.dot(corners_homogeneous.T).T
        
        # Convert to integer points and draw the rectangle
        points = rotated_corners.astype(np.int32)
        cv2.drawContours(img, [points], 0, color, thickness)
        
        # Draw handles if requested
        if draw_handles:
            # Draw corner handles
            for point in points:
                cv2.circle(img, tuple(point), self.HANDLE_RADIUS, self.HANDLE_COLOR, -1)
            
            # Draw rotation handle above the rectangle
            rotation_handle = (center[0], center[1] - h//2 - 20)
            # Rotate the rotation handle
            rotation_handle_homogeneous = np.array([[rotation_handle[0], rotation_handle[1], 1]])
            rotated_handle = rotation_matrix.dot(rotation_handle_homogeneous.T).T
            rotated_handle = rotated_handle[0][:2].astype(np.int32)
            
            # Draw line from center to rotation handle
            cv2.line(img, center, tuple(rotated_handle), self.ROTATION_HANDLE_COLOR, 2)
            cv2.circle(img, tuple(rotated_handle), self.HANDLE_RADIUS, self.ROTATION_HANDLE_COLOR, -1)
    
    def is_point_in_rect(self, point, rect):
        x, y, w, h, angle = rect
        center = (x + w/2, y + h/2)
        
        # Translate point to origin
        translated_point = (point[0] - center[0], point[1] - center[1])
        
        # Rotate point in the opposite direction
        theta = -angle * math.pi / 180
        rotated_point = (
            translated_point[0] * math.cos(theta) - translated_point[1] * math.sin(theta),
            translated_point[0] * math.sin(theta) + translated_point[1] * math.cos(theta)
        )
        
        # Translate back
        final_point = (rotated_point[0] + center[0], rotated_point[1] + center[1])
        
        # Check if point is inside the axis-aligned rectangle
        return (x <= final_point[0] <= x + w) and (y <= final_point[1] <= y + h)
    
    def is_point_near_rotation_handle(self, point, rect):
        x, y, w, h, angle = rect
        center = (x + w/2, y + h/2)
        
        # Calculate rotation handle position
        rotation_handle = (center[0], center[1] - h//2 - 20)
        
        # Create rotation matrix
        rotation_matrix = cv2.getRotationMatrix2D(center, angle, 1)
        
        # Rotate the rotation handle
        rotation_handle_homogeneous = np.array([[rotation_handle[0], rotation_handle[1], 1]])
        rotated_handle = rotation_matrix.dot(rotation_handle_homogeneous.T).T
        rotated_handle = rotated_handle[0][:2]
        
        # Calculate distance
        distance = math.sqrt((point[0] - rotated_handle[0])**2 + (point[1] - rotated_handle[1])**2)
        return distance <= self.HANDLE_RADIUS * 2
    
    def screen_to_image_coords(self, x, y):
        """Convert screen coordinates to image coordinates considering zoom and pan."""
        # Adjust for the instructions panel height
        instructions_height = 30 + len(self.instructions) * 20
        y = y - instructions_height
        
        # If y is negative, it's in the instructions panel, not the image
        if y < 0:
            return None, None
        
        # Convert screen coordinates to image coordinates with zoom and pan
        img_x = int((x - self.offset_x) / self.zoom_scale)
        img_y = int((y - self.offset_y) / self.zoom_scale)
        
        return img_x, img_y
    
    def apply_zoom(self, zoom_in, x, y):
        """Apply zoom centered at the given coordinates."""
        # Store old zoom for calculating new offsets
        old_zoom = self.zoom_scale
        
        # Determine zoom direction
        if zoom_in:
            # Zoom in
            self.zoom_scale = min(self.zoom_scale * self.ZOOM_FACTOR, self.MAX_ZOOM)
        else:
            # Zoom out
            self.zoom_scale = max(self.zoom_scale / self.ZOOM_FACTOR, self.MIN_ZOOM)
            
            # Also ensure we don't go below the minimum zoom to fit the image
            try:
                min_fit_zoom = min(
                    (self.window_width - 40) / max(1, self.original_image.shape[1]),
                    (self.window_height - 40 - (30 + len(self.instructions) * 20)) / max(1, self.original_image.shape[0])
                )
                self.zoom_scale = max(self.zoom_scale, min_fit_zoom * 0.5)  # Allow zooming out a bit more than fit
            except Exception as e:
                print(f"Warning: Error calculating min zoom: {e}")
        
        # Adjust offset to zoom toward mouse position
        if old_zoom > 0:  # Prevent division by zero
            zoom_ratio = self.zoom_scale / old_zoom
            # Calculate new offsets to zoom toward mouse position
            self.offset_x = x - (x - self.offset_x) * zoom_ratio
            self.offset_y = y - (y - self.offset_y) * zoom_ratio
    
    def mouse_callback(self, event, x, y, flags, param):
        # Convert screen coordinates to image coordinates
        img_x, img_y = self.screen_to_image_coords(x, y)
        
        # If coordinates are outside the image area, ignore the event
        if img_x is None or img_y is None:
            return
        
        # Handle zooming with mouse wheel
        if event == cv2.EVENT_MOUSEWHEEL:
            # Get the wheel delta (positive for zoom in, negative for zoom out)
            wheel_delta = flags
            
            # Apply zoom
            self.apply_zoom(wheel_delta > 0, x, y)
            return
        
        # Handle panning with middle mouse button
        if event == cv2.EVENT_MBUTTONDOWN:
            self.pan_start = (x, y)
            return
        
        elif event == cv2.EVENT_MOUSEMOVE and flags & cv2.EVENT_FLAG_MBUTTON:
            if self.pan_start:
                # Calculate the distance moved
                dx = x - self.pan_start[0]
                dy = y - self.pan_start[1]
                
                # Update the offset
                self.offset_x += dx
                self.offset_y += dy
                
                # Update the start position for the next move
                self.pan_start = (x, y)
            return
        
        elif event == cv2.EVENT_MBUTTONUP:
            self.pan_start = None
            return
        
        # Handle rectangle operations
        if event == cv2.EVENT_LBUTTONDOWN:
            if self.selected_rect_idx >= 0:
                # Check if clicking on rotation handle
                if self.is_point_near_rotation_handle((img_x, img_y), self.rectangles[self.selected_rect_idx]):
                    self.rotating = True
                    self.rotation_origin = (
                        self.rectangles[self.selected_rect_idx][0] + self.rectangles[self.selected_rect_idx][2]/2,
                        self.rectangles[self.selected_rect_idx][1] + self.rectangles[self.selected_rect_idx][3]/2
                    )
                    return
                
                # Check if clicking on selected rectangle (for moving)
                if self.is_point_in_rect((img_x, img_y), self.rectangles[self.selected_rect_idx]):
                    self.dragging = True
                    rect = self.rectangles[self.selected_rect_idx]
                    self.start_point = (img_x - rect[0], img_y - rect[1])  # Store offset
                    return
            
            # Start drawing a new rectangle
            self.current_rect = [img_x, img_y, 0, 0, 0]
            self.dragging = True
            self.selected_rect_idx = -1
        
        elif event == cv2.EVENT_MOUSEMOVE:
            if self.rotating and self.selected_rect_idx >= 0:
                # Calculate angle based on mouse position relative to center
                dx = img_x - self.rotation_origin[0]
                dy = img_y - self.rotation_origin[1]
                # Fix rotation direction by inverting the angle
                angle = -math.degrees(math.atan2(dy, dx)) + 90  # +90 to make 0 degrees point up
                self.rectangles[self.selected_rect_idx] = (
                    self.rectangles[self.selected_rect_idx][0],
                    self.rectangles[self.selected_rect_idx][1],
                    self.rectangles[self.selected_rect_idx][2],
                    self.rectangles[self.selected_rect_idx][3],
                    angle
                )
            elif self.dragging:
                if self.selected_rect_idx >= 0:
                    # Move existing rectangle
                    self.rectangles[self.selected_rect_idx] = (
                        img_x - self.start_point[0],
                        img_y - self.start_point[1],
                        self.rectangles[self.selected_rect_idx][2],
                        self.rectangles[self.selected_rect_idx][3],
                        self.rectangles[self.selected_rect_idx][4]
                    )
                else:
                    # Update size of new rectangle
                    width = img_x - self.current_rect[0]
                    height = img_y - self.current_rect[1]
                    self.current_rect[2] = width
                    self.current_rect[3] = height
        
        elif event == cv2.EVENT_LBUTTONUP:
            if self.rotating:
                self.rotating = False
            elif self.dragging:
                self.dragging = False
                if self.selected_rect_idx < 0 and self.current_rect:
                    # Finish drawing new rectangle
                    x, y, w, h, angle = self.current_rect
                    # Ensure width and height are positive
                    if w < 0:
                        x += w
                        w = abs(w)
                    if h < 0:
                        y += h
                        h = abs(h)
                    
                    if w > 5 and h > 5:  # Only add if rectangle has meaningful size
                        self.rectangles.append((x, y, w, h, angle))
                    self.current_rect = None
        
        elif event == cv2.EVENT_RBUTTONDOWN:
            # Select rectangle under cursor
            for i, rect in enumerate(self.rectangles):
                if self.is_point_in_rect((img_x, img_y), rect):
                    self.selected_rect_idx = i
                    break
            else:
                self.selected_rect_idx = -1
    
    def keyboard_callback(self, key):
        if key == 27:  # ESC key
            return False
        elif key == ord('s') or key == ord('S'):
            # Save the image with rectangles
            output = self.original_image.copy()
            for rect in self.rectangles:
                self.draw_rectangle(output, rect, self.RECT_COLOR, self.RECT_THICKNESS)
            cv2.imwrite(self.output_path, output)
            print(f"Image saved to {self.output_path}")
            return False
        elif key == 8 or key == 127:  # Backspace or Delete
            if self.selected_rect_idx >= 0:
                self.rectangles.pop(self.selected_rect_idx)
                self.selected_rect_idx = -1
        elif key == ord('+') or key == ord('='):  # Zoom in with + key
            # Get the center of the visible area
            center_x = self.window_width // 2
            center_y = self.window_height // 2
            self.apply_zoom(True, center_x, center_y)
        elif key == ord('-') or key == ord('_'):  # Zoom out with - key
            # Get the center of the visible area
            center_x = self.window_width // 2
            center_y = self.window_height // 2
            self.apply_zoom(False, center_x, center_y)
        return True
    
    def create_instructions_panel(self):
        """Create an image with instructions to display above the main image."""
        # Create a black image for instructions
        panel_height = 30 + len(self.instructions) * 20
        panel_width = max(int(self.original_image.shape[1] * self.zoom_scale), 600, self.window_width)
        panel = np.zeros((panel_height, panel_width, 3), dtype=np.uint8)
        
        # Draw instructions on the panel
        for i, instruction in enumerate(self.instructions):
            cv2.putText(panel, instruction, (20, 25 + i * 20), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
        
        # Add zoom information
        zoom_info = f"Zoom: {self.zoom_scale:.2f}x"
        cv2.putText(panel, zoom_info, (panel_width - 150, 25), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
        
        return panel
    
    def apply_zoom_and_pan(self, image):
        """Apply zoom and pan transformations to the image."""
        try:
            # Ensure zoom scale is positive
            if self.zoom_scale <= 0:
                self.zoom_scale = self.MIN_ZOOM
                print(f"Warning: Zoom scale was reset to minimum ({self.MIN_ZOOM})")
            
            # Calculate the dimensions of the zoomed image
            zoomed_height = max(1, int(image.shape[0] * self.zoom_scale))
            zoomed_width = max(1, int(image.shape[1] * self.zoom_scale))
            
            # Resize the image according to the zoom factor
            zoomed_image = cv2.resize(image, (zoomed_width, zoomed_height), interpolation=cv2.INTER_LINEAR)
            
            # Create a canvas large enough to hold the zoomed image with pan offsets
            canvas_height = max(1, self.window_height - (30 + len(self.instructions) * 20))
            canvas_width = max(1, self.window_width)
            canvas = np.zeros((canvas_height, canvas_width, 3), dtype=np.uint8)
            
            # Calculate the region of the zoomed image to display
            src_x = max(0, -int(self.offset_x))
            src_y = max(0, -int(self.offset_y))
            src_width = min(zoomed_width - src_x, canvas_width - max(0, int(self.offset_x)))
            src_height = min(zoomed_height - src_y, canvas_height - max(0, int(self.offset_y)))
            
            # Ensure src_width and src_height are positive
            src_width = max(0, src_width)
            src_height = max(0, src_height)
            
            # Calculate the destination region on the canvas
            dst_x = max(0, int(self.offset_x))
            dst_y = max(0, int(self.offset_y))
            
            # Ensure we don't try to copy regions outside the image bounds
            if src_width > 0 and src_height > 0:
                # Copy the visible portion of the zoomed image to the canvas
                canvas[dst_y:dst_y+src_height, dst_x:dst_x+src_width] = zoomed_image[src_y:src_y+src_height, src_x:src_x+src_width]
            
            return canvas
        except Exception as e:
            print(f"Error in apply_zoom_and_pan: {e}")
            # Return a simple black canvas as fallback
            return np.zeros((max(1, self.window_height - (30 + len(self.instructions) * 20)), 
                            max(1, self.window_width), 3), dtype=np.uint8)
    
    def run(self):
        try:
            # Create a window with a fixed size
            cv2.namedWindow(self.window_name, cv2.WINDOW_NORMAL)
            
            # Set mouse callback for the window
            cv2.setMouseCallback(self.window_name, self.mouse_callback)
            
            # Initialize zoom to fit the image on screen
            try:
                # Ensure we don't divide by zero
                img_width = max(1, self.original_image.shape[1])
                img_height = max(1, self.original_image.shape[0])
                
                # Calculate zoom to fit
                width_ratio = (self.window_width - 40) / img_width
                height_ratio = (self.window_height - 40 - (30 + len(self.instructions) * 20)) / img_height
                
                # Use the smaller ratio to ensure the entire image fits
                self.zoom_scale = max(min(width_ratio, height_ratio, self.MAX_ZOOM), self.MIN_ZOOM)
                
                # Center the image initially
                self.offset_x = (self.window_width - img_width * self.zoom_scale) / 2
                self.offset_y = (self.window_height - (30 + len(self.instructions) * 20) - img_height * self.zoom_scale) / 2
            except Exception as e:
                print(f"Warning: Error calculating initial zoom: {e}")
                # Use safe defaults
                self.zoom_scale = 1.0
                self.offset_x = 0
                self.offset_y = 0
            
            # Set window size
            try:
                cv2.resizeWindow(self.window_name, self.window_width, self.window_height)
            except Exception as e:
                print(f"Warning: Could not resize window: {e}")
            
            while True:
                try:
                    # Create the display image with the current rectangles
                    display_image = self.original_image.copy()
                    
                    # Draw all rectangles
                    for i, rect in enumerate(self.rectangles):
                        is_selected = (i == self.selected_rect_idx)
                        # Draw filled rectangle
                        self.draw_rectangle(display_image, rect, self.RECT_COLOR, self.RECT_THICKNESS)
                        # Draw outline for selected rectangle
                        if is_selected:
                            self.draw_rectangle(display_image, rect, self.OUTLINE_COLOR, 
                                              self.OUTLINE_THICKNESS, draw_handles=True)
                    
                    # Draw rectangle being created
                    if self.current_rect:
                        self.draw_rectangle(display_image, tuple(self.current_rect), 
                                          self.OUTLINE_COLOR, self.OUTLINE_THICKNESS)
                    
                    # Apply zoom and pan to the display image
                    zoomed_image = self.apply_zoom_and_pan(display_image)
                    
                    # Create instructions panel
                    instructions_panel = self.create_instructions_panel()
                    
                    # Combine instructions panel and display image
                    combined_image = np.vstack((instructions_panel, zoomed_image))
                    
                    # Show the combined image
                    cv2.imshow(self.window_name, combined_image)
                    
                    # Process keyboard input
                    key = cv2.waitKey(30)
                    if not self.keyboard_callback(key):
                        break
                except Exception as e:
                    print(f"Error in main loop: {e}")
                    # Brief pause to prevent tight error loop
                    cv2.waitKey(100)
        except Exception as e:
            print(f"Error in run method: {e}")
        finally:
            cv2.destroyAllWindows()


def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description='Interactive tool to draw rectangles on an image to cover text.')
    parser.add_argument('input_path', type=str, help='Path to the input image')
    parser.add_argument('output_path', type=str, help='Path to save the output image')
    parser.add_argument('--width', type=int, default=1200, help='Window width (default: 1200)')
    parser.add_argument('--height', type=int, default=800, help='Window height (default: 800)')
    return parser.parse_args()


def main():
    """Main function to run the interactive rectangle editor."""
    # Parse command line arguments
    args = parse_arguments()
    
    try:
        # Create and run the rectangle editor
        editor = RectangleEditor(args.input_path, args.output_path)
        
        # Set window size from command line arguments if provided
        editor.window_width = args.width
        editor.window_height = args.height
        
        editor.run()
    except Exception as e:
        print(f"Error: {e}")
        return 1
    
    return 0


if __name__ == "__main__":
    main()
