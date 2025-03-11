import argparse
import cv2
import numpy as np
import pytesseract
from PIL import Image
import os

# Check if easyocr is available, import if possible
try:
    import easyocr
    EASYOCR_AVAILABLE = True
except ImportError:
    EASYOCR_AVAILABLE = False
    print("EasyOCR not available. Install with: pip install easyocr")


def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description='Redact text from images by covering with black rectangles.')
    parser.add_argument('input_path', type=str, help='Path to the input image')
    parser.add_argument('output_path', type=str, help='Path to save the output image')
    parser.add_argument('--debug', action='store_true', help='Save intermediate processing images')
    return parser.parse_args()


def load_image(image_path):
    """Load an image from the given path."""
    try:
        image = cv2.imread(image_path)
        if image is None:
            raise ValueError(f"Could not load image from {image_path}")
        return image
    except Exception as e:
        print(f"Error loading image: {e}")
        exit(1)


def preprocess_image(image, debug=False, output_dir=None):
    """Preprocess the image to improve text detection using multiple techniques."""
    # Create a list to store all preprocessed images
    preprocessed_images = []
    
    # Original grayscale
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    preprocessed_images.append(("gray", gray))
    
    # Otsu's thresholding
    _, otsu = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    preprocessed_images.append(("otsu", otsu))
    
    # Adaptive thresholding
    adaptive_thresh = cv2.adaptiveThreshold(
        gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2
    )
    preprocessed_images.append(("adaptive", adaptive_thresh))
    
    # Edge detection using Canny
    edges = cv2.Canny(gray, 100, 200)
    # Dilate edges to connect text
    kernel = np.ones((3, 3), np.uint8)
    dilated_edges = cv2.dilate(edges, kernel, iterations=1)
    preprocessed_images.append(("edges", dilated_edges))
    
    # Noise removal with morphological operations
    kernel = np.ones((1, 1), np.uint8)
    opening = cv2.morphologyEx(otsu, cv2.MORPH_OPEN, kernel, iterations=1)
    preprocessed_images.append(("opening", opening))
    
    # Save debug images if requested
    if debug and output_dir:
        os.makedirs(output_dir, exist_ok=True)
        for name, img in preprocessed_images:
            cv2.imwrite(os.path.join(output_dir, f"preprocess_{name}.png"), img)
    
    return preprocessed_images


def get_contour_boxes(image):
    """Detect potential text regions using contour detection."""
    # Convert to grayscale if not already
    if len(image.shape) == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    else:
        gray = image
    
    # Apply threshold
    _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    
    # Find contours
    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    # Filter contours by size and shape
    boxes = []
    for contour in contours:
        x, y, w, h = cv2.boundingRect(contour)
        
        # Filter out very small contours and those with extreme aspect ratios
        area = w * h
        aspect_ratio = w / float(h) if h > 0 else 0
        
        if area > 100 and 0.1 < aspect_ratio < 10:
            boxes.append((x, y, w, h))
    
    return boxes


def get_text_bounding_boxes(image, debug=False):
    """Detect text in the image using multiple approaches and return bounding boxes."""
    # Create a directory for debug images
    debug_dir = "debug_images" if debug else None
    
    # Get preprocessed images
    preprocessed_images = preprocess_image(image, debug, debug_dir)
    
    all_boxes = []
    
    # 1. Use Tesseract with different PSM modes on preprocessed images
    for name, processed_img in preprocessed_images:
        # PSM 6 - Assume a single uniform block of text
        data_psm6 = pytesseract.image_to_data(
            processed_img, 
            config='--psm 6',
            output_type=pytesseract.Output.DICT
        )
        
        # PSM 11 - Sparse text. Find as much text as possible in no particular order
        data_psm11 = pytesseract.image_to_data(
            processed_img, 
            config='--psm 11',
            output_type=pytesseract.Output.DICT
        )
        
        # Extract boxes from both PSM modes
        for data in [data_psm6, data_psm11]:
            for i in range(len(data['text'])):
                if int(data['conf'][i]) > 20 and data['text'][i].strip() != '':
                    x = data['left'][i]
                    y = data['top'][i]
                    w = data['width'][i]
                    h = data['height'][i]
                    all_boxes.append((x, y, w, h))
    
    # 2. Use EasyOCR if available
    if EASYOCR_AVAILABLE:
        try:
            reader = easyocr.Reader(['en'])
            results = reader.readtext(image)
            
            for result in results:
                # EasyOCR returns bounding box as 4 corner points
                bbox = result[0]
                # Convert to x, y, w, h format
                x_min = min(point[0] for point in bbox)
                y_min = min(point[1] for point in bbox)
                x_max = max(point[0] for point in bbox)
                y_max = max(point[1] for point in bbox)
                
                w = x_max - x_min
                h = y_max - y_min
                
                all_boxes.append((int(x_min), int(y_min), int(w), int(h)))
        except Exception as e:
            print(f"EasyOCR error: {e}")
    
    # 3. Use contour detection to find potential text regions
    contour_boxes = get_contour_boxes(image)
    all_boxes.extend(contour_boxes)
    
    # 4. Post-processing: Remove duplicates and merge overlapping boxes
    merged_boxes = merge_overlapping_boxes(all_boxes)
    
    # 5. Filter out likely false positives
    filtered_boxes = filter_false_positives(merged_boxes, image.shape[1], image.shape[0])
    
    # Save debug image with boxes if requested
    if debug and debug_dir:
        debug_image = image.copy()
        for (x, y, w, h) in filtered_boxes:
            cv2.rectangle(debug_image, (x, y), (x + w, y + h), (0, 255, 0), 2)
        cv2.imwrite(os.path.join(debug_dir, "detected_text_boxes.png"), debug_image)
    
    return filtered_boxes


def merge_overlapping_boxes(boxes, overlap_threshold=0.3):
    """Merge boxes that overlap significantly."""
    if not boxes:
        return []
    
    # Sort boxes by x coordinate
    boxes = sorted(boxes, key=lambda x: x[0])
    
    merged_boxes = []
    current_box = list(boxes[0])
    
    for box in boxes[1:]:
        x1, y1, w1, h1 = current_box
        x2, y2, w2, h2 = box
        
        # Calculate coordinates of box corners
        current_x2 = x1 + w1
        current_y2 = y1 + h1
        box_x2 = x2 + w2
        box_y2 = y2 + h2
        
        # Check for overlap
        overlap_x = max(0, min(current_x2, box_x2) - max(x1, x2))
        overlap_y = max(0, min(current_y2, box_y2) - max(y1, y2))
        overlap_area = overlap_x * overlap_y
        
        box1_area = w1 * h1
        box2_area = w2 * h2
        smaller_area = min(box1_area, box2_area)
        
        # If overlap is significant, merge boxes
        if overlap_area > 0 and overlap_area / smaller_area > overlap_threshold:
            # Create a new box that encompasses both
            new_x = min(x1, x2)
            new_y = min(y1, y2)
            new_w = max(current_x2, box_x2) - new_x
            new_h = max(current_y2, box_y2) - new_y
            
            current_box = [new_x, new_y, new_w, new_h]
        else:
            merged_boxes.append(tuple(current_box))
            current_box = list(box)
    
    # Add the last box
    merged_boxes.append(tuple(current_box))
    
    return merged_boxes


def filter_false_positives(boxes, image_width, image_height, min_area=50, max_area_ratio=0.5):
    """Filter out boxes that are likely false positives."""
    filtered_boxes = []
    max_area = image_width * image_height * max_area_ratio
    
    for box in boxes:
        x, y, w, h = box
        area = w * h
        
        # Filter by size
        if area < min_area or area > max_area:
            continue
        
        # Filter by aspect ratio (exclude extremely thin or wide boxes)
        aspect_ratio = w / h if h > 0 else 0
        if aspect_ratio < 0.1 or aspect_ratio > 15:
            continue
        
        filtered_boxes.append(box)
    
    return filtered_boxes


def redact_text(image, boxes):
    """Create a copy of the image with black rectangles over text areas."""
    # Create a copy of the image
    redacted_image = image.copy()
    
    # Draw black rectangles over each text box
    for (x, y, w, h) in boxes:
        cv2.rectangle(redacted_image, (x, y), (x + w, y + h), (0, 0, 0), -1)
    
    return redacted_image


def save_image(image, output_path):
    """Save the image to the specified output path."""
    try:
        cv2.imwrite(output_path, image)
        print(f"Redacted image saved to {output_path}")
        return True
    except Exception as e:
        print(f"Error saving image: {e}")
        return False


def main():
    """Main function to process the image."""
    # Parse command line arguments
    args = parse_arguments()
    
    # Load the input image
    image = load_image(args.input_path)
    
    # Get text bounding boxes
    boxes = get_text_bounding_boxes(image, debug=args.debug)
    
    # Create redacted image
    redacted_image = redact_text(image, boxes)
    
    # Save the redacted image
    save_image(redacted_image, args.output_path)
    
    # Output summary
    print(f"Detected {len(boxes)} text regions")


if __name__ == "__main__":
    main()
