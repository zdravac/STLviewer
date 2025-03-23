"""
Parser for 3MF files
"""
import vtk
import zipfile
import xml.etree.ElementTree as ET
import numpy as np
from typing import List, Optional
from dataclasses import dataclass
from .object_manager import Color3MF

@dataclass
class Object3MF:
    """Represents a 3D object from a 3MF file"""
    name: str
    mesh: vtk.vtkPolyData
    transform: Optional[vtk.vtkMatrix4x4] = None
    color: Optional[Color3MF] = None

def load_3mf(file_path: str) -> List[Object3MF]:
    """Load objects from a 3MF file"""
    objects = []
    
    with zipfile.ZipFile(file_path, 'r') as zf:
        # Find and parse the main 3D model file
        model_file = None
        for name in zf.namelist():
            if name.endswith('3dmodel.model'):
                model_file = name
                break
        
        if not model_file:
            raise ValueError("No 3D model found in 3MF file")
        
        # Parse the XML content
        xml_content = zf.read(model_file)
        root = ET.fromstring(xml_content)
        
        # Define namespaces
        ns = {
            'm': 'http://schemas.microsoft.com/3dmanufacturing/material/2015/02',
            'p': 'http://schemas.microsoft.com/3dmanufacturing/production/2015/06'
        }
        
        # Process each mesh object
        resources = root.find('.//resources')
        if resources is not None:
            for obj in resources.findall('.//object'):
                mesh = obj.find('.//mesh')
                if mesh is not None:
                    # Create VTK mesh
                    vtk_mesh = vtk.vtkPolyData()
                    
                    # Process vertices
                    vertices = mesh.find('vertices')
                    points = vtk.vtkPoints()
                    for vertex in vertices.findall('vertex'):
                        x = float(vertex.get('x', 0))
                        y = float(vertex.get('y', 0))
                        z = float(vertex.get('z', 0))
                        points.InsertNextPoint(x, y, z)
                    vtk_mesh.SetPoints(points)
                    
                    # Process triangles
                    triangles = mesh.find('triangles')
                    cells = vtk.vtkCellArray()
                    for triangle in triangles.findall('triangle'):
                        v1 = int(triangle.get('v1', 0))
                        v2 = int(triangle.get('v2', 0))
                        v3 = int(triangle.get('v3', 0))
                        
                        tri = vtk.vtkTriangle()
                        tri.GetPointIds().SetId(0, v1)
                        tri.GetPointIds().SetId(1, v2)
                        tri.GetPointIds().SetId(2, v3)
                        cells.InsertNextCell(tri)
                    
                    vtk_mesh.SetPolys(cells)
                    
                    # Create object
                    name = obj.get('name', f'Object_{len(objects)}')
                    obj_3mf = Object3MF(name=name, mesh=vtk_mesh)
                    
                    # Process color if exists
                    color = obj.find('.//m:color', ns)
                    if color is not None:
                        color_value = color.get('value', '#FFFFFFFF')
                        if color_value.startswith('#'):
                            r = int(color_value[1:3], 16) / 255.0
                            g = int(color_value[3:5], 16) / 255.0
                            b = int(color_value[5:7], 16) / 255.0
                            a = int(color_value[7:9], 16) / 255.0 if len(color_value) > 7 else 1.0
                            obj_3mf.color = Color3MF(r, g, b, a)
                    
                    # Process transform if exists
                    transform = obj.find('.//transform')
                    if transform is not None:
                        matrix = transform.get('value', '1 0 0 0 0 1 0 0 0 0 1 0 0 0 0 1')
                        values = [float(x) for x in matrix.split()]
                        if len(values) == 16:
                            vtk_matrix = vtk.vtkMatrix4x4()
                            for i in range(4):
                                for j in range(4):
                                    vtk_matrix.SetElement(i, j, values[i*4 + j])
                            obj_3mf.transform = vtk_matrix
                    
                    objects.append(obj_3mf)
    
    return objects
