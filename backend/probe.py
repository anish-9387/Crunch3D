import pymeshlab

ms = pymeshlab.MeshSet()
ms.create_sphere()

params = ms.filter_parameter_values(
    'meshing_decimation_quadric_edge_collapse'
)

print(params)