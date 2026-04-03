import pymeshlab
import os
from pathlib import Path
from ..models.schemas import MeshStats


def analyze_mesh(filepath: str | Path) -> MeshStats:
    filepath = str(filepath)
    ms = pymeshlab.MeshSet()
    ms.load_new_mesh(filepath)
    mesh = ms.current_mesh()

    vertex_count = mesh.vertex_number()
    face_count = mesh.face_number()
    file_size = os.path.getsize(filepath)

    has_uvs = mesh.has_wedge_tex_coord() if hasattr(mesh, 'has_wedge_tex_coord') else False
    has_normals = mesh.has_vertex_normal() if hasattr(mesh, 'has_vertex_normal') else False

    bb = mesh.bounding_box()
    bounding_box = {
        "min": [bb.min()[0], bb.min()[1], bb.min()[2]],
        "max": [bb.max()[0], bb.max()[1], bb.max()[2]],
        "diagonal": bb.diagonal(),
    }

    return MeshStats(
        vertex_count=vertex_count,
        face_count=face_count,
        file_size_bytes=file_size,
        file_size_mb=round(file_size / (1024 * 1024), 3),
        has_uvs=has_uvs,
        has_normals=has_normals,
        bounding_box=bounding_box,
    )
