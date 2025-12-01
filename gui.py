#!/usr/bin/env python3
"""
gui.py

Contains the MainWindow class for the Temporal Scalar Field Generator application.
Handles the PyQt5 GUI, VTK rendering, menu creation, user interactions, and automatic
export of scalar fields at each time step.

Dependencies:
- PyQt5
- VTK
- gaussian_scene.py (GaussianScene class)
- vector_field.py (VectorFieldGenerator class)
"""

from umbrella_tracker import update_umbrella_tracking
from plot import plot_tracking_timeline

from noises import apply_noise_to_scalar_field

from gaussian_dock_window import GaussianDock

import math
import os
from functools import partial
from PyQt5 import QtCore, QtGui, QtWidgets
from vtkmodules.qt.QVTKRenderWindowInteractor import QVTKRenderWindowInteractor
import vtkmodules.vtkInteractionStyle
import vtkmodules.vtkRenderingOpenGL2
from vtkmodules.vtkRenderingCore import (
    vtkRenderer, vtkRenderWindow, vtkActor, vtkPolyDataMapper,
    vtkImageActor, vtkRenderWindowInteractor
)
from vtkmodules.vtkCommonDataModel import vtkImageData
from vtkmodules.vtkFiltersSources import vtkArrowSource
from vtkmodules.vtkFiltersCore import vtkGlyph3D
from vtkmodules.vtkIOXML import vtkXMLImageDataWriter
from vtkmodules.vtkIOLegacy import vtkStructuredPointsWriter
from vtkmodules.vtkCommonColor import vtkNamedColors
from vtkmodules.vtkFiltersModeling import vtkOutlineFilter
from vtkmodules.vtkInteractionStyle import vtkInteractorStyleImage
from vtkmodules.vtkInteractionStyle import vtkInteractorStyleTrackballCamera
import vtk
from gaussian_scene import GaussianScene
from vector_field import VectorFieldGenerator

from PyQt5.QtGui import QIcon

import numpy as np


def random_seed_points(num_seeds, width, height, spacing):
    pts = vtk.vtkPoints()
    pd = vtk.vtkPolyData()

    for _ in range(num_seeds):
        x = np.random.uniform(0, width * spacing)
        y = np.random.uniform(0, height * spacing)
        z = 0.005  # middle slice
        pts.InsertNextPoint(x, y, z)

    pd.SetPoints(pts)
    return pd


class MainWindow(QtWidgets.QMainWindow):
    """
    Main window for the application, managing the GUI, VTK rendering, and scalar field export.
    Provides menus for file operations, view controls, creation of scalar/vector fields,
    export configuration, and automatic export at each time step.
    """
    def __init__(self, parent=None):
        """
        Initialize the main window, VTK renderer, menus, and export settings.

        Args:
            parent: Parent widget (default: None).
        """
        super().__init__(parent)
        self.setWindowTitle('Temporal Scalar Field Generator')
        self.resize(1200, 800)

        # Central widget setup
        self.frame = QtWidgets.QFrame()
        self.layout = QtWidgets.QHBoxLayout()
        self.frame.setLayout(self.layout)
        self.setCentralWidget(self.frame)

        # VTK widget setup
        self.vtk_widget = QVTKRenderWindowInteractor(self.frame)
        self.layout.addWidget(self.vtk_widget, stretch=1)
        self.renderer = vtkRenderer()
        self.renderer.SetBackground(0.13, 0.14, 0.18)
        self.vtk_widget.GetRenderWindow().AddRenderer(self.renderer)
        self.iren = self.vtk_widget.GetRenderWindow().GetInteractor()

        self.colors = vtkNamedColors()

        self.gaussian_centers_actor = None

        # Initialize outline and contour actors
        self._create_outline()
        self._create_contours()

        # Initialize Gaussian scene
        self.grid_w = 50
        self.grid_h = 50
        self.gaussian_scene = GaussianScene(width=self.grid_w, height=self.grid_h)
        self.image_actor = None

        # Export settings
        self.export_enabled = False
        self.export_format = 'vti'  # Default to VTI
        self.export_dir = ''
        self.export_counter = 0


        self.tracking_timestep = 0
        self.tracking_output = os.path.join(os.getcwd(), "umbrella_output")

        # Create menus
        self._create_menus()

        self._create_toolbar()

        # Initialize dock widget placeholder
        self.gaussian_dock = None

        self.selected_gaussian_id = None
        self.pick_mode = False

        # Set 2D interactor style
        self.style = vtkInteractorStyleImage()
        self.istyle = vtkInteractorStyleTrackballCamera()
        self.iren.SetInteractorStyle(self.style)

        self.export_downsample = 1

        # store events
        self.events = []

        #noise details

        self.noise_type = 'None'
        self.noise_amount = 0.0


        # Timer for periodic updates
        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.update)
        self.timer.start(1000)

        self._apply_global_styles() 

        self.gaussian_path_actors = {}
        self.selected_vector_field_type = None


        # Start interactor
        self.iren.Start()

    def update(self):
        """
        Update the Gaussian scene, move Gaussians toward the center, refresh the visualization,
        and export the scalar field if enabled.
        """
        #self.gaussian_scene.move_gaussians_toward_center(0.5)
        if self.selected_vector_field_type is not None and self.selected_vector_field_type == "Custom": 
            self.gaussian_scene.move_gaussians_by_custom_path(getattr(self, "vector_field_data", None), speed=0.5)
        else:
            self.gaussian_scene.move_gaussians_by_vector_field(getattr(self, "vector_field_data", None), speed=0.5)

        self._update_timer()
        if self.export_enabled:
            self._export_scalar_field()

    def _create_contours(self):
        """
        Initialize the contour filter, mapper, and actor for visualizing scalar field contours.
        """

        self.contour_actors = []

        self.contour = vtk.vtkContourFilter()
        img = vtkImageData()
        img.SetDimensions(1, 1, 1)
        self.contour.SetInputData(img)
        self.contour.GenerateValues(30, img.GetScalarRange())

        self.cmapper = vtk.vtkPolyDataMapper()
        self.cmapper.SetInputConnection(self.contour.GetOutputPort())

        self.cactor = vtk.vtkActor()
        self.cactor.SetMapper(self.cmapper)

        self.renderer.AddActor(self.cactor)

    def _create_outline(self):
        """
        Create an outline actor for the visualization bounds (not displayed by default).
        """
        outline = vtkOutlineFilter()
        img = vtkImageData()
        img.SetDimensions(1, 1, 1)
        outline.SetInputData(img)
        outline.Update()
        mapper = vtkPolyDataMapper()
        mapper.SetInputConnection(outline.GetOutputPort())
        actor = vtkActor()
        actor.SetMapper(mapper)
        actor.GetProperty().SetColor(self.colors.GetColor3d('Black'))

    def _create_menus(self):
        """
        Create the menu bar with File, View, Create, Export, and Help menus.
        Adds an 'Export Settings' option to configure automatic exports.
        """
        menubar = self.menuBar()

        # File menu
        file_menu = menubar.addMenu('&File')
        new_act = QtWidgets.QAction('&New', self)
        new_act.setShortcut('Ctrl+N')
        new_act.triggered.connect(self.on_new)
        open_act = QtWidgets.QAction('&Open', self)
        open_act.setShortcut('Ctrl+O')
        open_act.triggered.connect(self.on_open)
        close_act = QtWidgets.QAction('&Close', self)
        close_act.triggered.connect(self.on_close)
        exit_act = QtWidgets.QAction('E&xit', self)
        exit_act.setShortcut('Ctrl+Q')
        exit_act.triggered.connect(QtWidgets.qApp.quit)
        file_menu.addAction(new_act)
        file_menu.addAction(open_act)
        file_menu.addAction(close_act)
        file_menu.addSeparator()
        file_menu.addAction(exit_act)

        # View menu
        view_menu = menubar.addMenu('&View')
        zoom_in_act = QtWidgets.QAction('Zoom &In', self)
        zoom_in_act.setShortcut('Ctrl++')
        zoom_in_act.triggered.connect(partial(self.zoom, 0.8))
        zoom_out_act = QtWidgets.QAction('Zoom &Out', self)
        zoom_out_act.setShortcut('Ctrl+-')
        zoom_out_act.triggered.connect(partial(self.zoom, 1.25))
        reset_act = QtWidgets.QAction('&Reset Camera', self)
        reset_act.setShortcut('Ctrl+R')
        reset_act.triggered.connect(self.reset_camera)
        view_menu.addAction(zoom_in_act)
        view_menu.addAction(zoom_out_act)
        view_menu.addAction(reset_act)

        # Create menu
        create_menu = menubar.addMenu('&Create')
        gaussian_act = QtWidgets.QAction('&Gaussian', self)
        gaussian_act.triggered.connect(self.open_gaussian_dock)
        variants_act = QtWidgets.QAction('&Other Variants', self)
        variants_act.triggered.connect(self.create_other_variants)
        vector_act = QtWidgets.QAction('&Vector Field', self)
        vector_act.triggered.connect(self.open_vector_field_dialog)
        create_menu.addAction(gaussian_act)
        create_menu.addAction(variants_act)
        create_menu.addAction(vector_act)


        #scenario menu
        scenario_menu = menubar.addMenu('&Scenario')

        scenario_act = QtWidgets.QAction('Open Scenario Generator', self)
        scenario_act.triggered.connect(self.open_scenario_generator)
        scenario_menu.addAction(scenario_act)


        # Export menu
        export_menu = menubar.addMenu('&Export')
        export_settings_act = QtWidgets.QAction('Export &Settings', self)
        export_settings_act.triggered.connect(self.open_export_settings)
        export_vti = QtWidgets.QAction('Export to &VTI (XML ImageData)', self)
        export_vti.triggered.connect(self.export_vti)
        export_vtk = QtWidgets.QAction('Export to &VTK (legacy)', self)
        export_vtk.triggered.connect(self.export_vtk_legacy)
        export_menu.addAction(export_settings_act)
        export_menu.addAction(export_vti)
        export_menu.addAction(export_vtk)

        # Help menu
        help_menu = menubar.addMenu('&Help')
        shortcuts_act = QtWidgets.QAction('&Shortcuts', self)
        shortcuts_act.triggered.connect(self.show_shortcuts)
        about_act = QtWidgets.QAction('&About', self)
        about_act.triggered.connect(self.show_about)
        help_menu.addAction(shortcuts_act)
        help_menu.addAction(about_act)


    def _create_toolbar(self):
        """
        Create a toolbar with controls to start and pause scalar field generation.
        """
        toolbar = self.addToolBar("Simulation Controls")
        toolbar.setMovable(False)

        # Start/Resume button
        self.action_start = QtWidgets.QAction(QtGui.QIcon.fromTheme("media-playback-start"), "Start/Resume", self)
        self.action_start.setToolTip("Start or resume scalar field generation")
        self.action_start.triggered.connect(self.resume_scalar_generation)
        toolbar.addAction(self.action_start)

        # Pause button
        self.action_pause = QtWidgets.QAction(QtGui.QIcon.fromTheme("media-playback-pause"), "Pause", self)
        self.action_pause.setToolTip("Pause scalar field generation")
        self.action_pause.triggered.connect(self.pause_scalar_generation)
        toolbar.addAction(self.action_pause)
        self.action_start.setIcon(QIcon.fromTheme("media-playback-start"))
        self.action_pause.setIcon(QIcon.fromTheme("media-playback-pause"))



        toolbar.addSeparator()


    def open_scenario_generator__(self):
        from scenario_generator import ScenarioGUI   # import your generator GUI
        
        # Create the window ONCE
        if not hasattr(self, 'scenario_gui') or self.scenario_gui is None:
            self.scenario_gui = ScenarioGUI(parent=self)
            self.scenario_gui.scene_generated.connect(self.on_scenario_generated)
        
        self.scenario_gui.show()
        self.scenario_gui.raise_()

    def open_scenario_generator(self):
        from scenario_generator import ScenarioGUI

        # Create as independent window (NO PARENT)
        if not hasattr(self, 'scenario_gui') or self.scenario_gui is None:
            self.scenario_gui = ScenarioGUI(parent=None)  # <--- MAKE TOP-LEVEL WINDOW
            self.scenario_gui.scene_generated.connect(self.on_scenario_generated)

        self.scenario_gui.show()
        self.scenario_gui.raise_()
        self.scenario_gui.activateWindow()



    def update_gaussian_list(self):
        try:
            self.gaussian_dock.gauss_list.clear()
            for g in self.gaussian_scene.gaussians:
                self.gaussian_dock.gauss_list.addItem(
                    f"ID={g['id']} | x={g['x']:.2f} y={g['y']:.2f} amp={g['amp']:.2f} var={g['var']:.2f}"
                )
        except Exception as e:
            print("Gaussian list update failed:", e)


    def on_scenario_generated(self, scene, vector_field,vector_field_type):
        # Replace current Gaussian scene
        self.gaussian_scene = scene
        
        # Reset existing data
        self.vector_field_data = None

        vector_field = None
        self.selected_vector_field_type = vector_field_type
        
        # Clear existing actors
        self.renderer.RemoveAllViewProps()

        # Recreate outline + contours
        self._create_outline()
        self._create_contours()

        self.draw_outline(scene.width, scene.height, scene.spacing)

        self.update_gaussian_list()

        # Visualize scalar field
        img = self.gaussian_scene.generate_image_data()
        self.contour.SetInputData(img)
        self.contour.GenerateValues(30, img.GetScalarRange())
        self.contour.Update()

        # If vector field exists: add streamlines + glyphs
        if vector_field is not None:
            self._add_vector_field_visualization(vector_field)

        # Add gaussian centers
        self._update_gaussian_centers()

        for gid in self.gaussian_scene.paths.keys():
            self.update_gaussian_path_actor(gid)


        self.reset_camera()
        self.vtk_widget.GetRenderWindow().Render()


    def _add_vector_field_visualization(self, vf):
        # Your existing streamline code here
        vf3d = self.convert_2D_to_3D(vf)
        
        seedPolyData = random_seed_points(20, self.grid_w, self.grid_h, self.gaussian_scene.spacing)

        streamTracer = vtk.vtkStreamTracer()
        streamTracer.SetInputData(vf3d)
        streamTracer.SetSourceData(seedPolyData)
        streamTracer.SetIntegratorTypeToRungeKutta45()
        streamTracer.SetMaximumPropagation(20)
        streamTracer.SetInitialIntegrationStep(0.1)
        streamTracer.SetIntegrationDirectionToBoth()
        streamTracer.Update()

        streamlineMapper = vtk.vtkPolyDataMapper()
        streamlineMapper.SetInputConnection(streamTracer.GetOutputPort())

        streamlineActor = vtk.vtkActor()
        streamlineActor.SetMapper(streamlineMapper)
        streamlineActor.GetProperty().SetColor(0, 1, 0)
        streamlineActor.GetProperty().SetLineWidth(2)

        self.renderer.AddActor(streamlineActor)





    def pause_scalar_generation(self):
        """
        Pause the automatic scalar field updates.
        """
        if self.timer.isActive():
            self.timer.stop()
            QtWidgets.QMessageBox.information(self, "Paused", "Scalar field generation paused.")
        else:
            QtWidgets.QMessageBox.information(self, "Info", "Generation is already paused.")


    def resume_scalar_generation(self):
        """
        Resume scalar field updates if paused.
        """
        if not self.timer.isActive():
            self.timer.start(1000)  # Resume with the same interval
            QtWidgets.QMessageBox.information(self, "Resumed", "Scalar field generation resumed.")
        else:
            QtWidgets.QMessageBox.information(self, "Info", "Generation is already running.")



    def open_export_settings(self):
        """
        Open a dialog to configure automatic export settings (format and directory).
        """
        dlg = QtWidgets.QDialog(self)
        dlg.setWindowTitle('Export Settings')
        form = QtWidgets.QFormLayout()

        # Export toggle
        export_toggle = QtWidgets.QCheckBox('Enable automatic export at each time step')
        export_toggle.setChecked(self.export_enabled)
        export_toggle.stateChanged.connect(lambda state: setattr(self, 'export_enabled', state == QtCore.Qt.Checked))

        # Export format
        format_combo = QtWidgets.QComboBox()
        format_combo.addItems(['VTI (XML ImageData)', 'VTK (Legacy)'])
        format_combo.setCurrentText('VTI (XML ImageData)' if self.export_format == 'vti' else 'VTK (Legacy)')
        format_combo.currentTextChanged.connect(
            lambda text: setattr(self, 'export_format', 'vti' if text == 'VTI (XML ImageData)' else 'vtk')
        )

        # Export directory
        dir_edit = QtWidgets.QLineEdit(self.export_dir)
        dir_btn = QtWidgets.QPushButton('Browse...')
        dir_btn.clicked.connect(lambda: self._select_export_directory(dir_edit))

        # Layout
        dir_layout = QtWidgets.QHBoxLayout()
        dir_layout.addWidget(dir_edit)
        dir_layout.addWidget(dir_btn)
        form.addRow('Automatic Export:', export_toggle)
        form.addRow('Export Format:', format_combo)
        form.addRow('Export Directory:', dir_layout)
        downsample_spin = QtWidgets.QSpinBox()
        downsample_spin.setRange(1, 100)
        downsample_spin.setValue(self.export_downsample)
        downsample_spin.setToolTip('Export every Nth time step (1 = every step)')
        downsample_spin.valueChanged.connect(lambda val: setattr(self, 'export_downsample', val))
        form.addRow('Downsample factor:', downsample_spin)
        form.addRow(QtWidgets.QPushButton('OK', clicked=dlg.accept))
        dlg.setLayout(form)
        dlg.exec_()

    def _select_export_directory(self, line_edit):
        """
        Open a directory selection dialog and update the export directory.

        Args:
            line_edit (QLineEdit): Line edit widget to display the selected directory.
        """
        directory = QtWidgets.QFileDialog.getExistingDirectory(self, 'Select Export Directory')
        if directory:
            self.export_dir = directory
            line_edit.setText(directory)

    def _export_scalar_field(self):
        """
        Export the current scalar field to a file with an incrementing index.
        Uses the configured format (VTI or VTK) and directory.
        """
        if not self.gaussian_scene.gaussians:
            return
        img = self.gaussian_scene.generate_image_data()
        

        if not self.export_dir:
            QtWidgets.QMessageBox.warning(self, 'Export', 'No export directory specified')
            return
        filename = f"scalar_field_{self.export_counter:04d}.{self.export_format}"
        path = os.path.join(self.export_dir, filename)
        
        if(self.export_counter % self.export_downsample != 0):
            self.export_counter += 1
            return

        self.export_counter += 1

        if self.export_format == 'vti':
            writer = vtkXMLImageDataWriter()
        else:
            writer = vtkStructuredPointsWriter()
        writer.SetFileName(path)
        writer.SetInputData(img)
        writer.Write()

    def on_new(self):
        """
        Clear the Gaussian scene, reset export counter, and update the visualization.
        """
        self.gaussian_scene.clear()
        self.export_counter = 0
        self.gaussian_dock.gauss_list.clear()
        self._update_gaussian_visualization()

    def on_open(self):
        """
        Placeholder for opening a file (not implemented).
        """
        QtWidgets.QMessageBox.information(self, 'Open', 'Open not implemented in this demo')

    def on_close(self):
        """
        Close the Gaussian dock widget, clear the scene, reset export counter, and update visualization.
        """
        if self.gaussian_dock:
            self.gaussian_dock.close()
            self.gaussian_dock = None
        self.gaussian_scene.clear()
        self.export_counter = 0
        self._update_gaussian_visualization()

    def zoom(self, factor):
        """
        Zoom the camera by the specified factor.

        Args:
            factor (float): Zoom factor (e.g., 0.8 for zoom in, 1.25 for zoom out).
        """
        camera = self.renderer.GetActiveCamera()
        camera.Zoom(factor)
        self.vtk_widget.GetRenderWindow().Render()

    def reset_camera(self):
        """
        Reset the camera to its default position.
        """
        self.renderer.ResetCamera()
        self.vtk_widget.GetRenderWindow().Render()

    def open_gaussian_dock(self):
        if not hasattr(self, "gaussian_dock") or self.gaussian_dock is None:
            print("[DEBUG] Creating new GaussianControlsDock...")
            self.gaussian_dock = GaussianDock(self)
            self.addDockWidget(QtCore.Qt.LeftDockWidgetArea, self.gaussian_dock)

            # connect the signals to your GUI handlers
            self.gaussian_dock.add_btn.clicked.connect(self.add_gaussians_from_dock)
            self.gaussian_dock.clear_btn.clicked.connect(self.on_new)
            self.gaussian_dock.plot_btn.clicked.connect(self.plot_the_timeline_with_events)
            self.gaussian_dock.apply_noise_btn.clicked.connect(self.on_apply_noise)

            self.gaussian_dock.gauss_list.itemSelectionChanged.connect(self.on_gaussian_selected)
            self.gaussian_dock.btn_update_center.clicked.connect(self.apply_direct_update)
            self.gaussian_dock.btn_pick_center.clicked.connect(self.enable_pick_mode)

            self.gaussian_dock.path_btn.clicked.connect(self.enable_path_pick_mode)


            print("[DEBUG] GaussianControlsDock created and added.")

        else:
            self.gaussian_dock.show()
            self.gaussian_dock.raise_()

    def enable_path_pick_mode(self):
        if self.selected_gaussian_id is None:
            QtWidgets.QMessageBox.warning(self, "Path", "Please select a Gaussian first.")
            return

        print("Path picking mode enabled for Gaussian:", self.selected_gaussian_id)
        self.pick_path_mode = True

        gid = self.selected_gaussian_id
        g = next((gg for gg in self.gaussian_scene.gaussians if gg['id'] == gid), None)
        if g is None:
            print("Error: selected gaussian not found!")
            return

        x0, y0 = g['x'], g['y']
        print(f"Initial path point (Gaussian center): {x0}, {y0}")
        self.collected_path_points = [(x0,y0)]

        # Use a temporary picking style
        track = vtk.vtkInteractorStyleTrackballCamera()
        track.AddObserver("LeftButtonPressEvent", self.on_path_click)

        track.AddObserver("RightButtonPressEvent",
                           lambda obj, evt: self.finish_path_pick_mode())
        self.iren.SetInteractorStyle(track)
        self.pick_style = track

    def on_path_click(self, obj, event):
        if not self.pick_path_mode:
            return

        click_pos = self.iren.GetEventPosition()
        self.renderer.SetDisplayPoint(click_pos[0], click_pos[1], 0)
        self.renderer.DisplayToWorld()
        world = self.renderer.GetWorldPoint()
        x, y = world[0], world[1]

        print("Path point added:", x, y)
        self.collected_path_points.append((x, y))

        # Draw small marker on the screen
        #self.draw_path_point_marker(x, y)
        temp_gid = self.selected_gaussian_id
        self.gaussian_scene.paths[temp_gid] = self.collected_path_points.copy()
        self.update_gaussian_path_actor(temp_gid)

        # Press ESC or RightClick to finish
    def update_gaussian_path_actor(self, gid):
        """
        Draw or update the polyline representing the Gaussian's path.
        """
        if gid not in self.gaussian_scene.paths:
            return

        points = self.gaussian_scene.paths[gid]
        if len(points) < 2:
            return  # Not enough points to draw a line

        # ------------------------------
        # Build VTK PolyLine
        # ------------------------------
        vtk_pts = vtk.vtkPoints()
        for (x, y) in points:
            vtk_pts.InsertNextPoint(x, y, 0)

        polyline = vtk.vtkPolyLine()
        polyline.GetPointIds().SetNumberOfIds(len(points))
        for i in range(len(points)):
            polyline.GetPointIds().SetId(i, i)

        cells = vtk.vtkCellArray()
        cells.InsertNextCell(polyline)

        polydata = vtk.vtkPolyData()
        polydata.SetPoints(vtk_pts)
        polydata.SetLines(cells)

        mapper = vtk.vtkPolyDataMapper()
        mapper.SetInputData(polydata)

        actor = vtk.vtkActor()
        actor.SetMapper(mapper)
        actor.GetProperty().SetColor(1, 0, 0)  # red
        actor.GetProperty().SetLineWidth(3)

        # ------------------------------
        # Remove old actor if exists
        # ------------------------------
        if gid in self.gaussian_path_actors:
            self.renderer.RemoveActor(self.gaussian_path_actors[gid])

        # Save and add new actor
        self.gaussian_path_actors[gid] = actor
        self.renderer.AddActor(actor)

        self.vtk_widget.GetRenderWindow().Render()


    def draw_path_point_marker(self, x, y):
        sphere = vtk.vtkSphereSource()
        sphere.SetRadius(0.3)
        sphere.SetCenter(x, y, 0)

        mapper = vtk.vtkPolyDataMapper()
        mapper.SetInputConnection(sphere.GetOutputPort())

        actor = vtk.vtkActor()
        actor.SetMapper(mapper)
        actor.GetProperty().SetColor(1, 1, 0)
        self.renderer.AddActor(actor)
        self.vtk_widget.GetRenderWindow().Render()


    def finish_path_pick_mode_(self):
        if not self.pick_path_mode:
            return

        gid = self.selected_gaussian_id
        self.gaussian_scene.paths[gid] = list(self.collected_path_points)
        self.gaussian_scene.path_index[gid] = 0

        print("Path saved for Gaussian", gid, ":", self.gaussian_scene.paths[gid])

        self.pick_path_mode = False

        # Restore interactor safely
        QtCore.QTimer.singleShot(0, lambda: self.iren.SetInteractorStyle(self.style))


    def finish_path_pick_mode(self):
        if not self.pick_path_mode:
            return

        gid = self.selected_gaussian_id
        self.gaussian_scene.paths[gid] = list(self.collected_path_points)
        self.gaussian_scene.path_index[gid] = 0

        print("Final path for Gaussian", gid, ":", self.gaussian_scene.paths[gid])

        self.update_gaussian_path_actor(gid)

        self.pick_path_mode = False

        QtCore.QTimer.singleShot(0, lambda: self.iren.SetInteractorStyle(self.style))



    def on_gaussian_selected(self):
        item = self.gaussian_dock.gauss_list.currentItem()
        if not item:
            self.selected_gaussian_id = None
            return


        text = item.text() # e.g. "ID=4, amp=1.0, var=2.0, x=25, y=30"
        try:
            gid = int(text.split(',')[0].split('=')[1])
            self.selected_gaussian_id = gid
        except:
            self.selected_gaussian_id = None


    def apply_direct_update(self):
        if self.selected_gaussian_id is None:
            return
        x = self.gaussian_dock.update_x.value()
        y = self.gaussian_dock.update_y.value()


        for g in self.gaussian_scene.gaussians:
            if g['id'] == self.selected_gaussian_id:
                g['x'] = x
                g['y'] = y
                break


        self._update_gaussian_visualization()

    def enable_pick_mode(self):
        if self.selected_gaussian_id is None:
            return

        self.pick_mode = True
        trackstyle = vtkInteractorStyleTrackballCamera()
        trackstyle.AddObserver('LeftButtonPressEvent', self.on_vtk_click)
        self.iren.SetInteractorStyle(trackstyle)

    def on_vtk_click(self, obj, event):
        if not self.pick_mode:
            return

        # click position in screen coords
        click_pos = self.iren.GetEventPosition()

        renderer = self.renderer

        # STEP 1: Get camera Z depth at clicked location
        renderer.SetDisplayPoint(click_pos[0], click_pos[1], 0)
        renderer.DisplayToWorld()
        world = renderer.GetWorldPoint()

        x = world[0]
        y = world[1]

        print("Picked world XY:", x, y)

        # Update Gaussian
        for g in self.gaussian_scene.gaussians:
            if g['id'] == self.selected_gaussian_id:
                g['x'] = x
                g['y'] = y
                print("Gaussian moved to:", x, y)
                break

        self.pick_mode = False
        self._update_gaussian_visualization()
        #self.iren.SetInteractorStyle(self.style)
        QtCore.QTimer.singleShot(0, lambda: self.iren.SetInteractorStyle(self.style))





    def on_vtk_click__(self, obj, event):
        if not self.pick_mode:
            return

        
        click_pos = self.iren.GetEventPosition()


        picker = vtk.vtkPropPicker()
        picker.Pick(click_pos[0], click_pos[1], 0, self.renderer)
        world = picker.GetPickPosition()


        x, y = world[0], world[1]

        print("Picked position:", x, y)
        
        for g in self.gaussian_scene.gaussians:
            if g['id'] == self.selected_gaussian_id:
                g['x'] = x
                g['y'] = y
                print("gaussian position is updated")
                break
                        

        self.pick_mode = False
        #self._update_gaussian_visualization()
        #self.iren.SetInteractorStyle(self.style)



    def on_apply_noise(self):
        self.noise_type = self.gaussian_dock.noise_type_combo.currentText()
        self.noise_amount = self.gaussian_dock.noise_amount_spin.value()




    def plot_the_timeline_with_events(self):
        plot_tracking_timeline(self.events)


    def add_gaussians_from_dock(self):
        """
        Add Gaussians to the scene based on dock widget inputs and update the visualization.
        """
        if not self.gaussian_dock:
            QtWidgets.QMessageBox.warning(self, "Gaussian Dock", "Please open the Gaussian Controls dock first.")
            return

        n = self.gaussian_dock.spin_count.value()
        amp = self.gaussian_dock.spin_amp.value()
        var = self.gaussian_dock.spin_var.value()

        # NEW: read x,y from dock
        user_x = self.gaussian_dock.spin_x.value()
        user_y = self.gaussian_dock.spin_y.value()

        self.gaussian_scene.distribution_type = self.gaussian_dock.dist_type_combo.currentText()


        for _ in range(n):

            if user_x != 0 or user_y != 0:
                self.gaussian_scene.add_gaussian(
                    amplitude=amp,
                    variance=var,
                    x=user_x,
                    y=user_y
                )
            else:
                # fallback: original random location
                self.gaussian_scene.add_gaussian(
                    amplitude=amp,
                    variance=var
                )

            #self.gaussian_scene.add_gaussian(x= user_x,y=user_y,amplitude=amp, variance=var)
            g = self.gaussian_scene.gaussians[-1]
            gid = g.get('id', '?')
            self.gaussian_dock.gauss_list.addItem(f"ID={gid}, amp={amp:.2f}, var={var:.2f}")

        self._update_gaussian_visualization()


    def create_other_variants(self):
        """
        Placeholder for creating other variants (not implemented).
        """
        QtWidgets.QMessageBox.information(self, 'Other Variants', 'Other variants not implemented in this demo')

    def open_vector_field_dialog(self):
        """
        Open a dialog to configure and generate a vector field.
        """
        dlg = QtWidgets.QDialog(self)
        dlg.setWindowTitle('Generate Vector Field')
        form = QtWidgets.QFormLayout()
        width_spin = QtWidgets.QSpinBox()
        width_spin.setRange(4, 200)
        width_spin.setValue(self.grid_w)
        height_spin = QtWidgets.QSpinBox()
        height_spin.setRange(4, 200)
        height_spin.setValue(self.grid_h)
        spacing_spin = QtWidgets.QDoubleSpinBox()
        spacing_spin.setRange(0.1, 10.0)
        spacing_spin.setValue(1.0)


        type_combo = QtWidgets.QComboBox()
        type_combo.addItems(["Circular", "Sink", "Saddle", "Source","Custom"])
        type_combo.setCurrentText("Circular")



        gen_btn = QtWidgets.QPushButton('Generate')
        gen_btn.clicked.connect(lambda: (self.generate_vector_field(width_spin.value(),
                                 height_spin.value(), spacing_spin.value(),type_combo.currentText()),
                                 dlg.accept()))
        form.addRow('Width:', width_spin)
        form.addRow('Height:', height_spin)
        form.addRow('Spacing:', spacing_spin)
        form.addRow('Field Type:', type_combo)
        form.addRow(gen_btn)
        dlg.setLayout(form)
        dlg.exec_()

    def draw_outline(self, width, height, spacing):
        # Create a rectangle outline using vtkPolyLine
        pts = vtk.vtkPoints()
        pts.InsertNextPoint(0, 0, 0)
        pts.InsertNextPoint(width * spacing, 0, 0)
        pts.InsertNextPoint(width * spacing, height * spacing, 0)
        pts.InsertNextPoint(0, height * spacing, 0)
        pts.InsertNextPoint(0, 0, 0)  # close loop

        polyline = vtk.vtkPolyLine()
        polyline.GetPointIds().SetNumberOfIds(5)
        for i in range(5):
            polyline.GetPointIds().SetId(i, i)

        cells = vtk.vtkCellArray()
        cells.InsertNextCell(polyline)

        polydata = vtk.vtkPolyData()
        polydata.SetPoints(pts)
        polydata.SetLines(cells)

        mapper = vtk.vtkPolyDataMapper()
        mapper.SetInputData(polydata)

        actor = vtk.vtkActor()
        actor.SetMapper(mapper)
        actor.GetProperty().SetColor(1, 1, 1)   # white
        actor.GetProperty().SetLineWidth(2)

        # remove old outline
        if hasattr(self, "grid_outline_actor") and self.grid_outline_actor:
            self.renderer.RemoveActor(self.grid_outline_actor)

        self.grid_outline_actor = actor
        self.renderer.AddActor(actor)
        self.vtk_widget.GetRenderWindow().Render()


    # ------------------------------------------------------------
    # Convert 2D → thin 3D (needed for StreamTracer)
    # ------------------------------------------------------------
    def convert_2D_to_3D(self,vf):
        W, H, _ = vf.GetDimensions()
        sx, sy, _ = vf.GetSpacing()
        ox, oy, oz = vf.GetOrigin()

        vf3d = vtk.vtkImageData()
        vf3d.SetDimensions(W, H, 2)             # 2 slices
        vf3d.SetSpacing(sx, sy, 0.01)           # tiny thickness
        vf3d.SetOrigin(ox, oy, oz)

        v2d = vf.GetPointData().GetVectors()
        name = v2d.GetName()

        arr = vtk.vtkFloatArray()
        arr.SetName(name)
        arr.SetNumberOfComponents(3)
        arr.SetNumberOfTuples(W * H * 2)

        idx = 0
        for z in range(2):
            for n in range(W * H):
                vx, vy, vz = v2d.GetTuple3(n)
                arr.SetTuple3(idx, vx, vy, 0)
                idx += 1

        vf3d.GetPointData().SetVectors(arr)
        vf3d.GetPointData().SetActiveVectors(name)
        return vf3d





    def generate_vector_field(self, width, height, spacing,field_type="Sink"):
        """
        Generate and visualize a vector field using arrow glyphs.

        Args:
            width (int): Grid width.
            height (int): Grid height.
            spacing (float): Grid spacing.
        """

        self.selected_vector_field_type = field_type

        self.gaussian_scene.updateWidthHeight(width,height,space=spacing)

        # Always draw outline
        self.draw_outline(width, height, spacing)

        # If custom, ONLY draw outline
        if field_type == "Custom":
            print("Custom field: Only drawing outline.")
            self.vector_field_data = None

            # Remove old glyphs/streamlines if any
            if hasattr(self, "glyph_actor") and self.glyph_actor:
                self.renderer.RemoveActor(self.glyph_actor)

            if hasattr(self, "streamline_actor") and self.streamline_actor:
                self.renderer.RemoveActor(self.streamline_actor)

            self.reset_camera()
            self.vtk_widget.GetRenderWindow().Render()
            return

        vf = VectorFieldGenerator.create_vector_field(width=width, height=height, spacing=spacing,field_type=field_type)
        self.vector_field_data = vf

        vf3d = self.convert_2D_to_3D(vf)


        streamTracer = vtk.vtkStreamTracer()
        seedPolyData = random_seed_points(100, width, height, spacing)
        streamTracer.SetSourceData(seedPolyData)
    
        streamTracer.SetInputData(vf3d)
        streamTracer.SetSourceData(seedPolyData)
        streamTracer.SetIntegratorTypeToRungeKutta45()
        streamTracer.SetMaximumPropagation(20)
        streamTracer.SetInitialIntegrationStep(0.1)
        streamTracer.SetIntegrationDirectionToBoth()
        streamTracer.Update()

        streamlineMapper = vtk.vtkPolyDataMapper()
        streamlineMapper.SetInputConnection(streamTracer.GetOutputPort())

        streamlineActor = vtk.vtkActor()
        streamlineActor.SetMapper(streamlineMapper)
        streamlineActor.GetProperty().SetColor(0.5, 0.5, 0.5)
        streamlineActor.GetProperty().SetLineWidth(2)




        geometry_filter = vtk.vtkImageDataGeometryFilter()
        geometry_filter.SetInputData(vf)
        geometry_filter.Update()

        polydata = geometry_filter.GetOutput()


        arrow = vtkArrowSource()
        glyph = vtkGlyph3D()
        glyph.SetSourceConnection(arrow.GetOutputPort())
        glyph.SetInputData(polydata)

        glyph.SetVectorModeToUseVector()
        glyph.SetScaleModeToScaleByVector()
        glyph.SetScaleFactor(0.8)
        glyph.Update()

        mapper = vtkPolyDataMapper()
        mapper.SetInputConnection(glyph.GetOutputPort())
        glyph_actor = vtkActor()
        glyph_actor.SetMapper(mapper)

        glyph_actor.GetProperty().SetColor(0.6, 0.6, 0.9)  # light bluish tone
        glyph_actor.GetProperty().SetOpacity(0.8)

        if self.image_actor:
            self.renderer.AddActor(self.image_actor)

        self.glyph_actor = glyph_actor
        self.streamline_actor = streamlineActor
        
        self.renderer.AddActor(glyph_actor)
        self.renderer.AddActor(streamlineActor)
        self.reset_camera()
        self.vtk_widget.GetRenderWindow().Render()

    def _update_timer(self):
        """
        Update the visualization using the current Gaussian scene data.
        """
        img = self.gaussian_scene.generate_image_data()

        img_noise = apply_noise_to_scalar_field(img,self.noise_type,self.noise_amount)




        self.contour.SetInputData(img_noise)
        self.contour.GenerateValues(30, img_noise.GetScalarRange())
        self.contour.Update()
        #self._update_gaussian_visualization()
        self._update_gaussian_centers()
        self.vtk_widget.GetRenderWindow().Render()

        try:
            events_detected  = update_umbrella_tracking(self.gaussian_scene,"umbrella_output",self.tracking_timestep)
            self.events.extend(events_detected)
            self.tracking_timestep += 1
        except Exception as e:
            print(f"[UmbrellaTracking] Error: {e}")


    def export_vti(self):
            """
            Export the current Gaussian scene as a VTI (XML ImageData) file.
            """
            if not self.gaussian_scene.gaussians:
                QtWidgets.QMessageBox.warning(self, 'Export', 'No gaussian data to export')
                return
            img = self.gaussian_scene.generate_image_data()
            img = apply_noise_to_scalar_field(img,self.noise_type,self.noise_amount)
            path, _ = QtWidgets.QFileDialog.getSaveFileName(self, 'Save VTI', filter='*.vti')
            if not path:
                return
            if not path.lower().endswith('.vti'):
                path += '.vti'
            writer = vtkXMLImageDataWriter()
            writer.SetFileName(path)
            writer.SetInputData(img)
            writer.Write()
            QtWidgets.QMessageBox.information(self, 'Export', f'Exported to {path}')

    def export_vtk_legacy(self):
        """
        Export the current Gaussian scene as a legacy VTK file.
        """
        if not self.gaussian_scene.gaussians:
            QtWidgets.QMessageBox.warning(self, 'Export', 'No gaussian data to export')
            return
        img = self.gaussian_scene.generate_image_data()
        path, _ = QtWidgets.QFileDialog.getSaveFileName(self, 'Save VTK', filter='*.vtk')
        if not path:
            return
        if not path.lower().endswith('.vtk'):
            path += '.vtk'
        writer = vtkStructuredPointsWriter()
        writer.SetFileName(path)
        writer.SetInputData(img)
        writer.Write()
        QtWidgets.QMessageBox.information(self, 'Export', f'Exported to {path}')

    def show_shortcuts(self):
        """
        Display a dialog with keyboard shortcuts.
        """
        shortcuts = (
            'Shortcuts:\n'
            'Ctrl+N: New (clear)\n'
            'Ctrl+O: Open (not implemented)\n'
            'Ctrl+Q: Quit\n'
            'Ctrl++: Zoom In\n'
            'Ctrl+-: Zoom Out\n'
            'Ctrl+R: Reset Camera\n'
            '\nUse Create->Gaussian to open the Gaussian controls panel.\n'
            'Click Add Gaussian to add components to the scene.\n'
            'Use Export->Export Settings to configure automatic exports.'
        )
        QtWidgets.QMessageBox.information(self, 'Shortcuts', shortcuts)

    def show_about(self):
        """
        Display an about dialog.
        """
        QtWidgets.QMessageBox.information(self, 'About', 'Scalar Field Generator \nAuthor: Boppena Nagaraju \n Akshay B M')


    def _update_gaussian_centers(self):
        """
        Create or update colored points representing Gaussian centers.
        Each Gaussian center gets a unique color and a text label with its ID.
        """
        # --- Remove old actors if present ---
        if hasattr(self, "gaussian_text_actors"):
            for actor in self.gaussian_text_actors:
                self.renderer.RemoveActor(actor)
        self.gaussian_text_actors = []

        if not self.gaussian_scene.gaussians:
            if self.gaussian_centers_actor:
                self.renderer.RemoveActor(self.gaussian_centers_actor)
                self.gaussian_centers_actor = None
            return

        num_gauss = len(self.gaussian_scene.gaussians)

        # Create VTK points
        points = vtk.vtkPoints()
        for g in self.gaussian_scene.gaussians:
            points.InsertNextPoint(g['x'], g['y'], 0.0)

        # Create color array
        colors = vtk.vtkUnsignedCharArray()
        colors.SetNumberOfComponents(3)
        colors.SetName("Colors")

        import random
        random.seed(0)
        for i in range(num_gauss):
            r = random.randint(50, 255)
            g = random.randint(50, 255)
            b = random.randint(50, 255)
            colors.InsertNextTuple3(r, g, b)

        # Create polydata
        polydata = vtk.vtkPolyData()
        polydata.SetPoints(points)
        polydata.GetPointData().SetScalars(colors)

        # Glyph to render points
        glyph_filter = vtk.vtkVertexGlyphFilter()
        glyph_filter.SetInputData(polydata)
        glyph_filter.Update()

        mapper = vtk.vtkPolyDataMapper()
        mapper.SetInputConnection(glyph_filter.GetOutputPort())

        actor = vtk.vtkActor()
        actor.SetMapper(mapper)
        actor.GetProperty().SetPointSize(10)
        actor.GetProperty().SetRenderPointsAsSpheres(True)

        # Replace previous actor
        if self.gaussian_centers_actor:
            self.renderer.RemoveActor(self.gaussian_centers_actor)
        self.gaussian_centers_actor = actor
        self.renderer.AddActor(actor)

        # --- Add text labels (IDs) for each Gaussian ---
        for g in self.gaussian_scene.gaussians:
            text = f"ID {g['id']}"
            txt_actor = vtk.vtkBillboardTextActor3D()
            txt_actor.SetInput(text)
            txt_actor.SetPosition(g['x'], g['y'] + 1.0, 0.0)  # slight offset above
            txt_actor.GetTextProperty().SetFontSize(12)
            txt_actor.GetTextProperty().SetColor(1, 0, 0)
            txt_actor.GetTextProperty().BoldOn()
            self.renderer.AddActor(txt_actor)
            self.gaussian_text_actors.append(txt_actor)



    def _update_gaussian_visualization(self):
        """
        Update the visualization with the current Gaussian scene data.
        """
        img = self.gaussian_scene.generate_image_data()
        self.contour.SetInputData(img)
        self.contour.GenerateValues(30, img.GetScalarRange())
        self.contour.Update()
        self._update_gaussian_centers()

        self.reset_camera()
        self.vtk_widget.GetRenderWindow().Render()

    def _apply_global_styles(self):
        """
        Apply a rich dark style to the main window, menu bar, and toolbars.
        Matches the Gaussian Dock styling for visual consistency.
        """

        self.setStyleSheet("""
            QMainWindow {
                background-color: #1e1e2e;
                color: #dcdcdc;
                font-family: 'Segoe UI';
                font-size: 11pt;
            }

            /* ---- MENU BAR ---- */
            QMenuBar {
                background-color: #2b2b3d;
                color: #e0e0e0;
                border-bottom: 1px solid #3c3f41;
            }
            QMenuBar::item {
                background-color: transparent;
                padding: 6px 12px;
            }
            QMenuBar::item:selected {
                background-color: #4f8cc9;
                color: white;
                border-radius: 4px;
            }

            /* ---- MENUS ---- */
            QMenu {
                background-color: #2b2b3d;
                border: 1px solid #3c3f41;
                color: #e0e0e0;
            }
            QMenu::item {
                padding: 6px 20px;
                border-radius: 4px;
            }
            QMenu::item:selected {
                background-color: #4f8cc9;
                color: white;
            }
            QMenu::separator {
                height: 1px;
                background: #4a4a4a;
                margin: 6px 0px;
            }

            /* ---- TOOLBAR ---- */
            QToolBar {
                background-color: #252537;
                border: none;
                padding: 4px;
                spacing: 6px;
            }
            QToolButton {
                background-color: #3c3f41;
                color: white;
                border-radius: 6px;
                padding: 6px 10px;
            }
            QToolButton:hover {
                background-color: #4f8cc9;
            }
            QToolButton:pressed {
                background-color: #2d6da3;
            }

            /* ---- STATUS BAR ---- */
            QStatusBar {
                background-color: #2b2b3d;
                color: #dcdcdc;
                border-top: 1px solid #3c3f41;
            }
        """)

