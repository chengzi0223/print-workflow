"""Read-only STL checks. No mesh repair and no claim of physical printability."""
import hashlib
from pathlib import Path

import numpy as np
import trimesh


# 步骤5：只读检查；不悄悄修网格，不以基础检查代替壁厚/装配验证。
def check_stl(path):
    path = Path(path).resolve()
    if path.suffix.lower() != '.stl':
        raise ValueError('网格自动检查目前只接受 STL；STEP/3MF 请同时导出对应 STL。')
    mesh = trimesh.load_mesh(path, process=False)
    if not isinstance(mesh, trimesh.Trimesh) or not len(mesh.faces):
        raise ValueError('文件不包含可检查的三角网格。')
    finite = bool(np.isfinite(mesh.vertices).all())
    if not finite:
        raise ValueError('网格包含非有限坐标。')
    # STL repeats vertices per triangle: weld a copy for topology analysis only.
    topo = mesh.copy()
    topo.merge_vertices(digits_vertex=8)
    ordered = np.sort(topo.faces, axis=1)
    duplicate = int(len(ordered) - len(np.unique(ordered, axis=0)))
    degenerate = int(np.count_nonzero(mesh.area_faces <= 1e-12))
    _, edge_counts = np.unique(topo.edges_sorted, axis=0, return_counts=True)
    boundary = int(np.count_nonzero(edge_counts == 1))
    nonmanifold = int(np.count_nonzero(edge_counts > 2))
    # Count face-connected components without optional scipy/networkx.
    parents = list(range(len(topo.faces)))
    def root(i):
        while parents[i] != i:
            parents[i] = parents[parents[i]]
            i = parents[i]
        return i
    for a, b in topo.face_adjacency:
        parents[root(int(a))] = root(int(b))
    components = len({root(i) for i in range(len(parents))})
    ok = bool(topo.is_watertight and topo.is_winding_consistent and
              topo.volume > 0 and not duplicate and not degenerate and not nonmanifold)
    return {
        'file': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
        'units': 'mm assumed for STL; compare with CAD dimensions',
        'bounds_mm': mesh.bounds.tolist(), 'dimensions_mm': mesh.extents.tolist(),
        'triangles': len(mesh.faces), 'components': components,
        'watertight': bool(topo.is_watertight),
        'winding_consistent': bool(topo.is_winding_consistent),
        'signed_volume_mm3': float(topo.volume),
        'boundary_edges': boundary, 'nonmanifold_edges': nonmanifold,
        'duplicate_triangles': duplicate, 'degenerate_triangles': degenerate,
        'basic_mesh_checks_passed': ok,
        'not_verified': ['self_intersections', 'minimum_wall_thickness', 'CAD_dimensions',
                         'interference_and_fit', 'support_removability', 'bed_adhesion',
                         'physical_print_and_assembly'],
    }
