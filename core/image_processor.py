"""
Image processing operations and executor
"""
import math
import numpy as np
from PIL import Image, ImageOps, ImageFilter, ImageDraw
from typing import Optional
from core.process import Process, Operation


class ImageProcessor:
    """Executes a process on an image"""

    def __init__(self):
        self.current_image: Optional[Image.Image] = None
        self.height_map: Optional[np.ndarray] = None
        self.angle: float = 75.0  # Build angle in degrees
        self.pixel_size_mm: float = 0.5  # X spacing between vertices (mm)
        self.pixel_size_mm_y: float = 0.5  # Y spacing between vertices (mm)
        self.geometry: str = "flat"  # "flat" or "cylindrical"
        self.arc_degrees: float = 360.0  # Cylindrical wrap arc

    def execute_process(self, image_path: str, process: Process, crop_rect: tuple = None) -> np.ndarray:
        """
        Execute all operations in a process on an image
        Returns the final height map as a numpy array

        Args:
            image_path: Path to the source image
            process: Process containing operations to execute
            crop_rect: Optional tuple (x, y, w, h) with normalized coordinates (0-1)
                       for cropping before processing
        """
        # Load the image
        self.current_image = Image.open(image_path)

        # Apply crop if specified
        if crop_rect is not None:
            self._apply_crop(crop_rect)

        # Execute each operation in sequence
        for operation in process.operations:
            self._execute_operation(operation)

        # Return the height map
        return self.height_map

    def _apply_crop(self, crop_rect: tuple):
        """
        Apply crop to the current image.

        Args:
            crop_rect: Tuple (x, y, w, h) with normalized coordinates (0-1)
        """
        x, y, w, h = crop_rect

        # Skip if full image (no crop needed)
        if x == 0.0 and y == 0.0 and w == 1.0 and h == 1.0:
            return

        img_width, img_height = self.current_image.size

        # Convert normalized coordinates to pixels
        left = int(x * img_width)
        top = int(y * img_height)
        right = int((x + w) * img_width)
        bottom = int((y + h) * img_height)

        # Clamp to image bounds
        left = max(0, min(img_width, left))
        top = max(0, min(img_height, top))
        right = max(0, min(img_width, right))
        bottom = max(0, min(img_height, bottom))

        # Ensure we have a valid crop region
        if right > left and bottom > top:
            self.current_image = self.current_image.crop((left, top, right, bottom))

    def _execute_operation(self, operation: Operation):
        """Execute a single operation on the current image"""
        op_type = operation.type
        params = operation.parameters

        if op_type == "set_lithophane_parameters":
            self._set_lithophane_parameters(params)
        elif op_type == "auto_contrast":
            self._apply_auto_contrast(params)
        else:
            raise ValueError(f"Unknown operation type: {op_type}")

    def _apply_auto_contrast(self, params: dict):
        """Stretch image contrast so darkest -> 0, brightest -> 255.

        Operates on the current PIL image (color or grayscale). When listed
        before set_lithophane_parameters, runs on the original-mode crop;
        when listed after, runs on the L-mode lithophane image.
        """
        if self.current_image is None:
            return
        cutoff = float(params.get("cutoff", 1.0))
        # autocontrast doesn't accept palettized/CMYK directly; normalize first.
        if self.current_image.mode not in ("L", "RGB", "RGBA"):
            self.current_image = self.current_image.convert("RGB")
        self.current_image = ImageOps.autocontrast(self.current_image, cutoff=cutoff)

    def _set_lithophane_parameters(self, params: dict):
        """
        Set lithophane physical dimensions and convert image to height map
        This operation simultaneously:
        1. Crops or pads the image based on crop_mode
        2. Scales the image to match the specified physical dimensions
        3. Converts to grayscale
        4. Converts the image to a height map with min/max thickness
        """
        # Get parameters
        width_mm = params.get("width_mm", 100.0)
        height_mm = params.get("height_mm", 100.0)
        min_thickness_mm = params.get("min_thickness_mm", 0.8)  # For saturated (white) pixels
        max_thickness_mm = params.get("max_thickness_mm", 5.0)  # For black pixels
        invert = params.get("invert", False)
        crop_mode = params.get("crop_mode", "crop_to_size")
        background_tint = params.get("background_tint", 0.0)  # 0-100%
        blur_mm = params.get("blur_mm", 0.0)  # Blur radius in mm

        # Geometry: flat plate or wrapped cylinder. For cylinders the build
        # angle is meaningless (the model stands on its base ring), so override.
        self.geometry = params.get("geometry", "flat")
        self.arc_degrees = float(params.get("arc_degrees", 360.0))
        if self.geometry == "cylindrical":
            self.angle = 0.0
        else:
            self.angle = params.get("angle", 75.0)

        # Calculate pixel density to achieve desired physical dimensions
        # Default 2 pixels/mm gives good quality without excessive triangles
        # (100x100mm = 200x200 pixels = ~160k triangles, reasonable for preview)
        pixels_per_mm = params.get("pixels_per_mm", 2.0)
        # Need at least 2 pixels per axis to compute fence-post spacing
        target_width_pixels = max(2, int(width_mm * pixels_per_mm))
        target_height_pixels = max(2, int(height_mm * pixels_per_mm))
        # Per-axis spacing between vertices (fence-post: N pixels = N-1 gaps)
        self.pixel_size_mm = width_mm / (target_width_pixels - 1)
        self.pixel_size_mm_y = height_mm / (target_height_pixels - 1)

        # Calculate aspect ratios
        target_aspect = width_mm / height_mm
        src_width, src_height = self.current_image.size
        src_aspect = src_width / src_height

        if self.geometry == "cylindrical":
            # Wrap-around mode: width_mm is the unrolled arc length, height_mm
            # is the cylinder height. Crop/pad would distort the wrap, so we
            # just stretch-resize to the target grid.
            if self.current_image.mode not in ('L', 'RGB', 'RGBA'):
                self.current_image = self.current_image.convert('RGB')
            self.current_image = self.current_image.resize(
                (target_width_pixels, target_height_pixels),
                Image.Resampling.LANCZOS
            )
        elif crop_mode == "crop_to_size":
            # Crop to match target aspect ratio, then resize
            if src_aspect > target_aspect:
                # Source is wider - crop left/right
                new_width = int(src_height * target_aspect)
                left = (src_width - new_width) // 2
                self.current_image = self.current_image.crop((left, 0, left + new_width, src_height))
            elif src_aspect < target_aspect:
                # Source is taller - crop top/bottom
                new_height = int(src_width / target_aspect)
                top = (src_height - new_height) // 2
                self.current_image = self.current_image.crop((0, top, src_width, top + new_height))
            # Resize to target dimensions
            self.current_image = self.current_image.resize(
                (target_width_pixels, target_height_pixels),
                Image.Resampling.LANCZOS
            )
        else:  # keep_full_image
            # Pad to match target aspect ratio, then resize
            # Background tint: 0% = white (255), 100% = black (0)
            bg_gray = int(255 * (1.0 - background_tint / 100.0))

            # Normalize unusual modes (palettized, CMYK, LA, etc.) up front so
            # Image.new + paste accepts a uniform fill value.
            if self.current_image.mode not in ('L', 'RGB', 'RGBA'):
                self.current_image = self.current_image.convert('RGB')
            mode = self.current_image.mode
            if mode == 'L':
                bg_value = bg_gray
            elif mode == 'RGB':
                bg_value = (bg_gray, bg_gray, bg_gray)
            else:  # RGBA
                bg_value = (bg_gray, bg_gray, bg_gray, 255)

            if src_aspect > target_aspect:
                # Source is wider - pad top/bottom
                new_height = int(src_width / target_aspect)
                pad_total = new_height - src_height
                pad_top = pad_total // 2
                # Create new image with padding
                padded = Image.new(mode, (src_width, new_height), bg_value)
                padded.paste(self.current_image, (0, pad_top))
                self.current_image = padded
            elif src_aspect < target_aspect:
                # Source is taller - pad left/right
                new_width = int(src_height * target_aspect)
                pad_total = new_width - src_width
                pad_left = pad_total // 2
                # Create new image with padding
                padded = Image.new(mode, (new_width, src_height), bg_value)
                padded.paste(self.current_image, (pad_left, 0))
                self.current_image = padded
            # Resize to target dimensions
            self.current_image = self.current_image.resize(
                (target_width_pixels, target_height_pixels),
                Image.Resampling.LANCZOS
            )

        # Convert to grayscale
        self.current_image = ImageOps.grayscale(self.current_image)

        # Invert if specified
        if invert:
            self.current_image = ImageOps.invert(self.current_image)

        # Apply blur if specified (convert mm to pixels)
        if blur_mm > 0:
            blur_pixels = blur_mm * pixels_per_mm
            self.current_image = self.current_image.filter(ImageFilter.GaussianBlur(radius=blur_pixels))

        # Apply border if specified
        border_width_mm = params.get("border_width_mm", 0.0)
        if border_width_mm > 0:
            border_width_pixels = int(border_width_mm * pixels_per_mm)
            border_intensity = params.get("border_intensity", 50.0) / 100.0  # 0-1
            border_texture = params.get("border_texture", "solid")
            self._apply_border(border_width_pixels, border_intensity, border_texture)

        # Convert image to numpy array (0-255)
        img_array = np.array(self.current_image)

        # Normalize to 0-1
        normalized = img_array.astype(float) / 255.0

        # Create height map
        # White (saturated, value=1.0) -> min_thickness
        # Black (value=0.0) -> max_thickness
        # We invert because white should be thinner in a lithophane
        thickness_range = max_thickness_mm - min_thickness_mm
        self.height_map = min_thickness_mm + ((1.0 - normalized) * thickness_range)

    def _apply_border(self, width_pixels: int, intensity: float, texture: str):
        """
        Apply a decorative border to the grayscale image.

        Args:
            width_pixels: Border width in pixels
            intensity: Border darkness (0=white/thin, 1=black/thick)
            texture: Border texture type (solid, gradient, ribbed, dotted, wave, crosshatch)
        """
        if width_pixels <= 0:
            return

        img_array = np.array(self.current_image, dtype=np.float32)
        h, w = img_array.shape

        # Base border gray value (0=black, 255=white)
        # intensity 0 = white (255), intensity 1 = black (0)
        base_gray = 255.0 * (1.0 - intensity)

        # Distance-from-nearest-edge map (vectorized).
        ys = np.arange(h)[:, None]
        xs = np.arange(w)[None, :]
        dist = np.minimum(np.minimum(xs, w - 1 - xs), np.minimum(ys, h - 1 - ys))
        in_border = dist < width_pixels

        if not in_border.any():
            return

        if texture == "solid":
            img_array = np.where(in_border, base_gray, img_array)

        elif texture == "gradient":
            fade = np.clip(dist / max(width_pixels, 1), 0.0, 1.0)
            blended = base_gray * (1 - fade) + img_array * fade
            img_array = np.where(in_border, blended, img_array)

        elif texture == "ribbed":
            rib_spacing = max(3, width_pixels // 4)
            # Pos along border: x for top/bottom strips, y for left/right strips.
            top_or_bottom = (ys < width_pixels) | (ys >= h - width_pixels)
            rib_pos = np.where(top_or_bottom, xs % rib_spacing, ys % rib_spacing)
            rib_factor = 0.5 + 0.5 * np.sin(rib_pos / rib_spacing * math.pi * 2)
            gray = base_gray * (0.7 + 0.3 * rib_factor)
            img_array = np.where(in_border, gray, img_array)

        elif texture == "dotted":
            dot_spacing = max(4, width_pixels // 3)
            dot_radius = max(1, dot_spacing // 3)
            dx = xs % dot_spacing - dot_spacing // 2
            dy = ys % dot_spacing - dot_spacing // 2
            in_dot = (dx * dx + dy * dy) < (dot_radius * dot_radius)
            border_pixels = np.where(in_dot, 255.0, base_gray)
            img_array = np.where(in_border, border_pixels, img_array)

        elif texture == "wave":
            wave_freq = 2 * math.pi / max(10, width_pixels * 2)
            wave_amp = width_pixels * 0.3
            # Position along the border edge depends on which edge we're nearest.
            top_or_bottom = (ys < width_pixels) | (ys >= h - width_pixels)
            pos = np.where(top_or_bottom, xs, ys)
            wave = np.sin(pos * wave_freq) * wave_amp
            effective_dist = dist + wave
            inner_band = effective_dist < width_pixels * 0.7
            outer_band = (~inner_band) & (effective_dist < width_pixels)
            outer_fade = (effective_dist - width_pixels * 0.7) / max(width_pixels * 0.3, 1e-6)
            outer_blend = base_gray * (1 - outer_fade) + img_array * outer_fade
            img_array = np.where(in_border & inner_band, base_gray, img_array)
            img_array = np.where(in_border & outer_band, outer_blend, img_array)

        elif texture == "crosshatch":
            line_spacing = max(3, width_pixels // 3)
            diag1 = (xs + ys) % line_spacing < 2
            diag2 = (xs - ys) % line_spacing < 2
            on_line = diag1 | diag2
            border_pixels = np.where(on_line, base_gray * 0.7, base_gray)
            img_array = np.where(in_border, border_pixels, img_array)

        self.current_image = Image.fromarray(np.clip(img_array, 0, 255).astype(np.uint8), mode='L')

    def get_current_image(self) -> Optional[Image.Image]:
        """Get the current processed image"""
        return self.current_image

    def get_height_map(self) -> Optional[np.ndarray]:
        """Get the current height map"""
        return self.height_map

    def get_angle(self) -> float:
        """Get the build angle in degrees"""
        return self.angle

    def get_pixel_size_mm(self) -> float:
        """Get the X-axis vertex spacing in mm"""
        return self.pixel_size_mm

    def get_pixel_size_mm_y(self) -> float:
        """Get the Y-axis vertex spacing in mm"""
        return self.pixel_size_mm_y

    def get_geometry(self) -> str:
        """Get the geometry mode ('flat' or 'cylindrical')"""
        return self.geometry

    def get_arc_degrees(self) -> float:
        """Get the cylindrical wrap arc in degrees"""
        return self.arc_degrees
