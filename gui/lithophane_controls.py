"""
Direct lithophane parameter controls with sliders and text inputs
"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QSlider, QDoubleSpinBox, QSpinBox, QCheckBox,
    QRadioButton, QButtonGroup, QGroupBox, QScrollArea,
    QFrame, QComboBox
)
from PySide6.QtCore import Signal, Qt
from PySide6.QtGui import QWheelEvent


class NoScrollDoubleSpinBox(QDoubleSpinBox):
    """DoubleSpinBox that ignores mouse wheel events"""
    def wheelEvent(self, event: QWheelEvent):
        event.ignore()


class NoScrollSlider(QSlider):
    """Slider that ignores mouse wheel events"""
    def wheelEvent(self, event: QWheelEvent):
        event.ignore()


class SliderWithInput(QWidget):
    """A slider with a synchronized text input.

    Only emits value_changed when:
    - Slider is released (not while dragging)
    - Enter is pressed in the spinbox
    """
    value_changed = Signal(float)

    def __init__(self, label: str, min_val: float, max_val: float,
                 default: float, decimals: int = 2, parent=None):
        super().__init__(parent)
        self.decimals = decimals
        self.multiplier = 10 ** decimals

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 5)

        # Label
        self.label = QLabel(label)
        layout.addWidget(self.label)

        # Slider and spinbox row
        row = QHBoxLayout()

        # Slider (no scroll)
        self.slider = NoScrollSlider(Qt.Horizontal)
        self.slider.setMinimum(int(min_val * self.multiplier))
        self.slider.setMaximum(int(max_val * self.multiplier))
        self.slider.setValue(int(default * self.multiplier))
        # Sync spinbox display while dragging (but don't emit signal)
        self.slider.valueChanged.connect(self._on_slider_moved)
        # Only emit signal when slider is released
        self.slider.sliderReleased.connect(self._on_slider_released)
        row.addWidget(self.slider, stretch=3)

        # Spinbox (no scroll)
        self.spinbox = NoScrollDoubleSpinBox()
        self.spinbox.setMinimum(min_val)
        self.spinbox.setMaximum(max_val)
        self.spinbox.setDecimals(decimals)
        self.spinbox.setValue(default)
        self.spinbox.setKeyboardTracking(False)  # Don't emit while typing
        # Only emit when Enter is pressed (not on focus loss, which causes loops with dialogs)
        self.spinbox.lineEdit().returnPressed.connect(self._on_spinbox_enter_pressed)
        row.addWidget(self.spinbox, stretch=1)

        layout.addLayout(row)

        self._updating = False

    def _on_slider_moved(self, value):
        """Sync spinbox display while slider is being dragged (no signal emission)"""
        if self._updating:
            return
        self._updating = True
        float_val = value / self.multiplier
        self.spinbox.setValue(float_val)
        self._updating = False

    def _on_slider_released(self):
        """Emit signal only when slider is released"""
        if self._updating:
            return
        self.value_changed.emit(self.spinbox.value())

    def _on_spinbox_enter_pressed(self):
        """Emit signal when Enter is pressed in spinbox"""
        if self._updating:
            return
        self._updating = True
        self.slider.setValue(int(self.spinbox.value() * self.multiplier))
        self._updating = False
        self.value_changed.emit(self.spinbox.value())

    def value(self) -> float:
        return self.spinbox.value()

    def setValue(self, val: float):
        self._updating = True
        self.spinbox.setValue(val)
        self.slider.setValue(int(val * self.multiplier))
        self._updating = False


class LithophaneControls(QWidget):
    """Direct controls for lithophane parameters"""
    parameters_changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._updating = False
        self._setup_ui()

    def _setup_ui(self):
        # Use scroll area for many controls
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setSpacing(10)

        # Dimensions group
        dims_group = QGroupBox("Dimensions")
        dims_layout = QVBoxLayout(dims_group)

        self.width_control = SliderWithInput("Width (mm)", 10, 300, 100, decimals=1)
        self.width_control.value_changed.connect(self._emit_changed)
        dims_layout.addWidget(self.width_control)

        self.height_control = SliderWithInput("Height (mm)", 10, 300, 100, decimals=1)
        self.height_control.value_changed.connect(self._emit_changed)
        dims_layout.addWidget(self.height_control)

        layout.addWidget(dims_group)

        # Thickness group
        thick_group = QGroupBox("Thickness")
        thick_layout = QVBoxLayout(thick_group)

        self.min_thickness_control = SliderWithInput("Min Thickness (mm) - bright areas", 0.3, 3.0, 0.8, decimals=2)
        self.min_thickness_control.value_changed.connect(self._emit_changed)
        thick_layout.addWidget(self.min_thickness_control)

        self.max_thickness_control = SliderWithInput("Max Thickness (mm) - dark areas", 1.0, 10.0, 5.0, decimals=2)
        self.max_thickness_control.value_changed.connect(self._emit_changed)
        thick_layout.addWidget(self.max_thickness_control)

        layout.addWidget(thick_group)

        # Quality group
        quality_group = QGroupBox("Quality & Effects")
        quality_layout = QVBoxLayout(quality_group)

        self.resolution_control = SliderWithInput("Resolution (pixels/mm)", 0.5, 5.0, 2.0, decimals=1)
        self.resolution_control.value_changed.connect(self._emit_changed)
        quality_layout.addWidget(self.resolution_control)

        self.blur_control = SliderWithInput("Blur", 0, 10, 0, decimals=1)
        self.blur_control.value_changed.connect(self._emit_changed)
        quality_layout.addWidget(self.blur_control)

        layout.addWidget(quality_group)

        # Build angle group
        angle_group = QGroupBox("Build Orientation")
        angle_layout = QVBoxLayout(angle_group)

        self.angle_control = SliderWithInput("Build Angle (degrees)", 0, 90, 75, decimals=0)
        self.angle_control.value_changed.connect(self._emit_changed)
        angle_layout.addWidget(self.angle_control)

        layout.addWidget(angle_group)

        # Crop mode group
        crop_group = QGroupBox("Crop Mode")
        crop_layout = QVBoxLayout(crop_group)

        self.crop_button_group = QButtonGroup(self)

        self.crop_to_size_radio = QRadioButton("Crop to size (maintain aspect ratio, crop excess)")
        self.crop_to_size_radio.setChecked(True)
        self.crop_button_group.addButton(self.crop_to_size_radio, 0)
        crop_layout.addWidget(self.crop_to_size_radio)

        self.keep_full_radio = QRadioButton("Keep full image (pad empty space)")
        self.crop_button_group.addButton(self.keep_full_radio, 1)
        crop_layout.addWidget(self.keep_full_radio)

        self.crop_button_group.buttonClicked.connect(self._emit_changed)

        # Background tint (only for keep_full_image mode)
        self.background_tint_control = SliderWithInput("Background Tint (0%=thin, 100%=thick)", 0, 100, 0, decimals=0)
        self.background_tint_control.value_changed.connect(self._emit_changed)
        crop_layout.addWidget(self.background_tint_control)

        layout.addWidget(crop_group)

        # Border group
        border_group = QGroupBox("Border")
        border_layout = QVBoxLayout(border_group)

        self.border_width_control = SliderWithInput("Border Width (mm)", 0, 20, 0, decimals=1)
        self.border_width_control.value_changed.connect(self._emit_changed)
        border_layout.addWidget(self.border_width_control)

        self.border_intensity_control = SliderWithInput("Border Intensity (0%=thin, 100%=thick)", 0, 100, 50, decimals=0)
        self.border_intensity_control.value_changed.connect(self._emit_changed)
        border_layout.addWidget(self.border_intensity_control)

        # Border texture dropdown
        texture_row = QHBoxLayout()
        texture_row.addWidget(QLabel("Border Texture:"))
        self.border_texture_combo = QComboBox()
        self.border_texture_combo.addItems([
            "Solid",
            "Gradient (fade inward)",
            "Ribbed (vertical lines)",
            "Dotted (perforated)",
            "Wave (sine pattern)",
            "Crosshatch"
        ])
        self.border_texture_combo.currentIndexChanged.connect(self._emit_changed)
        texture_row.addWidget(self.border_texture_combo)
        border_layout.addLayout(texture_row)

        layout.addWidget(border_group)

        # Options group
        options_group = QGroupBox("Options")
        options_layout = QVBoxLayout(options_group)

        self.invert_checkbox = QCheckBox("Invert Colors")
        self.invert_checkbox.stateChanged.connect(self._emit_changed)
        options_layout.addWidget(self.invert_checkbox)

        layout.addWidget(options_group)

        # Add stretch at bottom
        layout.addStretch()

        scroll.setWidget(container)

        # Main layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(scroll)

    def _emit_changed(self):
        if not self._updating:
            self.parameters_changed.emit()

    def get_parameters(self) -> dict:
        """Get current parameters as a dictionary"""
        crop_mode = "crop_to_size" if self.crop_to_size_radio.isChecked() else "keep_full_image"
        # Map combo box index to texture name
        texture_names = ["solid", "gradient", "ribbed", "dotted", "wave", "crosshatch"]
        border_texture = texture_names[self.border_texture_combo.currentIndex()]
        return {
            "width_mm": self.width_control.value(),
            "height_mm": self.height_control.value(),
            "min_thickness_mm": self.min_thickness_control.value(),
            "max_thickness_mm": self.max_thickness_control.value(),
            "pixels_per_mm": self.resolution_control.value(),
            "blur": self.blur_control.value(),
            "angle": self.angle_control.value(),
            "crop_mode": crop_mode,
            "background_tint": self.background_tint_control.value(),
            "border_width_mm": self.border_width_control.value(),
            "border_intensity": self.border_intensity_control.value(),
            "border_texture": border_texture,
            "invert": self.invert_checkbox.isChecked()
        }

    def set_parameters(self, params: dict):
        """Set parameters from a dictionary"""
        self._updating = True

        if "width_mm" in params:
            self.width_control.setValue(params["width_mm"])
        if "height_mm" in params:
            self.height_control.setValue(params["height_mm"])
        if "min_thickness_mm" in params:
            self.min_thickness_control.setValue(params["min_thickness_mm"])
        if "max_thickness_mm" in params:
            self.max_thickness_control.setValue(params["max_thickness_mm"])
        if "pixels_per_mm" in params:
            self.resolution_control.setValue(params["pixels_per_mm"])
        if "blur" in params:
            self.blur_control.setValue(params["blur"])
        if "angle" in params:
            self.angle_control.setValue(params["angle"])
        if "crop_mode" in params:
            if params["crop_mode"] == "crop_to_size":
                self.crop_to_size_radio.setChecked(True)
            else:
                self.keep_full_radio.setChecked(True)
        if "background_tint" in params:
            self.background_tint_control.setValue(params["background_tint"])
        if "border_width_mm" in params:
            self.border_width_control.setValue(params["border_width_mm"])
        if "border_intensity" in params:
            self.border_intensity_control.setValue(params["border_intensity"])
        if "border_texture" in params:
            texture_names = ["solid", "gradient", "ribbed", "dotted", "wave", "crosshatch"]
            if params["border_texture"] in texture_names:
                self.border_texture_combo.setCurrentIndex(texture_names.index(params["border_texture"]))
        if "invert" in params:
            self.invert_checkbox.setChecked(params["invert"])

        self._updating = False
