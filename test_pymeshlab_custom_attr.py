import pymeshlab
import numpy as np

with open("cube.obj", "w") as f:
    f.write("v 0 0 0\nv 1 0 0\nv 1 1 0\nv 0 1 0\nf 1 2 3\nf 1 3 4\n")

ms = pymeshlab.MeshSet()
ms.load_new_mesh("cube.obj")
mesh = ms.current_mesh()

n_verts = mesh.vertex_number()
importance = np.linspace(0.1, 0.9, n_verts).astype(np.float64)

try:
    mesh.add_vertex_custom_scalar_attribute(importance, "my_importance")
    ms.apply_filter("compute_scalar_by_function_per_vertex", q="my_importance", normalize=False)
    print("Quality array:", mesh.vertex_scalar_array())
except Exception as e:
    print("Error:", e)
