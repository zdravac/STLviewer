import os
import traceback
from typing import Optional, Tuple, Union, Literal
from pathlib import Path
from enum import Enum

import vtk
from PyQt6.QtCore import QDir, QFileInfo, Qt
from PyQt6.QtWidgets import QFileDialog, QWidget, QMessageBox, QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel


class SaveOption(Enum):
    """Options for saving screenshots"""
    SAVE_NEXT_TO_ORIGINAL = 1
    CHOOSE_LOCATION = 2
    CANCEL = 3

class SaveScreenshotDialog(QDialog):
    """Dialog for screenshot saving options"""
    
    def __init__(self, parent=None, model_path=None):
        super().__init__(parent)
        self.model_path = model_path
        self.setWindowTitle("Save Screenshot")
        self.setMinimumWidth(400)
        
        # Main layout
        layout = QVBoxLayout(self)
        
        # Information label
        if model_path:
            model_name = os.path.basename(model_path)
            layout.addWidget(QLabel(f"Save screenshot of model: {model_name}"))
        else:
            layout.addWidget(QLabel("Save screenshot of current view"))
            
        # Options layout
        buttons_layout = QVBoxLayout()
        
        # Option 1: Save next to original
        self.btn_save_next = QPushButton("Save next to original model file")
        self.btn_save_next.setEnabled(model_path is not None)
        if model_path:
            model_dir = os.path.dirname(model_path)
            model_name = os.path.splitext(os.path.basename(model_path))[0]
            tooltip = f"Save as {model_name}.png in {model_dir}"
            self.btn_save_next.setToolTip(tooltip)
        buttons_layout.addWidget(self.btn_save_next)
        
        # Option 2: Choose location
        self.btn_choose = QPushButton("Choose where to save")
        buttons_layout.addWidget(self.btn_choose)
        
        # Option 3: Cancel
        self.btn_cancel = QPushButton("Cancel")
        buttons_layout.addWidget(self.btn_cancel)
        
        layout.addLayout(buttons_layout)
        
        # Connect buttons
        self.btn_save_next.clicked.connect(self._save_next_to_original)
        self.btn_choose.clicked.connect(self._choose_location)
        self.btn_cancel.clicked.connect(self.reject)
        
        # Set button styles
        self.btn_save_next.setDefault(True)
        self.btn_cancel.setStyleSheet("color: #555;")
        
    def _save_next_to_original(self):
        self.selected_option = SaveOption.SAVE_NEXT_TO_ORIGINAL
        self.accept()
        
    def _choose_location(self):
        self.selected_option = SaveOption.CHOOSE_LOCATION
        self.accept()
        
    def get_result(self):
        """Get the selected option after dialog execution"""
        if self.result() == QDialog.DialogCode.Accepted:
            return self.selected_option
        return SaveOption.CANCEL

class ScreenshotTools:
    """Class that handles capturing and saving screenshots from a VTK render window."""
    
    # Define supported image formats
    FORMAT_PNG = "png"
    SUPPORTED_FORMATS = [FORMAT_PNG]
    
    def __init__(self, render_window: vtk.vtkRenderWindow, parent_widget: QWidget = None):
        """
        Initialize the screenshot tools with a render window and parent widget.
        
        Args:
            render_window: The VTK render window to capture screenshots from
            parent_widget: The parent Qt widget for dialogs
        """
        self.render_window = render_window
        self.parent_widget = parent_widget
    
    def capture_screenshot(self, render_window: vtk.vtkRenderWindow = None, high_res: bool = False) -> vtk.vtkWindowToImageFilter:
        """
        Captures a screenshot from a VTK render window.
        
        Args:
            render_window: The VTK render window to capture from
            high_res: Whether to capture a high-resolution screenshot (400 DPI vs 75 DPI)
            
        Returns:
            A VTK window to image filter with the captured screenshot
        """
        window_to_image_filter = vtk.vtkWindowToImageFilter()
        # Use provided render window or the instance's render window
        render_window_to_use = render_window if render_window is not None else self.render_window
        window_to_image_filter.SetInput(render_window_to_use)
        
        # Set resolution based on high_res flag
        # Regular screenshots: 75 DPI (scale factor ~1)
        # High-res screenshots: 400 DPI (scale factor ~5-6)
        scale_factor = 5 if high_res else 1
        window_to_image_filter.SetScale(scale_factor)
        
        window_to_image_filter.SetInputBufferTypeToRGBA()  # Capture alpha channel
        window_to_image_filter.ReadFrontBufferOff()  # Read from back buffer
        window_to_image_filter.Update()
        return window_to_image_filter
    
    def save_screenshot(
        self,
        window_to_image_filter: vtk.vtkWindowToImageFilter,
        file_path: str,
        format: str = FORMAT_PNG
    ) -> bool:
        """
        Saves a captured screenshot to a file.
        
        Args:
            window_to_image_filter: The VTK window to image filter with captured image
            file_path: Path where the screenshot should be saved
            format: Image format to save as (jpg or png)
            quality: Image quality (0-100, only applies to jpg)
            
        Returns:
            bool: True if saved successfully, False otherwise
        """
        # Validate format
        # Validate format
        format = format.lower()
        if format not in self.SUPPORTED_FORMATS:
            raise ValueError(f"Unsupported image format: {format}. " 
                            f"Supported formats are: {', '.join(self.SUPPORTED_FORMATS)}")
        try:
            # Ensure the directory exists
            os.makedirs(os.path.dirname(os.path.abspath(file_path)), exist_ok=True)
            
            # Create writer based on format
            if format == self.FORMAT_PNG:
                writer = vtk.vtkPNGWriter()
            else:
                return False
                
            # Write the file
            writer.SetFileName(file_path)
            writer.SetInputConnection(window_to_image_filter.GetOutputPort())
            writer.Write()
            
            return os.path.exists(file_path)
            
        except Exception as e:
            print(f"Error saving screenshot: {str(e)}")
            traceback.print_exc()
            return False
    
    def capture_and_save_to_model_location(
        self,
        model_path: str,
        render_window: vtk.vtkRenderWindow = None,
        format: str = FORMAT_PNG
    ) -> Tuple[bool, str]:
        """
        Captures a screenshot and saves it next to the model file with the same name.
        
        Args:
            render_window: The VTK render window to capture from
            model_path: Path to the model file
            format: Image format to save as (jpg or png)
            quality: Image quality (0-100, only applies to jpg)
            
        Returns:
            Tuple[bool, str]: (Success status, Path to saved file or error message)
        """
        try:
            # Generate screenshot path based on model path
            model_info = QFileInfo(model_path)
            screenshot_path = f"{model_info.absolutePath()}/{model_info.baseName()}.{format}"
            
            # Capture and save screenshot
            render_window_to_use = render_window if render_window is not None else self.render_window
            window_filter = self.capture_screenshot(render_window_to_use)
            success = self.save_screenshot(
                window_filter, screenshot_path, format)
            
            if success:
                return True, screenshot_path
            else:
                return False, f"Failed to save screenshot to {screenshot_path}"
        except Exception as e:
            return False, f"Error capturing screenshot: {str(e)}"
    
    def prompt_save_screenshot(
        self,
        default_path: Optional[str] = None,
        parent: QWidget = None,
        render_window: vtk.vtkRenderWindow = None,
        default_format: str = FORMAT_PNG
    ) -> Tuple[bool, str]:
        """
        Prompts the user to select where to save the screenshot and saves it.
        
        Args:
            parent: Parent widget for the file dialog
            render_window: The VTK render window to capture from
            default_path: Default directory to open the file dialog
            default_format: Default image format
            
        Returns:
            Tuple[bool, str]: (Success status, Path to saved file or error message)
        """
        try:
            # Prepare file dialog filters
            filters = "PNG Image (*.png)"
            selected_filter = "PNG Image (*.png)"
            
            # Show save dialog
            parent_to_use = parent if parent is not None else self.parent_widget
            file_path, filter_used = QFileDialog.getSaveFileName(
                parent_to_use,
                "Save Screenshot",
                default_path or QDir.homePath(),
                filters,
                selected_filter
            )
            
            if not file_path:
                return False, "Screenshot saving cancelled"
            
            # Format is always PNG
            format = self.FORMAT_PNG
                
            # Ensure proper extension
            if not file_path.lower().endswith(f".{format}"):
                file_path += f".{format}"
                
                
            # Capture and save screenshot
            render_window_to_use = render_window if render_window is not None else self.render_window
            window_filter = self.capture_screenshot(render_window_to_use)
            success = self.save_screenshot(window_filter, file_path, format)
            if success:
                return True, file_path
            else:
                return False, f"Failed to save screenshot to {file_path}"
        except Exception as e:
            return False, f"Error saving screenshot: {str(e)}"

    
    def prompt_for_screenshot_options(
        self,
        model_path: Optional[str] = None,
        parent: QWidget = None,
        render_window: vtk.vtkRenderWindow = None,
        window_to_image_filter: vtk.vtkWindowToImageFilter = None
    ) -> Tuple[bool, str]:
        """
        Prompts the user to select screenshot saving options and saves the screenshot accordingly.
        
        Args:
            parent: Parent widget for the dialog
            render_window: The VTK render window to capture from
            model_path: Path to the currently loaded model file (if any)
            
        Returns:
            Tuple[bool, str]: (Success status, Path to saved file or error message)
        """
        try:
            # Show dialog with options
            parent_to_use = parent if parent is not None else self.parent_widget
            dialog = SaveScreenshotDialog(parent_to_use, model_path)
            dialog.exec()
            
            selected_option = dialog.get_result()
            
            if selected_option == SaveOption.CANCEL:
                return False, "Screenshot cancelled"
                
            # Use provided filter or capture a new screenshot
            if window_to_image_filter is not None:
                window_filter = window_to_image_filter
            else:
                # Capture the screenshot
                render_window_to_use = render_window if render_window is not None else self.render_window
                window_filter = self.capture_screenshot(render_window_to_use)
                
            if selected_option == SaveOption.SAVE_NEXT_TO_ORIGINAL:
                if not model_path:
                    return False, "No model path provided"
                    
                # Generate path next to original
                model_info = QFileInfo(model_path)
                screenshot_path = f"{model_info.absolutePath()}/{model_info.baseName()}.png"
                
                # Save the screenshot
                success = self.save_screenshot(
                    window_filter, 
                    screenshot_path, 
                    format=self.FORMAT_PNG
                )
                if success:
                    return True, screenshot_path
                else:
                    return False, f"Failed to save screenshot to {screenshot_path}"
                    
            elif selected_option == SaveOption.CHOOSE_LOCATION:
                # Show save dialog with default filename
                default_dir = os.path.dirname(model_path) if model_path else QDir.homePath()
                default_filename = ""
                if model_path:
                    # Use the model name for the default filename
                    model_info = QFileInfo(model_path)
                    default_filename = f"{model_info.baseName()}.png"
                    default_path = os.path.join(default_dir, default_filename)
                else:
                    default_path = default_dir
                
                file_path, _ = QFileDialog.getSaveFileName(
                    parent_to_use,
                    "Save Screenshot",
                    default_path,
                    "PNG Image (*.png)"
                )
                
                if not file_path:
                    return False, "Screenshot saving cancelled"
                    
                # Ensure proper extension
                if not file_path.lower().endswith(f".{self.FORMAT_PNG}"):
                    file_path += f".{self.FORMAT_PNG}"
                    
                # Save the screenshot
                success = self.save_screenshot(
                    window_filter, 
                    file_path,
                    format=self.FORMAT_PNG
                )
                if success:
                    return True, file_path
                else:
                    return False, f"Failed to save screenshot to {file_path}"
            
            return False, "Screenshot cancelled"
                
        except Exception as e:
            return False, f"Error saving screenshot: {str(e)}"
