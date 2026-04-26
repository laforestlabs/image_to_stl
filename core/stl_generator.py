"""
STL file generator from height maps
"""
import numpy as np
from stl import mesh


class STLGenerator:
    """Generate STL mesh from height map"""

    def __init__(self):
        self.mesh = None

    def generate_from_heightmap(self, height_map: np.ndarray, pixel_size_mm: float = 0.1,
                                angle: float = 75.0, pixel_size_mm_y: float = None,
                                progress_cb=None) -> mesh.Mesh:
        """
        Generate an STL mesh from a height map

        Args:
            height_map: 2D numpy array where values represent heights in mm
            pixel_size_mm: X-axis vertex spacing in mm
            angle: Build angle in degrees (0=flat, 90=vertical)
            pixel_size_mm_y: Y-axis vertex spacing in mm (defaults to pixel_size_mm)

        Returns:
            numpy-stl Mesh object
        """
        if pixel_size_mm_y is None:
            pixel_size_mm_y = pixel_size_mm
        if progress_cb is None:
            progress_cb = lambda *_: None
        progress_cb(0.0, "Building vertex grid…")

        rows, cols = height_map.shape

        # Create top-surface vertices vectorized.
        # Flip Y so image top (row 0) maps to high Y, making the STL right-side-up.
        xs = np.arange(cols) * pixel_size_mm
        ys = (rows - 1 - np.arange(rows)) * pixel_size_mm_y
        xx, yy = np.meshgrid(xs, ys)
        vertices_top = np.stack([xx.ravel(), yy.ravel(), height_map.ravel()], axis=1).astype(float)

        # Choose mesh strategy based on angle
        # angle=0: simplified bottom (4 corners) - saves ~50% triangles
        # angle!=0: grid-based bottom - handles vertex clamping correctly
        use_simplified_bottom = (angle == 0)

        progress_cb(40.0, "Assembling triangles…")
        if use_simplified_bottom:
            stl_mesh = self._create_simplified_mesh(vertices_top, rows, cols, pixel_size_mm, pixel_size_mm_y)
        else:
            stl_mesh = self._create_grid_mesh(vertices_top, rows, cols, pixel_size_mm, pixel_size_mm_y)

        progress_cb(80.0, "Orienting for build plate…")
        if angle != 0 and angle != 90:
            stl_mesh = self._apply_angled_rotation(stl_mesh, angle, pixel_size_mm)
        elif angle == 90:
            stl_mesh = self._apply_vertical_rotation(stl_mesh)

        progress_cb(100.0, "Mesh ready")
        self.mesh = stl_mesh
        return stl_mesh

    def _create_simplified_mesh(self, vertices_top: np.ndarray, rows: int, cols: int,
                                pixel_size_mm: float, pixel_size_mm_y: float = None) -> mesh.Mesh:
        """Create mesh with simplified bottom (4 corners, 2 triangles) for angle=0"""
        if pixel_size_mm_y is None:
            pixel_size_mm_y = pixel_size_mm
        max_x = (cols - 1) * pixel_size_mm
        max_y = (rows - 1) * pixel_size_mm_y
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
        stl_mesh.vectors[:] = all_vertices[faces]

        return stl_mesh

    def _create_grid_mesh(self, vertices_top: np.ndarray, rows: int, cols: int,
                          pixel_size_mm: float, pixel_size_mm_y: float = None) -> mesh.Mesh:
        """Create mesh with simplified back face using perimeter fan triangulation.

        Uses perimeter fan for back face:
        - Full grid: (rows-1)*(cols-1)*2 ≈ 79k triangles for 200x200
        - Perimeter fan: 2*(rows-1) + 2*(cols-1) ≈ 800 triangles for 200x200

        The _merge_z0_vertices() function handles vertex alignment after rotation.
        """
        if pixel_size_mm_y is None:
            pixel_size_mm_y = pixel_size_mm
        max_x = (cols - 1) * pixel_size_mm
        max_y = (rows - 1) * pixel_size_mm_y

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
            y = (rows - 1 - i) * pixel_size_mm_y
            bottom_idx_map[(i, 0)] = len(vertices_bottom)
            vertices_bottom.append([x, y, 0])

        # Right edge (j=cols-1), excluding corners already added
        for i in range(1, rows - 1):
            x = max_x
            y = (rows - 1 - i) * pixel_size_mm_y
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
        stl_mesh.vectors[:] = all_vertices[faces]

        return stl_mesh

    def _apply_angled_rotation(self, stl_mesh: mesh.Mesh, angle: float, pixel_size_mm: float) -> mesh.Mesh:
        """Apply rotation and clamping for angled builds (0 < angle < 90)"""
        # Avoid exactly 45° which causes numeric precision issues
        # (sin(45°) = cos(45°) creates vertex coincidences)
        if abs(angle - 45.0) < 0.1:
            angle = 45.1

        # Record original Y span - this is the target height when laid flat
        original_height = stl_mesh.vectors[:, :, 1].max() - stl_mesh.vectors[:, :, 1].min()

        angle_rad = np.radians(angle)
        cos_a = np.cos(angle_rad)
        sin_a = np.sin(angle_rad)

        # Rotate around X-axis vectorized over all (triangle, vertex) pairs.
        ys = stl_mesh.vectors[..., 1].copy()
        zs = stl_mesh.vectors[..., 2].copy()
        stl_mesh.vectors[..., 1] = ys * cos_a - zs * sin_a
        stl_mesh.vectors[..., 2] = ys * sin_a + zs * cos_a

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

        # Scale Z so that the LAID-FLAT bounding box matches target height.
        # When laid flat, the axis-aligned bounding box is larger than the standing Z
        # due to the angled geometry. The extra comes from:
        # 1. flat_depth creating a shelf at the base
        # 2. The tilted front face extending the bounding box
        # Empirically: overhang ≈ flat_depth / sin(angle) + thickness * cos(angle) / sin(angle)
        # Simplified: we compute the actual bounding box expansion and compensate.
        current_z_max = stl_mesh.vectors[:, :, 2].max()
        current_y_extent = stl_mesh.vectors[:, :, 1].max() - stl_mesh.vectors[:, :, 1].min()
        if current_z_max > 0:
            # The laid-flat Y extent includes standing Z plus Y contribution from angle
            # Y_flat ≈ Z_standing + |Y_min_standing| where Y_min comes from clamping offset
            y_min_abs = abs(stl_mesh.vectors[:, :, 1].min())
            estimated_flat_y = current_z_max + y_min_abs
            target_z = original_height * (current_z_max / estimated_flat_y)
            scale_factor = target_z / current_z_max
            stl_mesh.vectors[:, :, 2] *= scale_factor

        return stl_mesh

    def _apply_vertical_rotation(self, stl_mesh: mesh.Mesh) -> mesh.Mesh:
        """Apply 90 degree rotation for vertical builds"""
        # 90° rotation around X: (y, z) -> (-z, y). cos=0, sin=1 — exact.
        ys = stl_mesh.vectors[..., 1].copy()
        zs = stl_mesh.vectors[..., 2].copy()
        stl_mesh.vectors[..., 1] = -zs
        stl_mesh.vectors[..., 2] = ys

        # Translate so bottom sits on build plate
        min_z = stl_mesh.vectors[:, :, 2].min()
        stl_mesh.vectors[:, :, 2] -= min_z

        return stl_mesh

    def _remove_duplicate_faces(self, stl_mesh: mesh.Mesh) -> mesh.Mesh:
        """Remove duplicate faces that have the same vertices (regardless of order)"""
        n = len(stl_mesh.vectors)
        if n == 0:
            return stl_mesh

        # Round to int keys to avoid float-precision misses.
        rounded = np.round(stl_mesh.vectors * 1e6).astype(np.int64)  # (N, 3, 3)

        # Sort the 3 vertices within each triangle so order-permuted faces
        # produce identical keys. Use a structured dtype so np.sort orders
        # vertices lexicographically as (x, y, z) tuples.
        rec_dtype = np.dtype([('x', 'i8'), ('y', 'i8'), ('z', 'i8')])
        recs = np.empty((n, 3), dtype=rec_dtype)
        recs['x'] = rounded[..., 0]
        recs['y'] = rounded[..., 1]
        recs['z'] = rounded[..., 2]
        recs.sort(axis=1)

        # Now the 3 vertices are canonically ordered; dedupe by row.
        keys = recs.view(np.int64).reshape(n, 9)
        _, unique_idx = np.unique(keys, axis=0, return_index=True)

        if len(unique_idx) == n:
            return stl_mesh

        unique_idx.sort()  # preserve original triangle order
        new_mesh = mesh.Mesh(np.zeros(len(unique_idx), dtype=mesh.Mesh.dtype))
        new_mesh.vectors[:] = stl_mesh.vectors[unique_idx]
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

    def _remove_degenerate_triangles(self, stl_mesh: mesh.Mesh) -> mesh.Mesh:
        """Remove triangles where vertices have collapsed to the same position"""
        tolerance = 1e-6
        v = stl_mesh.vectors  # (N, 3, 3)
        # Edge lengths for all triangles at once.
        d01 = np.linalg.norm(v[:, 1] - v[:, 0], axis=1)
        d12 = np.linalg.norm(v[:, 2] - v[:, 1], axis=1)
        d20 = np.linalg.norm(v[:, 0] - v[:, 2], axis=1)
        keep = (d01 > tolerance) & (d12 > tolerance) & (d20 > tolerance)

        if keep.all():
            return stl_mesh

        new_mesh = mesh.Mesh(np.zeros(int(keep.sum()), dtype=mesh.Mesh.dtype))
        new_mesh.vectors[:] = stl_mesh.vectors[keep]
        return new_mesh

    def generate_cylindrical_from_heightmap(self, height_map: np.ndarray,
                                            pixel_size_mm: float,
                                            pixel_size_mm_y: float = None,
                                            arc_degrees: float = 360.0,
                                            progress_cb=None) -> mesh.Mesh:
        """Generate a hollow cylindrical-shell mesh from a height map.

        The image wraps around a vertical cylinder. The user's width_mm
        (passed in via pixel_size_mm * (cols-1)) is the unrolled arc length
        at the inner surface, so the inner radius is arc_length / arc_radians.
        Per-pixel height_map values displace outward from r_inner.

        Full 360° wraps closed (no seam end caps); partial arcs add two flat
        radial walls at θ=0 and θ=arc_radians.

        progress_cb(percent: float, label: str) is invoked at coarse milestones
        between 0 and 100. Cylindrical generation produces ~2× the triangle
        count of a flat lithophane of similar resolution, so progress reporting
        is meaningful here.
        """
        if pixel_size_mm_y is None:
            pixel_size_mm_y = pixel_size_mm
        if progress_cb is None:
            progress_cb = lambda *_: None

        progress_cb(0.0, "Building vertex grid…")

        rows, cols = height_map.shape
        arc_radians = np.radians(arc_degrees)
        is_full = abs(arc_degrees - 360.0) < 1e-6

        arc_length = pixel_size_mm * (cols - 1)
        r_inner = arc_length / arc_radians

        if is_full:
            thetas = np.arange(cols) * (2.0 * np.pi / cols)
        else:
            thetas = np.arange(cols) * (arc_radians / (cols - 1))

        zs = (rows - 1 - np.arange(rows)) * pixel_size_mm_y

        cos_t = np.cos(thetas)[None, :]
        sin_t = np.sin(thetas)[None, :]
        r_outer = r_inner + height_map

        outer_x = r_outer * cos_t
        outer_y = r_outer * sin_t
        z_grid = np.broadcast_to(zs[:, None], (rows, cols))
        outer_verts = np.stack([outer_x, outer_y, z_grid], axis=-1).reshape(-1, 3)

        inner_xy_x = np.broadcast_to(r_inner * cos_t, (rows, cols))
        inner_xy_y = np.broadcast_to(r_inner * sin_t, (rows, cols))
        inner_verts = np.stack([inner_xy_x, inner_xy_y, z_grid], axis=-1).reshape(-1, 3)

        n_outer = rows * cols
        progress_cb(20.0, "Building face indices…")

        # Vectorized face-index construction: build the (i, j) grid for each
        # quad, then stack triangle vertices in the correct winding order.
        j_max = cols if is_full else cols - 1
        i_idx = np.arange(rows - 1)[:, None]   # (rows-1, 1)
        j_idx = np.arange(j_max)[None, :]      # (1, j_max)
        jp_idx = (j_idx + 1) % cols            # wraps for full 360°

        o_ij = i_idx * cols + j_idx                     # outer[i, j]
        o_inj = (i_idx + 1) * cols + j_idx              # outer[i+1, j]
        o_ijp = i_idx * cols + jp_idx                   # outer[i, j+1]
        o_injp = (i_idx + 1) * cols + jp_idx            # outer[i+1, j+1]
        n_ij = n_outer + o_ij
        n_inj = n_outer + o_inj
        n_ijp = n_outer + o_ijp
        n_injp = n_outer + o_injp

        def stack_tri(a, b, c):
            return np.stack([a, b, c], axis=-1).reshape(-1, 3)

        # Outer surface (outward normals).
        outer_t1 = stack_tri(o_ij, o_injp, o_ijp)
        outer_t2 = stack_tri(o_ij, o_inj, o_injp)
        # Inner surface (reversed winding -> inward-facing normals).
        inner_t1 = stack_tri(n_ij, n_ijp, n_injp)
        inner_t2 = stack_tri(n_ij, n_injp, n_inj)

        # Cap rings: top at i=0, bottom at i=rows-1.
        j_cap = np.arange(j_max)
        jp_cap = (j_cap + 1) % cols
        last_row = rows - 1
        top_t1 = np.stack([j_cap, jp_cap, n_outer + jp_cap], axis=-1)
        top_t2 = np.stack([j_cap, n_outer + jp_cap, n_outer + j_cap], axis=-1)
        bot_t1 = np.stack([last_row * cols + j_cap,
                           n_outer + last_row * cols + jp_cap,
                           last_row * cols + jp_cap], axis=-1)
        bot_t2 = np.stack([last_row * cols + j_cap,
                           n_outer + last_row * cols + j_cap,
                           n_outer + last_row * cols + jp_cap], axis=-1)

        face_chunks = [outer_t1, outer_t2, inner_t1, inner_t2,
                       top_t1, top_t2, bot_t1, bot_t2]

        if not is_full:
            # Partial-arc end walls. Left cap at j=0 has outward = -tangent(0);
            # right cap at j=cols-1 has outward = +tangent(arc).
            i_wall = np.arange(rows - 1)
            o_wall_top = i_wall * cols
            o_wall_bot = (i_wall + 1) * cols
            n_wall_top = n_outer + o_wall_top
            n_wall_bot = n_outer + o_wall_bot
            left_t1 = np.stack([o_wall_top, n_wall_top, n_wall_bot], axis=-1)
            left_t2 = np.stack([o_wall_top, n_wall_bot, o_wall_bot], axis=-1)
            last_col = cols - 1
            o_rt = i_wall * cols + last_col
            o_rb = (i_wall + 1) * cols + last_col
            n_rt = n_outer + o_rt
            n_rb = n_outer + o_rb
            right_t1 = np.stack([o_rt, o_rb, n_rb], axis=-1)
            right_t2 = np.stack([o_rt, n_rb, n_rt], axis=-1)
            face_chunks.extend([left_t1, left_t2, right_t1, right_t2])

        faces = np.concatenate(face_chunks, axis=0).astype(np.int64)
        progress_cb(60.0, "Assembling triangles…")

        all_verts = np.vstack([outer_verts, inner_verts])
        precision = 1e-6
        all_verts = np.round(all_verts / precision) * precision

        # Vectorized vertex copy — a single fancy-indexing operation replaces
        # the previous per-triangle Python loop (≈13× faster on a 320×240 grid).
        stl_mesh = mesh.Mesh(np.zeros(faces.shape[0], dtype=mesh.Mesh.dtype))
        stl_mesh.vectors[:] = all_verts[faces]
        progress_cb(100.0, "Mesh ready")

        self.mesh = stl_mesh
        return stl_mesh

    def save(self, filepath: str):
        """Save the mesh to an STL file"""
        if self.mesh is not None:
            self.mesh.save(filepath)
        else:
            raise ValueError("No mesh generated. Call generate_from_heightmap first.")

    def get_mesh(self) -> mesh.Mesh:
        """Get the current mesh"""
        return self.mesh
