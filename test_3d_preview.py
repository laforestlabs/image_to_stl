#!/usr/bin/env python3
"""
Test script for 3D preview functionality
"""
import sys
import numpy as np
from PySide6.QtWidgets import QApplication
from gui.preview_widget import PreviewWidget
from core.stl_generator import STLGenerator

def main():
    app = QApplication(sys.argv)

    # Create a simple test height map (10x10 grid)
    height_map = np.random.rand(10, 10) * 5.0

    # Generate STL mesh
    generator = STLGenerator()
    test_mesh = generator.generate_from_heightmap(height_map, pixel_size_mm=1.0)

    # Create preview widget
    preview = PreviewWidget()
    preview.setWindowTitle("3D Preview Test")
    preview.resize(800, 600)
    preview.show()

    # Set the mesh
    print("Setting mesh...")
    preview.set_mesh(test_mesh)
    print("Mesh set successfully!")

    sys.exit(app.exec())

if __name__ == "__main__":
    main()
