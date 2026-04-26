"""
Main application window
"""
import json
import random
import time
from pathlib import Path
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QFileDialog, QMessageBox,
    QLabel, QGroupBox, QFrame, QDialog, QMenuBar, QMenu, QApplication,
    QComboBox, QProgressBar
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
    # percent (0..100), label text. Worker maps the STL-generator's 0..100
    # range into the 30..100 portion (image processing is the first 30%).
    progress = Signal(float, str)

    def __init__(self, image_processor, stl_generator, image_path, process, crop_rect=None):
        super().__init__()
        self.image_processor = image_processor
        self.stl_generator = stl_generator
        self.image_path = image_path
        self.process = process
        self.crop_rect = crop_rect  # (x, y, w, h) normalized 0-1

    def _stl_progress(self, sub_percent: float, label: str):
        # Map sub-stage 0..100 onto overall 30..100.
        overall = 30.0 + 0.70 * sub_percent
        self.progress.emit(overall, label)

    def run(self):
        try:
            self.progress.emit(0.0, "Loading image…")
            height_map = self.image_processor.execute_process(
                self.image_path,
                self.process,
                crop_rect=self.crop_rect
            )
            self.progress.emit(30.0, "Building mesh…")

            pixel_size_mm = self.image_processor.get_pixel_size_mm()
            pixel_size_mm_y = self.image_processor.get_pixel_size_mm_y()
            geometry = self.image_processor.get_geometry()

            if geometry == "cylindrical":
                self.stl_generator.generate_cylindrical_from_heightmap(
                    height_map,
                    pixel_size_mm=pixel_size_mm,
                    pixel_size_mm_y=pixel_size_mm_y,
                    arc_degrees=self.image_processor.get_arc_degrees(),
                    progress_cb=self._stl_progress,
                )
            else:
                self.stl_generator.generate_from_heightmap(
                    height_map,
                    pixel_size_mm=pixel_size_mm,
                    angle=self.image_processor.get_angle(),
                    pixel_size_mm_y=pixel_size_mm_y,
                    progress_cb=self._stl_progress,
                )

            self.progress.emit(100.0, "Done")
            self.finished.emit(height_map)
        except Exception as e:
            self.error.emit(str(e))


class LoadingDialog(QDialog):
    """Loading dialog with determinate progress bar, percent, and ETA."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Processing...")
        self.setModal(True)
        self.setFixedSize(360, 340)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowCloseButtonHint)

        # Track elapsed time so we can estimate ETA from observed progress.
        self._start_time = time.monotonic()
        self._last_percent = 0.0

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)

        # GIF label (smaller now to make room for the progress bar)
        self.gif_label = QLabel()
        self.gif_label.setAlignment(Qt.AlignCenter)
        gif_path = Path(__file__).parent / "assets" / "loading.gif"
        if gif_path.exists():
            self.movie = QMovie(str(gif_path))
            self.movie.setScaledSize(QSize(140, 140))
            self.gif_label.setMovie(self.movie)
            self.movie.start()
        else:
            self.gif_label.setText("Processing...")
        layout.addWidget(self.gif_label)

        # Stage label (e.g. "Building vertex grid…")
        self.status_label = QLabel("Generating your lithophane…")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setStyleSheet("font-size: 14px; color: #666;")
        layout.addWidget(self.status_label)

        # Determinate progress bar.
        self.progress_bar = QProgressBar()
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setFormat("%p%")
        layout.addWidget(self.progress_bar)

        # ETA line below the bar.
        self.eta_label = QLabel("Estimating time…")
        self.eta_label.setAlignment(Qt.AlignCenter)
        self.eta_label.setStyleSheet("font-size: 12px; color: #888;")
        layout.addWidget(self.eta_label)

    def set_status(self, text: str):
        self.status_label.setText(text)

    def set_progress(self, percent: float, label: str = ""):
        """Update progress bar, percent, and ETA. Safe to call from the main thread."""
        percent = max(0.0, min(100.0, float(percent)))
        self._last_percent = percent
        self.progress_bar.setValue(int(round(percent)))
        if label:
            self.status_label.setText(label)
        elapsed = time.monotonic() - self._start_time
        # ETA needs a few percent of progress to be meaningful — early
        # estimates (e.g. at 1%) are wildly noisy.
        if percent >= 5.0 and percent < 100.0:
            remaining = elapsed * (100.0 / percent - 1.0)
            self.eta_label.setText(f"~{_format_eta(remaining)} remaining")
        elif percent >= 100.0:
            self.eta_label.setText(f"Done in {_format_eta(elapsed)}")
        else:
            self.eta_label.setText("Estimating time…")


def _format_eta(seconds: float) -> str:
    """Render an ETA in a compact human form: '3s', '42s', '1m 12s'."""
    seconds = max(0.0, seconds)
    if seconds < 60:
        return f"{int(round(seconds))}s"
    m, s = divmod(int(round(seconds)), 60)
    if m < 60:
        return f"{m}m {s:02d}s"
    h, m = divmod(m, 60)
    return f"{h}h {m:02d}m"


class MainWindow(QMainWindow):
    """Main application window"""

    def __init__(self):
        super().__init__()
        # Single source of truth for the process lives in self.process_editor.
        # We only track the file path here so save-without-as works.
        self.current_process_file = None
        self.current_image_file = None
        self.image_processor = ImageProcessor()
        self.stl_generator = STLGenerator()
        self.worker = None
        self.loading_dialog = None
        self._current_crop = (0.0, 0.0, 1.0, 1.0)  # Normalized crop coords (x, y, w, h)
        # Guards prevent cascading signals from spawning duplicate workers
        # during a programmatic load (preset switch or new image).
        self._loading_image = False

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

        self.setAcceptDrops(True)

        self._setup_menu_bar()
        self._setup_ui()

    def dragEnterEvent(self, event):
        """Accept drags that contain at least one supported image file."""
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                if url.isLocalFile():
                    suffix = Path(url.toLocalFile()).suffix.lower()
                    if suffix in self.SUPPORTED_IMAGE_SUFFIXES:
                        event.acceptProposedAction()
                        return
        event.ignore()

    def dropEvent(self, event):
        """Load the first dropped image file."""
        for url in event.mimeData().urls():
            if not url.isLocalFile():
                continue
            path = url.toLocalFile()
            if Path(path).suffix.lower() in self.SUPPORTED_IMAGE_SUFFIXES:
                self._load_image_from_path(path)
                event.acceptProposedAction()
                return
        event.ignore()

    RECENT_IMAGES_MAX = 8
    RECENT_FILE_PATH = Path(__file__).parent.parent / "processes" / ".recent.json"
    LAST_EXPORT_DIR_PATH = Path(__file__).parent.parent / "processes" / ".last_export_dir"

    def _setup_menu_bar(self):
        """Setup the menu bar"""
        menu_bar = self.menuBar()

        # File menu
        file_menu = menu_bar.addMenu("File")

        open_image_action = QAction("Open Image…", self)
        open_image_action.setShortcut(QKeySequence.Open)
        open_image_action.triggered.connect(self._load_image)
        file_menu.addAction(open_image_action)

        open_process_action = QAction("Open Process…", self)
        open_process_action.triggered.connect(self._load_process)
        file_menu.addAction(open_process_action)

        self.recent_menu = file_menu.addMenu("Recent Images")
        self._refresh_recent_menu()

        # View menu
        view_menu = menu_bar.addMenu("View")

        # Fullscreen action
        self.fullscreen_action = QAction("Fullscreen", self)
        self.fullscreen_action.setShortcut(QKeySequence("F11"))
        self.fullscreen_action.setCheckable(True)
        self.fullscreen_action.triggered.connect(self._toggle_fullscreen)
        view_menu.addAction(self.fullscreen_action)

    def _load_recent_list(self) -> list:
        try:
            if self.RECENT_FILE_PATH.exists():
                data = json.loads(self.RECENT_FILE_PATH.read_text())
                if isinstance(data, list):
                    return [p for p in data if isinstance(p, str)]
        except Exception:
            pass
        return []

    def _save_recent_list(self, paths: list):
        try:
            self.RECENT_FILE_PATH.write_text(json.dumps(paths, indent=2))
        except Exception:
            pass  # non-critical

    def _load_last_export_dir(self) -> Path:
        """Return the last directory the user exported an STL to, or HOME."""
        try:
            if self.LAST_EXPORT_DIR_PATH.exists():
                text = self.LAST_EXPORT_DIR_PATH.read_text().strip()
                if text:
                    p = Path(text)
                    if p.is_dir():
                        return p
        except Exception:
            pass
        return Path.home()

    def _save_last_export_dir(self, directory: Path):
        try:
            self.LAST_EXPORT_DIR_PATH.write_text(str(directory))
        except Exception:
            pass  # non-critical

    def _add_to_recent(self, file_path: str):
        recent = [p for p in self._load_recent_list() if p != file_path]
        recent.insert(0, file_path)
        recent = recent[: self.RECENT_IMAGES_MAX]
        self._save_recent_list(recent)
        self._refresh_recent_menu()

    def _refresh_recent_menu(self):
        if not hasattr(self, "recent_menu"):
            return
        self.recent_menu.clear()
        recent = self._load_recent_list()
        if not recent:
            empty = QAction("(none)", self)
            empty.setEnabled(False)
            self.recent_menu.addAction(empty)
            return
        for path in recent:
            display = Path(path).name
            action = QAction(display, self)
            action.setToolTip(path)
            action.triggered.connect(lambda _checked=False, p=path: self._load_image_from_path(p))
            self.recent_menu.addAction(action)

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

        # Preset picker — populated from processes/presets/*.json on startup.
        button_layout.addSpacing(15)
        button_layout.addWidget(QLabel("Preset:"))
        self.preset_combo = QComboBox()
        self.preset_combo.setMinimumWidth(180)
        self._preset_paths = []  # parallel to combo entries; empty for "(Custom)"
        self._loading_preset = False
        self._populate_presets()
        self.preset_combo.currentIndexChanged.connect(self._on_preset_selected)
        button_layout.addWidget(self.preset_combo)

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

    PRESETS_DIR = Path(__file__).parent.parent / "processes" / "presets"

    def _populate_presets(self):
        """Scan presets dir on startup and fill the combo."""
        self.preset_combo.blockSignals(True)
        self.preset_combo.clear()
        self._preset_paths = []
        # Always include a (Custom) sentinel as index 0.
        self.preset_combo.addItem("(Custom)")
        self._preset_paths.append(None)
        if self.PRESETS_DIR.exists():
            preset_files = sorted(self.PRESETS_DIR.glob("*.json"))
            for path in preset_files:
                try:
                    proc = Process.load(path)
                    label = proc.name or path.stem
                except Exception:
                    label = path.stem
                self.preset_combo.addItem(label)
                self._preset_paths.append(path)
        self.preset_combo.blockSignals(False)

    def _on_preset_selected(self, index: int):
        """Load the selected preset, or ignore the (Custom) sentinel."""
        if index <= 0:
            return
        path = self._preset_paths[index]
        if path is None:
            return
        try:
            process = Process.load(path)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load preset: {e}")
            return
        # _loading_preset suppresses the auto-flip-to-(Custom) below while
        # we apply the preset to the controls.
        self._loading_preset = True
        try:
            self.current_process_file = str(path)
            self.process_editor.set_process(process)
            self._sync_controls_from_process()
            self.status_label.setText(f"Loaded preset: {process.name}")
            if self.current_image_file:
                self._process_image()
        finally:
            self._loading_preset = False

    def _mark_custom_preset(self):
        """Flip the combo to (Custom) when user edits parameters by hand."""
        if self._loading_preset:
            return
        if self.preset_combo.currentIndex() != 0:
            self.preset_combo.blockSignals(True)
            self.preset_combo.setCurrentIndex(0)
            self.preset_combo.blockSignals(False)

    def _load_default_process(self):
        """Load the default process if it exists"""
        default_path = Path(__file__).parent.parent / "processes" / "default.json"
        if default_path.exists():
            try:
                process = Process.load(default_path)
                self.process_editor.set_process(process)
                # Sync lithophane controls with the process
                self._sync_controls_from_process()
                self.status_label.setText(f"Loaded default process: {process.name}")
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
        self._mark_custom_preset()
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
        """Load a random sample image on startup, skipping any unreadable files."""
        samples_dir = Path(__file__).parent.parent / "samples"
        if not samples_dir.exists():
            return

        image_extensions = {'.png', '.jpg', '.jpeg', '.bmp', '.tiff'}
        image_files = []
        for ext in image_extensions:
            image_files.extend(samples_dir.rglob(f"*{ext}"))
            image_files.extend(samples_dir.rglob(f"*{ext.upper()}"))

        if not image_files:
            return

        # A handful of bundled samples are corrupt (HTML pages saved with .jpg
        # extension). Shuffle the full list and verify each candidate's image
        # header until one opens cleanly so we don't surface that as a startup
        # error dialog.
        random.shuffle(image_files)
        chosen = None
        for candidate in image_files:
            try:
                with Image.open(candidate) as probe:
                    probe.verify()
                chosen = candidate
                break
            except Exception:
                continue
        if chosen is None:
            return

        self.current_image_file = str(chosen)
        self._update_original_image_preview(self.current_image_file)
        self.status_label.setText(f"Loaded sample: {chosen.name}")

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
                process = Process.load(Path(file_path))
                self.current_process_file = file_path
                self.process_editor.set_process(process)
                # Sync lithophane controls with the loaded process
                self._sync_controls_from_process()
                self.status_label.setText(f"Loaded process: {process.name}")

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

    SUPPORTED_IMAGE_SUFFIXES = {'.png', '.jpg', '.jpeg', '.bmp', '.tiff'}

    def _load_image(self):
        """Load an image file and automatically process it"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Load Image",
            str(Path(__file__).parent.parent / "samples"),
            "Image Files (*.png *.jpg *.jpeg *.bmp *.tiff);;All Files (*)"
        )
        if file_path:
            self._load_image_from_path(file_path)

    def _load_image_from_path(self, file_path: str):
        """Shared loader used by file dialog, drag-drop, and recent files."""
        # _update_original_image_preview calls crop_preview.reset_crop(), which
        # emits crop_changed → _on_crop_changed → _process_image. The guard
        # below suppresses that intermediate worker so the single explicit
        # _process_image() call below is the only trigger; otherwise we get
        # two workers and the dialog stalls at 100% (same failure mode as
        # the preset double-spawn we already fixed).
        self._loading_image = True
        try:
            self.current_image_file = file_path
            self.status_label.setText(f"Loaded image: {Path(file_path).name}")
            self._update_original_image_preview(file_path)
            self._add_to_recent(file_path)
        finally:
            self._loading_image = False
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

        # Show loading dialog non-modally so a fast worker can't beat the
        # event loop and try to close a dialog whose exec() hasn't started.
        self.loading_dialog = LoadingDialog(self)
        self.loading_dialog.show()

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
        self.worker.progress.connect(self.loading_dialog.set_progress)
        self.worker.start()

    def _on_processing_finished(self, height_map):
        """Handle successful processing completion"""
        # Close loading dialog
        if self.loading_dialog:
            self.loading_dialog.close()
            self.loading_dialog = None

        # Update processed image preview
        self._update_processed_image_preview()

        self.export_stl_btn.setEnabled(True)
        self.status_label.setText("Processing complete. Ready to export STL.")

    def _on_processing_error(self, error_msg):
        """Handle processing error"""
        # Close loading dialog
        if self.loading_dialog:
            self.loading_dialog.close()
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

        # Default to the directory of the last successful export so users
        # don't have to renavigate every time. Falls back to HOME on a fresh
        # install or if the previously saved directory has been removed.
        start_dir = self._load_last_export_dir()
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export STL",
            str(start_dir / f"{default_name}.stl"),
            "STL Files (*.stl);;All Files (*)"
        )

        if file_path:
            try:
                self.stl_generator.save(file_path)
                self._save_last_export_dir(Path(file_path).parent)
                self.status_label.setText(f"Exported STL to: {file_path}")
                QMessageBox.information(self, "Success", f"STL file saved to:\n{file_path}")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to export STL: {e}")

    def _on_process_changed(self):
        """Handle process changes - sync controls and reprocess if image is loaded"""
        # During preset load, ProcessEditor.set_process fires textChanged on
        # name_edit, which cascades into process_changed. _on_preset_selected
        # owns the sync + reprocess in that path, so we must not also kick off
        # a worker here — doing so creates a second dialog and orphans the
        # signal connections, leaving the dialog stuck at 100%.
        if self._loading_preset:
            return
        self._mark_custom_preset()
        # Sync lithophane controls when process changes via editor
        self._sync_controls_from_process()
        if self.current_image_file:
            self._process_image()

    def _on_crop_changed(self, x: float, y: float, w: float, h: float):
        """Handle crop region changes from the preview widget"""
        # Store the crop coordinates so the worker reads the latest value.
        self._current_crop = (x, y, w, h)
        # During programmatic image load, _load_image_from_path owns the
        # single _process_image call — skip the cascade-driven one.
        if self._loading_image:
            return
        if self.current_image_file:
            self._process_image()

    def _reset_crop(self):
        """Reset the crop region to full image"""
        self.crop_preview.reset_crop()
        self._current_crop = (0.0, 0.0, 1.0, 1.0)
