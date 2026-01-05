#!/usr/bin/env python3
"""
Test matplotlib-based 3D preview
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

def test_preview():
    print("=" * 60)
    print("MATPLOTLIB 3D PREVIEW TEST")
    print("=" * 60)

    app = QApplication(sys.argv)

    # Create simple test image
    print("\n1. Creating test image...")
    img_array = np.random.randint(100, 200, (30, 30), dtype=np.uint8)
    img = Image.fromarray(img_array, mode='L')
    with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
        tmp_path = tmp.name
        img.save(tmp_path)
    print(f"   ✓ Image created")

    # Create process
    print("\n2. Creating process...")
    process = Process("Test")
    process.add_operation(Operation("set_lithophane_parameters", {
        "width_mm": 30.0,
        "height_mm": 30.0,
        "min_thickness_mm": 1.0,
        "max_thickness_mm": 3.0,
        "invert": False
    }))

    # Process
    print("\n3. Processing image...")
    processor = ImageProcessor()
    height_map = processor.execute_process(tmp_path, process)
    print(f"   ✓ Height map: {height_map.shape}")

    # Generate STL (smaller for faster processing)
    print("\n4. Generating STL mesh...")
    generator = STLGenerator()
    stl_mesh = generator.generate_from_heightmap(height_map, pixel_size_mm=0.1)
    print(f"   ✓ STL: {len(stl_mesh.vectors):,} triangles")

    # Create preview
    print("\n5. Creating preview widget...")
    preview = PreviewWidget()
    preview.setWindowTitle("Matplotlib 3D Preview Test")
    preview.resize(900, 700)
    preview.show()

    # Display mesh
    print("\n6. Generating 3D preview...")
    preview.set_mesh(stl_mesh)

    def check_result():
        print("\n" + "=" * 60)
        print("✓ TEST COMPLETE")
        print("=" * 60)
        print("\nIf you see a 3D rendered image above, the preview is working!")
        print("The preview uses matplotlib to generate a static 3D view.")
        app.quit()

    # Close after 3 seconds
    QTimer.singleShot(3000, check_result)

    # Cleanup
    os.unlink(tmp_path)

    app.exec()

if __name__ == "__main__":
    test_preview()
