"""
LANbu Handy - Model Thumbnail Generation Service

This module provides thumbnail generation for 3D models using the Bambu Studio CLI
as a fallback when Three.js previews fail or for complex models.
"""

import logging
import tempfile
from pathlib import Path
from typing import Optional, Union

from app.slicer_service import BambuStudioCLIWrapper, CLIResult

logger = logging.getLogger(__name__)


class ThumbnailGenerationError(Exception):
    """Exception raised when thumbnail generation fails."""

    pass


class ThumbnailService:
    """
    Service for generating model thumbnails using Bambu Studio CLI.

    Provides thumbnail generation as a fallback for complex 3D models
    that may not render properly in Three.js viewers.
    """

    def __init__(self):
        """Initialize the thumbnail service."""
        self.cli_wrapper = BambuStudioCLIWrapper()
        self.temp_dir = Path(tempfile.gettempdir()) / "lanbu-handy" / "thumbnails"
        self.temp_dir.mkdir(parents=True, exist_ok=True)

    def generate_thumbnail(
        self,
        model_path: Union[str, Path],
        thumbnail_path: Optional[Union[str, Path]] = None,
        width: int = 300,
        height: int = 300,
    ) -> Path:
        """
        Generate a thumbnail image for a 3D model.

        Args:
            model_path: Path to the 3D model file (.stl, .3mf)
            thumbnail_path: Optional output path for the thumbnail
                          (auto-generated if None)
            width: Thumbnail width in pixels (default: 300)
            height: Thumbnail height in pixels (default: 300)

        Returns:
            Path to the generated thumbnail image

        Raises:
            ThumbnailGenerationError: If thumbnail generation fails
        """
        model_path = Path(model_path)

        if not model_path.exists():
            raise ThumbnailGenerationError(f"Model file not found: {model_path}")

        # Generate thumbnail path if not provided
        if thumbnail_path is None:
            thumbnail_name = f"{model_path.stem}_thumbnail.png"
            thumbnail_path = self.temp_dir / thumbnail_name
        else:
            thumbnail_path = Path(thumbnail_path)

        # Ensure thumbnail directory exists
        thumbnail_path.parent.mkdir(parents=True, exist_ok=True)

        # Try to generate thumbnail using Bambu Studio CLI
        # Note: This is a placeholder implementation since we need to determine
        # the actual CLI options for thumbnail generation
        try:
            result = self._generate_with_cli(model_path, thumbnail_path, width, height)

            if result.success and thumbnail_path.exists():
                logger.info(f"Thumbnail generated successfully: {thumbnail_path}")
                return thumbnail_path
            else:
                # Fallback: Generate a simple placeholder image
                return self._generate_placeholder_thumbnail(
                    model_path, thumbnail_path, width, height
                )

        except Exception as e:
            logger.warning(f"CLI thumbnail generation failed: {e}")
            # Fallback: Generate a simple placeholder image
            return self._generate_placeholder_thumbnail(
                model_path, thumbnail_path, width, height
            )

    def _generate_with_cli(
        self,
        model_path: Path,
        thumbnail_path: Path,
        width: int,
        height: int,
    ) -> CLIResult:
        """
        Generate thumbnail using Bambu Studio CLI.

        This is a placeholder implementation. The actual CLI options for
        thumbnail generation need to be determined from Bambu Studio documentation.
        """
        # For now, return a failed result to trigger fallback
        # TODO: Implement actual CLI thumbnail generation
        return CLIResult(
            exit_code=1,
            stdout="",
            stderr="Thumbnail generation not yet implemented in CLI wrapper",
            success=False,
        )

    def _generate_placeholder_thumbnail(
        self,
        model_path: Path,
        thumbnail_path: Path,
        width: int,
        height: int,
    ) -> Path:
        """
        Generate a placeholder thumbnail using PIL/Pillow.

        Creates a simple image with model information when CLI generation fails.
        """
        try:
            from PIL import Image, ImageDraw, ImageFont

            # Create a simple placeholder image
            img = Image.new("RGB", (width, height), color="#f5f5f5")
            draw = ImageDraw.Draw(img)

            # Draw a simple 3D cube icon
            self._draw_3d_icon(draw, width, height)

            # Add model name text
            model_name = model_path.stem
            if len(model_name) > 20:
                model_name = model_name[:17] + "..."

            # Try to use a font, fallback to default
            try:
                font = ImageFont.truetype(
                    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 12
                )
            except Exception:
                font = ImageFont.load_default()

            # Calculate text position (centered at bottom)
            text_bbox = draw.textbbox((0, 0), model_name, font=font)
            text_width = text_bbox[2] - text_bbox[0]
            text_height = text_bbox[3] - text_bbox[1]
            text_x = (width - text_width) // 2
            text_y = height - text_height - 10

            draw.text((text_x, text_y), model_name, fill="#333333", font=font)

            # Add file type indicator
            file_ext = model_path.suffix.upper()
            ext_text = f"{file_ext} Model"
            ext_bbox = draw.textbbox((0, 0), ext_text, font=font)
            ext_width = ext_bbox[2] - ext_bbox[0]
            ext_x = (width - ext_width) // 2
            ext_y = text_y - text_height - 5

            draw.text((ext_x, ext_y), ext_text, fill="#666666", font=font)

            # Save the image
            img.save(thumbnail_path, "PNG")

            logger.info(f"Generated placeholder thumbnail: {thumbnail_path}")
            return thumbnail_path

        except ImportError:
            # PIL not available, create a very simple fallback
            return self._generate_simple_fallback(thumbnail_path, width, height)
        except Exception as e:
            logger.error(f"Failed to generate placeholder thumbnail: {e}")
            return self._generate_simple_fallback(thumbnail_path, width, height)

    def _draw_3d_icon(self, draw, width: int, height: int):
        """Draw a simple 3D cube icon in the center of the image."""
        # Calculate cube dimensions
        cube_size = min(width, height) // 3
        center_x = width // 2
        center_y = height // 2 - 20  # Offset up to leave room for text

        # Cube corners (isometric view)
        offset = cube_size // 4

        # Front face
        front_corners = [
            (center_x - cube_size // 2, center_y - cube_size // 2),
            (center_x + cube_size // 2, center_y - cube_size // 2),
            (center_x + cube_size // 2, center_y + cube_size // 2),
            (center_x - cube_size // 2, center_y + cube_size // 2),
        ]

        # Back face (offset for 3D effect)
        back_corners = [
            (center_x - cube_size // 2 - offset, center_y - cube_size // 2 - offset),
            (center_x + cube_size // 2 - offset, center_y - cube_size // 2 - offset),
            (center_x + cube_size // 2 - offset, center_y + cube_size // 2 - offset),
            (center_x - cube_size // 2 - offset, center_y + cube_size // 2 - offset),
        ]

        # Draw back face
        draw.polygon(back_corners, fill="#cccccc", outline="#999999", width=2)

        # Draw connecting lines
        for i in range(4):
            draw.line([front_corners[i], back_corners[i]], fill="#999999", width=2)

        # Draw front face
        draw.polygon(front_corners, fill="#e0e0e0", outline="#666666", width=2)

    def _generate_simple_fallback(
        self, thumbnail_path: Path, width: int, height: int
    ) -> Path:
        """
        Generate a very simple text-based fallback when PIL is not available.

        Creates a minimal SVG image.
        """
        try:
            svg_content = f'''<?xml version="1.0" encoding="UTF-8"?>
<svg width="{width}" height="{height}" xmlns="http://www.w3.org/2000/svg">
  <rect width="{width}" height="{height}" fill="#f5f5f5"/>
  <rect x="{width//4}" y="{height//4}" width="{width//2}" height="{height//2}"
        fill="#e0e0e0" stroke="#999999" stroke-width="2"/>
  <text x="{width//2}" y="{height - 20}" text-anchor="middle"
        font-family="Arial, sans-serif" font-size="12" fill="#333333">
    3D Model Preview
  </text>
</svg>'''

            # Save as SVG (can be displayed in browsers)
            svg_path = thumbnail_path.with_suffix(".svg")
            with open(svg_path, "w") as f:
                f.write(svg_content)

            logger.info(f"Generated simple SVG fallback: {svg_path}")
            return svg_path

        except Exception as e:
            logger.error(f"Failed to generate simple fallback: {e}")
            raise ThumbnailGenerationError(
                f"All thumbnail generation methods failed: {e}"
            )

    def cleanup_old_thumbnails(self, max_age_hours: int = 24) -> None:
        """
        Clean up old thumbnail files.

        Args:
            max_age_hours: Maximum age of thumbnails to keep (default: 24 hours)
        """
        try:
            import time

            current_time = time.time()
            max_age_seconds = max_age_hours * 3600

            for thumbnail_file in self.temp_dir.glob("*"):
                if thumbnail_file.is_file():
                    file_age = current_time - thumbnail_file.stat().st_mtime
                    if file_age > max_age_seconds:
                        thumbnail_file.unlink()
                        logger.debug(f"Cleaned up old thumbnail: {thumbnail_file}")

        except Exception as e:
            logger.warning(f"Error during thumbnail cleanup: {e}")

    def get_thumbnail_path(self, model_path: Union[str, Path]) -> Path:
        """
        Get the expected thumbnail path for a model file.

        Args:
            model_path: Path to the model file

        Returns:
            Path where the thumbnail should be stored
        """
        model_path = Path(model_path)
        thumbnail_name = f"{model_path.stem}_thumbnail.png"
        return self.temp_dir / thumbnail_name

    def thumbnail_exists(self, model_path: Union[str, Path]) -> bool:
        """
        Check if a thumbnail already exists for a model.

        Args:
            model_path: Path to the model file

        Returns:
            True if thumbnail exists, False otherwise
        """
        thumbnail_path = self.get_thumbnail_path(model_path)
        return thumbnail_path.exists()


# Convenience functions
def generate_thumbnail(
    model_path: Union[str, Path],
    thumbnail_path: Optional[Union[str, Path]] = None,
    width: int = 300,
    height: int = 300,
) -> Path:
    """
    Generate a thumbnail for a 3D model.

    Args:
        model_path: Path to the 3D model file
        thumbnail_path: Optional output path for the thumbnail
        width: Thumbnail width in pixels (default: 300)
        height: Thumbnail height in pixels (default: 300)

    Returns:
        Path to the generated thumbnail
    """
    service = ThumbnailService()
    return service.generate_thumbnail(model_path, thumbnail_path, width, height)
