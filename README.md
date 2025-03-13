# Ski Map Processor

Processing ski maps for my upcoming project Ski-o-guessr, a geography guessing game focused on ski resorts.

## Features

- Collect and edit metadata about ski resorts using their trail maps
- Generate redacted copies of trail maps with text covered for use in the game
- Interactive drawing tools to mark text areas for redaction
- PyQt5-based GUI for easy metadata editing and image processing
- Smart dropdowns that learn from existing metadata entries
- Country-dependent region selection
- "Other" option in dropdowns for custom values
- Zoom controls for detailed image editing
- Automatic index generation for all processed ski resorts

## Requirements

- Python 3.6+
- PyQt5
- Pillow (PIL Fork)

## Setup for Development

1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/ski-map-processor.git
   cd ski-map-processor
   ```

2. Create a virtual environment (recommended):
   ```bash
   python -m venv venv
   
   # On Windows
   venv\Scripts\activate
   
   # On macOS/Linux
   source venv/bin/activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Create the files directory structure:
   ```bash
   mkdir -p files
   ```

## Usage

1. Place ski map folders in the `files/` directory. Each folder should contain:
   - `ski_map_original.png` - The original ski map image
   - Optional: `metadata.json` - Existing metadata (will be created if not present)

2. Run the application:
   ```bash
   python main.py
   ```

3. Use the interface to:
   - View ski maps
   - Edit metadata using the form
   - Draw boxes around text to be redacted
   - Save metadata and generate redacted images
   - Navigate between different ski maps using Previous/Next buttons

## Interface Guide

### Image Controls
- **Zoom Controls**: Use +/- buttons or Ctrl+Mouse Wheel to zoom in/out
- **Draw Mode**: Toggle to enable drawing boxes around text areas
- **Undo Box**: Remove the last drawn box
- **Clear Boxes**: Remove all boxes
- **View Redacted**: Toggle between original and redacted views

### Metadata Form
- **Resort Name**: Simple text input
- **Country**: Dropdown with "Other" option for custom values
- **State/Region**: Dropdown that shows regions specific to the selected country
- **Parent Company**: Dropdown with "Other" option for custom values
- **Continent**: Dropdown with "Other" option for custom values
- **Skiable Acreage**: Numeric input for resort size
- **Number of Lifts**: Numeric input for lift count

### Keyboard Shortcuts
- **Ctrl++**: Zoom in
- **Ctrl+-**: Zoom out
- **Ctrl+0**: Reset zoom to 100%

## Data Structure

### Folder Structure
```
ski-map-processor/
├── files/
│   ├── index.json                  # Auto-generated index of all resorts
│   ├── resort_folder_1/
│   │   ├── ski_map_original.png    # Original trail map
│   │   ├── ski_map_redacted.png    # Generated redacted map
│   │   └── metadata.json           # Resort metadata
│   └── resort_folder_2/
│       └── ...
├── main.py                         # Main application code
├── requirements.txt                # Python dependencies
└── README.md                       # This file
```

### Metadata Format
The `metadata.json` file contains:
```json
{
    "name": "Resort Name",
    "country": "Country",
    "region": "State/Region",
    "parent_company": "Parent Company",
    "continent": "Continent",
    "skiable_acreage": 1000,
    "lifts": 20,
    "boxes": [[x, y, width, height], ...]
}
```

## Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature-name`
3. Make your changes
4. Submit a pull request

### Development Guidelines
- Follow PEP 8 style guidelines
- Add comments for complex functionality
- Update the README if adding new features
- Test thoroughly before submitting pull requests

## License

[MIT License](LICENSE)