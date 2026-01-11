"""
Process editor widget for creating and modifying processing operations
"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QListWidget, QListWidgetItem, QDialog, QFormLayout,
    QLineEdit, QComboBox, QDoubleSpinBox, QSpinBox,
    QCheckBox, QDialogButtonBox, QLabel
)
from PySide6.QtCore import Signal
from core.process import Process, Operation


class OperationDialog(QDialog):
    """Dialog for creating/editing an operation"""

    OPERATION_TYPES = {
        "set_lithophane_parameters": {
            "name": "Set Lithophane Parameters",
            "parameters": {
                "width_mm": {"type": "float", "default": 100.0, "label": "Width (mm)"},
                "height_mm": {"type": "float", "default": 100.0, "label": "Height (mm)"},
                "min_thickness_mm": {"type": "float", "default": 0.8, "label": "Min Thickness (mm) - saturated pixels"},
                "max_thickness_mm": {"type": "float", "default": 5.0, "label": "Max Thickness (mm) - black pixels"},
                "pixels_per_mm": {"type": "float", "default": 2.0, "label": "Resolution (pixels/mm)"},
                "blur_mm": {"type": "float", "default": 0.0, "label": "Blur (mm)"},
                "angle": {"type": "float", "default": 75.0, "label": "Build Angle (degrees)"},
                "invert": {"type": "bool", "default": False, "label": "Invert Colors"},
                "crop_mode": {"type": "combo", "default": "crop_to_size", "label": "Crop Mode",
                              "options": ["crop_to_size", "keep_full_image"]},
                "background_tint": {"type": "float", "default": 0.0, "label": "Background Tint (0-100%)"}
            }
        }
    }

    def __init__(self, operation: Operation = None, parent=None):
        super().__init__(parent)
        self.operation = operation
        self.param_widgets = {}

        self.setWindowTitle("Edit Operation" if operation else "Add Operation")
        self.setModal(True)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # Operation type selector
        type_layout = QHBoxLayout()
        type_layout.addWidget(QLabel("Operation Type:"))
        self.type_combo = QComboBox()
        for op_type, op_info in self.OPERATION_TYPES.items():
            self.type_combo.addItem(op_info["name"], op_type)
        self.type_combo.currentIndexChanged.connect(self._update_parameters)
        type_layout.addWidget(self.type_combo)
        layout.addLayout(type_layout)

        # Parameters form
        self.param_form = QFormLayout()
        layout.addLayout(self.param_form)

        # Buttons
        button_box = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

        # Load existing operation if editing
        if self.operation:
            for i in range(self.type_combo.count()):
                if self.type_combo.itemData(i) == self.operation.type:
                    self.type_combo.setCurrentIndex(i)
                    break
        else:
            self._update_parameters()

    def _update_parameters(self):
        """Update parameter fields based on selected operation type"""
        # Clear existing parameter widgets
        while self.param_form.rowCount() > 0:
            self.param_form.removeRow(0)
        self.param_widgets.clear()

        # Get current operation type
        op_type = self.type_combo.currentData()
        if not op_type:
            return

        op_info = self.OPERATION_TYPES[op_type]

        # Create widgets for each parameter
        for param_name, param_info in op_info["parameters"].items():
            label = param_info["label"]
            param_type = param_info["type"]

            # Get current value if editing
            if self.operation and param_name in self.operation.parameters:
                current_value = self.operation.parameters[param_name]
            else:
                current_value = param_info["default"]

            # Create appropriate widget based on type
            if param_type == "int":
                widget = QSpinBox()
                widget.setRange(0, 10000)
                widget.setValue(current_value)
                self.param_widgets[param_name] = widget
            elif param_type == "float":
                widget = QDoubleSpinBox()
                widget.setRange(0.0, 1000.0)
                widget.setDecimals(2)
                widget.setValue(current_value)
                self.param_widgets[param_name] = widget
            elif param_type == "bool":
                widget = QCheckBox()
                widget.setChecked(current_value)
                self.param_widgets[param_name] = widget
            elif param_type == "combo":
                widget = QComboBox()
                widget.addItems(param_info["options"])
                widget.setCurrentText(str(current_value))
                self.param_widgets[param_name] = widget
            else:
                widget = QLineEdit(str(current_value))
                self.param_widgets[param_name] = widget

            self.param_form.addRow(label + ":", widget)

    def get_operation(self) -> Operation:
        """Get the operation from the dialog"""
        op_type = self.type_combo.currentData()
        parameters = {}

        for param_name, widget in self.param_widgets.items():
            if isinstance(widget, QSpinBox):
                parameters[param_name] = widget.value()
            elif isinstance(widget, QDoubleSpinBox):
                parameters[param_name] = widget.value()
            elif isinstance(widget, QCheckBox):
                parameters[param_name] = widget.isChecked()
            elif isinstance(widget, QComboBox):
                parameters[param_name] = widget.currentText()
            elif isinstance(widget, QLineEdit):
                parameters[param_name] = widget.text()

        return Operation(op_type, parameters)


class ProcessEditor(QWidget):
    """Widget for editing a process"""

    process_changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.process = Process()
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # Process name
        name_layout = QHBoxLayout()
        name_layout.addWidget(QLabel("Process Name:"))
        self.name_edit = QLineEdit()
        self.name_edit.setText(self.process.name)
        self.name_edit.textChanged.connect(self._on_name_changed)
        name_layout.addWidget(self.name_edit)
        layout.addLayout(name_layout)

        # Operations list
        self.operations_list = QListWidget()
        layout.addWidget(self.operations_list)

        # Buttons
        button_layout = QHBoxLayout()

        self.add_btn = QPushButton("Add Operation")
        self.add_btn.clicked.connect(self._add_operation)
        button_layout.addWidget(self.add_btn)

        self.edit_btn = QPushButton("Edit")
        self.edit_btn.clicked.connect(self._edit_operation)
        button_layout.addWidget(self.edit_btn)

        self.remove_btn = QPushButton("Remove")
        self.remove_btn.clicked.connect(self._remove_operation)
        button_layout.addWidget(self.remove_btn)

        self.move_up_btn = QPushButton("Move Up")
        self.move_up_btn.clicked.connect(self._move_up)
        button_layout.addWidget(self.move_up_btn)

        self.move_down_btn = QPushButton("Move Down")
        self.move_down_btn.clicked.connect(self._move_down)
        button_layout.addWidget(self.move_down_btn)

        layout.addLayout(button_layout)

    def set_process(self, process: Process):
        """Set the process to edit"""
        self.process = process
        self.name_edit.setText(process.name)
        self._refresh_list()

    def get_process(self) -> Process:
        """Get the current process"""
        return self.process

    def _refresh_list(self):
        """Refresh the operations list"""
        self.operations_list.clear()
        for i, operation in enumerate(self.process.operations):
            op_info = OperationDialog.OPERATION_TYPES.get(operation.type, {})
            op_name = op_info.get("name", operation.type)
            item_text = f"{i+1}. {op_name}"

            # Add some parameter info
            if operation.type == "set_lithophane_parameters":
                item_text += f" ({operation.parameters.get('width_mm')}x{operation.parameters.get('height_mm')}mm, {operation.parameters.get('min_thickness_mm')}-{operation.parameters.get('max_thickness_mm')}mm)"

            self.operations_list.addItem(item_text)

    def _add_operation(self):
        """Add a new operation"""
        dialog = OperationDialog(parent=self)
        if dialog.exec():
            operation = dialog.get_operation()
            self.process.add_operation(operation)
            self._refresh_list()
            self.process_changed.emit()

    def _edit_operation(self):
        """Edit the selected operation"""
        current_row = self.operations_list.currentRow()
        if current_row >= 0:
            operation = self.process.operations[current_row]
            dialog = OperationDialog(operation, parent=self)
            if dialog.exec():
                new_operation = dialog.get_operation()
                self.process.operations[current_row] = new_operation
                self._refresh_list()
                self.process_changed.emit()

    def _remove_operation(self):
        """Remove the selected operation"""
        current_row = self.operations_list.currentRow()
        if current_row >= 0:
            self.process.remove_operation(current_row)
            self._refresh_list()
            self.process_changed.emit()

    def _move_up(self):
        """Move the selected operation up"""
        current_row = self.operations_list.currentRow()
        if current_row > 0:
            self.process.move_operation(current_row, current_row - 1)
            self._refresh_list()
            self.operations_list.setCurrentRow(current_row - 1)
            self.process_changed.emit()

    def _move_down(self):
        """Move the selected operation down"""
        current_row = self.operations_list.currentRow()
        if current_row >= 0 and current_row < len(self.process.operations) - 1:
            self.process.move_operation(current_row, current_row + 1)
            self._refresh_list()
            self.operations_list.setCurrentRow(current_row + 1)
            self.process_changed.emit()

    def _on_name_changed(self, text: str):
        """Handle process name change"""
        self.process.name = text
        self.process_changed.emit()
