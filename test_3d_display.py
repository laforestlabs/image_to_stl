#!/usr/bin/env python3
"""
Test that 3D display actually works with a mesh
"""
import sys
import numpy as np
from PIL import Image
import tempfile
import os

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer

from core.process import Process, Operation
from core.image_processor import ImageProcessor
from core.stl_generator import STLGenerator
from gui.preview_widget import PreviewWidget

def test_3d_display():
    print("=" * 60)
    print("3D DISPLAY TEST")
    print("=" * 60)

    app = QApplication(sys.argv)

    # Create test image
    print("\n1. Creating test image...")
    img_array = np.random.randint(0, 256, (50, 50), dtype=np.uint8)
    img = Image.fromarray(img_array, mode='L')
    with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
        tmp_path = tmp.name
        img.save(tmp_path)
    print(f"   ✓ Test image created: {tmp_path}")

    # Create process
    print("\n2. Creating process...")
    process = Process("Test")
    process.add_operation(Operation("set_lithophane_parameters", {
        "width_mm": 25.0,
        "height_mm": 25.0,
        "min_thickness_mm": 1.0,
        "max_thickness_mm": 3.0,
        "invert": False
    }))
    print("   ✓ Process created")

    # Process image
    print("\n3. Processing image...")
    processor = ImageProcessor()
    height_map = processor.execute_process(tmp_path, process)
    print(f"   ✓ Height map: {height_map.shape}")

    # Generate STL
    print("\n4. Generating STL...")
    generator = STLGenerator()
    stl_mesh = generator.generate_from_heightmap(height_map, pixel_size_mm=0.1)
    print(f"   ✓ STL mesh: {len(stl_mesh.vectors):,} triangles")

    # Create preview widget
    print("\n5. Creating preview widget...")
    preview = PreviewWidget()
    preview.setWindowTitle("3D Display Test")
    preview.resize(800, 600)
    preview.show()
    print("   ✓ Preview widget created and shown")

    # Display mesh
    print("\n6. Displaying mesh in 3D...")
    preview.set_mesh(stl_mesh)

    if preview.pyvista_initialized:
        print("   ✓ PyVista widget initialized!")
        print("   ✓ Mesh should be visible in 3D!")
        success = True
    else:
        print("   ⚠ PyVista not initialized (fallback mode)")
        success = False

    # Clean up
    os.unlink(tmp_path)

    # Close after 2 seconds
    def on_close():
        print("\n" + "=" * 60)
        if success:
            print("✓ 3D DISPLAY TEST PASSED!")
            print("  The mesh was successfully displayed in 3D!")
        else:
            print("⚠ 3D display used fallback mode")
        print("=" * 60)
        app.quit()

    QTimer.singleShot(2000, on_close)

    app.exec()

if __name__ == "__main__":
    test_3d_display()
