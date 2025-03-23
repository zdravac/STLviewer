import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QFileDialog, QMenuBar, QStatusBar, QToolBar, QTreeView,
    QDockWidget, QMessageBox, QLabel, QColorDialog, QSpinBox,
    QGroupBox, QCheckBox, QSlider, QWidgetAction
)
from PyQt6.QtGui import QAction, QKeySequence, QStandardItemModel, QStandardItem, QIcon
from PyQt6.QtCore import Qt, QSettings, QDir, QSize
from PyQt6.QtWidgets import QStyle
from src.viewer import ModelViewer
from src.settings_manager import SettingsManager
import vtk
from vtk.qt.QVTKRenderWindowInteractor import QVTKRenderWindowInteractor

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        # Initialize icons
        self.folder_icon = self.style().standardIcon(QStyle.StandardPixmap.SP_DirIcon)
        self.file_icon = self.style().standardIcon(QStyle.StandardPixmap.SP_FileIcon)
        
        # Initialize settings manager
        self.settings_manager = SettingsManager()
        
        # Create central widget with horizontal layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QHBoxLayout(central_widget)
        layout.setContentsMargins(0, 0, 0, 0)

        # Create file browser on the left (30% width)
        self.file_tree = QTreeView()
        self.file_model = QStandardItemModel()
        self.file_model.setHorizontalHeaderLabels(["Name"])
        self.file_tree.setModel(self.file_model)
        
        # File filters
        self.file_filters = ['.stl', '.3mf']
        
        # Configure tree view
        self.file_tree.setHeaderHidden(True)
        self.file_tree.setAnimated(True)
        self.file_tree.setIndentation(20)
        self.file_tree.setSortingEnabled(True)
        
        # Set maximum width (30% of window)
        self.file_tree.setMaximumWidth(int(self.width() * 0.3))
        
        # Set initial directory
        self.current_dir = self.settings_manager.settings.last_directory
        if not self.current_dir or not os.path.exists(self.current_dir):
            self.current_dir = os.path.expanduser("~")
            
        # Populate the file model with the initial directory
        self._populate_file_model(self.current_dir)
        
        # Connect file selection signal
        self.file_tree.doubleClicked.connect(self._on_file_selected)
        
        # Add to layout before viewer container
        layout.addWidget(self.file_tree)

        # Create VTK widget container
        viewer_container = QWidget()
        viewer_layout = QVBoxLayout(viewer_container)
        viewer_layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(viewer_container)

        # Create and setup VTK render window
        self.vtk_widget = QVTKRenderWindowInteractor(viewer_container)
        render_window = self.vtk_widget.GetRenderWindow()
        
        # Create renderer
        renderer = vtk.vtkRenderer()
        render_window.AddRenderer(renderer)
        
        # Configure renderer
        renderer.SetBackground(0.2, 0.2, 0.2)  # Dark gray background
        
        viewer_layout.addWidget(self.vtk_widget)
        
        # Initialize viewer with renderer
        self.viewer = ModelViewer(renderer, self)
        
        # Configure interaction for smoother rotation
        interactor_style = vtk.vtkInteractorStyleTrackballCamera()
        self.vtk_widget.GetRenderWindow().GetInteractor().SetInteractorStyle(interactor_style)
        
        # Improve response to mouse movements
        self.vtk_widget.GetRenderWindow().GetInteractor().SetDesiredUpdateRate(30.0)
        self.vtk_widget.GetRenderWindow().SetMultiSamples(8)  # Anti-aliasing
        
        # Initialize light actions dictionary
        self.light_actions = {}
        
        # Create menus and toolbars
        self._create_status_bar()
        self._create_menu_bar()
        self._create_dock_widgets()
        
        # Apply saved settings
        self._apply_saved_settings()
        
        # Set window title
        self.setWindowTitle("STL Viewer")
        
        # Restore window geometry
        self.resize(800, 600)
        
        # Initialize interactor
        self.iren = self.vtk_widget.GetRenderWindow().GetInteractor()
        self.iren.Initialize()

    def _populate_file_model(self, directory):
        """Populate the file model with contents of the specified directory"""
        self.file_model.clear()
        self.file_model.setHorizontalHeaderLabels(["File Browser"])
        
        # Create parent directory item (for navigation)
        if os.path.exists(os.path.dirname(directory)):
            parent_item = QStandardItem("..")
            parent_item.setIcon(self.folder_icon)
            parent_item.setData(os.path.dirname(directory))
            parent_item.setEditable(False)
            self.file_model.appendRow(parent_item)
        
        # Add directories first
        directories = []
        files = []
        
        try:
            for item in os.listdir(directory):
                item_path = os.path.join(directory, item)
                if os.path.isdir(item_path):
                    directories.append((item, item_path))
                elif os.path.isfile(item_path):
                    # Only include files with supported extensions
                    ext = os.path.splitext(item)[1].lower()
                    if ext in self.file_filters:
                        files.append((item, item_path))
        except PermissionError:
            self.statusBar().showMessage(f"Permission denied: {directory}")
            return
        
        # Sort directories and files
        directories.sort(key=lambda x: x[0].lower())
        files.sort(key=lambda x: x[0].lower())
        
        # Add directories to the model
        for name, path in directories:
            item = QStandardItem(name)
            item.setIcon(self.folder_icon)
            item.setData(path)
            item.setEditable(False)
            self.file_model.appendRow(item)
        
        # Add files to the model
        for name, path in files:
            item = QStandardItem(name)
            item.setIcon(self.file_icon)
            item.setData(path)
            item.setEditable(False)
            self.file_model.appendRow(item)
        
        # Update current directory
        self.current_dir = directory
        
    def _on_file_selected(self, index):
        """Handle file selection in the tree view"""
        item = self.file_model.itemFromIndex(index)
        if not item:
            return
            
        file_path = item.data()
        if not file_path:
            return
            
        if os.path.isdir(file_path):
            # Navigate to directory
            try:
                self._populate_file_model(file_path)
            except PermissionError:
                self.statusBar().showMessage(f"Permission denied: Cannot access directory {file_path}")
            except Exception as e:
                self.statusBar().showMessage(f"Error accessing directory: {str(e)}")
            return
            
        # Check if file exists and is readable
        if not os.path.exists(file_path):
            self.statusBar().showMessage(f"File not found: {file_path}")
            return
            
        if not os.path.isfile(file_path):
            self.statusBar().showMessage(f"Not a file: {file_path}")
            return
            
        try:
            # Verify file is readable
            with open(file_path, 'rb') as f:
                pass
        except (IOError, PermissionError):
            self.statusBar().showMessage(f"Permission denied: Cannot read file {os.path.basename(file_path)}")
            return
            
        # Proceed with loading the file
        ext = os.path.splitext(file_path)[1].lower()
        if ext in self.file_filters:
            if hasattr(self.viewer, 'load_' + ext[1:]):
                load_method = getattr(self.viewer, 'load_' + ext[1:])
                
                try:
                    success = load_method(file_path)
                    
                    if success:
                        try:
                            # Get model statistics - handle potential errors
                            # Get model statistics - handle potential errors
                            stats = self.viewer.get_model_statistics()
                            status_message = f"Loaded {os.path.basename(file_path)} - "
                            
                            if stats:
                                if stats.get('vertices', 0) > 0:  # Check if valid data
                                    status_message += f"Vertices: {stats.get('vertices', 0):,} | "
                                    status_message += f"Triangles: {stats.get('triangles', 0):,} | "
                                    if 'volume' in stats:
                                        status_message += f"Volume: {stats.get('volume', 0):.2f} mm³"
                                    if 'dimensions' in stats:
                                        dims = stats.get('dimensions')
                                        status_message += f" | Dims: ({dims[0]:.1f}, {dims[1]:.1f}, {dims[2]:.1f}) mm"
                                else:
                                    status_message += "No valid geometry data found"
                            else:
                                status_message += "Statistics unavailable"
                                
                            # Update status bar with the message
                            self.statusBar().showMessage(status_message)
                            
                            # Save the directory in settings
                            self.settings_manager.update_settings(last_directory=os.path.dirname(file_path))
                        except Exception as e:
                            self.statusBar().showMessage(f"Error getting model statistics: {str(e)}")
                    else:
                        self.statusBar().showMessage(f"Failed to load model: {os.path.basename(file_path)}")
                except Exception as ve:
                    self.statusBar().showMessage(f"VTK Error: {str(ve)}")
                except Exception as e:
                    self.statusBar().showMessage(f"Error loading file {os.path.basename(file_path)}: {str(e)}")
            else:
                self.statusBar().showMessage(f"No loader available for {ext} files")

    def _create_menu_bar(self):
        """Create the main menu bar"""
        menu_bar = self.menuBar()
        
        # File menu
        file_menu = menu_bar.addMenu("&File")
        
        # Set default directory action
        set_dir_action = QAction("Set Default Directory...", self)
        set_dir_action.triggered.connect(self._set_default_directory)
        file_menu.addAction(set_dir_action)
        
        file_menu.addSeparator()
        
        # Exit action
        exit_action = QAction("E&xit", self)
        exit_action.setShortcut(QKeySequence("Ctrl+Q"))
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        # View menu
        view_menu = menu_bar.addMenu("&View")
        
        # Reset camera action
        reset_view_action = QAction("Reset Camera", self)
        reset_view_action.setShortcut(QKeySequence("Ctrl+R"))
        reset_view_action.triggered.connect(lambda: self.viewer.reset_camera())
        reset_view_action.triggered.connect(lambda: self.viewer.reset_camera())
        view_menu.addAction(reset_view_action)
        
        # Screenshot actions
        screenshot_action = QAction("Take Screenshot", self)
        screenshot_action.setShortcut(QKeySequence("Ctrl+S"))
        screenshot_action.triggered.connect(self._take_screenshot)
        view_menu.addAction(screenshot_action)
        
        # High-res screenshot action
        hires_screenshot_action = QAction("Take High-Res Screenshot", self)
        hires_screenshot_action.setShortcut(QKeySequence("Ctrl+Shift+S"))
        hires_screenshot_action.triggered.connect(self._take_hires_screenshot)
        view_menu.addAction(hires_screenshot_action)
        
        view_menu.addSeparator()
        
        # Toggle axes action
        axes_action = QAction("Show Axes", self)
        axes_action.setCheckable(True)
        axes_action.setChecked(self.settings_manager.settings.show_axes)
        axes_action.triggered.connect(lambda checked: self.viewer.toggle_axes(checked))
        view_menu.addAction(axes_action)
        # Create appearance menu (colors, lighting)
        self._create_appearance_menu()
        
        # Settings menu
        settings_menu = menu_bar.addMenu("&Settings")
        
        # Auto-load last model
        auto_load_action = QAction("Auto-load Last Model", self)
        auto_load_action.setCheckable(True)
        auto_load_action.setChecked(self.settings_manager.settings.auto_load_last)
        auto_load_action.triggered.connect(
            lambda checked: self.settings_manager.update_settings(auto_load_last=checked)
        )
        settings_menu.addAction(auto_load_action)
    def _create_status_bar(self):
        """Create the status bar"""
        self.statusBar().showMessage("Ready")

    def _create_dock_widgets(self):
        """Create dock widgets"""
        pass  # We removed the properties panel

    def _set_model_color(self):
        """Open color picker for model color"""
        color = QColorDialog.getColor()
        if color.isValid():
            rgb = color.getRgbF()[:3]
            self.viewer.set_model_color(rgb)
            self.settings_manager.update_settings(model_color=rgb)

    def _set_background_color(self):
        """Open color picker for background color"""
        color = QColorDialog.getColor()
        if color.isValid():
            rgb = color.getRgbF()[:3]
            self.viewer.set_background_color(rgb)
            self.settings_manager.update_settings(background_color=rgb)

    def _toggle_background_gradient(self, enabled):
        """Toggle background gradient"""
        self.viewer.set_background_gradient(enabled)
        self.settings_manager.update_settings(background_gradient=enabled)

    def _toggle_light(self, light_name, enabled):
        """Toggle a specific light source"""
        self.viewer.toggle_light(light_name, enabled)
        # Update settings
        light_states = self.settings_manager.settings.light_states.copy()
        light_states[light_name] = enabled
        self.settings_manager.update_settings(light_states=light_states)

    def _create_appearance_menu(self):
        """Create appearance menu for color and lighting controls"""
        appearance_menu = self.menuBar().addMenu("&Appearance")
        
        # Model color action
        model_color_action = QAction("Set Model Color...", self)
        model_color_action.triggered.connect(self._set_model_color)
        appearance_menu.addAction(model_color_action)
        appearance_menu.addSeparator()
        
        # Background color action
        bg_color_action = QAction("Set Background Color...", self)
        bg_color_action.triggered.connect(self._set_background_color)
        appearance_menu.addAction(bg_color_action)
        
        # Background gradient action
        bg_gradient_action = QAction("Enable Background Gradient", self)
        bg_gradient_action.setCheckable(True)
        bg_gradient_action.setChecked(self.settings_manager.settings.background_gradient)
        bg_gradient_action.triggered.connect(self._toggle_background_gradient)
        appearance_menu.addAction(bg_gradient_action)
        
        appearance_menu.addSeparator()
        
        # Lighting submenu
        lighting_menu = appearance_menu.addMenu("Lighting")
        
        # Light configurations
        light_configs = [
            ("ambient", "Ambient Light"),
            ("key", "Key Light"),
            ("fill", "Fill Light"),
            ("rim", "Rim Light")
        ]
        
        # Get light states from settings
        light_states = self.settings_manager.settings.light_states
        
        # Create light toggle actions
        for light_id, light_name in light_configs:
            action = QAction(light_name, self)
            action.setCheckable(True)
            action.setChecked(light_states.get(light_id, True))
            action.triggered.connect(
                lambda checked, lid=light_id: self._toggle_light(lid, checked)
            )
            lighting_menu.addAction(action)
            self.light_actions[light_id] = action
        
        # Add intensity slider
        lighting_menu.addSeparator()
        intensity_action = QWidgetAction(self)
        intensity_widget = QWidget()
        intensity_layout = QHBoxLayout(intensity_widget)
        intensity_layout.setContentsMargins(8, 4, 8, 4)
        
        intensity_label = QLabel("Intensity:", intensity_widget)
        intensity_layout.addWidget(intensity_label)
        
        self.intensity_slider = QSlider(Qt.Orientation.Horizontal, intensity_widget)
        self.intensity_slider.setMinimum(50)
        self.intensity_slider.setMaximum(300)
        initial_intensity = int(self.settings_manager.settings.light_intensity * 100)
        self.intensity_slider.setValue(initial_intensity)
        self.intensity_slider.setToolTip("Adjust overall light intensity (50% - 300%)")
        self.intensity_slider.valueChanged.connect(
            lambda v: self._set_light_intensity(v / 100)
        )
        intensity_layout.addWidget(self.intensity_slider)
        
        intensity_value_label = QLabel(f"{initial_intensity}%", intensity_widget)
        self.intensity_slider.valueChanged.connect(
            lambda v: intensity_value_label.setText(f"{v}%")
        )
        intensity_layout.addWidget(intensity_value_label)
        
        intensity_action.setDefaultWidget(intensity_widget)
        lighting_menu.addAction(intensity_action)

    def _set_light_intensity(self, intensity: float):
        """Set the overall light intensity"""
        self.viewer.set_light_intensity(intensity)
        self.settings_manager.update_settings(light_intensity=intensity)

    def _apply_saved_settings(self):
        """Apply saved settings from previous session"""
        settings = self.settings_manager.settings
        
        # Apply colors
        self.viewer.set_model_color(settings.model_color)
        self.viewer.set_background_color(settings.background_color)
        self.viewer.set_background_gradient(settings.background_gradient)
        
        # Apply light states
        for light_name, enabled in settings.light_states.items():
            if light_name in self.light_actions:
                self.light_actions[light_name].setChecked(enabled)
            self.viewer.toggle_light(light_name, enabled)
        # Apply light intensity
        # Apply it before setting the slider to ensure it's applied even if slider isn't created yet
        self.viewer.set_light_intensity(settings.light_intensity)
        if hasattr(self, 'intensity_slider'):
            self.intensity_slider.setValue(int(settings.light_intensity * 100))
            
        # Apply axes visibility
        self.viewer.toggle_axes(settings.show_axes)

    def _set_default_directory(self):
        """Set the default directory for file browsing"""
        directory = QFileDialog.getExistingDirectory(
            self,
            "Select Default Directory",
            self.current_dir,
            QFileDialog.Option.ShowDirsOnly
        )
        
        if directory:
            # Update current directory and settings
            self.current_dir = directory
            self._populate_file_model(directory)
            self.settings_manager.update_settings(last_directory=directory)
            self.statusBar().showMessage(f"Default directory set to: {directory}")

    def _take_screenshot(self):
        """
        Take a regular screenshot of the current view using the custom dialog
        with three options: save next to original, choose location, or cancel
        """
        # Check if a model is loaded
        if not self.viewer.actors:
            QMessageBox.warning(self, "No Model", "No model is currently loaded to take a screenshot.")
            self.statusBar().showMessage("Screenshot failed: No model loaded")
            return
            
        # Find the original model file path of the currently loaded model
        model_path = self._get_current_model_path()
        
        # Take the screenshot
        self.statusBar().showMessage("Taking screenshot...")
        success, result = self.viewer.take_screenshot(model_path)
        
        # Handle the result
        if success:
            self.statusBar().showMessage(f"Screenshot saved to: {result}")
        else:
            self.statusBar().showMessage(f"Screenshot failed: {result}")
            if "cancelled" not in result.lower():
                QMessageBox.warning(self, "Screenshot Error", result)
    
    def _take_hires_screenshot(self):
        """
        Take a high-resolution screenshot (4x normal resolution)
        """
        # Check if a model is loaded
        if not self.viewer.actors:
            QMessageBox.warning(self, "No Model", "No model is currently loaded to take a screenshot.")
            self.statusBar().showMessage("High-res screenshot failed: No model loaded")
            return
            
        # Find the original model file path of the currently loaded model
        model_path = self._get_current_model_path()
        
        # Take the high-res screenshot (4x normal resolution)
        self.statusBar().showMessage("Taking high-resolution screenshot...")
        success, result = self.viewer.take_high_res_screenshot(model_path, scale_factor=4)
        
        # Handle the result
        if success:
            self.statusBar().showMessage(f"High-resolution screenshot saved to: {result}")
        else:
            self.statusBar().showMessage(f"High-resolution screenshot failed: {result}")
            if "cancelled" not in result.lower():
                QMessageBox.warning(self, "Screenshot Error", result)
    
    def _get_current_model_path(self):
        """
        Get the file path of the currently loaded model
        
        Returns:
            str or None: Path to the current model file, or None if not found
        """
        # Find out the original model file path
        for item_idx in range(self.file_model.rowCount()):
            item = self.file_model.item(item_idx)
            file_path = item.data()
            if not file_path or not os.path.isfile(file_path):
                continue
                
            # Check if this is a model file and if it's loaded
            ext = os.path.splitext(file_path)[1].lower()
            if ext in self.file_filters:
                base_name = os.path.basename(file_path)
                if base_name in self.viewer.actors:
                    return file_path
        
        return None

    def resizeEvent(self, event):
        """Handle window resize event to maintain proper proportions"""
        super().resizeEvent(event)
        # Update file tree width to maintain 30% of the window width
        self.file_tree.setMaximumWidth(int(self.width() * 0.3))

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
