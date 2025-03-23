"""
Main viewer class for STL/3MF viewer
"""
import vtk
from PyQt6.QtCore import QObject, pyqtSignal
from dataclasses import dataclass
from typing import Dict, Optional, List
import os
import traceback
from .parser_3mf import load_3mf, Object3MF
from .screenshot_tools import ScreenshotTools
from .object_manager import ObjectProperties

@dataclass
class ModelStats:
    """Statistics about a 3D model"""
    vertices: int
    faces: int
    volume: float
    surface_area: float

class ModelViewer(QObject):
    """Main viewer class for 3D models"""
    model_loaded = pyqtSignal(bool)
    model_stats_updated = pyqtSignal(object)  # ModelStats
    object_properties_changed = pyqtSignal(object)  # ObjectProperties

    def __init__(self, renderer: vtk.vtkRenderer, parent_widget=None):
        super().__init__()
        self.renderer = renderer
        self.parent_widget = parent_widget
        self.actors: Dict[str, vtk.vtkActor] = {}
        
        # Initialize default viewer settings
        self._model_color = (1.0, 1.0, 1.0)  # Default white color
        self._show_axes = True  # Default state
        self._current_intensity = 1.0  # Default light intensity
        self._gradient_enabled = False  # Default background state
        
        # Store base light intensities for reference
        self._base_intensities = {
            'ambient': 0.3,
            'key': 0.6,
            'fill': 0.4,
            'rim': 0.3
        }
        
        # Initialize axes orientation widget
        self._axes_widget = None
        self._axes_actor = None
        self._axes_initialized = False
        
        # Initialize tools
        # Initialize tools
        self.screenshot_tools = None
        # Set up viewer with default settings
        self._setup_lighting()
        self._initialize_camera()
        
        # Initialize tools after renderer is set up
        self._initialize_tools()

    def file_exists(self, file_path: str) -> bool:
        """
        Check if a file exists and is accessible before attempting to load it
        
        Args:
            file_path (str): Path to the file to check
            
        Returns:
            bool: True if the file exists and is accessible, False otherwise
        """
        if not file_path:
            return False
            
        if not os.path.exists(file_path):
            return False
            
        if not os.path.isfile(file_path):
            return False
            
        # Check if file is readable
        try:
            with open(file_path, 'rb') as f:
                pass
            return True
        except (IOError, PermissionError):
            return False
            
    def _initialize_renderer(self):
        """Initialize renderer with high quality settings"""
        # Set background color
        self.renderer.SetBackground(0.2, 0.2, 0.2)  # Dark gray
        
        # Enable depth peeling for better transparency
        self.renderer.SetUseDepthPeeling(1)
        self.renderer.SetMaximumNumberOfPeels(8)
        self.renderer.SetOcclusionRatio(0.0)
        
        # Enable two-sided lighting for better model visualization
        self.renderer.SetTwoSidedLighting(True)
        
        # Enable shadows for better depth perception
        self.renderer.SetUseShadows(True)
        
        # Enable anti-aliasing
        render_window = self.renderer.GetRenderWindow()
        if render_window:
            render_window.SetMultiSamples(8)  # Enable MSAA with 8 samples
            render_window.SetAlphaBitPlanes(True)  # Enable alpha channel
            render_window.SetPointSmoothing(True)  # Enable point smoothing
            render_window.SetLineSmoothing(True)  # Enable line smoothing
            render_window.SetPolygonSmoothing(True)  # Enable polygon smoothing
    
    def _initialize_camera(self):
        """Initialize camera with good default settings"""
        camera = self.renderer.GetActiveCamera()
        
        # Set better default camera position for isometric-like view
        camera.SetPosition(1, 1, 1)
        camera.SetFocalPoint(0, 0, 0)
        camera.SetViewUp(0, 1, 0)
        
        # Set view angle for perspective projection (smaller = more telephoto lens effect)
        camera.SetViewAngle(30.0)
        
        # Set clipping range to see objects from close to far
        camera.SetClippingRange(0.1, 1000)
        
        # Set camera to have smooth motion
        render_window = self.renderer.GetRenderWindow()
        if render_window and render_window.GetInteractor():
            # Use trackball style for smoother interaction
            style = vtk.vtkInteractorStyleTrackballCamera()
            render_window.GetInteractor().SetInteractorStyle(style)
    
    def _initialize_tools(self):
        """Initialize viewer tools"""
        # Initialize screenshot tools
        from .screenshot_tools import ScreenshotTools
        render_window = self.renderer.GetRenderWindow()
        if render_window:
            self.screenshot_tools = ScreenshotTools(render_window, parent_widget=self.parent_widget)
        
        # Initialize axes if render window interactor exists
        try:
            render_window = self.renderer.GetRenderWindow()
            if render_window and render_window.GetInteractor():
                self._initialize_axes()
                # Apply initial axes visibility based on settings
                if self._axes_widget:
                    # Set the initial visibility state properly
                    self.toggle_axes(self._show_axes)
        except Exception as e:
            print(f"Error initializing axes: {e}")

    def _initialize_axes(self, custom_interactor=None):
        """
        Initialize the coordinate axes widget for orientation display
        
        This method creates and configures the axes widget that appears in
        the corner of the view to help with orientation. It handles:
        1. Creating the axes actor with proper labels and colors
        2. Setting up the orientation marker widget
        3. Positioning the widget in the viewport
        4. Setting initial visibility based on settings
        
        Args:
            custom_interactor (vtkRenderWindowInteractor, optional): 
                Optional specific interactor to use. If not provided, will use
                the renderer's current interactor.
        
        Note: The axes actor is only used in the orientation widget and is not
        added to the main renderer to prevent duplicate axes in the scene.
        """
        try:
            # Check if widget already exists and is in valid state
            if self._axes_widget is not None and self._axes_initialized:
                # If the widget is already initialized and valid, just return
                # This prevents unnecessary recreation of the widget
                print("Axes widget already exists, skipping initialization")
                return

            # If the widget exists but isn't fully initialized, clean it up
            if self._axes_widget is not None:
                print("Cleaning up partially initialized axes widget")
                self._cleanup_axes()
                
            # Ensure widget references are properly reset
            if self._axes_widget is not None:
                print("Warning: Axes widget still exists after cleanup, forcing deletion")
                self._axes_widget = None
                self._axes_actor = None
                self._axes_initialized = False
                
            # Get the render window interactor
            render_window = self.renderer.GetRenderWindow()
            if not render_window:
                print("Cannot initialize axes: No render window available")
                return
            
            # Use provided interactor or get from render window
            interactor = custom_interactor
            if interactor is None:
                interactor = render_window.GetInteractor()
                
            if not interactor:
                print("Cannot initialize axes: No interactor available")
                return
            
            # Create axes actor - will only be used in the orientation widget
            self._axes_actor = vtk.vtkAxesActor()
            
            # Customize axes appearance
            self._axes_actor.SetShaftTypeToCylinder()
            self._axes_actor.SetXAxisLabelText("X")
            self._axes_actor.SetYAxisLabelText("Y")
            self._axes_actor.SetZAxisLabelText("Z")
            
            # Set axis colors
            self._axes_actor.GetXAxisShaftProperty().SetColor(1, 0, 0)  # Red
            self._axes_actor.GetYAxisShaftProperty().SetColor(0, 1, 0)  # Green
            self._axes_actor.GetZAxisShaftProperty().SetColor(0, 0, 1)  # Blue
            
            # Set cone radius and shaft radius (size of arrows)
            self._axes_actor.SetConeRadius(0.2)
            self._axes_actor.SetShaftTypeToLine()
            
            # Create orientation marker widget
            self._axes_widget = vtk.vtkOrientationMarkerWidget()
            self._axes_widget.SetOrientationMarker(self._axes_actor)
            self._axes_widget.SetInteractor(interactor)
            self._axes_widget.SetViewport(0.0, 0.0, 0.2, 0.2)  # Lower left corner
            
            # Enable the widget if axes should be visible based on settings
            if self._show_axes:
                self._axes_widget.SetEnabled(1)
                self._axes_actor.SetVisibility(1)
            else:
                self._axes_widget.SetEnabled(0)
                self._axes_actor.SetVisibility(0)
                
            self._axes_widget.InteractiveOff()  # Make it non-interactive by default
            
            self._axes_initialized = True
            
            # Force a render refresh
            render_window.Render()
            print("Axes initialized successfully")
        except Exception as e:
            print(f"Error setting up axes widget: {e}")
            self._cleanup_axes()  # Clean up on failure
    def toggle_axes(self, show: bool):
        """
        Toggle the visibility of coordinate axes in the orientation widget
        
        Args:
            show (bool): Whether to show or hide the axes
        """
        try:
            # Store the desired state
            if self._show_axes == show and self._axes_initialized:
                # Even if state isn't changing, force a render to ensure proper display
                if self.renderer and self.renderer.GetRenderWindow():
                    render_window = self.renderer.GetRenderWindow()
                    render_window.Render()
                return
                
            # Update the state
            self._show_axes = show
            
            # Get render window and interactor safely
            render_window = None
            interactor = None
            if self.renderer:
                render_window = self.renderer.GetRenderWindow()
                if render_window:
                    interactor = render_window.GetInteractor()
            
            # Check if we have the necessary components
            if not render_window or not interactor:
                print("Cannot toggle axes: No render window or interactor available")
                return
            
            # Initialize axes widget if it doesn't exist yet
            if not self._axes_widget or not self._axes_initialized:
                self._initialize_axes(interactor)
            
            # Now toggle visibility on the existing widget
            if self._axes_widget:
                # Simply enable/disable the widget without destroying it
                try:
                    self._axes_widget.SetEnabled(1 if show else 0)
                    if self._axes_actor:
                        self._axes_actor.SetVisibility(1 if show else 0)
                except Exception as e:
                    print(f"Error toggling axes widget visibility: {e}")
                    # If there was an error with the widget, try to reinitialize
                    if show:
                        print("Reinitializing axes widget after error")
                        self._cleanup_axes()
                        self._initialize_axes(interactor)
                        if self._axes_widget:
                            self._axes_widget.SetEnabled(1)
                            if self._axes_actor:
                                self._axes_actor.SetVisibility(1)
            
            # Force an immediate render to ensure visibility change is applied
            if render_window:
                try:
                    # Update the render window to reflect changes immediately
                    render_window.Modified()
                    render_window.Render()
                    
                    # Force a processing of events for immediate visual update
                    if interactor:
                        interactor.ProcessEvents()
                        
                    # Render again to ensure complete update
                    render_window.Render()
                except Exception as e:
                    print(f"Error refreshing render after axes toggle: {e}")
            
            print(f"Axes visibility set to: {'visible' if show else 'hidden'}")
        except Exception as e:
            print(f"Error toggling axes: {e}")
            traceback.print_exc()
    def load_stl(self, file_path: str) -> bool:
        """
        Load an STL file
        
        Args:
            file_path (str): Path to the STL file to load
            
        Returns:
            bool: True if the file was loaded successfully, False otherwise
        
        Raises:
            FileNotFoundError: If the file doesn't exist
            PermissionError: If the file can't be accessed
            ValueError: If the file contains invalid data
        """
        # Check if file exists
        if not self.file_exists(file_path):
            raise FileNotFoundError(f"STL file not found or not accessible: {file_path}")
            
        try:
            print(f"Loading STL file: {file_path}")
            # Store current interactor before clearing scene
            interactor = None
            render_window = self.renderer.GetRenderWindow()
            if render_window:
                interactor = render_window.GetInteractor()
            
            # Remember axes visibility state and widget instance
            axes_visible = self._show_axes
            axes_widget = self._axes_widget
            axes_actor = self._axes_actor
            
            # Clear existing scene and reset lighting
            # We'll handle axes preservation separately
            self.clear_scene(preserve_axes=True)
            
            # Reset lighting without affecting axes
            self._setup_lighting()
            self._setup_lighting()
            
            # Create reader
            reader = vtk.vtkSTLReader()
            reader.SetFileName(file_path)
            print("Reading STL file...")
            reader.Update()
            
            output = reader.GetOutput()
            if not output or output.GetNumberOfPoints() == 0:
                raise ValueError("STL file contains no points")
            
            print(f"Loaded {output.GetNumberOfPoints()} points and {output.GetNumberOfCells()} cells")
            
            # Create mapper
            mapper = vtk.vtkPolyDataMapper()
            mapper.SetInputConnection(reader.GetOutputPort())
            mapper.ScalarVisibilityOff()
            
            # Create actor with default properties
            actor = vtk.vtkActor()
            actor.SetMapper(mapper)
            
            prop = actor.GetProperty()
            prop.SetColor(*self._model_color)
            prop.SetAmbient(0.1)
            prop.SetDiffuse(0.7)
            prop.SetSpecular(0.2)
            prop.SetSpecularPower(30.0)
            
            # Add to scene
            self.renderer.AddActor(actor)
            name = os.path.basename(file_path)
            self.actors[name] = actor
            
            # Create and emit object properties
            props = ObjectProperties(
                name=name,
                visible=True,
                color=self._model_color,
                opacity=1.0,
                wireframe=False,
                cast_shadows=True,
                receive_shadows=True
            )
            self.object_properties_changed.emit(props)
            
            # Update statistics
            self._update_stats(output)
            
            # Reset camera and render
            # Reset camera and render
            self.reset_view()
            
            # Apply the axes visibility without recreating the widget if possible
            if interactor and render_window:
                # Only initialize axes if they don't exist
                if not self._axes_initialized:
                    self._initialize_axes(interactor)
                
                # Just update the visibility state without recreating
                self.toggle_axes(axes_visible)
                
            # Ensure full render refresh
            render_window = self.renderer.GetRenderWindow()
            if render_window:
                render_window.Render()
            self.model_loaded.emit(True)
            return True
            
        except FileNotFoundError as e:
            traceback.print_exc()
            print(f"File not found: {e}")
            self.model_loaded.emit(False)
            raise
        except PermissionError as e:
            traceback.print_exc()
            print(f"Permission error: {e}")
            self.model_loaded.emit(False)
            raise
        except ValueError as e:
            traceback.print_exc()
            print(f"Invalid STL data: {e}")
            self.model_loaded.emit(False)
            raise
        except Exception as e:
            traceback.print_exc()
            print(f"Error loading STL: {e}")
            self.model_loaded.emit(False)
            raise

    def load_3mf(self, file_path: str) -> bool:
        """
        Load a 3MF file
        
        Args:
            file_path (str): Path to the 3MF file to load
            
        Returns:
            bool: True if the file was loaded successfully, False otherwise
            
        Raises:
            FileNotFoundError: If the file doesn't exist
            PermissionError: If the file can't be accessed
            ValueError: If the file contains invalid data
        """
        # Check if file exists
        if not self.file_exists(file_path):
            raise FileNotFoundError(f"3MF file not found or not accessible: {file_path}")
            
        try:
            # Store current interactor before clearing scene
            interactor = None
            render_window = self.renderer.GetRenderWindow()
            if render_window:
                interactor = render_window.GetInteractor()
            
            # Remember axes visibility state
            axes_visible = self._show_axes
                
            # Clear existing models but preserve axes
            self.clear_scene(preserve_axes=True)
            
            # Load 3MF objects
            objects = load_3mf(file_path)
            
            for obj in objects:
                # Create mapper
                mapper = vtk.vtkPolyDataMapper()
                mapper.SetInputData(obj.mesh)
                
                # Create actor
                actor = vtk.vtkActor()
                actor.SetMapper(mapper)
                
                # Apply transform if exists
                if obj.transform:
                    transform = vtk.vtkTransform()
                    transform.SetMatrix(obj.transform)
                    actor.SetUserTransform(transform)
                
                # Apply color if exists
                if obj.color:
                    actor.GetProperty().SetColor(obj.color.r, obj.color.g, obj.color.b)
                    actor.GetProperty().SetOpacity(obj.color.a)
                
                # Add to scene
                self.renderer.AddActor(actor)
                self.actors[obj.name] = actor
                
                # Create and emit object properties
                props = ObjectProperties()
                props.name = obj.name
                props.visible = True
                if obj.color:
                    props.color = (obj.color.r, obj.color.g, obj.color.b)
                    props.opacity = obj.color.a
                else:
                    props.color = self._model_color
                    props.opacity = 1.0
                props.wireframe = False
                props.cast_shadows = True
                props.receive_shadows = True
                
                # Update object tree widget
                self.object_properties_changed.emit(props)
                
                # Update statistics for first object
                if len(self.actors) == 1:
                    self._update_stats(obj.mesh)
            
            # Reset camera
            self.reset_view()
            
            # Properly restore the axes with the stored interactor
            if interactor and render_window:
                # Re-initialize the axes with the saved interactor
                self._initialize_axes()
                # Apply the previous visibility state
                self.toggle_axes(axes_visible)
                
            # Ensure full render refresh
            render_window = self.renderer.GetRenderWindow()
            if render_window:
                render_window.Render()
                
            self.model_loaded.emit(True)
            return True
            
        except FileNotFoundError as e:
            traceback.print_exc()
            print(f"File not found: {e}")
            self.model_loaded.emit(False)
            raise
        except PermissionError as e:
            traceback.print_exc()
            print(f"Permission error: {e}")
            self.model_loaded.emit(False)
            raise
        except ValueError as e:
            traceback.print_exc()
            print(f"Invalid 3MF data: {e}")
            self.model_loaded.emit(False)
            raise
        except Exception as e:
            traceback.print_exc()
            print(f"Error loading 3MF: {e}")
            self.model_loaded.emit(False)
            raise

    def _cleanup_axes(self):
        """
        Properly clean up the axes widget and actor
        
        This method performs a thorough cleanup of the axes widget to ensure
        no duplicate widgets are created and all resources are properly released.
        """
        try:
            if self._axes_widget:
                # Get the render window and interactor for later refresh
                render_window = None
                interactor = None
                if self.renderer:
                    render_window = self.renderer.GetRenderWindow()
                    if render_window:
                        interactor = render_window.GetInteractor()

                # First disable the widget before any other operations
                try:
                    if self._axes_widget.GetEnabled():
                        self._axes_widget.SetEnabled(0)
                        print("Axes widget disabled")
                except Exception as e:
                    print(f"Error disabling axes widget: {e}")
                
                # Detach from the orientation marker
                try:
                    self._axes_widget.SetOrientationMarker(None)
                    print("Orientation marker detached")
                except Exception as e:
                    print(f"Error detaching orientation marker: {e}")
                
                # Detach interactor to prevent memory leaks
                try:
                    self._axes_widget.SetInteractor(None)
                    print("Interactor detached from axes widget")
                except Exception as e:
                    print(f"Error detaching interactor from axes widget: {e}")
                
                # Remove widget from renderer if possible
                try:
                    # VTK doesn't have a direct DeleteWidget method, but this helps
                    del self._axes_widget
                    print("Axes widget deleted")
                except Exception as e:
                    print(f"Error deleting axes widget: {e}")
                
                # Remove from renderer if it was somehow added
                if self._axes_actor and self.renderer:
                    if self.renderer.HasViewProp(self._axes_actor):
                        self.renderer.RemoveActor(self._axes_actor)
                        print("Axes actor removed from renderer")
                    
                    # Delete the actor
                    try:
                        del self._axes_actor
                        print("Axes actor deleted")
                    except Exception as e:
                        print(f"Error deleting axes actor: {e}")
                
                # Force multiple render passes to ensure complete cleanup
                if render_window:
                    try:
                        render_window.Render()
                        if interactor:
                            interactor.Render()
                        render_window.Render()
                    except Exception as e:
                        print(f"Error rendering during cleanup: {e}")
        except Exception as e:
            print(f"Error during axes cleanup: {e}")
        finally:
            # Reset references even if cleanup had errors
            self._axes_widget = None
            self._axes_actor = None
            self._axes_initialized = False
            
            # Force a render to ensure changes are visible
            try:
                if self.renderer and self.renderer.GetRenderWindow():
                    self.renderer.GetRenderWindow().Render()
            except Exception as e:
                print(f"Error rendering after axes cleanup: {e}")

    def clear_scene(self, preserve_axes=False):
        """
        Clear all actors from the scene
        
        Args:
            preserve_axes (bool): Whether to preserve axes state during clearing
        """
        # Store interactor reference before clearing
        interactor = None
        render_window = self.renderer.GetRenderWindow()
        if render_window:
            interactor = render_window.GetInteractor()
        
        # Remember axes visibility state
        axes_visible = self._show_axes
        
        # Remove all model actors
        for actor in self.actors.values():
            self.renderer.RemoveActor(actor)
        self.actors.clear()
        
        # We don't toggle axes here to avoid unnecessary re-initialization
        # The axes state will be handled by the load methods
            
        # Force multiple renders to ensure complete update
        if self.renderer and self.renderer.GetRenderWindow():
            self.renderer.GetRenderWindow().Render()
            self.renderer.GetRenderWindow().Render()

    def reset_view(self):
        """Reset camera to show all actors"""
        if not self.actors:
            return
            
        print("Resetting camera view...")
        
        # Store light positions
        light_positions = {}
        light_focal_points = {}
        for name, light in self._lights.items():
            if light.GetLightType() != 1:  # 1 is VTK_LIGHT_TYPE_HEADLIGHT
                light_positions[name] = light.GetPosition()
                light_focal_points[name] = light.GetFocalPoint()
        
        # Reset camera
        self.renderer.ResetCamera()
        
        # Get bounds of all actors
        bounds = [0]*6
        self.renderer.ComputeVisiblePropBounds(bounds)
        print(f"Scene bounds: [{', '.join(map(str, bounds))}]")
        
        camera = self.renderer.GetActiveCamera()
        camera.SetViewUp(0, 1, 0)
        
        # Position camera at an angle
        center = [(bounds[1] + bounds[0])/2,
                (bounds[3] + bounds[2])/2,
                (bounds[5] + bounds[4])/2]
                
        radius = max(bounds[1]-bounds[0],
                  bounds[3]-bounds[2],
                  bounds[5]-bounds[4]) * 1.5
                  
        camera.SetPosition(center[0] + radius,
                        center[1] + radius,
                        center[2] + radius)
        camera.SetFocalPoint(*center)
        
        # Restore light positions in world space
        for name, light in self._lights.items():
            if light.GetLightType() != 1:  # 1 is VTK_LIGHT_TYPE_HEADLIGHT
                if name in light_positions:
                    light.SetPosition(*light_positions[name])
                    light.SetFocalPoint(*light_focal_points[name])
        
        self.renderer.ResetCameraClippingRange()
        pos = camera.GetPosition()
        focal = camera.GetFocalPoint()
        print(f"Camera position: [{', '.join(map(str, pos))}]")
        print(f"Focal point: [{', '.join(map(str, focal))}]")
        
        self.renderer.GetRenderWindow().Render()

    def center_model(self):
        """Center the model in view"""
        if self.actors:
            self.renderer.ResetCamera()
            camera = self.renderer.GetActiveCamera()
            camera.SetViewUp(0, 1, 0)
            self.renderer.GetRenderWindow().Render()

    def reset_camera(self):
        """
        Reset the camera to show the full model
        
        This method:
        1. Positions the camera to show the entire model
        2. Maintains proper up vector orientation
        3. Ensures proper zoom level
        The camera will be positioned to show all actors in the scene.
        """
        if not self.actors:
            print("No actors in scene to reset camera for")
            return

        print("Resetting camera to show full model...")
        
        # Get bounds of all actors
        bounds = [0]*6
        self.renderer.ComputeVisiblePropBounds(bounds)
        
        # Calculate center of the bounds
        center = [
            (bounds[1] + bounds[0])/2,
            (bounds[3] + bounds[2])/2,
            (bounds[5] + bounds[4])/2
        ]
        
        # Calculate the diagonal size to determine proper distance
        diagonal = ((bounds[1]-bounds[0])**2 + 
                    (bounds[3]-bounds[2])**2 + 
                    (bounds[5]-bounds[4])**2)**0.5
        
        # Get camera and ensure it exists
        camera = self.renderer.GetActiveCamera()
        if not camera:
            print("Error: No active camera found")
            return
        
        # Reset the camera to its default settings
        self.renderer.ResetCamera()
        
        # Set the camera position using the diagonal
        # Position at slightly elevated angle for better 3D perspective
        camera.SetPosition(
            center[0] + diagonal * 0.5,  
            center[1] + diagonal * 0.7,
            center[2] + diagonal * 0.5
        )
        
        # Set focal point to the center of the model
        camera.SetFocalPoint(*center)
        
        # Ensure Y-up orientation
        camera.SetViewUp(0, 1, 0)
        
        # Adjust zoom to fit everything with some margin
        self.renderer.ResetCameraClippingRange()
        
        # Log camera information
        pos = camera.GetPosition()
        focal = camera.GetFocalPoint()
        print(f"Camera reset successful")
        print(f"Camera position: [{', '.join(map(str, pos))}]")
        print(f"Focal point: [{', '.join(map(str, focal))}]")
        print(f"Model bounds: [{', '.join(map(str, bounds))}]")
        
        # Force render to apply changes
        if self.renderer.GetRenderWindow():
            self.renderer.GetRenderWindow().Render()

    def set_camera_mode(self, mode: str):
        """Set camera interaction mode"""
        if not self.renderer.GetRenderWindow().GetInteractor():
            return
            
        if mode == 'trackball':
            style = vtk.vtkInteractorStyleTrackballCamera()
            self.renderer.GetRenderWindow().GetInteractor().SetInteractorStyle(style)

    def set_object_visibility(self, name: str, visible: bool):
        """Set object visibility"""
        if name in self.actors:
            self.actors[name].SetVisibility(visible)
            self.renderer.GetRenderWindow().Render()

    def set_object_color(self, name: str, color: tuple):
        """Set object color"""
        if name in self.actors:
            self.actors[name].GetProperty().SetColor(*color)
            self.renderer.GetRenderWindow().Render()

    def set_object_opacity(self, name: str, opacity: float):
        """Set object opacity"""
        if name in self.actors:
            self.actors[name].GetProperty().SetOpacity(opacity)
            self.renderer.GetRenderWindow().Render()

    def set_object_wireframe(self, name: str, wireframe: bool):
        """Set object wireframe mode"""
        if name in self.actors:
            if wireframe:
                self.actors[name].GetProperty().SetRepresentationToWireframe()
            else:
                self.actors[name].GetProperty().SetRepresentationToSurface()
            self.renderer.GetRenderWindow().Render()

    def set_object_shadows(self, name: str, cast: bool, receive: bool):
        """Set object shadow properties"""
        if name not in self.actors:
            return
            
        actor = self.actors[name]
        prop = actor.GetProperty()
        
        # Adjust material properties for shadow effects
        if receive:
            prop.SetAmbient(0.1)
            prop.SetDiffuse(0.9)
            prop.SetSpecular(0.1)
        else:
            prop.SetAmbient(0.5)
            prop.SetDiffuse(0.5)
            prop.SetSpecular(0.0)
        
        # Adjust opacity for shadow casting
        if not cast:
            current_opacity = prop.GetOpacity()
            prop.SetOpacity(min(current_opacity, 0.95))
        
        self.renderer.GetRenderWindow().Render()

    def take_screenshot(self, model_path=None):
        """
        Take a screenshot and prompt user for save options
        
        Args:
            model_path (str, optional): Path to the currently loaded model file.
                                        Used for auto-naming screenshots.
        
        Returns:
            bool: True if screenshot was saved successfully, False otherwise
        """
        if not self.renderer or not self.renderer.GetRenderWindow():
            print("Error: No render window available for screenshot")
            return False, "No render window available"
            
        # Check if screenshot tools are initialized
        if not self.screenshot_tools:
            print("Initializing screenshot tools...")
            try:
                render_window = self.renderer.GetRenderWindow()
                self.screenshot_tools = ScreenshotTools(render_window, self.parent_widget)
            except Exception as e:
                print(f"Error initializing screenshot tools: {e}")
                traceback.print_exc()
                return False, f"Screenshot error: {str(e)}"
        
        try:
            # Capture a normal resolution screenshot (75 DPI)
            window_filter = self.screenshot_tools.capture_screenshot(high_res=False)
            
            # Show the dialog with three options and handle the screenshot
            success, result = self.screenshot_tools.prompt_for_screenshot_options(
                model_path=model_path,
                parent=self.parent_widget,
                window_to_image_filter=window_filter
            )
            
            if success:
                print(f"Screenshot saved: {result}")
            else:
                print(f"Screenshot not saved: {result}")
            
            return success, result
        except Exception as e:
            print(f"Error taking screenshot: {e}")
            traceback.print_exc()
            return False, f"Screenshot error: {str(e)}"

    def take_high_res_screenshot(self, model_path=None, scale_factor: int = 4):
        """
        Take a high-resolution screenshot
        
        Args:
            model_path (str, optional): Path to the currently loaded model file
            scale_factor (int): Resolution multiplier (4 = 4x the window resolution)
            
        Returns:
            tuple: (success, message) where success is a boolean and message is the
                   path to the saved file or an error message
        """
        if not self.screenshot_tools:
            print("Screenshot tools not initialized")
            return False, "Screenshot tools not initialized"
            
        try:
            # First capture the high-res screenshot to a filter
            window_filter = self.screenshot_tools.capture_screenshot(high_res=True)
            # No need to set scale factor here as it's already set in capture_screenshot
            window_filter.Update()
            
            # Then show the dialog and save based on user selection
            return self.screenshot_tools.prompt_for_screenshot_options(
                model_path=model_path,
                parent=self.parent_widget,
                window_to_image_filter=window_filter
            )
        except Exception as e:
            print(f"Error taking high-res screenshot: {e}")
            traceback.print_exc()
            return False, f"Screenshot error: {str(e)}"

    def set_background_color(self, color):
        """Set background color"""
        self.renderer.SetBackground(*color)
        if hasattr(self, '_gradient_enabled') and self._gradient_enabled:
            # Darker gradient color for bottom
            darker = [c * 0.5 for c in color]
            self.renderer.GradientBackgroundOn()
            self.renderer.SetBackground2(*color)  # Top color
            self.renderer.SetBackground(*darker)  # Bottom color
        else:
            self.renderer.GradientBackgroundOff()
            self.renderer.SetBackground(*color)
        self.renderer.GetRenderWindow().Render()

    def set_background_gradient(self, enabled):
        """Enable/disable background gradient"""
        self._gradient_enabled = enabled
        if enabled:
            # Get current background color
            color = self.renderer.GetBackground()
            darker = [c * 0.5 for c in color]
            self.renderer.GradientBackgroundOn()
            self.renderer.SetBackground2(*color)  # Top color
            self.renderer.SetBackground(*darker)  # Bottom color
        else:
            self.renderer.GradientBackgroundOff()
        self.renderer.GetRenderWindow().Render()

    def toggle_light(self, light_name: str, enabled: bool):
        """Toggle a specific light source"""
        if light_name in self._lights:
            self._lights[light_name].SetSwitch(1 if enabled else 0)
            self.renderer.GetRenderWindow().Render()

    def set_model_color(self, color: tuple):
        """Set the model color for all models"""
        self._model_color = color
        # Update all loaded models
        for actor in self.actors.values():
            actor.GetProperty().SetColor(*color)
        self.renderer.GetRenderWindow().Render()
        
    def update_model_color(self, model_id: str, color: tuple):
        """Update color for a specific model"""
        if model_id in self.actors:
            self.actors[model_id].GetProperty().SetColor(*color)
            self.renderer.GetRenderWindow().Render()
        
    def set_light_intensity(self, intensity: float):
        """Set the overall light intensity for all lights

        Args:
            intensity (float): Intensity multiplier for all lights (0.5 to 3.0)
        """
        # Clamp intensity value to valid range (now 0.5 to 3.0)
        intensity = max(0.5, min(3.0, intensity))
        
        # Store current intensity
        self._current_intensity = intensity
        
        # Apply intensity multiplier to all lights
        for name, light in self._lights.items():
            if name in self._base_intensities and light is not None:
                base_intensity = self._base_intensities[name]
                light.SetIntensity(base_intensity * intensity)
        
        # Update render
        if self.renderer and self.renderer.GetRenderWindow():
            self.renderer.GetRenderWindow().Render()
            
        print(f"Light intensity set to {intensity:.2f}")
    
    def _setup_lighting(self):
        """Set up scene lighting"""
        # Remove existing lights
        lights = self.renderer.GetLights()
        lights.InitTraversal()
        light = lights.GetNextItem()
        while light:
            self.renderer.RemoveLight(light)
            light = lights.GetNextItem()

        # Store lights in a dictionary for easy access
        self._lights = {}

        # Create ambient light (headlight)
        ambient = vtk.vtkLight()
        ambient.SetLightTypeToHeadlight()
        ambient.SetIntensity(self._base_intensities['ambient'] * self._current_intensity)
        ambient.SetColor(1.0, 1.0, 1.0)
        self.renderer.AddLight(ambient)
        self._lights["ambient"] = ambient

        # Create key light
        key = vtk.vtkLight()
        key.SetLightTypeToSceneLight()
        key.SetPosition(5, 10, 15)
        key.SetFocalPoint(0, 0, 0)
        key.SetColor(1.0, 1.0, 1.0)
        key.SetIntensity(self._base_intensities['key'] * self._current_intensity)
        key.SetPositional(True)
        self.renderer.AddLight(key)
        self._lights["key"] = key

        # Create fill light
        fill = vtk.vtkLight()
        fill.SetLightTypeToSceneLight()
        fill.SetPosition(-10, -5, -15)
        fill.SetFocalPoint(0, 0, 0)
        fill.SetColor(0.9, 0.9, 1.0)
        fill.SetIntensity(self._base_intensities['fill'] * self._current_intensity)
        fill.SetPositional(True)
        self.renderer.AddLight(fill)
        self._lights["fill"] = fill

        # Create rim light
        rim = vtk.vtkLight()
        rim.SetLightTypeToSceneLight()
        rim.SetPosition(-5, 15, -10)
        rim.SetFocalPoint(0, 0, 0)
        rim.SetColor(1.0, 1.0, 0.9)
        rim.SetIntensity(self._base_intensities['rim'] * self._current_intensity)
        rim.SetPositional(True)
        self.renderer.AddLight(rim)
        self._lights["rim"] = rim

    def get_model_statistics(self):
        """
        Get statistics for the current model.
        
        Returns:
            dict: Dictionary containing:
                - vertices count
                - triangles count
                - model volume
                
        Note:
            Returns zeros for all values if no actors are present or if calculation fails
        """
        if not self.actors:
            return {
                "vertices": 0,
                "triangles": 0,
                "volume": 0
            }
            
        # Initialize counters
        vertices_count = 0
        triangles_count = 0
        total_volume = 0
        
        try:
            # Calculate statistics for all actors
            for actor in self.actors.values():
                # Get the polydata
                poly_data = actor.GetMapper().GetInput()
                if not poly_data:
                    continue
                    
                # Count vertices and triangles
                vertices_count += poly_data.GetNumberOfPoints()
                triangles_count += poly_data.GetNumberOfCells()
                
                try:
                    # Calculate volume using vtkMassProperties
                    mass_props = vtk.vtkMassProperties()
                    mass_props.SetInputData(poly_data)
                    total_volume += mass_props.GetVolume()
                except Exception as e:
                    print(f"Error calculating volume: {e}")
                    # Continue with other statistics even if volume calculation fails
        
            return {
                "vertices": vertices_count,
                "triangles": triangles_count,
                "volume": total_volume
            }
        except Exception as e:
            print(f"Error calculating model statistics: {e}")
            return {
                "vertices": 0,
                "triangles": 0,
                "volume": 0
            }

    def _update_stats(self, poly_data):
        """
        Update model statistics
        
        Args:
            poly_data: VTK polydata object to calculate statistics for
        """
        try:
            # Get number of points and cells
            n_points = poly_data.GetNumberOfPoints()
            n_cells = poly_data.GetNumberOfCells()
            
            # Calculate volume and surface area using vtkMassProperties
            mass_props = vtk.vtkMassProperties()
            mass_props.SetInputData(poly_data)
            volume = mass_props.GetVolume()
            surface_area = mass_props.GetSurfaceArea()
            
            # Create stats using the existing ModelStats dataclass
            stats = ModelStats(
                vertices=n_points,
                faces=n_cells,
                volume=volume,
                surface_area=surface_area
            )
            
            # Emit the stats update signal
            self.model_stats_updated.emit(stats)
        except Exception as e:
            print(f"Error updating model statistics: {e}")
            # Create empty stats on error
            stats = ModelStats(vertices=0, faces=0, volume=0, surface_area=0)
            self.model_stats_updated.emit(stats)
    
    def apply_settings(self, settings):
        """
        Apply viewer settings from the settings manager
        
        Args:
            settings: Application settings object with viewer-related properties
        """
        # Apply light intensity if available
        if hasattr(settings, 'light_intensity'):
            self.set_light_intensity(settings.light_intensity)
            
        # Apply axes visibility if available
        if hasattr(settings, 'show_axes'):
            try:
                # First ensure axes are completely off to reset state
                self.toggle_axes(False)
                
                # Update the stored state
                self._show_axes = settings.show_axes
                
                # Apply the visibility setting properly if they should be on
                if settings.show_axes:
                    self.toggle_axes(True)
                    
                # Force multiple renders to ensure the view is completely updated
                if self.renderer and self.renderer.GetRenderWindow():
                    self.renderer.GetRenderWindow().Render()
            except Exception as e:
                print(f"Error applying axes visibility setting: {e}")
                
        # Apply background color/gradient if available
        if hasattr(settings, 'background_color'):
            self.set_background_color(settings.background_color)
            
        if hasattr(settings, 'background_gradient'):
            self.set_background_gradient(settings.background_gradient)
            
        # Apply model color if available
        if hasattr(settings, 'model_color'):
            self.set_model_color(settings.model_color)
