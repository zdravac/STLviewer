"""
Object manager for handling object properties and tree view
"""
from PyQt6.QtWidgets import (
    QTreeWidget, QTreeWidgetItem, QWidget, QVBoxLayout, QHBoxLayout,
    QCheckBox, QColorDialog, QSlider, QLabel, QPushButton
)
from PyQt6.QtCore import Qt, pyqtSignal
from dataclasses import dataclass
from typing import Optional

@dataclass
class ObjectProperties:
    """Properties for a 3D object"""
    name: str = ""
    visible: bool = True
    color: tuple = (0.8, 0.8, 0.8)
    opacity: float = 1.0
    wireframe: bool = False
    cast_shadows: bool = True
    receive_shadows: bool = True

@dataclass
class Color3MF:
    """Color information from 3MF file"""
    r: float
    g: float
    b: float
    a: float = 1.0

class ObjectTreeWidget(QTreeWidget):
    """Tree widget for displaying and managing 3D objects"""
    object_visibility_changed = pyqtSignal(str, bool)
    object_color_changed = pyqtSignal(str, tuple)
    object_opacity_changed = pyqtSignal(str, float)
    object_wireframe_changed = pyqtSignal(str, bool)
    object_shadows_changed = pyqtSignal(str, bool, bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setHeaderLabels(["Objects"])  # Single column for cleaner look
        self.setColumnWidth(0, 200)  # Wider for better visibility
        self.setExpandsOnDoubleClick(False)
        self.setAlternatingRowColors(True)
        
        # Container widget for properties
        self.properties_container = QWidget()
        self.properties_layout = QVBoxLayout(self.properties_container)
        self.properties_layout.setContentsMargins(4, 4, 4, 4)
        self.properties_layout.setSpacing(4)
        
        # Dictionary to store property widgets
        self.property_widgets = {}

    def add_object(self, name: str):
        """Add a new object to the tree"""
        # Remove any existing object with the same name
        self.remove_object(name)
        
        # Create tree item
        item = QTreeWidgetItem(self)
        item.setText(0, name)
        self.addTopLevelItem(item)
        
        # Create property widget
        prop_widget = ObjectPropertiesWidget(name)
        
        # Clear existing widgets from container
        while self.properties_layout.count():
            child = self.properties_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        
        # Add new property widget to container
        self.properties_layout.addWidget(prop_widget)
        self.properties_layout.addStretch()
        
        # Connect signals
        prop_widget.visibility_changed.connect(
            lambda checked: self.object_visibility_changed.emit(name, checked)
        )
        prop_widget.color_changed.connect(
            lambda color: self.object_color_changed.emit(name, color)
        )
        prop_widget.opacity_changed.connect(
            lambda value: self.object_opacity_changed.emit(name, value)
        )
        prop_widget.wireframe_changed.connect(
            lambda checked: self.object_wireframe_changed.emit(name, checked)
        )
        prop_widget.shadows_changed.connect(
            lambda cast, receive: self.object_shadows_changed.emit(name, cast, receive)
        )
        
        self.property_widgets[name] = prop_widget
        return prop_widget
        
    def remove_object(self, name: str):
        """Remove an object from the tree"""
        if name in self.property_widgets:
            # Find and remove the tree item
            items = self.findItems(name, Qt.MatchFlag.MatchExactly)
            for item in items:
                index = self.indexOfTopLevelItem(item)
                if index >= 0:
                    self.takeTopLevelItem(index)
            
            # Remove property widget
            self.property_widgets[name].deleteLater()
            del self.property_widgets[name]
    
    def clear_objects(self):
        """Clear all objects from the tree"""
        self.clear()
        for widget in self.property_widgets.values():
            widget.deleteLater()
        self.property_widgets.clear()

    def get_properties_container(self):
        """Get the properties container widget"""
        return self.properties_container

class ObjectPropertiesWidget(QWidget):
    """Widget for controlling object properties"""
    visibility_changed = pyqtSignal(bool)
    color_changed = pyqtSignal(tuple)
    opacity_changed = pyqtSignal(float)
    wireframe_changed = pyqtSignal(bool)
    shadows_changed = pyqtSignal(bool, bool)

    def __init__(self, name: str, parent=None):
        super().__init__(parent)
        self.name = name
        self.current_color = (0.8, 0.8, 0.8)  # Store current color
        self._setup_ui()

    def _setup_ui(self):
        """Set up the UI controls"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        # Object name label
        name_label = QLabel(f"<b>{self.name}</b>")
        layout.addWidget(name_label)

        # Visibility checkbox
        self.visibility_check = QCheckBox("Visible")
        self.visibility_check.setChecked(True)
        self.visibility_check.toggled.connect(self.visibility_changed)
        layout.addWidget(self.visibility_check)

        # Color selection
        color_layout = QHBoxLayout()
        color_label = QLabel("Color:")
        self.color_button = QPushButton()
        self.color_button.setFixedSize(24, 24)
        self._update_color_button()
        self.color_button.clicked.connect(self._choose_color)
        color_layout.addWidget(color_label)
        color_layout.addWidget(self.color_button)
        color_layout.addStretch()
        layout.addLayout(color_layout)

        # Opacity control
        opacity_layout = QHBoxLayout()
        opacity_label = QLabel("Opacity:")
        self.opacity_slider = QSlider(Qt.Orientation.Horizontal)
        self.opacity_slider.setRange(0, 100)
        self.opacity_slider.setValue(100)
        self.opacity_value = QLabel("100%")
        self.opacity_slider.valueChanged.connect(self._update_opacity)
        opacity_layout.addWidget(opacity_label)
        opacity_layout
