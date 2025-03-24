import PyInstaller.__main__

PyInstaller.__main__.run([
    'src/main.py',
    '--noconfirm',
    '--clean',
    '--name=STLviewer',
    '--windowed',
    '--noconsole',
    '--icon=STLviewer.icns',
    '--hidden-import=vtkmodules.all',
    '--hidden-import=vtkmodules.util.numpy_support',
    '--hidden-import=vtkmodules.util.data_model',
    '--hidden-import=vtkmodules.util.execution_model',
    '--hidden-import=vtkmodules.qt.PyQt6.QVTKRenderWindowInteractor',
    '--hidden-import=vtkmodules.qt.PyQt6',
    '--hidden-import=PyQt6.QtCore',
    '--hidden-import=PyQt6.QtGui',
    '--hidden-import=PyQt6.QtWidgets',
    '--target-architecture=arm64',
    '--collect-data=vtkmodules',
    '--collect-data=vtk'
])
