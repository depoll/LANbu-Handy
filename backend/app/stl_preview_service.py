"""
STL Preview Generation Service

Generates preview images for STL files using numpy-stl and matplotlib.
This provides a headless alternative to Bambu Studio CLI for thumbnail generation.
"""

import logging
from pathlib import Path
from typing import Optional

# Try to import matplotlib with proper error handling
try:
    import matplotlib
    import matplotlib.pyplot as plt
    import numpy as np
    from mpl_toolkits.mplot3d import Axes3D
    from stl import mesh

    # Use Agg backend for headless operation
    matplotlib.use("Agg")
    MATPLOTLIB_AVAILABLE = True

except ImportError as e:
    logger = logging.getLogger(__name__)
    logger.warning(f"matplotlib or dependencies not available: {e}")
    MATPLOTLIB_AVAILABLE = False

    # Mock the imports for graceful degradation
    matplotlib = None
    plt = None
    np = None
    Axes3D = None
    mesh = None

logger = logging.getLogger(__name__)


class STLPreviewService:
    """Service for generating preview images from STL files."""

    def __init__(self):
        """Initialize the STL preview service."""
        if not MATPLOTLIB_AVAILABLE:
            logger.warning(
                "STL preview service initialized without matplotlib - "
                "previews will not be available"
            )

    def generate_preview(
        self,
        stl_file_path: Path,
        output_path: Optional[Path] = None,
        image_size: tuple = (800, 600),
        dpi: int = 100,
    ) -> Path:
        """
        Generate an isometric preview image from an STL file.

        Args:
            stl_file_path: Path to the STL file
            output_path: Path for output PNG file (optional, auto-generated if None)
            image_size: Image size in pixels (width, height)
            dpi: DPI for the output image

        Returns:
            Path to the generated preview image

        Raises:
            FileNotFoundError: If STL file doesn't exist
            ValueError: If STL file is invalid
            RuntimeError: If preview generation fails
        """
        if not MATPLOTLIB_AVAILABLE:
            raise RuntimeError(
                "STL preview generation requires matplotlib and dependencies"
            )

        if not stl_file_path.exists():
            raise FileNotFoundError(f"STL file not found: {stl_file_path}")

        if output_path is None:
            output_path = stl_file_path.with_suffix(".png")

        try:
            # Load the STL mesh
            logger.info(f"Loading STL file: {stl_file_path}")
            stl_mesh = mesh.Mesh.from_file(str(stl_file_path))

            if len(stl_mesh.vectors) == 0:
                raise ValueError(f"STL file contains no triangles: {stl_file_path}")

            # Create the isometric preview
            logger.info(f"Generating isometric preview: {output_path}")
            self._create_preview_image(stl_mesh, output_path, image_size, dpi)

            logger.info(f"Preview generated successfully: {output_path}")
            return output_path

        except Exception as e:
            logger.error(f"Failed to generate STL preview: {e}")
            raise RuntimeError(f"STL preview generation failed: {e}") from e

    def _create_preview_image(
        self, stl_mesh: mesh.Mesh, output_path: Path, image_size: tuple, dpi: int
    ) -> None:
        """Create and save the preview image."""
        # Calculate figure size in inches
        fig_width = image_size[0] / dpi
        fig_height = image_size[1] / dpi

        # Create figure and 3D axis
        fig = plt.figure(figsize=(fig_width, fig_height), dpi=dpi)
        ax = fig.add_subplot(111, projection="3d")

        # Extract vertices from the mesh
        vertices = stl_mesh.vectors.reshape(-1, 3)

        # Create triangles for plotting
        triangles = vertices.reshape(-1, 3, 3)

        # Plot the mesh
        from mpl_toolkits.mplot3d.art3d import Poly3DCollection

        collection = Poly3DCollection(triangles)
        collection.set_facecolor([0.8, 0.8, 1.0, 0.8])  # Light blue with transparency
        collection.set_edgecolor([0.2, 0.2, 0.6, 0.6])  # Darker blue edges
        collection.set_linewidth(0.1)

        ax.add_collection3d(collection)

        # Set equal aspect ratio and fit the model
        max_range = (
            np.array(
                [
                    vertices[:, 0].max() - vertices[:, 0].min(),
                    vertices[:, 1].max() - vertices[:, 1].min(),
                    vertices[:, 2].max() - vertices[:, 2].min(),
                ]
            ).max()
            / 2.0
        )

        mid_x = (vertices[:, 0].max() + vertices[:, 0].min()) * 0.5
        mid_y = (vertices[:, 1].max() + vertices[:, 1].min()) * 0.5
        mid_z = (vertices[:, 2].max() + vertices[:, 2].min()) * 0.5

        ax.set_xlim(mid_x - max_range, mid_x + max_range)
        ax.set_ylim(mid_y - max_range, mid_y + max_range)
        ax.set_zlim(mid_z - max_range, mid_z + max_range)

        # Set isometric view angle
        ax.view_init(elev=30, azim=45)

        # Remove axes for cleaner look
        ax.set_axis_off()

        # Set background color
        fig.patch.set_facecolor("white")

        # Save the image
        plt.savefig(
            output_path,
            dpi=dpi,
            bbox_inches="tight",
            pad_inches=0.1,
            facecolor="white",
            edgecolor="none",
        )
        plt.close(fig)
