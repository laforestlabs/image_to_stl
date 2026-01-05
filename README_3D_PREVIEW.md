# 3D Preview Feature

The application now includes a fully functional 3D preview of generated STL models using PyVista!

## What's New

### 1. Lithophane Parameters Operation
The old "Add Border" and "Set Thickness" operations have been replaced with a unified **Set Lithophane Parameters** operation that controls:

- **Width (mm)**: Physical width of the final lithophane
- **Height (mm)**: Physical height of the final lithophane
- **Min Thickness (mm)**: Thickness for saturated/white pixels (default: 0.8mm)
- **Max Thickness (mm)**: Thickness for black pixels (default: 5.0mm)

This operation simultaneously:
1. Scales the image to match the specified physical dimensions
2. Converts the grayscale image to a height map
3. Maps pixel brightness to thickness (white = thin, black = thick)

### 2. Real-time 3D Visualization
When you process an image, the STL mesh is now displayed in an interactive 3D viewer:

- **Rotate**: Click and drag to rotate the model
- **Zoom**: Scroll wheel to zoom in/out
- **Pan**: Right-click and drag to pan
- **Axes**: Visual axes showing X, Y, Z orientation

## Usage

1. **Load or create a process** with these recommended operations:
   - Convert to Grayscale (optional: invert for standard lithophanes)
   - Set Lithophane Parameters (specify dimensions and thickness range)

2. **Load an image** using the "Load Image" button

3. **Process the image** - the 3D preview will update automatically showing your lithophane model

4. **Export the STL** when satisfied with the preview

## Requirements

The 3D preview requires:
- PyVista (`pip install pyvista`)
- PyVistaQt (`pip install pyvistaqt`)

Both should already be installed. If not, run:
```bash
pip install pyvista pyvistaqt
```

## Example Workflow

```
1. Grayscale Conversion (with invert: true)
   └─> Converts image to grayscale and inverts (bright areas = thin)

2. Set Lithophane Parameters
   ├─> Width: 100 mm
   ├─> Height: 100 mm
   ├─> Min Thickness: 0.8 mm (for white/bright pixels)
   └─> Max Thickness: 5.0 mm (for black/dark pixels)
```

This creates a 100x100mm lithophane where:
- Bright image areas = 0.8mm thick (lets light through)
- Dark image areas = 5.0mm thick (blocks light)

## Technical Details

### Pixel Density
The lithophane parameters operation uses 10 pixels per millimeter, giving excellent detail while keeping file sizes manageable.

### STL Mesh Structure
- Top surface follows the height map
- Bottom surface is flat at z=0
- Side walls connect top and bottom
- All faces have correct normals for 3D printing

### 3D Rendering
- Uses PyVista's QtInteractor for smooth Qt integration
- Smooth shading with specular highlights
- Light blue color for easy visualization
- Automatic camera positioning to show entire model

## Troubleshooting

**3D preview shows "PyVista not available"**
- Install with: `pip install pyvista pyvistaqt`

**Preview is blank after processing**
- Check the console output for error messages
- Ensure your process includes the "Set Lithophane Parameters" operation
- Try a smaller image first (< 500x500 pixels)

**Application crashes when opening**
- Check that you have a working display/X server
- Try running the test scripts first: `python3 test_full_workflow.py`

## Advanced Tips

1. **For detailed lithophanes**: Use images with good contrast
2. **For large lithophanes**: Keep the pixel count reasonable (< 2000x2000)
3. **For faster previews**: Use smaller test images during design iteration
4. **For printing**: Most slicers prefer 0.8-1.2mm min thickness, 3-6mm max thickness
