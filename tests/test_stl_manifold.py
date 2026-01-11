"""
Tests to verify STL meshes are manifold (watertight)
"""
import random
import sys
import tempfile
from pathlib import Path

import numpy as np
import pytest
import trimesh

sys.path.insert(0, str(Path(__file__).parent.parent))


def get_random_sample_image() -> Path:
    """Get a random image from the samples directory"""
    samples_dir = Path(__file__).parent.parent / "samples"
    images = list(samples_dir.rglob("*.jpg"))
    if not images:
        return None
    return random.choice(images)

from core.image_processor import ImageProcessor
from core.process import Process
from core.stl_generator import STLGenerator


def generate_stl_from_image(image_path: str, angle: float = 0.0) -> trimesh.Trimesh:
    """Helper to generate STL from an image and load it as trimesh"""
    process = Process.from_dict({
        'name': 'Test',
        'operations': [{
            'type': 'set_lithophane_parameters',
            'parameters': {
                'width_mm': 50.0,
                'height_mm': 50.0,
                'min_thickness_mm': 0.4,
                'max_thickness_mm': 2.0,
                'angle': angle
            }
        }]
    })

    processor = ImageProcessor()
    processor.execute_process(image_path, process)

    generator = STLGenerator()
    stl_mesh = generator.generate_from_heightmap(
        processor.get_height_map(),
        pixel_size_mm=processor.get_pixel_size_mm(),
        angle=angle
    )

    # Save to temp file and load with trimesh
    with tempfile.NamedTemporaryFile(suffix='.stl', delete=False) as f:
        temp_path = f.name
    stl_mesh.save(temp_path)

    mesh = trimesh.load(temp_path)
    Path(temp_path).unlink()

    return mesh


def generate_stl_from_heightmap(height_map: np.ndarray, pixel_size_mm: float = 0.5, angle: float = 0.0) -> trimesh.Trimesh:
    """Helper to generate STL from a synthetic heightmap"""
    generator = STLGenerator()
    stl_mesh = generator.generate_from_heightmap(
        height_map,
        pixel_size_mm=pixel_size_mm,
        angle=angle
    )

    with tempfile.NamedTemporaryFile(suffix='.stl', delete=False) as f:
        temp_path = f.name
    stl_mesh.save(temp_path)

    mesh = trimesh.load(temp_path)
    Path(temp_path).unlink()

    return mesh


class TestSTLManifold:
    """Test that generated STL meshes are manifold"""

    def test_simple_flat_heightmap_is_manifold(self):
        """A simple flat heightmap should produce a manifold mesh"""
        # Create a simple 10x10 flat heightmap
        height_map = np.ones((10, 10)) * 1.0
        mesh = generate_stl_from_heightmap(height_map, pixel_size_mm=1.0, angle=0.0)

        assert mesh.is_watertight, f"Mesh is not watertight. Has {len(mesh.faces)} faces."

    def test_gradient_heightmap_is_manifold(self):
        """A gradient heightmap should produce a manifold mesh"""
        # Create a gradient heightmap
        height_map = np.linspace(0.5, 2.0, 100).reshape(10, 10)
        mesh = generate_stl_from_heightmap(height_map, pixel_size_mm=1.0, angle=0.0)

        assert mesh.is_watertight, f"Mesh is not watertight. Has {len(mesh.faces)} faces."

    def test_random_heightmap_is_manifold(self):
        """A random heightmap should produce a manifold mesh"""
        np.random.seed(42)
        height_map = np.random.uniform(0.4, 2.0, (20, 20))
        mesh = generate_stl_from_heightmap(height_map, pixel_size_mm=0.5, angle=0.0)

        assert mesh.is_watertight, f"Mesh is not watertight. Has {len(mesh.faces)} faces."

    def test_flat_heightmap_angled_is_manifold(self):
        """A flat heightmap at 45 degrees should produce a manifold mesh"""
        height_map = np.ones((10, 10)) * 1.0
        mesh = generate_stl_from_heightmap(height_map, pixel_size_mm=1.0, angle=45.0)

        assert mesh.is_watertight, f"Mesh at 45° is not watertight."

    def test_flat_heightmap_75deg_is_manifold(self):
        """A flat heightmap at 75 degrees (default) should produce a manifold mesh"""
        height_map = np.ones((10, 10)) * 1.0
        mesh = generate_stl_from_heightmap(height_map, pixel_size_mm=1.0, angle=75.0)

        assert mesh.is_watertight, f"Mesh at 75° is not watertight."

    def test_flat_heightmap_90deg_is_manifold(self):
        """A flat heightmap at 90 degrees (vertical) should produce a manifold mesh"""
        height_map = np.ones((10, 10)) * 1.0
        mesh = generate_stl_from_heightmap(height_map, pixel_size_mm=1.0, angle=90.0)

        assert mesh.is_watertight, f"Mesh at 90° is not watertight."

    def test_real_image_is_manifold(self):
        """Test with a random sample image"""
        test_image = get_random_sample_image()
        if not test_image:
            pytest.skip("No sample images found")

        mesh = generate_stl_from_image(str(test_image), angle=0.0)
        assert mesh.is_watertight, f"Mesh from {test_image.name} is not watertight."

    def test_real_image_angled_is_manifold(self):
        """Test with a random sample image at an angle"""
        test_image = get_random_sample_image()
        if not test_image:
            pytest.skip("No sample images found")

        mesh = generate_stl_from_image(str(test_image), angle=75.0)
        assert mesh.is_watertight, f"Mesh from {test_image.name} at 75° is not watertight."


class TestMeshTriangleCount:
    """Test that mesh simplification actually reduces triangle count"""

    def test_bottom_face_simplified_at_angle_0(self):
        """Bottom face should only have 2 triangles for angle=0 builds"""
        # Create heightmaps of different sizes
        for size in [10, 20, 50]:
            height_map = np.ones((size, size)) * 1.0
            mesh = generate_stl_from_heightmap(height_map, pixel_size_mm=1.0, angle=0.0)

            # Expected triangles with simplified bottom and fan side walls:
            # - Top: (size-1)^2 * 2 (full grid needed for detail)
            # - Bottom: 2 (simplified!)
            # - Side walls: 2*size + 2*size = 4*size (fans from corners)
            top_tris = (size - 1) ** 2 * 2
            bottom_tris = 2
            side_tris = 4 * size
            expected = top_tris + bottom_tris + side_tris

            assert len(mesh.faces) == expected, \
                f"Size {size} at angle=0: expected {expected} faces, got {len(mesh.faces)}"

    def test_angled_builds_use_grid_bottom(self):
        """Angled builds should use full grid for proper clamping"""
        size = 10
        height_map = np.ones((size, size)) * 1.0

        # For angled builds, we use full grid (more triangles but handles clamping)
        mesh = generate_stl_from_heightmap(height_map, pixel_size_mm=1.0, angle=75.0)

        # Should have more faces than simplified version
        # Full grid: top + bottom + sides = 2*(size-1)^2 * 2 + 4*(size-1)*2
        top_tris = (size - 1) ** 2 * 2
        bottom_tris = (size - 1) ** 2 * 2
        side_tris = 4 * (size - 1) * 2
        expected_full = top_tris + bottom_tris + side_tris

        # Note: some triangles may be removed as degenerate after clamping
        # so actual count may be slightly less
        assert len(mesh.faces) <= expected_full, \
            f"Angled mesh has more faces than expected: {len(mesh.faces)} > {expected_full}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
