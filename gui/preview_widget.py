"""
3D preview widget for STL visualization
"""
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QScrollArea
from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap, QImage
from stl import mesh as stl_mesh
import numpy as np
import tempfile
import os


class PreviewWidget(QWidget):
    """Widget for displaying 3D preview of STL mesh"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_mesh = None
        self.plotter = None
        self.pyvista_widget = None
        self.pyvista_available = False
        self.pyvista_initialized = False
        self.info_label = None
        self._setup_ui()

    def _setup_ui(self):
        """Setup the UI"""
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)

        # Disable PyVista by default due to VTK/OpenGL issues
        # Use matplotlib-based preview instead
        self.pyvista_available = False

        # Show placeholder message
        self.info_label = QLabel("No mesh loaded.\nProcess an image to generate a 3D model.")
        self.info_label.setAlignment(Qt.AlignCenter)
        self.info_label.setWordWrap(True)
        self.layout.addWidget(self.info_label)

    def _initialize_pyvista_widget(self):
        """Initialize PyVista widget on first use (lazy initialization)"""
        if self.pyvista_initialized or not self.pyvista_available:
            return

        try:
            from pyvistaqt import QtInteractor

            # Remove the info label
            if self.info_label is not None:
                self.layout.removeWidget(self.info_label)
                self.info_label.deleteLater()
                self.info_label = None

            # Create PyVista widget
            self.pyvista_widget = QtInteractor(self)
            self.layout.addWidget(self.pyvista_widget)

            # Set up the plotter
            self.pyvista_widget.set_background('white')
            self.pyvista_initialized = True
            print("PyVista widget initialized successfully")

        except Exception as e:
            print(f"Error initializing PyVista widget: {e}")
            import traceback
            traceback.print_exc()
            self.pyvista_available = False

            # Show error message
            if self.info_label is None:
                self.info_label = QLabel()
                self.info_label.setAlignment(Qt.AlignCenter)
                self.info_label.setWordWrap(True)
                self.layout.addWidget(self.info_label)

            self.info_label.setText(f"PyVista initialization failed: {e}\n\nThe STL file can be viewed in external software.")

    def _create_matplotlib_preview(self, mesh: stl_mesh.Mesh):
        """Create a 3D preview using matplotlib"""
        try:
            import matplotlib
            matplotlib.use('Agg')  # Non-interactive backend
            import matplotlib.pyplot as plt
            from mpl_toolkits.mplot3d import Axes3D

            # Create figure
            fig = plt.figure(figsize=(10, 8), facecolor='white')
            ax = fig.add_subplot(111, projection='3d')

            # Plot the mesh
            collection = ax.plot_trisurf(
                mesh.vectors[:, :, 0].flatten(),
                mesh.vectors[:, :, 1].flatten(),
                mesh.vectors[:, :, 2].flatten(),
                color='lightblue',
                edgecolor='none',
                alpha=0.8,
                shade=True
            )

            # Set labels and title
            ax.set_xlabel('X (mm)')
            ax.set_ylabel('Y (mm)')
            ax.set_zlabel('Z (mm)')
            ax.set_title('Lithophane 3D Preview', fontsize=14, fontweight='bold')

            # Set aspect ratio
            bounds = mesh.vectors.reshape(-1, 3)
            x_range = bounds[:, 0].max() - bounds[:, 0].min()
            y_range = bounds[:, 1].max() - bounds[:, 1].min()
            z_range = bounds[:, 2].max() - bounds[:, 2].min()

            max_range = max(x_range, y_range, z_range)
            ax.set_box_aspect([x_range/max_range, y_range/max_range, z_range/max_range])

            # Save to buffer
            buf = tempfile.NamedTemporaryFile(suffix='.png', delete=False)
            plt.savefig(buf.name, dpi=100, bbox_inches='tight')
            plt.close(fig)

            # Load as QPixmap
            pixmap = QPixmap(buf.name)
            os.unlink(buf.name)

            return pixmap

        except Exception as e:
            print(f"Error creating matplotlib preview: {e}")
            import traceback
            traceback.print_exc()
            return None

    def set_mesh(self, mesh: stl_mesh.Mesh):
        """Set the mesh to display"""
        self.current_mesh = mesh

        # Calculate mesh info
        num_triangles = len(mesh.vectors)
        bounds = mesh.vectors.reshape(-1, 3)
        x_range = bounds[:, 0].max() - bounds[:, 0].min()
        y_range = bounds[:, 1].max() - bounds[:, 1].min()
        z_range = bounds[:, 2].max() - bounds[:, 2].min()

        # Create matplotlib preview
        print("Creating 3D preview with matplotlib...")
        pixmap = self._create_matplotlib_preview(mesh)

        if pixmap is not None:
            # Remove info label if it exists
            if self.info_label is not None:
                self.layout.removeWidget(self.info_label)
                self.info_label.deleteLater()

            # Create image label
            image_label = QLabel()
            image_label.setPixmap(pixmap.scaled(
                800, 600,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            ))
            image_label.setAlignment(Qt.AlignCenter)

            # Create info text
            info_text = QLabel(
                f"3D Preview Generated!\n"
                f"Triangles: {num_triangles:,} | "
                f"Size: {x_range:.1f} x {y_range:.1f} x {z_range:.1f} mm"
            )
            info_text.setAlignment(Qt.AlignCenter)
            info_text.setStyleSheet("font-size: 12px; padding: 10px;")

            # Add to layout
            self.layout.addWidget(info_text)
            self.layout.addWidget(image_label, stretch=1)

            self.info_label = None
            print("3D preview displayed successfully!")

        else:
            # Fallback to text info
            if self.info_label is not None:
                info_text = f"STL Mesh Generated Successfully!\n\n"
                info_text += f"Triangles: {num_triangles:,}\n"
                info_text += f"Dimensions (mm):\n"
                info_text += f"  X: {x_range:.2f}\n"
                info_text += f"  Y: {y_range:.2f}\n"
                info_text += f"  Z: {z_range:.2f}\n\n"
                info_text += f"3D preview unavailable.\n"
                info_text += f"Export STL to view in external software."

                self.info_label.setText(info_text)

    def clear(self):
        """Clear the preview"""
        self.current_mesh = None

        # Clear all widgets
        while self.layout.count():
            item = self.layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # Reset to placeholder
        self.info_label = QLabel("No mesh loaded.\nProcess an image to generate a 3D model.")
        self.info_label.setAlignment(Qt.AlignCenter)
        self.info_label.setWordWrap(True)
        self.layout.addWidget(self.info_label)
