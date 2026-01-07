"""
Main application window
"""
import random
from pathlib import Path
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QFileDialog, QMessageBox,
    QLabel, QGroupBox, QFrame, QDialog, QMenuBar, QMenu, QApplication
)
from PySide6.QtCore import Qt, QThread, Signal, QSize
from PySide6.QtGui import QPixmap, QImage, QMovie, QAction, QKeySequence
from PIL import Image
from gui.process_editor import ProcessEditor
from gui.lithophane_controls import LithophaneControls
from gui.crop_preview_widget import CropPreviewWidget
from core.process import Process, Operation
from core.image_processor import ImageProcessor
from core.stl_generator import STLGenerator


class ProcessingWorker(QThread):
    """Background worker for image processing"""
    finished = Signal(object)  # Emits the height_map or None on error
    error = Signal(str)

    def __init__(self, image_processor, stl_generator, image_path, process, crop_rect=None):
        super().__init__()
        self.image_processor = image_processor
        self.stl_generator = stl_generator
        self.image_path = image_path
        self.process = process
        self.crop_rect = crop_rect  # (x, y, w, h) normalized 0-1

    def run(self):
        try:
            # Process image with optional crop
            height_map = self.image_processor.execute_process(
                self.image_path,
                self.process,
                crop_rect=self.crop_rect
            )

            # Generate STL
            angle = self.image_processor.get_angle()
            self.stl_generator.generate_from_heightmap(height_map, angle=angle)

            self.finished.emit(height_map)
        except Exception as e:
            self.error.emit(str(e))


class LoadingDialog(QDialog):
    """Fun loading dialog with animated GIF"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Processing...")
        self.setModal(True)
        self.setFixedSize(300, 350)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowCloseButtonHint)

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)

        # GIF label
        self.gif_label = QLabel()
        self.gif_label.setAlignment(Qt.AlignCenter)

        # Load the animated GIF
        gif_path = Path(__file__).parent / "assets" / "loading.gif"
        if gif_path.exists():
            self.movie = QMovie(str(gif_path))
            self.movie.setScaledSize(QSize(200, 200))
            self.gif_label.setMovie(self.movie)
            self.movie.start()
        else:
            self.gif_label.setText("Processing...")

        layout.addWidget(self.gif_label)

        # Status label
        self.status_label = QLabel("Generating your lithophane...")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setStyleSheet("font-size: 14px; color: #666;")
        layout.addWidget(self.status_label)

    def set_status(self, text: str):
        self.status_label.setText(text)


class MainWindow(QMainWindow):
    """Main application window"""

    def __init__(self):
        super().__init__()
        self.current_process = None
        self.current_process_file = None
        self.current_image_file = None
        self.image_processor = ImageProcessor()
        self.stl_generator = STLGenerator()
        self.worker = None
        self.loading_dialog = None
        self._current_crop = (0.0, 0.0, 1.0, 1.0)  # Normalized crop coords (x, y, w, h)

        self.setWindowTitle("Image to STL Converter")

        # Set window to nearly full screen (90% of screen size)
        screen = QApplication.primaryScreen().availableGeometry()
        width = int(screen.width() * 0.9)
        height = int(screen.height() * 0.9)
        self.setGeometry(
            (screen.width() - width) // 2,
            (screen.height() - height) // 2,
            width,
            height
        )

        self._setup_menu_bar()
        self._setup_ui()

    def _setup_menu_bar(self):
        """Setup the menu bar"""
        menu_bar = self.menuBar()

        # View menu
        view_menu = menu_bar.addMenu("View")

        # Fullscreen action
        self.fullscreen_action = QAction("Fullscreen", self)
        self.fullscreen_action.setShortcut(QKeySequence("F11"))
        self.fullscreen_action.setCheckable(True)
        self.fullscreen_action.triggered.connect(self._toggle_fullscreen)
        view_menu.addAction(self.fullscreen_action)

    def _toggle_fullscreen(self):
        """Toggle fullscreen mode"""
        if self.isFullScreen():
            self.showNormal()
            self.fullscreen_action.setChecked(False)
        else:
            self.showFullScreen()
            self.fullscreen_action.setChecked(True)

    def _setup_ui(self):
        """Setup the user interface"""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        main_layout = QVBoxLayout(central_widget)

        # Top button bar
        button_layout = QHBoxLayout()

        self.load_process_btn = QPushButton("Load Process")
        self.load_process_btn.clicked.connect(self._load_process)
        button_layout.addWidget(self.load_process_btn)

        self.save_process_btn = QPushButton("Save Process")
        self.save_process_btn.clicked.connect(self._save_process)
        button_layout.addWidget(self.save_process_btn)

        self.save_process_as_btn = QPushButton("Save Process As...")
        self.save_process_as_btn.clicked.connect(self._save_process_as)
        button_layout.addWidget(self.save_process_as_btn)

        button_layout.addStretch()

        self.load_image_btn = QPushButton("Load Image")
        self.load_image_btn.clicked.connect(self._load_image)
        button_layout.addWidget(self.load_image_btn)

        self.export_stl_btn = QPushButton("Export STL")
        self.export_stl_btn.clicked.connect(self._export_stl)
        self.export_stl_btn.setEnabled(False)
        button_layout.addWidget(self.export_stl_btn)

        main_layout.addLayout(button_layout)

        # Status label
        self.status_label = QLabel("Ready. Load an image to begin.")
        main_layout.addWidget(self.status_label)

        # Image preview section
        image_preview_layout = QHBoxLayout()

        # Original image preview with interactive crop
        original_group = QGroupBox("Original Image (Drag to crop)")
        original_layout = QVBoxLayout()
        self.crop_preview = CropPreviewWidget()
        self.crop_preview.setMinimumSize(400, 350)
        self.crop_preview.crop_changed.connect(self._on_crop_changed)
        original_layout.addWidget(self.crop_preview, stretch=1)

        # Reset crop button
        self.reset_crop_btn = QPushButton("Reset Crop")
        self.reset_crop_btn.clicked.connect(self._reset_crop)
        original_layout.addWidget(self.reset_crop_btn)

        original_group.setLayout(original_layout)
        image_preview_layout.addWidget(original_group)

        # Processed image preview
        processed_group = QGroupBox("Processed (Simulated Print)")
        processed_layout = QVBoxLayout()
        self.processed_image_label = QLabel("Load an image to preview")
        self.processed_image_label.setAlignment(Qt.AlignCenter)
        self.processed_image_label.setMinimumSize(400, 350)
        self.processed_image_label.setStyleSheet("QLabel { background-color: #333; color: #999; }")
        self.processed_image_label.setFrameStyle(QFrame.StyledPanel)
        processed_layout.addWidget(self.processed_image_label, stretch=1)
        processed_group.setLayout(processed_layout)
        image_preview_layout.addWidget(processed_group)

        # Give image preview section more vertical space (stretch=3)
        main_layout.addLayout(image_preview_layout, stretch=3)

        # Bottom section: split into left (process list) and right (controls)
        bottom_layout = QHBoxLayout()

        # Left side: Process Editor (operation list)
        process_group = QGroupBox("Process Operations")
        process_layout = QVBoxLayout()
        self.process_editor = ProcessEditor()
        self.process_editor.process_changed.connect(self._on_process_changed)
        process_layout.addWidget(self.process_editor)
        process_group.setLayout(process_layout)
        bottom_layout.addWidget(process_group, stretch=1)

        # Right side: Lithophane Controls (sliders and inputs)
        controls_group = QGroupBox("Lithophane Parameters")
        controls_layout = QVBoxLayout()
        self.lithophane_controls = LithophaneControls()
        self.lithophane_controls.parameters_changed.connect(self._on_controls_changed)
        controls_layout.addWidget(self.lithophane_controls)
        controls_group.setLayout(controls_layout)
        bottom_layout.addWidget(controls_group, stretch=1)

        # Bottom section takes less vertical space (stretch=1)
        main_layout.addLayout(bottom_layout, stretch=1)

        # Load default process if it exists
        self._load_default_process()

        # Load a random sample image on startup
        self._load_random_sample_image()

    def _load_default_process(self):
        """Load the default process if it exists"""
        default_path = Path(__file__).parent.parent / "processes" / "default.json"
        if default_path.exists():
            try:
                self.current_process = Process.load(default_path)
                self.process_editor.set_process(self.current_process)
                # Sync lithophane controls with the process
                self._sync_controls_from_process()
                self.status_label.setText(f"Loaded default process: {self.current_process.name}")
            except Exception as e:
                self.status_label.setText(f"Could not load default process: {e}")

    def _sync_controls_from_process(self):
        """Sync lithophane controls from current process"""
        process = self.process_editor.get_process()
        for op in process.operations:
            if op.type == "set_lithophane_parameters":
                self.lithophane_controls.set_parameters(op.parameters)
                break

    def _on_controls_changed(self):
        """Handle lithophane control changes - update process and reprocess"""
        # Get current parameters from controls
        params = self.lithophane_controls.get_parameters()

        # Update the process with new parameters
        process = self.process_editor.get_process()

        # Find and update the lithophane parameters operation
        found = False
        for i, op in enumerate(process.operations):
            if op.type == "set_lithophane_parameters":
                process.operations[i] = Operation("set_lithophane_parameters", params)
                found = True
                break

        # If no lithophane operation exists, add one
        if not found:
            process.add_operation(Operation("set_lithophane_parameters", params))

        # Update the process editor display
        self.process_editor._refresh_list()

        # Reprocess the image
        if self.current_image_file:
            self._process_image()

    def _load_random_sample_image(self):
        """Load a random sample image on startup"""
        samples_dir = Path(__file__).parent.parent / "samples"
        if not samples_dir.exists():
            return

        # Find all image files in samples and subdirectories
        image_extensions = {'.png', '.jpg', '.jpeg', '.bmp', '.tiff'}
        image_files = []
        for ext in image_extensions:
            image_files.extend(samples_dir.rglob(f"*{ext}"))
            image_files.extend(samples_dir.rglob(f"*{ext.upper()}"))

        if not image_files:
            return

        # Select a random image
        random_image = random.choice(image_files)
        self.current_image_file = str(random_image)

        # Update the original image preview (this triggers processing via crop_changed signal)
        self._update_original_image_preview(self.current_image_file)

        self.status_label.setText(f"Loaded sample: {random_image.name}")

    def _load_process(self):
        """Load a process from a JSON file"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Load Process",
            str(Path.home()),
            "JSON Files (*.json);;All Files (*)"
        )

        if file_path:
            try:
                self.current_process = Process.load(Path(file_path))
                self.current_process_file = file_path
                self.process_editor.set_process(self.current_process)
                # Sync lithophane controls with the loaded process
                self._sync_controls_from_process()
                self.status_label.setText(f"Loaded process: {self.current_process.name}")

                # Re-process if we have an image loaded
                if self.current_image_file:
                    self._process_image()
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to load process: {e}")

    def _save_process(self):
        """Save the current process"""
        if self.current_process_file:
            self._save_process_to_file(self.current_process_file)
        else:
            self._save_process_as()

    def _save_process_as(self):
        """Save the current process to a new file"""
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Process As",
            str(Path.home() / "process.json"),
            "JSON Files (*.json);;All Files (*)"
        )

        if file_path:
            self._save_process_to_file(file_path)
            self.current_process_file = file_path

    def _save_process_to_file(self, file_path: str):
        """Save process to specified file"""
        try:
            process = self.process_editor.get_process()
            process.save(Path(file_path))
            self.status_label.setText(f"Saved process to: {file_path}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save process: {e}")

    def _load_image(self):
        """Load an image file and automatically process it"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Load Image",
            str(Path(__file__).parent.parent / "samples"),
            "Image Files (*.png *.jpg *.jpeg *.bmp *.tiff);;All Files (*)"
        )

        if file_path:
            self.current_image_file = file_path
            self.status_label.setText(f"Loaded image: {Path(file_path).name}")

            # Display original image preview
            self._update_original_image_preview(file_path)

            # Automatically process the image
            self._process_image()

    def _update_original_image_preview(self, file_path: str):
        """Update the original image preview"""
        try:
            self.crop_preview.set_image(file_path)
            # Reset crop when loading a new image
            self.crop_preview.reset_crop()
        except Exception:
            self.crop_preview.clear_image()

    def _update_processed_image_preview(self):
        """Update the processed image preview with the grayscale result"""
        try:
            pil_image = self.image_processor.get_current_image()
            if pil_image is not None:
                # Convert PIL image to QPixmap
                if pil_image.mode == 'L':
                    # Grayscale
                    data = pil_image.tobytes()
                    qimage = QImage(data, pil_image.width, pil_image.height,
                                   pil_image.width, QImage.Format_Grayscale8)
                else:
                    # Convert to RGB if needed
                    rgb_image = pil_image.convert('RGB')
                    data = rgb_image.tobytes()
                    qimage = QImage(data, rgb_image.width, rgb_image.height,
                                   rgb_image.width * 3, QImage.Format_RGB888)

                pixmap = QPixmap.fromImage(qimage)
                scaled = pixmap.scaled(
                    self.processed_image_label.size(),
                    Qt.KeepAspectRatio,
                    Qt.SmoothTransformation
                )
                self.processed_image_label.setPixmap(scaled)
        except Exception as e:
            self.processed_image_label.setText(f"Preview error: {e}")

    def _process_image(self):
        """Process the loaded image with the current process"""
        if not self.current_image_file:
            return

        process = self.process_editor.get_process()
        if len(process.operations) == 0:
            QMessageBox.warning(self, "Warning", "Process has no operations")
            return

        # If a worker is already running, wait for it to finish first
        if self.worker is not None and self.worker.isRunning():
            self.worker.wait()

        # Show loading dialog
        self.loading_dialog = LoadingDialog(self)

        # Create and start worker thread with crop coordinates
        self.worker = ProcessingWorker(
            self.image_processor,
            self.stl_generator,
            self.current_image_file,
            process,
            crop_rect=self._current_crop
        )
        self.worker.finished.connect(self._on_processing_finished)
        self.worker.error.connect(self._on_processing_error)
        self.worker.start()

        # Show the dialog (blocks until closed)
        self.loading_dialog.exec()

    def _on_processing_finished(self, height_map):
        """Handle successful processing completion"""
        # Close loading dialog
        if self.loading_dialog:
            self.loading_dialog.accept()
            self.loading_dialog = None

        # Update processed image preview
        self._update_processed_image_preview()

        self.export_stl_btn.setEnabled(True)
        self.status_label.setText("Processing complete. Ready to export STL.")

    def _on_processing_error(self, error_msg):
        """Handle processing error"""
        # Close loading dialog
        if self.loading_dialog:
            self.loading_dialog.reject()
            self.loading_dialog = None

        QMessageBox.critical(self, "Error", f"Failed to process image: {error_msg}")
        self.status_label.setText(f"Error: {error_msg}")

    def _export_stl(self):
        """Export the generated STL file"""
        # Generate default filename from image name + process name
        default_name = "model"
        if self.current_image_file:
            image_stem = Path(self.current_image_file).stem
            process_name = self.process_editor.get_process().name.replace(" ", "_")
            default_name = f"{image_stem}_{process_name}"

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export STL",
            str(Path.home() / f"{default_name}.stl"),
            "STL Files (*.stl);;All Files (*)"
        )

        if file_path:
            try:
                self.stl_generator.save(file_path)
                self.status_label.setText(f"Exported STL to: {file_path}")
                QMessageBox.information(self, "Success", f"STL file saved to:\n{file_path}")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to export STL: {e}")

    def _on_process_changed(self):
        """Handle process changes - sync controls and reprocess if image is loaded"""
        # Sync lithophane controls when process changes via editor
        self._sync_controls_from_process()
        if self.current_image_file:
            self._process_image()

    def _on_crop_changed(self, x: float, y: float, w: float, h: float):
        """Handle crop region changes from the preview widget"""
        # Store the crop coordinates
        self._current_crop = (x, y, w, h)

        # Reprocess the image with the new crop
        if self.current_image_file:
            self._process_image()

    def _reset_crop(self):
        """Reset the crop region to full image"""
        self.crop_preview.reset_crop()
        self._current_crop = (0.0, 0.0, 1.0, 1.0)
