"""
Tests for image processing pipeline (crop, padding, borders, mode handling).
"""
import sys
import tempfile
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.image_processor import ImageProcessor
from core.process import Process


def _process(params: dict, image: Image.Image, crop_rect=None) -> ImageProcessor:
    """Save image to a temp file and run it through the processor."""
    process = Process.from_dict({
        "name": "Test",
        "operations": [{"type": "set_lithophane_parameters", "parameters": params}],
    })
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
        path = f.name
    image.save(path)
    try:
        processor = ImageProcessor()
        processor.execute_process(path, process, crop_rect=crop_rect)
        return processor
    finally:
        Path(path).unlink(missing_ok=True)


class TestCrop:
    """_apply_crop and crop_rect handling."""

    def test_full_crop_is_noop(self):
        img = Image.new("RGB", (100, 100), (128, 128, 128))
        proc = _process(
            {"width_mm": 50, "height_mm": 50, "min_thickness_mm": 0.5, "max_thickness_mm": 2.0},
            img,
            crop_rect=(0.0, 0.0, 1.0, 1.0),
        )
        assert proc.height_map is not None

    def test_partial_crop_changes_aspect_input(self):
        # Crop the right half of a 200x100 image -> 100x100
        img = Image.new("RGB", (200, 100), (128, 128, 128))
        proc = _process(
            {"width_mm": 50, "height_mm": 50, "min_thickness_mm": 0.5, "max_thickness_mm": 2.0},
            img,
            crop_rect=(0.5, 0.0, 0.5, 1.0),
        )
        assert proc.height_map is not None
        assert proc.height_map.shape[0] > 0 and proc.height_map.shape[1] > 0

    def test_invalid_crop_does_not_crash(self):
        img = Image.new("RGB", (100, 100), (128, 128, 128))
        # Zero-area crop should be skipped, not crash
        proc = _process(
            {"width_mm": 50, "height_mm": 50, "min_thickness_mm": 0.5, "max_thickness_mm": 2.0},
            img,
            crop_rect=(0.5, 0.5, 0.0, 0.0),
        )
        assert proc.height_map is not None


class TestCropMode:
    """crop_to_size vs keep_full_image."""

    def test_keep_full_image_pads_correctly(self):
        # Wider source, square target -> needs top/bottom padding
        img = Image.new("RGB", (200, 100), (128, 128, 128))
        proc = _process(
            {
                "width_mm": 50,
                "height_mm": 50,
                "min_thickness_mm": 0.5,
                "max_thickness_mm": 2.0,
                "crop_mode": "keep_full_image",
                "background_tint": 0.0,
                "pixels_per_mm": 2.0,
            },
            img,
        )
        # 50mm * 2 px/mm = 100 px per axis (square)
        assert proc.height_map.shape == (100, 100)

    def test_palette_mode_image_does_not_crash(self):
        # Palettized PIL mode used to break Image.new(...) in keep_full_image branch.
        img = Image.new("P", (120, 80))
        # Give it a palette so PIL keeps it in 'P' mode
        img.putpalette([i for i in range(256)] * 3)
        proc = _process(
            {
                "width_mm": 50,
                "height_mm": 50,
                "min_thickness_mm": 0.5,
                "max_thickness_mm": 2.0,
                "crop_mode": "keep_full_image",
                "pixels_per_mm": 2.0,
            },
            img,
        )
        assert proc.height_map is not None


class TestPixelSpacing:
    """Per-axis pixel spacing for non-square lithophanes."""

    def test_non_square_dimensions_have_correct_aspect(self):
        img = Image.new("RGB", (100, 100), (128, 128, 128))
        proc = _process(
            {
                "width_mm": 100.0,
                "height_mm": 50.0,
                "min_thickness_mm": 0.5,
                "max_thickness_mm": 2.0,
                "pixels_per_mm": 2.0,
            },
            img,
        )
        # 100mm wide, 50mm tall, 2 px/mm -> 200x100 px
        assert proc.height_map.shape == (100, 200)
        # X spacing should be ~0.502mm (100/199), Y ~0.505mm (50/99).
        # Mesh extent = (cols-1)*x + (rows-1)*y = 100mm and 50mm exactly.
        assert abs((200 - 1) * proc.get_pixel_size_mm() - 100.0) < 1e-9
        assert abs((100 - 1) * proc.get_pixel_size_mm_y() - 50.0) < 1e-9


class TestBorderTextures:
    """All six border textures should run without error and stay in [0,255]."""

    @pytest.mark.parametrize(
        "texture",
        ["solid", "gradient", "ribbed", "dotted", "wave", "crosshatch"],
    )
    def test_each_texture_produces_valid_output(self, texture):
        img = Image.new("RGB", (100, 100), (128, 128, 128))
        proc = _process(
            {
                "width_mm": 50,
                "height_mm": 50,
                "min_thickness_mm": 0.8,
                "max_thickness_mm": 3.0,
                "pixels_per_mm": 2.0,
                "border_width_mm": 5.0,
                "border_intensity": 80.0,
                "border_texture": texture,
            },
            img,
        )
        # Heightmap should reflect border (some pixels darker -> thicker).
        hm = proc.height_map
        assert hm is not None
        assert hm.min() >= 0.8 - 1e-9
        assert hm.max() <= 3.0 + 1e-9
        # Border should produce a non-uniform heightmap.
        assert hm.max() - hm.min() > 0.1


class TestAutoContrast:
    """auto_contrast operation stretches the input range."""

    def test_low_contrast_grayscale_stretches_to_full_range(self):
        # Build a low-contrast L-mode image with values in 100..150.
        arr = np.linspace(100, 150, 100 * 100, dtype=np.uint8).reshape(100, 100)
        img = Image.fromarray(arr, mode="L")
        process = Process.from_dict({
            "name": "Test",
            "operations": [
                {"type": "auto_contrast", "parameters": {"cutoff": 0.0}},
                {"type": "set_lithophane_parameters", "parameters": {
                    "width_mm": 50, "height_mm": 50,
                    "min_thickness_mm": 0.5, "max_thickness_mm": 2.5,
                    "pixels_per_mm": 2.0,
                }},
            ],
        })
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            path = f.name
        img.save(path)
        try:
            processor = ImageProcessor()
            processor.execute_process(path, process)
        finally:
            Path(path).unlink(missing_ok=True)

        hm = processor.height_map
        # After stretching 100..150 -> 0..255 the heightmap should span
        # essentially the full min..max thickness range.
        assert hm.min() < 0.55
        assert hm.max() > 2.45

    def test_auto_contrast_runs_after_lithophane_op(self):
        # auto_contrast can also be appended after the lithophane op
        # (operates on the L-mode result).
        img = Image.new("L", (50, 50), 120)
        process = Process.from_dict({
            "name": "Test",
            "operations": [
                {"type": "set_lithophane_parameters", "parameters": {
                    "width_mm": 30, "height_mm": 30,
                    "min_thickness_mm": 0.5, "max_thickness_mm": 2.0,
                }},
                {"type": "auto_contrast", "parameters": {"cutoff": 0.0}},
            ],
        })
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            path = f.name
        img.save(path)
        try:
            processor = ImageProcessor()
            processor.execute_process(path, process)
        finally:
            Path(path).unlink(missing_ok=True)
        # Just checking it doesn't throw — height_map is built by the prior op.
        assert processor.height_map is not None


class TestCylindricalParams:
    """Cylindrical mode bypasses crop/pad and forces angle=0."""

    def test_cylindrical_geometry_stored_on_processor(self):
        img = Image.new("RGB", (100, 100), (128, 128, 128))
        proc = _process(
            {
                "width_mm": 100, "height_mm": 80,
                "min_thickness_mm": 0.6, "max_thickness_mm": 2.5,
                "pixels_per_mm": 2.0,
                "geometry": "cylindrical", "arc_degrees": 360.0,
                "angle": 75.0,  # should be overridden to 0 for cylindrical
            },
            img,
        )
        assert proc.get_geometry() == "cylindrical"
        assert proc.get_arc_degrees() == 360.0
        assert proc.get_angle() == 0.0

    def test_cylindrical_preserves_image_aspect_via_crop(self):
        # Cylindrical mode must respect crop_mode just like flat mode does,
        # otherwise the wrapped image visibly distorts when source aspect
        # differs from target aspect. Build a marker image that's mostly
        # neutral gray with a black square in the center; after a center
        # crop+resize, the black square should still be square (equal width
        # and height in the resulting heightmap).
        arr = np.full((100, 200, 3), 200, dtype=np.uint8)  # 2:1 source
        arr[40:60, 90:110] = 0  # 20x20 centered black square
        img = Image.fromarray(arr, mode="RGB")
        proc = _process(
            {
                "width_mm": 50, "height_mm": 50,  # 1:1 target
                "min_thickness_mm": 0.5, "max_thickness_mm": 2.0,
                "pixels_per_mm": 2.0,
                "geometry": "cylindrical", "arc_degrees": 360.0,
                "crop_mode": "crop_to_size",
            },
            img,
        )
        # 50mm @ 2 px/mm -> 100x100 grid.
        assert proc.height_map.shape == (100, 100)
        # The black square should map to roughly equal width and height
        # in the heightmap (indicating no horizontal/vertical stretch).
        thick = proc.height_map > 1.5  # darker pixels are thicker
        rows_with_black = np.where(thick.any(axis=1))[0]
        cols_with_black = np.where(thick.any(axis=0))[0]
        h_extent = rows_with_black.max() - rows_with_black.min() + 1
        w_extent = cols_with_black.max() - cols_with_black.min() + 1
        # Allow a few pixels' tolerance for resampling/centering.
        assert abs(h_extent - w_extent) <= 3, (
            f"Black square distorted: {w_extent}px wide vs {h_extent}px tall"
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
