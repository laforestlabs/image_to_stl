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
        self.pixel_size_mm: float = 0.5  # Physical size of each pixel (1/pixels_per_mm)

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
        else:
            raise ValueError(f"Unknown operation type: {op_type}")

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
        self.angle = params.get("angle", 75.0)  # Store angle for STL generation
        crop_mode = params.get("crop_mode", "crop_to_size")
        background_tint = params.get("background_tint", 0.0)  # 0-100%
        blur_mm = params.get("blur_mm", 0.0)  # Blur radius in mm

        # Calculate pixel density to achieve desired physical dimensions
        # Default 2 pixels/mm gives good quality without excessive triangles
        # (100x100mm = 200x200 pixels = ~160k triangles, reasonable for preview)
        pixels_per_mm = params.get("pixels_per_mm", 2.0)
        self.pixel_size_mm = 1.0 / pixels_per_mm  # Store for STL generation
        target_width_pixels = int(width_mm * pixels_per_mm)
        target_height_pixels = int(height_mm * pixels_per_mm)

        # Calculate aspect ratios
        target_aspect = width_mm / height_mm
        src_width, src_height = self.current_image.size
        src_aspect = src_width / src_height

        if crop_mode == "crop_to_size":
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

            # Create appropriate fill value based on image mode
            mode = self.current_image.mode
            if mode == 'L':
                bg_value = bg_gray
            elif mode == 'RGB':
                bg_value = (bg_gray, bg_gray, bg_gray)
            elif mode == 'RGBA':
                bg_value = (bg_gray, bg_gray, bg_gray, 255)
            else:
                bg_value = bg_gray

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
        base_gray = 255 * (1.0 - intensity)

        # Create border mask based on texture
        if texture == "solid":
            # Simple solid border
            for y in range(h):
                for x in range(w):
                    dist = min(x, y, w - 1 - x, h - 1 - y)
                    if dist < width_pixels:
                        img_array[y, x] = base_gray

        elif texture == "gradient":
            # Gradient that fades from border intensity to image
            for y in range(h):
                for x in range(w):
                    dist = min(x, y, w - 1 - x, h - 1 - y)
                    if dist < width_pixels:
                        # Fade factor: 0 at edge, 1 at inner border edge
                        fade = dist / width_pixels
                        img_array[y, x] = base_gray * (1 - fade) + img_array[y, x] * fade

        elif texture == "ribbed":
            # Vertical ribbed pattern
            rib_spacing = max(3, width_pixels // 4)
            for y in range(h):
                for x in range(w):
                    dist = min(x, y, w - 1 - x, h - 1 - y)
                    if dist < width_pixels:
                        # Create ribs based on position along border
                        if y < width_pixels or y >= h - width_pixels:
                            rib_pos = x % rib_spacing
                        else:
                            rib_pos = y % rib_spacing
                        rib_factor = 0.5 + 0.5 * math.sin(rib_pos / rib_spacing * math.pi * 2)
                        gray = base_gray * (0.7 + 0.3 * rib_factor)
                        img_array[y, x] = gray

        elif texture == "dotted":
            # Perforated dot pattern
            dot_spacing = max(4, width_pixels // 3)
            dot_radius = max(1, dot_spacing // 3)
            for y in range(h):
                for x in range(w):
                    dist = min(x, y, w - 1 - x, h - 1 - y)
                    if dist < width_pixels:
                        # Check if we're in a dot
                        dx = x % dot_spacing - dot_spacing // 2
                        dy = y % dot_spacing - dot_spacing // 2
                        in_dot = (dx * dx + dy * dy) < (dot_radius * dot_radius)
                        if in_dot:
                            img_array[y, x] = 255  # White (thin) for dots
                        else:
                            img_array[y, x] = base_gray

        elif texture == "wave":
            # Sine wave pattern along border
            wave_freq = 2 * math.pi / max(10, width_pixels * 2)
            wave_amp = width_pixels * 0.3
            for y in range(h):
                for x in range(w):
                    dist = min(x, y, w - 1 - x, h - 1 - y)
                    if dist < width_pixels:
                        # Determine which edge we're on and position along it
                        if y < width_pixels:
                            pos = x
                        elif y >= h - width_pixels:
                            pos = x
                        elif x < width_pixels:
                            pos = y
                        else:
                            pos = y
                        wave = math.sin(pos * wave_freq) * wave_amp
                        effective_dist = dist + wave
                        if effective_dist < width_pixels * 0.7:
                            img_array[y, x] = base_gray
                        elif effective_dist < width_pixels:
                            fade = (effective_dist - width_pixels * 0.7) / (width_pixels * 0.3)
                            img_array[y, x] = base_gray * (1 - fade) + img_array[y, x] * fade

        elif texture == "crosshatch":
            # Crosshatch diagonal pattern
            line_spacing = max(3, width_pixels // 3)
            for y in range(h):
                for x in range(w):
                    dist = min(x, y, w - 1 - x, h - 1 - y)
                    if dist < width_pixels:
                        # Diagonal lines in both directions
                        diag1 = (x + y) % line_spacing < 2
                        diag2 = (x - y) % line_spacing < 2
                        if diag1 or diag2:
                            img_array[y, x] = base_gray * 0.7
                        else:
                            img_array[y, x] = base_gray

        # Convert back to PIL Image
        self.current_image = Image.fromarray(img_array.astype(np.uint8), mode='L')

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
        """Get the pixel size in mm (1/pixels_per_mm)"""
        return self.pixel_size_mm
