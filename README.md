# Image to STL Converter

A PySide6 GUI application for converting images to STL files for 3D printing.

## Features

- Load and save custom processing workflows as JSON files
- Sequential image processing operations:
  - Resize images to specific dimensions with PPI control
  - Convert to grayscale with optional inversion
  - Add borders
  - Set thickness parameters for 3D model generation
- Mesh statistics display (triangles, dimensions)
- Edit and modify processing workflows through the GUI
- Export STL files ready for 3D printing

## Installation

1. Create a virtual environment (recommended):
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

## Usage

Run the application:
```bash
python main.py
```

### Workflow

1. **Load a Process**: Click "Load Process" to load an existing process JSON file, or use the default process that loads automatically
2. **Load an Image**: Click "Load Image" to select an image file (PNG, JPG, BMP, TIFF)
3. **Edit Process** (optional): Use the Process Editor to add, remove, or modify operations:
   - Add Operation: Create new processing steps
   - Edit: Modify existing operations
   - Remove: Delete operations
   - Move Up/Down: Reorder operations
4. **Process Image**: Click "Process Image" to apply the operations and generate the STL model
5. **Preview**: View mesh statistics (triangle count, dimensions) in the preview panel
6. **Export**: Click "Export STL" to save the model as an STL file
7. **View**: Open the exported STL in MeshLab, Blender, or your 3D printer slicer software

### Process Operations

- **Resize**: Scale image to specific dimensions with PPI control
  - Width/Height: Physical dimensions
  - Unit: mm or inches
  - PPI: Pixels per inch resolution
  - Maintain Aspect Ratio: Preserve original proportions

- **Convert to Grayscale**: Convert to grayscale color space
  - Invert: Reverse brightness values

- **Add Border**: Add a border around the image
  - Size: Border width in pixels
  - Color: Border color (0-255)

- **Set Thickness**: Define 3D model height parameters
  - Base Thickness: Minimum height in mm
  - Max Thickness: Maximum height in mm (bright areas)

### Saving and Loading Processes

- **Save Process**: Save changes to the current process file
- **Save Process As**: Save the process to a new JSON file
- **Load Process**: Open an existing process JSON file

Custom processes are stored as JSON files that can be shared and reused.

## Project Structure

```
image_to_stl/
├── main.py                 # Application entry point
├── core/
│   ├── __init__.py
│   ├── process.py          # Process and Operation models
│   ├── image_processor.py  # Image processing operations
│   └── stl_generator.py    # STL mesh generation
├── gui/
│   ├── __init__.py
│   ├── main_window.py      # Main application window
│   ├── process_editor.py   # Process editing widget
│   └── preview_widget.py   # 3D preview widget
├── processes/
│   └── default.json        # Default process
└── requirements.txt        # Python dependencies
```

## Example Process JSON

```json
{
  "name": "My Custom Process",
  "operations": [
    {
      "type": "resize",
      "parameters": {
        "width": 100,
        "height": 100,
        "unit": "mm",
        "ppi": 96,
        "maintain_aspect_ratio": true
      }
    },
    {
      "type": "grayscale",
      "parameters": {
        "invert": false
      }
    },
    {
      "type": "add_border",
      "parameters": {
        "size": 10,
        "color": 0
      }
    },
    {
      "type": "set_thickness",
      "parameters": {
        "base_thickness_mm": 1.0,
        "max_thickness_mm": 5.0
      }
    }
  ]
}
```

## Dependencies

- PySide6: Qt-based GUI framework
- NumPy: Numerical operations
- Pillow: Image processing
- numpy-stl: STL file generation

## License

This project is open source and available for modification and distribution.
