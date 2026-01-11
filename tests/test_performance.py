"""
Performance tests for STL generation
"""
import sys
import time
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.image_processor import ImageProcessor
from core.process import Process
from core.stl_generator import STLGenerator


def get_sample_image() -> Path:
    """Get a sample image for testing"""
    samples_dir = Path(__file__).parent.parent / "samples"
    images = list(samples_dir.rglob("*.jpg"))
    return images[0] if images else None


class TestPerformance:
    """Performance benchmarks for mesh generation"""

    # Thresholds in seconds (with headroom for CI variance)
    THRESHOLD_FLAT = 2.0        # angle=0, simplified mesh
    THRESHOLD_ANGLED = 10.0     # angle=75, full processing

    def test_generation_time_flat(self):
        """Mesh generation at angle=0 should complete within threshold"""
        test_image = get_sample_image()
        if not test_image:
            pytest.skip("No sample images found")

        process = Process.from_dict({
            'name': 'Perf Test',
            'operations': [{
                'type': 'set_lithophane_parameters',
                'parameters': {
                    'width_mm': 75.0,
                    'height_mm': 75.0,
                    'min_thickness_mm': 0.8,
                    'max_thickness_mm': 2.5,
                    'pixels_per_mm': 4.0,
                    'angle': 0.0
                }
            }]
        })

        processor = ImageProcessor()
        generator = STLGenerator()

        start = time.perf_counter()
        processor.execute_process(str(test_image), process)
        stl_mesh = generator.generate_from_heightmap(
            processor.get_height_map(),
            pixel_size_mm=processor.get_pixel_size_mm(),
            angle=0.0
        )
        elapsed = time.perf_counter() - start

        print(f"\nFlat mesh (angle=0): {elapsed:.2f}s, {len(stl_mesh.vectors)} triangles")
        assert elapsed < self.THRESHOLD_FLAT, \
            f"Generation took {elapsed:.2f}s, threshold is {self.THRESHOLD_FLAT}s"

    def test_generation_time_angled_default(self):
        """Mesh generation at default angle (75°) should complete within threshold"""
        test_image = get_sample_image()
        if not test_image:
            pytest.skip("No sample images found")

        # Default settings from processes/default.json
        process = Process.from_dict({
            'name': 'Perf Test',
            'operations': [{
                'type': 'set_lithophane_parameters',
                'parameters': {
                    'width_mm': 75.0,
                    'height_mm': 75.0,
                    'min_thickness_mm': 0.8,
                    'max_thickness_mm': 2.5,
                    'pixels_per_mm': 4.0,
                    'blur_mm': 0.1,
                    'angle': 75.0
                }
            }]
        })

        processor = ImageProcessor()
        generator = STLGenerator()

        start = time.perf_counter()
        processor.execute_process(str(test_image), process)
        stl_mesh = generator.generate_from_heightmap(
            processor.get_height_map(),
            pixel_size_mm=processor.get_pixel_size_mm(),
            angle=75.0
        )
        elapsed = time.perf_counter() - start

        print(f"\nAngled mesh (75°): {elapsed:.2f}s, {len(stl_mesh.vectors)} triangles")
        assert elapsed < self.THRESHOLD_ANGLED, \
            f"Generation took {elapsed:.2f}s, threshold is {self.THRESHOLD_ANGLED}s"

    def test_stl_generator_only(self):
        """Test just the STL generation step (no image processing)"""
        # 300x300 heightmap matches default 75mm at 4 pixels/mm
        np.random.seed(42)
        height_map = np.random.uniform(0.8, 2.5, (300, 300))
        pixel_size = 75.0 / 299  # fence-post corrected

        generator = STLGenerator()

        start = time.perf_counter()
        stl_mesh = generator.generate_from_heightmap(
            height_map,
            pixel_size_mm=pixel_size,
            angle=75.0
        )
        elapsed = time.perf_counter() - start

        print(f"\nSTL generation only (75°): {elapsed:.2f}s, {len(stl_mesh.vectors)} triangles")
        # STL generation alone should be faster than full pipeline
        assert elapsed < self.THRESHOLD_ANGLED, \
            f"STL generation took {elapsed:.2f}s, threshold is {self.THRESHOLD_ANGLED}s"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
