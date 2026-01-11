"""
STL file generator from height maps
"""
import numpy as np
from stl import mesh


class STLGenerator:
    """Generate STL mesh from height map"""

    def __init__(self):
        self.mesh = None

    def generate_from_heightmap(self, height_map: np.ndarray, pixel_size_mm: float = 0.1, angle: float = 75.0) -> mesh.Mesh:
        """
        Generate an STL mesh from a height map

        Args:
            height_map: 2D numpy array where values represent heights in mm
            pixel_size_mm: Physical size of each pixel in mm
            angle: Build angle in degrees (0=flat, 90=vertical)

        Returns:
            numpy-stl Mesh object
        """
        rows, cols = height_map.shape

        # Create vertices for the top surface
        # Note: Flip Y so image top (row 0) maps to high Y, making the STL right-side-up
        vertices_top = []
        for i in range(rows):
            for j in range(cols):
                x = j * pixel_size_mm
                y = (rows - 1 - i) * pixel_size_mm
                z = height_map[i, j]
                vertices_top.append([x, y, z])

        vertices_top = np.array(vertices_top)

        # Choose mesh strategy based on angle
        # angle=0: simplified bottom (4 corners) - saves ~50% triangles
        # angle!=0: grid-based bottom - handles vertex clamping correctly
        use_simplified_bottom = (angle == 0)

        if use_simplified_bottom:
            stl_mesh = self._create_simplified_mesh(vertices_top, rows, cols, pixel_size_mm)
        else:
            stl_mesh = self._create_grid_mesh(vertices_top, rows, cols, pixel_size_mm)

        # Apply rotation around X-axis if angle is not 0
        if angle != 0 and angle != 90:
            stl_mesh = self._apply_angled_rotation(stl_mesh, angle, pixel_size_mm)
        elif angle == 90:
            stl_mesh = self._apply_vertical_rotation(stl_mesh)

        # For angle == 0, no rotation needed, mesh already has flat bottom

        self.mesh = stl_mesh
        return stl_mesh

    def _create_simplified_mesh(self, vertices_top: np.ndarray, rows: int, cols: int, pixel_size_mm: float) -> mesh.Mesh:
        """Create mesh with simplified bottom (4 corners, 2 triangles) for angle=0"""
        max_x = (cols - 1) * pixel_size_mm
        max_y = (rows - 1) * pixel_size_mm
        vertices_bottom = np.array([
            [0, max_y, 0],      # TL - top-left (high Y, low X)
            [max_x, max_y, 0],  # TR - top-right (high Y, high X)
            [0, 0, 0],          # BL - bottom-left (low Y, low X)
            [max_x, 0, 0],      # BR - bottom-right (low Y, high X)
        ])

        faces = []

        # Top surface faces (full detail needed)
        for i in range(rows - 1):
            for j in range(cols - 1):
                idx = i * cols + j
                faces.append([idx, idx + cols, idx + 1])
                faces.append([idx + 1, idx + cols, idx + cols + 1])

        # Bottom corner indices
        offset = rows * cols
        TL, TR, BL, BR = offset, offset + 1, offset + 2, offset + 3

        # Bottom surface - just 2 triangles
        faces.append([BL, TL, BR])
        faces.append([TL, TR, BR])

        # Side faces as triangle fans from bottom corners to top edge vertices
        # Left wall: fan from BL
        for i in range(rows - 1):
            top_curr = (rows - 1 - i) * cols
            top_next = (rows - 2 - i) * cols
            faces.append([BL, top_curr, top_next])
        faces.append([BL, 0, TL])

        # Right wall: fan from BR
        faces.append([BR, TR, cols - 1])
        for i in range(rows - 1):
            top_curr = i * cols + (cols - 1)
            top_next = (i + 1) * cols + (cols - 1)
            faces.append([BR, top_curr, top_next])

        # Front wall: fan from TL
        for j in range(cols - 1):
            faces.append([TL, j, j + 1])
        faces.append([TL, cols - 1, TR])

        # Back wall: fan from BR
        for j in range(cols - 1):
            top_curr = (rows - 1) * cols + (cols - 1 - j)
            top_next = (rows - 1) * cols + (cols - 2 - j)
            faces.append([BR, top_curr, top_next])
        faces.append([BR, (rows - 1) * cols, BL])

        faces = np.array(faces)
        all_vertices = np.vstack([vertices_top, vertices_bottom])

        stl_mesh = mesh.Mesh(np.zeros(faces.shape[0], dtype=mesh.Mesh.dtype))
        for i, face in enumerate(faces):
            for j in range(3):
                stl_mesh.vectors[i][j] = all_vertices[face[j]]

        return stl_mesh

    def _create_grid_mesh(self, vertices_top: np.ndarray, rows: int, cols: int, pixel_size_mm: float) -> mesh.Mesh:
        """Create mesh with simplified back face using perimeter fan triangulation.

        Uses perimeter fan for back face:
        - Full grid: (rows-1)*(cols-1)*2 ≈ 79k triangles for 200x200
        - Perimeter fan: 2*(rows-1) + 2*(cols-1) ≈ 800 triangles for 200x200

        The _merge_z0_vertices() function handles vertex alignment after rotation.
        """
        max_x = (cols - 1) * pixel_size_mm
        max_y = (rows - 1) * pixel_size_mm

        # Bottom perimeter vertices only (not full grid)
        vertices_bottom = []
        bottom_idx_map = {}  # maps (i,j) to vertex index in vertices_bottom

        # Front edge (i=0)
        for j in range(cols):
            x = j * pixel_size_mm
            y = max_y
            bottom_idx_map[(0, j)] = len(vertices_bottom)
            vertices_bottom.append([x, y, 0])

        # Back edge (i=rows-1)
        for j in range(cols):
            x = j * pixel_size_mm
            y = 0
            bottom_idx_map[(rows - 1, j)] = len(vertices_bottom)
            vertices_bottom.append([x, y, 0])

        # Left edge (j=0), excluding corners already added
        for i in range(1, rows - 1):
            x = 0
            y = (rows - 1 - i) * pixel_size_mm
            bottom_idx_map[(i, 0)] = len(vertices_bottom)
            vertices_bottom.append([x, y, 0])

        # Right edge (j=cols-1), excluding corners already added
        for i in range(1, rows - 1):
            x = max_x
            y = (rows - 1 - i) * pixel_size_mm
            bottom_idx_map[(i, cols - 1)] = len(vertices_bottom)
            vertices_bottom.append([x, y, 0])

        # Add center vertex for fan triangulation
        center_idx = len(vertices_bottom)
        vertices_bottom.append([max_x / 2, max_y / 2, 0])

        vertices_bottom = np.array(vertices_bottom)
        offset = rows * cols  # bottom vertices start after top vertices

        faces = []

        # Top surface faces (full detail needed)
        for i in range(rows - 1):
            for j in range(cols - 1):
                idx = i * cols + j
                faces.append([idx, idx + cols, idx + 1])
                faces.append([idx + 1, idx + cols, idx + cols + 1])

        # Bottom surface - fan from center to perimeter
        center = offset + center_idx

        # Front edge (high Y)
        for j in range(cols - 1):
            v1 = offset + bottom_idx_map[(0, j)]
            v2 = offset + bottom_idx_map[(0, j + 1)]
            faces.append([center, v2, v1])

        # Right edge
        for i in range(rows - 1):
            v1 = offset + bottom_idx_map[(i, cols - 1)]
            v2 = offset + bottom_idx_map[(i + 1, cols - 1)]
            faces.append([center, v2, v1])

        # Back edge (low Y)
        for j in range(cols - 1, 0, -1):
            v1 = offset + bottom_idx_map[(rows - 1, j)]
            v2 = offset + bottom_idx_map[(rows - 1, j - 1)]
            faces.append([center, v2, v1])

        # Left edge
        for i in range(rows - 1, 0, -1):
            v1 = offset + bottom_idx_map[(i, 0)]
            v2 = offset + bottom_idx_map[(i - 1, 0)]
            faces.append([center, v2, v1])

        # Side faces - connecting top edge to bottom perimeter
        # Left edge (j=0)
        for i in range(rows - 1):
            top1 = i * cols
            top2 = (i + 1) * cols
            bot1 = offset + bottom_idx_map[(i, 0)]
            bot2 = offset + bottom_idx_map[(i + 1, 0)]
            faces.append([top1, bot1, top2])
            faces.append([top2, bot1, bot2])

        # Right edge (j=cols-1)
        for i in range(rows - 1):
            top1 = i * cols + (cols - 1)
            top2 = (i + 1) * cols + (cols - 1)
            bot1 = offset + bottom_idx_map[(i, cols - 1)]
            bot2 = offset + bottom_idx_map[(i + 1, cols - 1)]
            faces.append([top1, top2, bot1])
            faces.append([top2, bot2, bot1])

        # Front edge (i=0)
        for j in range(cols - 1):
            top1 = j
            top2 = j + 1
            bot1 = offset + bottom_idx_map[(0, j)]
            bot2 = offset + bottom_idx_map[(0, j + 1)]
            faces.append([top1, top2, bot1])
            faces.append([top2, bot2, bot1])

        # Back edge (i=rows-1)
        for j in range(cols - 1):
            top1 = (rows - 1) * cols + j
            top2 = (rows - 1) * cols + j + 1
            bot1 = offset + bottom_idx_map[(rows - 1, j)]
            bot2 = offset + bottom_idx_map[(rows - 1, j + 1)]
            faces.append([top1, bot1, top2])
            faces.append([top2, bot1, bot2])

        faces = np.array(faces)
        all_vertices = np.vstack([vertices_top, vertices_bottom])

        stl_mesh = mesh.Mesh(np.zeros(faces.shape[0], dtype=mesh.Mesh.dtype))
        for i, face in enumerate(faces):
            for j in range(3):
                stl_mesh.vectors[i][j] = all_vertices[face[j]]

        return stl_mesh

    def _apply_angled_rotation(self, stl_mesh: mesh.Mesh, angle: float, pixel_size_mm: float) -> mesh.Mesh:
        """Apply rotation and clamping for angled builds (0 < angle < 90)"""
        # Avoid exactly 45° which causes numeric precision issues
        # (sin(45°) = cos(45°) creates vertex coincidences)
        if abs(angle - 45.0) < 0.1:
            angle = 45.1

        angle_rad = np.radians(angle)
        cos_a = np.cos(angle_rad)
        sin_a = np.sin(angle_rad)

        # Rotation matrix around X-axis
        for i in range(len(stl_mesh.vectors)):
            for j in range(3):
                y = stl_mesh.vectors[i][j][1]
                z = stl_mesh.vectors[i][j][2]
                stl_mesh.vectors[i][j][1] = y * cos_a - z * sin_a
                stl_mesh.vectors[i][j][2] = y * sin_a + z * cos_a

        # Create a flat bottom
        min_z = stl_mesh.vectors[:, :, 2].min()
        max_z = stl_mesh.vectors[:, :, 2].max()
        model_height = max_z - min_z

        # Calculate how much to lower for good flat bottom contact
        target_flat_width = 2.0  # mm
        flat_depth = max(target_flat_width * np.sin(angle_rad), model_height * 0.01)

        # Move mesh so that min_z + flat_depth = 0
        stl_mesh.vectors[:, :, 2] -= (min_z + flat_depth)

        # Clamp vertices below z=0 to z=0, compensating y for the rotation angle
        # When clamping z, we need to slide along the tilted plane direction,
        # not just move straight up in Z. This keeps tilted faces planar.
        # For a vertex at z < 0, project onto z=0 along the rotated plane:
        #   y_new = y_old - z_old * cot(angle) = y_old - z_old * cos/sin
        cot_a = cos_a / sin_a
        below_zero = stl_mesh.vectors[:, :, 2] < 0
        # Adjust y based on how far below z=0 the vertex is
        stl_mesh.vectors[:, :, 1] = np.where(
            below_zero,
            stl_mesh.vectors[:, :, 1] - stl_mesh.vectors[:, :, 2] * cot_a,
            stl_mesh.vectors[:, :, 1]
        )
        # Then clamp z to 0
        stl_mesh.vectors[:, :, 2] = np.maximum(stl_mesh.vectors[:, :, 2], 0.0)

        # Round vertex positions to avoid floating-point precision issues
        # that create non-manifold edges (especially at angles like 45°)
        precision = 1e-6
        stl_mesh.vectors = np.round(stl_mesh.vectors / precision) * precision

        # Merge vertices that are very close together at z=0.
        # After Y-compensation, vertices at the same grid position but different
        # original heights end up at slightly different Y positions. This creates
        # non-manifold edges where side walls meet the back face.
        # Solution: snap z=0 vertices to grid based on their X position.
        stl_mesh = self._merge_z0_vertices(stl_mesh, pixel_size_mm)

        # Remove degenerate triangles created by clamping
        stl_mesh = self._remove_degenerate_triangles(stl_mesh)

        # Remove duplicate/overlapping faces that share the same vertices
        stl_mesh = self._remove_duplicate_faces(stl_mesh)

        return stl_mesh

    def _apply_vertical_rotation(self, stl_mesh: mesh.Mesh) -> mesh.Mesh:
        """Apply 90 degree rotation for vertical builds"""
        angle_rad = np.radians(90)
        cos_a = np.cos(angle_rad)
        sin_a = np.sin(angle_rad)

        for i in range(len(stl_mesh.vectors)):
            for j in range(3):
                y = stl_mesh.vectors[i][j][1]
                z = stl_mesh.vectors[i][j][2]
                stl_mesh.vectors[i][j][1] = y * cos_a - z * sin_a
                stl_mesh.vectors[i][j][2] = y * sin_a + z * cos_a

        # Translate so bottom sits on build plate
        min_z = stl_mesh.vectors[:, :, 2].min()
        stl_mesh.vectors[:, :, 2] -= min_z

        return stl_mesh

    def _remove_duplicate_faces(self, stl_mesh: mesh.Mesh) -> mesh.Mesh:
        """Remove duplicate faces that have the same vertices (regardless of order)"""
        seen_faces = set()
        valid_indices = []

        for i, triangle in enumerate(stl_mesh.vectors):
            # Create a canonical representation of the face
            # Sort vertices to create order-independent key
            verts = [tuple(np.round(v, 6)) for v in triangle]
            face_key = tuple(sorted(verts))

            if face_key not in seen_faces:
                seen_faces.add(face_key)
                valid_indices.append(i)

        if len(valid_indices) == len(stl_mesh.vectors):
            return stl_mesh  # No duplicates

        # Create new mesh without duplicates
        new_mesh = mesh.Mesh(np.zeros(len(valid_indices), dtype=mesh.Mesh.dtype))
        for new_idx, old_idx in enumerate(valid_indices):
            new_mesh.vectors[new_idx] = stl_mesh.vectors[old_idx]

        return new_mesh

    def _merge_z0_vertices(self, stl_mesh: mesh.Mesh, pixel_size_mm: float) -> mesh.Mesh:
        """Merge vertices at z=0 that should be at the same position.

        After Y-compensation, vertices at the same grid position but different
        original heights end up at slightly different Y positions. This merges
        them by grouping by X coordinate and using a consistent Y for each group.
        """
        z_tolerance = 1e-5

        # Build a map of X -> list of (triangle_idx, vertex_idx, y_value) for z=0 vertices
        x_groups = {}
        for i, triangle in enumerate(stl_mesh.vectors):
            for j, vertex in enumerate(triangle):
                if abs(vertex[2]) < z_tolerance:
                    # Snap X to pixel grid to group vertices
                    x_key = round(vertex[0] / pixel_size_mm) * pixel_size_mm
                    x_key = round(x_key, 6)  # Avoid float precision issues in key
                    if x_key not in x_groups:
                        x_groups[x_key] = []
                    x_groups[x_key].append((i, j, vertex[1]))

        # For each X group, find clusters of Y values and merge them
        # The merge tolerance needs to be large enough to cover the Y-compensation
        # differences from varying heights. At each X, all z=0 vertices should
        # merge into one of two groups: the back edge perimeter or the fan center.
        # Use a larger tolerance that covers typical height variations.
        merge_tolerance = pixel_size_mm * 2.0  # 2 pixels covers most height diffs

        for x_key, vertices in x_groups.items():
            if len(vertices) <= 1:
                continue

            # Sort by Y value
            y_values = sorted(set(round(v[2], 6) for v in vertices))

            # Group Y values that are close together
            y_clusters = []
            current_cluster = [y_values[0]]
            for y in y_values[1:]:
                if y - current_cluster[-1] < merge_tolerance:
                    current_cluster.append(y)
                else:
                    y_clusters.append(current_cluster)
                    current_cluster = [y]
            y_clusters.append(current_cluster)

            # Create mapping from original Y to canonical Y (mean of cluster)
            y_map = {}
            for cluster in y_clusters:
                canonical_y = sum(cluster) / len(cluster)
                canonical_y = round(canonical_y, 6)
                for y in cluster:
                    y_map[y] = canonical_y

            # Apply the mapping
            for tri_idx, vert_idx, orig_y in vertices:
                rounded_y = round(orig_y, 6)
                if rounded_y in y_map:
                    stl_mesh.vectors[tri_idx][vert_idx][1] = y_map[rounded_y]

        return stl_mesh

    def _merge_close_vertices(self, stl_mesh: mesh.Mesh, tolerance: float = 1e-6) -> mesh.Mesh:
        """Merge vertices that are very close together to avoid numeric precision issues"""
        # Flatten all vertices from all triangles
        all_vertices = stl_mesh.vectors.reshape(-1, 3)

        # Find unique vertices with tolerance
        unique_vertices = []
        vertex_map = {}  # maps original vertex tuple to unique index

        for v in all_vertices:
            v_tuple = tuple(np.round(v / tolerance) * tolerance)
            if v_tuple not in vertex_map:
                vertex_map[v_tuple] = len(unique_vertices)
                unique_vertices.append(v_tuple)

        # Reconstruct mesh with merged vertices
        for i, triangle in enumerate(stl_mesh.vectors):
            for j, vertex in enumerate(triangle):
                v_tuple = tuple(np.round(vertex / tolerance) * tolerance)
                # Update vertex to the canonical position
                stl_mesh.vectors[i][j] = np.array(v_tuple)

        return stl_mesh

    def _remove_degenerate_triangles(self, stl_mesh: mesh.Mesh) -> mesh.Mesh:
        """Remove triangles where vertices have collapsed to the same position"""
        tolerance = 1e-6
        valid_indices = []

        for i, triangle in enumerate(stl_mesh.vectors):
            v0, v1, v2 = triangle
            # Check if any two vertices are too close (degenerate)
            d01 = np.linalg.norm(v1 - v0)
            d12 = np.linalg.norm(v2 - v1)
            d20 = np.linalg.norm(v0 - v2)
            if d01 > tolerance and d12 > tolerance and d20 > tolerance:
                valid_indices.append(i)

        if len(valid_indices) == len(stl_mesh.vectors):
            return stl_mesh  # No degenerate triangles

        # Create new mesh with only valid triangles
        new_mesh = mesh.Mesh(np.zeros(len(valid_indices), dtype=mesh.Mesh.dtype))
        for new_idx, old_idx in enumerate(valid_indices):
            new_mesh.vectors[new_idx] = stl_mesh.vectors[old_idx]

        return new_mesh

    def save(self, filepath: str):
        """Save the mesh to an STL file"""
        if self.mesh is not None:
            self.mesh.save(filepath)
        else:
            raise ValueError("No mesh generated. Call generate_from_heightmap first.")

    def get_mesh(self) -> mesh.Mesh:
        """Get the current mesh"""
        return self.mesh
