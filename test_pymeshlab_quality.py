import pymeshlab

ms = pymeshlab.MeshSet()
# load a small mesh
with open("cube.obj", "w") as f:
    f.write("v 0 0 0\nv 1 0 0\nv 1 1 0\nv 0 1 0\nv 0 0 1\nv 1 0 1\nv 1 1 1\nv 0 1 1\nf 1 2 3 4\nf 5 6 7 8\n")
ms.load_new_mesh("cube.obj")

# check default quality
mesh = ms.current_mesh()
try:
    print("Default Quality:", mesh.vertex_scalar_array())
except Exception as e:
    print("No quality:", e)

# Run decimation
ms.apply_filter(
    "meshing_decimation_quadric_edge_collapse",
    targetfacenum=1,
    qualityweight=True,
)
print("Decimation finished.")
