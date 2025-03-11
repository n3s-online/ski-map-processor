import argparse
import cv2
import numpy as np
import pytesseract
from PIL import Image


def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description='Redact text from images by covering with black rectangles.')
    parser.add_argument('input_path', type=str, help='Path to the input image')
    parser.add_argument('output_path', type=str, help='Path to save the output image')
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


def get_text_bounding_boxes(image):
    """Detect text in the image and return bounding boxes."""
    # Convert to RGB for Tesseract
    rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    
    # Get data from Tesseract OCR
    data = pytesseract.image_to_data(rgb_image, output_type=pytesseract.Output.DICT)
    
    # Extract bounding boxes for text
    boxes = []
    for i in range(len(data['text'])):
        # Skip empty text
        if int(data['conf'][i]) > 0 and data['text'][i].strip() != '':
            x = data['left'][i]
            y = data['top'][i]
            w = data['width'][i]
            h = data['height'][i]
            boxes.append((x, y, w, h))
    
    return boxes


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
    boxes = get_text_bounding_boxes(image)
    
    # Create redacted image
    redacted_image = redact_text(image, boxes)
    
    # Save the redacted image
    save_image(redacted_image, args.output_path)


if __name__ == "__main__":
    main()
