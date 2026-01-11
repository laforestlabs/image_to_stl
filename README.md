# Image to STL Lithophane Converter

A desktop application for converting images into 3D-printable lithophane STL files.

![PySide6](https://img.shields.io/badge/PySide6-Qt-green) ![Python 3.8+](https://img.shields.io/badge/Python-3.8+-blue)

## Features

- **Interactive Crop Tool** - Drag and resize a crop region directly on the image preview
- **Real-time Preview** - See the processed grayscale result before exporting
- **Lithophane Parameters** - Full control over dimensions, thickness, blur, and build angle
- **Sample Images** - Includes 100+ categorized sample images to get started
- **Process Saving** - Save and load parameter presets as JSON files

## Installation

```bash
# Clone the repository
git clone https://github.com/laforestlabs/image_to_stl.git
cd image_to_stl

# Create virtual environment (recommended)
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

## Usage

```bash
python main.py
```

### Quick Start

1. The app loads with a random sample image on startup
2. Use the **crop tool** to select a region (drag the box or resize corners)
3. Adjust **lithophane parameters** in the right panel
4. Click **Export STL** to save your lithophane

### Crop Tool

- **Drag inside** the red box to move the crop region
- **Drag corner handles** (white circles) to resize
- Click **Reset Crop** to select the full image

### Lithophane Parameters

| Parameter | Description |
|-----------|-------------|
| **Width/Height** | Physical dimensions in mm |
| **Min Thickness** | Thickness at brightest areas (typically 0.6-1.0mm) |
| **Max Thickness** | Thickness at darkest areas (typically 3-5mm) |
| **Resolution** | Pixels per mm (higher = more detail, larger file) |
| **Blur** | Smoothing radius in mm to reduce noise |
| **Build Angle** | Angle for the back surface (for easier printing) |
| **Crop Mode** | Crop to size or keep full image with padding |
| **Invert** | Flip light/dark (for negative images) |

### Tips for Good Lithophanes

- **High contrast images** work best
- **Portraits** benefit from slightly higher blur (0.5-1mm)
- Start with **2 pixels/mm** resolution, increase for fine detail
- **0.8mm min / 4mm max thickness** is a good starting point
- Print with **white or natural PLA** for best results

## Project Structure

```
image_to_stl/
├── main.py                     # Entry point
├── core/
│   ├── image_processor.py      # Image processing and height map generation
│   ├── process.py              # Process/operation data models
│   └── stl_generator.py        # STL mesh generation
├── gui/
│   ├── main_window.py          # Main application window
│   ├── crop_preview_widget.py  # Interactive crop tool
│   ├── lithophane_controls.py  # Parameter sliders and inputs
│   └── process_editor.py       # Process list editor
├── processes/
│   └── default.json            # Default parameters
└── samples/                    # Sample images by category
```

## Dependencies

- **PySide6** - Qt GUI framework
- **Pillow** - Image processing
- **NumPy** - Numerical operations
- **numpy-stl** - STL file generation

## License

MIT License - feel free to use and modify.
