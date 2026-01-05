#!/usr/bin/env python3
"""
Demo script that creates a simple lithophane and displays it in 3D
This is a standalone demo showing the 3D preview in action
"""
import sys
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import tempfile

from PySide6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget, QPushButton, QLabel
from PySide6.QtCore import Qt

from core.process import Process, Operation
from core.image_processor import ImageProcessor
from core.stl_generator import STLGenerator
from gui.preview_widget import PreviewWidget


class DemoWindow(QMainWindow):
    """Demo window showing 3D preview"""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("3D Lithophane Preview Demo")
        self.setGeometry(100, 100, 1000, 700)

        # Central widget
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        # Instructions
        info = QLabel(
            "3D Lithophane Preview Demo\n\n"
            "This demo creates a simple test lithophane and displays it in 3D.\n"
            "Click the button below to generate and view a sample lithophane."
        )
        info.setAlignment(Qt.AlignCenter)
        info.setStyleSheet("font-size: 14px; padding: 20px;")
        layout.addWidget(info)

        # Generate button
        self.generate_btn = QPushButton("Generate Demo Lithophane")
        self.generate_btn.setStyleSheet("font-size: 16px; padding: 10px;")
        self.generate_btn.clicked.connect(self.generate_demo)
        layout.addWidget(self.generate_btn)

        # Status label
        self.status_label = QLabel("Ready")
        self.status_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.status_label)

        # Preview widget
        self.preview = PreviewWidget()
        layout.addWidget(self.preview, stretch=1)

    def generate_demo(self):
        """Generate and display a demo lithophane"""
        try:
            self.status_label.setText("Creating test image...")
            self.generate_btn.setEnabled(False)

            # Create a simple test image with a gradient
            img_array = np.zeros((100, 100), dtype=np.uint8)

            # Create a circular gradient
            center_y, center_x = 50, 50
            for y in range(100):
                for x in range(100):
                    distance = np.sqrt((x - center_x)**2 + (y - center_y)**2)
                    intensity = max(0, min(255, int(255 * (1 - distance / 70))))
                    img_array[y, x] = intensity

            # Convert to PIL image
            img = Image.fromarray(img_array, mode='L')

            # Add text
            draw = ImageDraw.Draw(img)
            try:
                # Try to add text (may not work without font)
                draw.text((10, 40), "3D", fill=255)
            except:
                pass

            # Save temporarily
            with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
                tmp_path = tmp.name
                img.save(tmp_path)

            self.status_label.setText("Processing image...")

            # Create process
            process = Process("Demo Process")
            process.add_operation(Operation("set_lithophane_parameters", {
                "width_mm": 50.0,
                "height_mm": 50.0,
                "min_thickness_mm": 1.0,
                "max_thickness_mm": 4.0,
                "invert": False
            }))

            # Process image
            processor = ImageProcessor()
            height_map = processor.execute_process(tmp_path, process)

            self.status_label.setText("Generating 3D mesh...")

            # Generate STL
            generator = STLGenerator()
            stl_mesh = generator.generate_from_heightmap(height_map, pixel_size_mm=0.1)

            self.status_label.setText("Rendering 3D preview...")

            # Display in preview
            self.preview.set_mesh(stl_mesh)

            self.status_label.setText(
                f"✓ Demo complete! 3D model displayed.\n"
                f"Mesh: {len(stl_mesh.vectors):,} triangles | "
                f"Size: 50x50x3mm"
            )

            # Clean up
            import os
            os.unlink(tmp_path)

        except Exception as e:
            import traceback
            self.status_label.setText(f"Error: {e}")
            print("Error details:")
            traceback.print_exc()

        finally:
            self.generate_btn.setEnabled(True)


def main():
    print("=" * 60)
    print("3D LITHOPHANE PREVIEW DEMO")
    print("=" * 60)
    print("\nStarting demo application...")
    print("This will create a simple lithophane and display it in 3D.")
    print("\nInstructions:")
    print("1. Click 'Generate Demo Lithophane' button")
    print("2. Wait for processing")
    print("3. See the 3D model appear!")
    print("4. Use mouse to rotate, zoom, pan")
    print("\n" + "=" * 60 + "\n")

    app = QApplication(sys.argv)
    window = DemoWindow()
    window.show()

    # Auto-generate on startup for immediate demo
    window.generate_demo()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
