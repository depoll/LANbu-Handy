"""
Enhanced 3MF Repair Service for Three.js Compatibility

This module provides enhanced functionality to repair Bambu Studio 3MF files
for better compatibility with Three.js ThreeMFLoader by properly merging
external object mesh data and fixing vertex/triangle references.
"""

import logging
import tempfile
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path
from typing import List, Tuple

logger = logging.getLogger(__name__)


class ThreeMFRepairError(Exception):
    """Exception raised when 3MF repair operations fail."""

    pass


class EnhancedThreeMFRepairService:
    """Enhanced service to repair Bambu Studio 3MF files for Three.js compatibility."""

    def __init__(self):
        """Initialize the repair service."""
        self.default_namespace = (
            "http://schemas.microsoft.com/3dmanufacturing/core/2015/02"
        )
        self.production_namespace = (
            "http://schemas.microsoft.com/3dmanufacturing/production/2015/06"
        )
        self.bambu_namespace = "http://schemas.bambulab.com/package/2021"

        self.temp_dir = Path(tempfile.gettempdir()) / "lanbu-handy" / "repaired-3mf"
        self.temp_dir.mkdir(parents=True, exist_ok=True)

    def get_repaired_3mf_path(self, original_path: Path) -> Path:
        """Get the path where a repaired 3MF file would be stored."""
        return self.temp_dir / f"repaired_{original_path.name}"

    def needs_repair(self, file_path: Path) -> bool:
        """Check if a 3MF file needs repair."""
        if file_path.suffix.lower() != ".3mf":
            return False

        try:
            with zipfile.ZipFile(file_path, "r") as zf:
                # Check for external object files
                object_files = [
                    f
                    for f in zf.namelist()
                    if f.startswith("3D/Objects/") and f.endswith(".model")
                ]

                # Also check if main model has components referencing external objects
                if object_files:
                    return True

                # Check main model for component references
                try:
                    with zf.open("3D/3dmodel.model") as model_file:
                        content = model_file.read().decode("utf-8")
                        return "<component" in content and "objectid=" in content
                except Exception:
                    pass

                return False

        except Exception as e:
            logger.warning(f"Error checking if 3MF needs repair: {e}")
            return False

    def repair_3mf_file(self, input_path: Path) -> Path:
        """
        Repair a 3MF file by merging all mesh data into a single object.

        This creates a simplified 3MF that Three.js can properly load.
        """
        output_path = self.get_repaired_3mf_path(input_path)

        # Use cached version if available
        if (
            output_path.exists()
            and output_path.stat().st_mtime > input_path.stat().st_mtime
        ):
            logger.debug(f"Using existing repaired 3MF file: {output_path}")
            return output_path

        try:
            logger.info(f"Repairing 3MF file for Three.js: {input_path}")

            with zipfile.ZipFile(input_path, "r") as input_zip:
                # Extract all mesh data from all sources
                all_vertices, all_triangles = self._extract_all_mesh_data(input_zip)

                if not all_vertices:
                    logger.warning("No mesh data found, copying original file")
                    output_path.write_bytes(input_path.read_bytes())
                    return output_path

                # Create simplified 3MF with single merged object
                simplified_model = self._create_simplified_model(
                    all_vertices, all_triangles
                )

                # Create repaired 3MF file
                self._create_simplified_3mf(input_zip, simplified_model, output_path)

                logger.info(f"Successfully created simplified 3MF: {output_path}")
                return output_path

        except Exception as e:
            logger.error(f"Error repairing 3MF file {input_path}: {e}")
            raise ThreeMFRepairError(f"Failed to repair 3MF file: {str(e)}")

    def _extract_all_mesh_data(
        self, zip_file: zipfile.ZipFile
    ) -> Tuple[List[Tuple[float, float, float]], List[Tuple[int, int, int]]]:
        """
        Extract all mesh data from all model files and merge into single lists.

        Returns:
            Tuple of (vertices, triangles) where vertices is a list of (x,y,z) tuples
            and triangles is a list of (v1,v2,v3) index tuples
        """
        all_vertices = []
        all_triangles = []
        vertex_offset = 0

        # Process main model file
        try:
            with zip_file.open("3D/3dmodel.model") as model_file:
                content = model_file.read().decode("utf-8")
                vertices, triangles = self._extract_mesh_from_content(content)
                all_vertices.extend(vertices)
                all_triangles.extend(triangles)
                vertex_offset = len(all_vertices)
        except Exception as e:
            logger.warning(f"Error processing main model: {e}")

        # Process all external object files
        object_files = [
            f
            for f in zip_file.namelist()
            if f.startswith("3D/Objects/") and f.endswith(".model")
        ]

        for obj_file in sorted(object_files):  # Sort for consistent processing
            try:
                with zip_file.open(obj_file) as model_file:
                    content = model_file.read().decode("utf-8")
                    vertices, triangles = self._extract_mesh_from_content(content)

                    # Add vertices
                    all_vertices.extend(vertices)

                    # Add triangles with offset adjustment
                    for v1, v2, v3 in triangles:
                        all_triangles.append(
                            (v1 + vertex_offset, v2 + vertex_offset, v3 + vertex_offset)
                        )

                    vertex_offset = len(all_vertices)
                    logger.debug(f"Extracted {len(vertices)} vertices from {obj_file}")

            except Exception as e:
                logger.warning(f"Error processing {obj_file}: {e}")

        return all_vertices, all_triangles

    def _extract_mesh_from_content(
        self, content: str
    ) -> Tuple[List[Tuple[float, float, float]], List[Tuple[int, int, int]]]:
        """Extract vertices and triangles from model XML content."""
        vertices = []
        triangles = []

        try:
            root = ET.fromstring(content)

            # Find all mesh elements
            for mesh in root.findall(f".//{{{self.default_namespace}}}mesh"):
                # Extract vertices
                vertices_elem = mesh.find(f"{{{self.default_namespace}}}vertices")
                if vertices_elem is not None:
                    for vertex in vertices_elem.findall(
                        f"{{{self.default_namespace}}}vertex"
                    ):
                        x = float(vertex.get("x", 0))
                        y = float(vertex.get("y", 0))
                        z = float(vertex.get("z", 0))
                        vertices.append((x, y, z))

                # Extract triangles
                triangles_elem = mesh.find(f"{{{self.default_namespace}}}triangles")
                if triangles_elem is not None:
                    for triangle in triangles_elem.findall(
                        f"{{{self.default_namespace}}}triangle"
                    ):
                        v1 = int(triangle.get("v1", 0))
                        v2 = int(triangle.get("v2", 0))
                        v3 = int(triangle.get("v3", 0))
                        triangles.append((v1, v2, v3))

        except Exception as e:
            logger.error(f"Error extracting mesh data: {e}")

        return vertices, triangles

    def _create_simplified_model(
        self,
        vertices: List[Tuple[float, float, float]],
        triangles: List[Tuple[int, int, int]],
    ) -> str:
        """Create a simplified 3MF model XML with single merged object."""

        # Create root element with namespaces
        root = ET.Element(
            "model",
            attrib={
                "unit": "millimeter",
                "xml:lang": "en-US",
                "xmlns": self.default_namespace,
            },
        )

        # Add metadata
        ET.SubElement(root, "metadata", name="Application").text = (
            "LANbu Handy Repair Service"
        )

        # Add resources
        resources = ET.SubElement(root, "resources")

        # Create single object with all merged geometry
        obj = ET.SubElement(resources, "object", attrib={"id": "1", "type": "model"})

        # Add mesh
        mesh = ET.SubElement(obj, "mesh")

        # Add vertices
        vertices_elem = ET.SubElement(mesh, "vertices")
        for x, y, z in vertices:
            ET.SubElement(
                vertices_elem,
                "vertex",
                attrib={"x": f"{x:.6f}", "y": f"{y:.6f}", "z": f"{z:.6f}"},
            )

        # Add triangles
        triangles_elem = ET.SubElement(mesh, "triangles")
        for v1, v2, v3 in triangles:
            ET.SubElement(
                triangles_elem,
                "triangle",
                attrib={"v1": str(v1), "v2": str(v2), "v3": str(v3)},
            )

        # Add build item
        build = ET.SubElement(root, "build")
        ET.SubElement(build, "item", attrib={"objectid": "1"})

        # Convert to string
        ET.register_namespace("", self.default_namespace)
        xml_str = ET.tostring(root, encoding="unicode")

        # Add XML declaration
        return f'<?xml version="1.0" encoding="UTF-8"?>\n{xml_str}'

    def _create_simplified_3mf(
        self,
        input_zip: zipfile.ZipFile,
        simplified_model: str,
        output_path: Path,
    ):
        """Create a simplified 3MF file that Three.js can load."""

        with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as output_zip:
            # Create minimal content types
            content_types = (
                '<?xml version="1.0" encoding="UTF-8"?>\n'
                '<Types xmlns="http://schemas.openxmlformats.org/package'
                '/2006/content-types">\n'
                '    <Default Extension="rels" '
                'ContentType="application/vnd.openxmlformats-package'
                '.relationships+xml"/>\n'
                '    <Default Extension="model" '
                'ContentType="application/'
                'vnd.ms-package.3dmanufacturing-3dmodel+xml"/>\n'
                '    <Default Extension="png" ContentType="image/png"/>\n'
                "</Types>"
            )
            output_zip.writestr("[Content_Types].xml", content_types)

            # Create minimal relationships
            rels = (
                '<?xml version="1.0" encoding="UTF-8"?>\n'
                "<Relationships "
                'xmlns="http://schemas.openxmlformats.org/package'
                '/2006/relationships">\n'
                '    <Relationship Target="/3D/3dmodel.model" Id="rel0" '
                'Type="http://schemas.microsoft.com/'
                '3dmanufacturing/2013/01/3dmodel"/>\n'
                "</Relationships>"
            )
            output_zip.writestr("_rels/.rels", rels)

            # Create model relationships (empty but required)
            model_rels = """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
</Relationships>"""
            output_zip.writestr("3D/_rels/3dmodel.model.rels", model_rels)

            # Write the simplified model
            output_zip.writestr("3D/3dmodel.model", simplified_model.encode("utf-8"))

            # Copy thumbnails if available
            for file_name in input_zip.namelist():
                if file_name.startswith("Auxiliaries/") and file_name.endswith(".png"):
                    try:
                        with input_zip.open(file_name) as source_file:
                            output_zip.writestr(file_name, source_file.read())
                    except Exception:
                        pass  # Thumbnails are optional

    def cleanup_old_repaired_files(self, max_age_hours: int = 24):
        """Clean up old repaired files."""
        try:
            import time

            current_time = time.time()
            max_age_seconds = max_age_hours * 3600

            for file_path in self.temp_dir.glob("repaired_*.3mf"):
                file_age = current_time - file_path.stat().st_mtime
                if file_age > max_age_seconds:
                    file_path.unlink()
                    logger.debug(f"Cleaned up old repaired file: {file_path}")

        except Exception as e:
            logger.warning(f"Error during cleanup: {e}")
