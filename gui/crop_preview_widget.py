"""
Interactive crop preview widget with draggable crop box and corner handles
"""
from PySide6.QtWidgets import QWidget, QSizePolicy
from PySide6.QtCore import Qt, Signal, QRectF, QPointF
from PySide6.QtGui import QPainter, QPixmap, QPen, QBrush, QColor, QImage


class CropPreviewWidget(QWidget):
    """
    Widget displaying an image with an interactive crop box.

    Features:
    - Red rectangle crop box that can be dragged
    - White circle handles at corners for resizing
    - Emits crop_changed signal with normalized coordinates (0-1)
    """

    # Signal emitted when crop region changes: (x, y, width, height) normalized 0-1
    crop_changed = Signal(float, float, float, float)

    HANDLE_RADIUS = 8
    CROP_BOX_COLOR = QColor(255, 0, 0, 200)
    CROP_BOX_BORDER = QColor(255, 0, 0, 255)
    HANDLE_FILL = QColor(255, 255, 255, 255)
    HANDLE_BORDER = QColor(100, 100, 100, 255)
    OVERLAY_COLOR = QColor(0, 0, 0, 100)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(300, 250)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setMouseTracking(True)

        self._pixmap = None
        self._scaled_pixmap = None
        self._image_rect = QRectF()  # Where the image is drawn in widget coords

        # Crop box in normalized coordinates (0-1 relative to image)
        self._crop_x = 0.0
        self._crop_y = 0.0
        self._crop_w = 1.0
        self._crop_h = 1.0

        # Interaction state
        self._dragging = False
        self._resizing_handle = None  # 'tl', 'tr', 'bl', 'br' or None
        self._drag_start = None
        self._crop_start = None

        self.setStyleSheet("background-color: #333;")

    def set_image(self, file_path: str):
        """Load and display an image from file path"""
        self._pixmap = QPixmap(file_path)
        self._update_scaled_pixmap()
        self.update()

    def set_pixmap(self, pixmap: QPixmap):
        """Set the pixmap directly"""
        self._pixmap = pixmap
        self._update_scaled_pixmap()
        self.update()

    def clear_image(self):
        """Clear the current image"""
        self._pixmap = None
        self._scaled_pixmap = None
        self.update()

    def get_crop_rect(self) -> tuple:
        """
        Get the current crop rectangle in normalized coordinates.
        Returns: (x, y, width, height) where all values are 0-1
        """
        return (self._crop_x, self._crop_y, self._crop_w, self._crop_h)

    def set_crop_rect(self, x: float, y: float, w: float, h: float):
        """Set the crop rectangle in normalized coordinates (0-1)"""
        self._crop_x = max(0.0, min(1.0, x))
        self._crop_y = max(0.0, min(1.0, y))
        self._crop_w = max(0.05, min(1.0 - self._crop_x, w))
        self._crop_h = max(0.05, min(1.0 - self._crop_y, h))
        self.update()

    def reset_crop(self):
        """Reset crop to full image"""
        self._crop_x = 0.0
        self._crop_y = 0.0
        self._crop_w = 1.0
        self._crop_h = 1.0
        self.update()
        self.crop_changed.emit(self._crop_x, self._crop_y, self._crop_w, self._crop_h)

    def _update_scaled_pixmap(self):
        """Update the scaled pixmap based on widget size"""
        if self._pixmap is None or self._pixmap.isNull():
            self._scaled_pixmap = None
            self._image_rect = QRectF()
            return

        # Scale pixmap to fit widget while maintaining aspect ratio
        widget_rect = self.rect()
        pixmap_size = self._pixmap.size()

        # Calculate scaled size
        scaled_size = pixmap_size.scaled(
            widget_rect.size(),
            Qt.KeepAspectRatio
        )

        self._scaled_pixmap = self._pixmap.scaled(
            scaled_size,
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation
        )

        # Calculate image rectangle (centered in widget)
        x = (widget_rect.width() - self._scaled_pixmap.width()) / 2
        y = (widget_rect.height() - self._scaled_pixmap.height()) / 2
        self._image_rect = QRectF(x, y, self._scaled_pixmap.width(), self._scaled_pixmap.height())

    def _get_crop_box_widget_rect(self) -> QRectF:
        """Get the crop box rectangle in widget coordinates"""
        if self._image_rect.isEmpty():
            return QRectF()

        x = self._image_rect.x() + self._crop_x * self._image_rect.width()
        y = self._image_rect.y() + self._crop_y * self._image_rect.height()
        w = self._crop_w * self._image_rect.width()
        h = self._crop_h * self._image_rect.height()

        return QRectF(x, y, w, h)

    def _get_handle_rects(self) -> dict:
        """Get rectangles for each corner handle"""
        crop_rect = self._get_crop_box_widget_rect()
        if crop_rect.isEmpty():
            return {}

        r = self.HANDLE_RADIUS
        return {
            'tl': QRectF(crop_rect.left() - r, crop_rect.top() - r, r * 2, r * 2),
            'tr': QRectF(crop_rect.right() - r, crop_rect.top() - r, r * 2, r * 2),
            'bl': QRectF(crop_rect.left() - r, crop_rect.bottom() - r, r * 2, r * 2),
            'br': QRectF(crop_rect.right() - r, crop_rect.bottom() - r, r * 2, r * 2),
        }

    def _point_in_handle(self, pos: QPointF) -> str:
        """Check if point is in any handle, return handle name or None"""
        handles = self._get_handle_rects()
        for name, rect in handles.items():
            if rect.contains(pos):
                return name
        return None

    def _widget_to_normalized(self, pos: QPointF) -> tuple:
        """Convert widget coordinates to normalized image coordinates"""
        if self._image_rect.isEmpty():
            return (0, 0)

        x = (pos.x() - self._image_rect.x()) / self._image_rect.width()
        y = (pos.y() - self._image_rect.y()) / self._image_rect.height()
        return (x, y)

    def resizeEvent(self, event):
        """Handle widget resize"""
        super().resizeEvent(event)
        self._update_scaled_pixmap()

    def paintEvent(self, event):
        """Paint the widget"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # Fill background
        painter.fillRect(self.rect(), QColor(51, 51, 51))

        if self._scaled_pixmap is None:
            # Draw placeholder text
            painter.setPen(QColor(153, 153, 153))
            painter.drawText(self.rect(), Qt.AlignCenter, "No image loaded")
            return

        # Draw the image
        painter.drawPixmap(self._image_rect.topLeft(), self._scaled_pixmap)

        # Get crop box in widget coords
        crop_rect = self._get_crop_box_widget_rect()

        # Draw semi-transparent overlay outside crop area
        overlay_color = self.OVERLAY_COLOR

        # Top region
        if crop_rect.top() > self._image_rect.top():
            painter.fillRect(QRectF(
                self._image_rect.left(), self._image_rect.top(),
                self._image_rect.width(), crop_rect.top() - self._image_rect.top()
            ), overlay_color)

        # Bottom region
        if crop_rect.bottom() < self._image_rect.bottom():
            painter.fillRect(QRectF(
                self._image_rect.left(), crop_rect.bottom(),
                self._image_rect.width(), self._image_rect.bottom() - crop_rect.bottom()
            ), overlay_color)

        # Left region (between top and bottom overlays)
        if crop_rect.left() > self._image_rect.left():
            painter.fillRect(QRectF(
                self._image_rect.left(), crop_rect.top(),
                crop_rect.left() - self._image_rect.left(), crop_rect.height()
            ), overlay_color)

        # Right region (between top and bottom overlays)
        if crop_rect.right() < self._image_rect.right():
            painter.fillRect(QRectF(
                crop_rect.right(), crop_rect.top(),
                self._image_rect.right() - crop_rect.right(), crop_rect.height()
            ), overlay_color)

        # Draw crop box border
        pen = QPen(self.CROP_BOX_BORDER)
        pen.setWidth(2)
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)
        painter.drawRect(crop_rect)

        # Draw corner handles
        handles = self._get_handle_rects()
        for name, rect in handles.items():
            # Handle fill
            painter.setPen(QPen(self.HANDLE_BORDER, 1))
            painter.setBrush(QBrush(self.HANDLE_FILL))
            painter.drawEllipse(rect)

    def mousePressEvent(self, event):
        """Handle mouse press"""
        if event.button() != Qt.LeftButton:
            return

        pos = event.position()

        # Check if clicking on a handle
        handle = self._point_in_handle(pos)
        if handle:
            self._resizing_handle = handle
            self._drag_start = pos
            self._crop_start = (self._crop_x, self._crop_y, self._crop_w, self._crop_h)
            return

        # Check if clicking inside crop box
        crop_rect = self._get_crop_box_widget_rect()
        if crop_rect.contains(pos):
            self._dragging = True
            self._drag_start = pos
            self._crop_start = (self._crop_x, self._crop_y, self._crop_w, self._crop_h)

    def mouseMoveEvent(self, event):
        """Handle mouse move"""
        pos = event.position()

        # Update cursor based on position
        handle = self._point_in_handle(pos)
        crop_rect = self._get_crop_box_widget_rect()

        if handle in ('tl', 'br'):
            self.setCursor(Qt.SizeFDiagCursor)
        elif handle in ('tr', 'bl'):
            self.setCursor(Qt.SizeBDiagCursor)
        elif crop_rect.contains(pos):
            self.setCursor(Qt.SizeAllCursor)
        else:
            self.setCursor(Qt.ArrowCursor)

        if not self._drag_start:
            return

        if self._image_rect.isEmpty():
            return

        # Calculate delta in normalized coordinates
        dx = (pos.x() - self._drag_start.x()) / self._image_rect.width()
        dy = (pos.y() - self._drag_start.y()) / self._image_rect.height()

        start_x, start_y, start_w, start_h = self._crop_start

        if self._resizing_handle:
            # Resizing a corner
            handle = self._resizing_handle

            if handle == 'tl':
                # Top-left: adjust x, y, and size
                new_x = max(0, min(start_x + start_w - 0.05, start_x + dx))
                new_y = max(0, min(start_y + start_h - 0.05, start_y + dy))
                new_w = start_w - (new_x - start_x)
                new_h = start_h - (new_y - start_y)
                self._crop_x = new_x
                self._crop_y = new_y
                self._crop_w = new_w
                self._crop_h = new_h

            elif handle == 'tr':
                # Top-right: adjust y, width, and height
                new_y = max(0, min(start_y + start_h - 0.05, start_y + dy))
                new_w = max(0.05, min(1.0 - start_x, start_w + dx))
                new_h = start_h - (new_y - start_y)
                self._crop_y = new_y
                self._crop_w = new_w
                self._crop_h = new_h

            elif handle == 'bl':
                # Bottom-left: adjust x, width, and height
                new_x = max(0, min(start_x + start_w - 0.05, start_x + dx))
                new_w = start_w - (new_x - start_x)
                new_h = max(0.05, min(1.0 - start_y, start_h + dy))
                self._crop_x = new_x
                self._crop_w = new_w
                self._crop_h = new_h

            elif handle == 'br':
                # Bottom-right: adjust width and height
                new_w = max(0.05, min(1.0 - start_x, start_w + dx))
                new_h = max(0.05, min(1.0 - start_y, start_h + dy))
                self._crop_w = new_w
                self._crop_h = new_h

        elif self._dragging:
            # Moving the entire box
            new_x = start_x + dx
            new_y = start_y + dy

            # Clamp to image bounds
            new_x = max(0, min(1.0 - start_w, new_x))
            new_y = max(0, min(1.0 - start_h, new_y))

            self._crop_x = new_x
            self._crop_y = new_y

        self.update()

    def mouseReleaseEvent(self, event):
        """Handle mouse release"""
        if event.button() != Qt.LeftButton:
            return

        if self._dragging or self._resizing_handle:
            # Emit crop changed signal
            self.crop_changed.emit(self._crop_x, self._crop_y, self._crop_w, self._crop_h)

        self._dragging = False
        self._resizing_handle = None
        self._drag_start = None
        self._crop_start = None
