import pymeshlab
ms = pymeshlab.MeshSet()
ms.load_new_mesh("cube.obj")
mesh = ms.current_mesh()
print([m for m in dir(mesh) if "quality" in m or "color" in m or "scalar" in m or "update" in m])
