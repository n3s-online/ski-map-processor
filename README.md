# Ski Map Processor

Processing ski maps for my upcoming project Ski-o-guessr.

## Features

- Collect metadata about ski resorts given the trail map
- Generate a copy of the trail map with text covered
- PyQt5-based GUI for easy metadata editing
- Smart dropdowns that learn from existing metadata entries
- Country-dependent region selection
- "Other" option in dropdowns for custom values

## Setup and Usage

1. Install dependencies:
   ```
   pip install -r requirements.txt
   ```
   
   Note: This application uses PyQt5 for the GUI interface.

2. Place ski map folders in the `files/` directory. Each folder should contain:
   - `ski_map_original.png` - The original ski map image
   - Optional: `metadata.json` - Existing metadata (will be created if not present)

3. Run the application:
   ```
   python main.py
   ```

4. Use the interface to:
   - View ski maps
   - Edit metadata using the form
   - Save metadata
   - Navigate between different ski maps
   
5. Form functionality:
   - Resort Name: Simple text input
   - Country: Dropdown with "Other" option for custom values
   - State/Region: Dropdown that shows regions specific to the selected country
   - Parent Company: Dropdown with "Other" option for custom values
   - New values are automatically added to the dropdowns after saving