# Quick Start Guide

## Running the Application

```bash
cd /home/jason/image_to_stl
python3 main.py
```

## Creating Your First Lithophane

### Step 1: Set Up Your Process
1. Click "Add Operation"
2. Select "Convert to Grayscale"
   - Check "Invert Colors" (so bright areas become thin)
3. Click "Add Operation" again
4. Select "Set Lithophane Parameters"
   - Width: 100 mm (or your desired size)
   - Height: 100 mm (or your desired size)
   - Min Thickness: 0.8 mm (for white/bright pixels)
   - Max Thickness: 5.0 mm (for black/dark pixels)

### Step 2: Load Your Image
1. Click "Load Image"
2. Select any image file (PNG, JPG, etc.)

### Step 3: Process and Preview
1. Click "Process Image"
2. Wait for processing to complete
3. **The 3D model will appear in the preview pane!**
   - Rotate: Click and drag
   - Zoom: Scroll wheel
   - Pan: Right-click and drag

### Step 4: Export
1. Click "Export STL"
2. Choose save location
3. Load the STL file into your 3D printer slicer!

## What's Different Now

### Old Workflow (REMOVED)
```
❌ Resize → Grayscale → Add Border → Set Thickness
```

### New Workflow (CURRENT)
```
✓ Grayscale (with invert) → Set Lithophane Parameters
```

The new "Set Lithophane Parameters" operation combines sizing and thickness into one step!

## Key Parameters Explained

**Width & Height (mm)**
- Physical dimensions of your final print
- Example: 100mm x 100mm = ~4" x 4" print

**Min Thickness (mm)**
- How thin the bright/white areas will be
- Thinner = more light passes through
- Recommended: 0.8mm - 1.2mm

**Max Thickness (mm)**
- How thick the dark/black areas will be
- Thicker = less light passes through
- Recommended: 3.0mm - 6.0mm

## Tips

1. **Start small**: Test with a 50mm x 50mm lithophane first
2. **Good contrast**: Images with clear light/dark areas work best
3. **Resolution**: The app uses 10 pixels/mm (high detail)
4. **Printing**: Most slicers work best with the defaults (0.8-5.0mm)

## Troubleshooting

**No 3D preview showing?**
- PyVista should be installed (it is!)
- Check console for errors
- Make sure you added "Set Lithophane Parameters" operation

**Process fails?**
- Make sure you have both operations:
  1. Grayscale
  2. Set Lithophane Parameters
- Remove any old "Add Border" or "Set Thickness" operations

**STL file too large?**
- Use smaller physical dimensions
- Or use a smaller source image

## Testing

Run the comprehensive test:
```bash
python3 test_full_workflow.py
```

Verify everything works:
```bash
python3 verify_gui.py
```

## More Help

See [README_3D_PREVIEW.md](README_3D_PREVIEW.md) for detailed documentation.
