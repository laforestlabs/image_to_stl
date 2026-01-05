#!/usr/bin/env python3
"""
Test STL generation and PyVista mesh loading without display
"""
import numpy as np
import pyvista as pv
from core.stl_generator import STLGenerator
import tempfile

print("Creating test height map...")
height_map = np.random.rand(20, 20) * 5.0

print("Generating STL mesh...")
generator = STLGenerator()
stl_mesh = generator.generate_from_heightmap(height_map, pixel_size_mm=1.0)

print(f"STL mesh created with {len(stl_mesh.vectors)} triangles")

# Save to temporary file
with tempfile.NamedTemporaryFile(suffix='.stl', delete=False) as tmp:
    tmp_path = tmp.name
    stl_mesh.save(tmp_path)
    print(f"Saved to: {tmp_path}")

# Load with PyVista
print("Loading mesh with PyVista...")
pv_mesh = pv.read(tmp_path)
print(f"PyVista mesh loaded: {pv_mesh.n_points} points, {pv_mesh.n_cells} cells")

print("\n✓ All core functionality working!")
print("✓ STL generation: OK")
print("✓ PyVista loading: OK")
print("\nThe 3D preview should work when running with a display.")

import os
os.unlink(tmp_path)
