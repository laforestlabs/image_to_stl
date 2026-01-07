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

        # Create vertices for the bottom surface
        vertices_bottom = []
        for i in range(rows):
            for j in range(cols):
                x = j * pixel_size_mm
                y = (rows - 1 - i) * pixel_size_mm
                z = 0  # Bottom is at z=0
                vertices_bottom.append([x, y, z])

        vertices_top = np.array(vertices_top)
        vertices_bottom = np.array(vertices_bottom)

        # Generate faces
        faces = []

        # Top surface faces
        for i in range(rows - 1):
            for j in range(cols - 1):
                # Each quad becomes 2 triangles
                idx = i * cols + j

                # Triangle 1
                faces.append([idx, idx + cols, idx + 1])
                # Triangle 2
                faces.append([idx + 1, idx + cols, idx + cols + 1])

        # Bottom surface faces (reversed winding for correct normals)
        offset = rows * cols
        for i in range(rows - 1):
            for j in range(cols - 1):
                idx = offset + i * cols + j

                # Triangle 1
                faces.append([idx, idx + 1, idx + cols])
                # Triangle 2
                faces.append([idx + 1, idx + cols + 1, idx + cols])

        # Side faces (walls)
        # Left edge
        for i in range(rows - 1):
            top1 = i * cols
            top2 = (i + 1) * cols
            bot1 = offset + i * cols
            bot2 = offset + (i + 1) * cols
            faces.append([top1, bot1, top2])
            faces.append([top2, bot1, bot2])

        # Right edge
        for i in range(rows - 1):
            top1 = i * cols + (cols - 1)
            top2 = (i + 1) * cols + (cols - 1)
            bot1 = offset + i * cols + (cols - 1)
            bot2 = offset + (i + 1) * cols + (cols - 1)
            faces.append([top1, top2, bot1])
            faces.append([top2, bot2, bot1])

        # Front edge
        for j in range(cols - 1):
            top1 = j
            top2 = j + 1
            bot1 = offset + j
            bot2 = offset + j + 1
            faces.append([top1, top2, bot1])
            faces.append([top2, bot2, bot1])

        # Back edge
        for j in range(cols - 1):
            top1 = (rows - 1) * cols + j
            top2 = (rows - 1) * cols + j + 1
            bot1 = offset + (rows - 1) * cols + j
            bot2 = offset + (rows - 1) * cols + j + 1
            faces.append([top1, bot1, top2])
            faces.append([top2, bot1, bot2])

        faces = np.array(faces)

        # Combine top and bottom vertices
        all_vertices = np.vstack([vertices_top, vertices_bottom])

        # Create the mesh
        stl_mesh = mesh.Mesh(np.zeros(faces.shape[0], dtype=mesh.Mesh.dtype))
        for i, face in enumerate(faces):
            for j in range(3):
                stl_mesh.vectors[i][j] = all_vertices[face[j]]

        # Apply rotation around X-axis if angle is not 0
        if angle != 0 and angle != 90:
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

            # For angles between 0 and 90, create a flat bottom
            min_z = stl_mesh.vectors[:, :, 2].min()
            max_z = stl_mesh.vectors[:, :, 2].max()
            model_height = max_z - min_z

            # Calculate how much to lower for good flat bottom contact
            target_flat_width = 2.0  # mm
            flat_depth = max(target_flat_width * np.sin(angle_rad), model_height * 0.01)

            # Move mesh so that min_z + flat_depth = 0
            stl_mesh.vectors[:, :, 2] -= (min_z + flat_depth)

            # Simple vertex clamping approach - clamp all vertices below z=0 to z=0
            # This creates a flat bottom by collapsing the bottom of the mesh to the z=0 plane
            # The mesh remains manifold because we preserve all triangle connectivity
            stl_mesh.vectors[:, :, 2] = np.maximum(stl_mesh.vectors[:, :, 2], 0.0)

        elif angle == 90:
            # Vertical orientation - rotate but no clipping needed
            angle_rad = np.radians(angle)
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

        # For angle == 0, no rotation needed, mesh already has flat bottom

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
