#!/usr/bin/env python3
# scenario_generator.py
"""
Integrated Scenario Generator for your application.

- No QApplication created here; this is a QWidget-based tool to embed/open from your MainWindow.
- Emits scene_generated(scene, vector_field) when a scenario is created.
- Assumes `gaussian_scene.GaussianScene` and optional `vector_field.VectorFieldGenerator` exist in your project.
- Distribution type is global per scenario (option A from your request).
"""

import math
import random
from functools import partial

from PyQt5 import QtWidgets, QtCore

# Try imports from your project
try:
    from gaussian_scene import GaussianScene
except Exception as e:
    GaussianScene = None
    print("[scenario_generator] Warning: couldn't import gaussian_scene.GaussianScene:", e)

try:
    from vector_field import VectorFieldGenerator
except Exception:
    VectorFieldGenerator = None


class ScenarioGenerator:
    """Static helpers to create the 4 scenario types. Returns (GaussianScene, vector_field_or_None)."""

    @staticmethod
    def _create_scene(width, height, spacing, distribution):
        if GaussianScene is None:
            raise RuntimeError("GaussianScene not found. Place gaussian_scene.py next to this file.")
        s = GaussianScene(width=width, height=height)
        s.updateWidthHeight(width, height, space=spacing)
        s.distribution_type = distribution
        return s

    @staticmethod
    def _make_straight_path(start, end, steps=6):
        sx, sy = start
        ex, ey = end
        pts = []
        for i in range(steps):
            t = i / float(max(1, steps - 1))
            pts.append((sx + (ex - sx) * t, sy + (ey - sy) * t))
        return pts

    @staticmethod
    def scenario_merge_split(num_distributions=3, width=200, height=200, spacing=1.0,
                             merge_point=None, split_radius=40, steps=8, distribution='Gaussian'):
        scene = ScenarioGenerator._create_scene(width, height, spacing, distribution)

        # spawn sources around left/middle area
        for i in range(num_distributions):
            x = random.uniform(0.05, 0.45) * width * spacing
            y = random.uniform(0.1, 0.9) * height * spacing
            amp = random.uniform(0.6, 1.8)
            var = random.uniform(20, 150)
            scene.add_gaussian(x=x, y=y, amplitude=amp, variance=var)

        if merge_point is None:
            merge_point = (width * spacing * 0.5, height * spacing * 0.5)

        # create split destinations placed evenly around a circle
        split_points = []
        for idx in range(num_distributions):
            theta = 2 * math.pi * idx / max(1, num_distributions)
            sx = merge_point[0] + split_radius * math.cos(theta)
            sy = merge_point[1] + split_radius * math.sin(theta)
            split_points.append((sx, sy))

        # assign paths for each gaussian: start -> merge -> split
        for idx, g in enumerate(scene.gaussians):
            start = (g['x'], g['y'])
            first = ScenarioGenerator._make_straight_path(start, merge_point, steps=max(2, steps // 2 + 1))
            second = ScenarioGenerator._make_straight_path(merge_point, split_points[idx], steps=max(2, steps // 2 + 1))
            full = first + second[1:]
            scene.paths[g['id']] = full
            scene.path_index[g['id']] = 0

        vf = None
        # provide a sink vector field to help visually if available
        if VectorFieldGenerator is not None:
            try:
                vf = VectorFieldGenerator.create_vector_field(width=width, height=height, spacing=spacing, field_type='Sink')
            except Exception:
                vf = None

        return scene, vf

    @staticmethod
    def scenario_separate_paths(num_distributions=4, width=200, height=200, spacing=1.0, distribution='Gaussian'):
        scene = ScenarioGenerator._create_scene(width, height, spacing, distribution)

        # choose starts on left half, destinations on right half with spacing
        starts = []
        dests = []
        margin = 0.05
        for i in range(num_distributions):
            sx = random.uniform(margin, 0.45) * width * spacing
            sy = random.uniform(0.05, 0.95) * height * spacing
            starts.append((sx, sy))

        for i in range(num_distributions):
            dx = random.uniform(0.55, 0.95) * width * spacing
            # space destinations vertically
            dy = (0.05 + i * (0.9 / max(1, num_distributions))) * height * spacing
            dests.append((dx, dy))

        for i in range(num_distributions):
            amp = random.uniform(0.6, 1.8)
            var = random.uniform(15, 140)
            scene.add_gaussian(x=starts[i][0], y=starts[i][1], amplitude=amp, variance=var)

        print("Add paths for each gaussian distribution:")
        for idx, g in enumerate(scene.gaussians):
            print(f"  Gaussian ID {g['id']} from {starts[idx]} to {dests[idx]}")
            p = ScenarioGenerator._make_straight_path((g['x'], g['y']), dests[idx], steps=10)
            scene.paths[g['id']] = p
            scene.path_index[g['id']] = 0

        return scene, None

    @staticmethod
    def scenario_sink_and_vanish(num_distributions=6, width=200, height=200, spacing=1.0, sink_point=None, distribution='Gaussian'):
        scene = ScenarioGenerator._create_scene(width, height, spacing, distribution)

        if sink_point is None:
            sink_point = (width * spacing * 0.5, height * spacing * 0.5)

        # spawn at random places
        for i in range(num_distributions):
            x = random.uniform(0.05, 0.95) * width * spacing
            y = random.uniform(0.05, 0.95) * height * spacing
            amp = random.uniform(0.5, 2.0)
            var = random.uniform(10, 160)
            scene.add_gaussian(x=x, y=y, amplitude=amp, variance=var)

        # paths to sink
        for g in scene.gaussians:
            p = ScenarioGenerator._make_straight_path((g['x'], g['y']), sink_point, steps=12)
            scene.paths[g['id']] = p
            scene.path_index[g['id']] = 0

        vf = None
        if VectorFieldGenerator is not None:
            try:
                vf = VectorFieldGenerator.create_vector_field(width=width, height=height, spacing=spacing, field_type='Sink')
            except Exception:
                vf = None

        return scene, vf

    @staticmethod
    def scenario_many_starts_many_ends(num_distributions=8, width=200, height=200, spacing=1.0, distribution='Gaussian'):
        scene = ScenarioGenerator._create_scene(width, height, spacing, distribution)

        # create a few start clusters and end clusters
        K = max(2, num_distributions // 3)
        L = max(2, num_distributions // 3)
        starts = []
        dests = []
        for i in range(K):
            cx = random.uniform(0.05, 0.45) * width * spacing
            cy = random.uniform(0.05, 0.95) * height * spacing
            starts.append((cx, cy))
        for j in range(L):
            cx = random.uniform(0.55, 0.95) * width * spacing
            cy = random.uniform(0.05, 0.95) * height * spacing
            dests.append((cx, cy))

        for i in range(num_distributions):
            s = random.choice(starts)
            x = s[0] + random.uniform(-10, 10)
            y = s[1] + random.uniform(-10, 10)
            amp = random.uniform(0.6, 2.0)
            var = random.uniform(10, 160)
            scene.add_gaussian(x=x, y=y, amplitude=amp, variance=var)

        for g in scene.gaussians:
            d = random.choice(dests)
            p = ScenarioGenerator._make_straight_path((g['x'], g['y']), d, steps=10)
            scene.paths[g['id']] = p
            scene.path_index[g['id']] = 0

        return scene, None


class ScenarioGUI(QtWidgets.QWidget):
    """
    Qt widget for generating scenarios. Emits `scene_generated(scene, vector_field)`.
    Use from your MainWindow as a child window or dock.

    Example in MainWindow:
        from scenario_generator import ScenarioGUI
        self.scenario_gui = ScenarioGUI(parent=self)
        self.scenario_gui.scene_generated.connect(self.on_scenario_generated)
        self.scenario_gui.show()
    """

    scene_generated = QtCore.pyqtSignal(object, object,object)  # (GaussianScene, vtkImageData or None)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Scenario Generator")
        self.resize(560, 420)

        self._build_ui()
        self.current_scene = None

    def _build_ui(self):
        v = QtWidgets.QVBoxLayout(self)

        tabs = QtWidgets.QTabWidget()
        v.addWidget(tabs)

        # Tab: Merge & Split
        t1 = QtWidgets.QWidget()
        tabs.addTab(t1, "Merge & Split")
        f1 = QtWidgets.QFormLayout(t1)
        self.ms_count = QtWidgets.QSpinBox(); self.ms_count.setRange(1, 50); self.ms_count.setValue(3)
        #self.ms_steps = QtWidgets.QSpinBox(); self.ms_steps.setRange(2, 64); self.ms_steps.setValue(8)
        self.ms_splitrad = QtWidgets.QSpinBox(); self.ms_splitrad.setRange(1, 500); self.ms_splitrad.setValue(40)
        f1.addRow("Number of distributions:", self.ms_count)
        #f1.addRow("Merge/Split steps:", self.ms_steps)
        f1.addRow("Split radius:", self.ms_splitrad)
        self.ms_btn = QtWidgets.QPushButton("Generate Merge & Split")
        f1.addRow(self.ms_btn)

        # Tab: Separate Paths
        t2 = QtWidgets.QWidget()
        tabs.addTab(t2, "Separate Paths")
        f2 = QtWidgets.QFormLayout(t2)
        self.sep_count = QtWidgets.QSpinBox(); self.sep_count.setRange(1, 80); self.sep_count.setValue(4)
        f2.addRow("Number of distributions:", self.sep_count)
        self.sep_btn = QtWidgets.QPushButton("Generate Separate Paths")
        f2.addRow(self.sep_btn)

        # Tab: Sink & Vanish
        t3 = QtWidgets.QWidget()
        tabs.addTab(t3, "Sink & Vanish")
        f3 = QtWidgets.QFormLayout(t3)
        self.sv_count = QtWidgets.QSpinBox(); self.sv_count.setRange(1, 200); self.sv_count.setValue(8)
        f3.addRow("Number of distributions:", self.sv_count)
        self.sv_btn = QtWidgets.QPushButton("Generate Sink & Vanish")
        f3.addRow(self.sv_btn)

        # Tab: Many Starts & Ends
        t4 = QtWidgets.QWidget()
        tabs.addTab(t4, "Many Starts/Ends")
        f4 = QtWidgets.QFormLayout(t4)
        self.me_count = QtWidgets.QSpinBox(); self.me_count.setRange(1, 300); self.me_count.setValue(12)
        f4.addRow("Number of distributions:", self.me_count)
        self.me_btn = QtWidgets.QPushButton("Generate Many Starts/Ends")
        f4.addRow(self.me_btn)

        # bottom controls
        h = QtWidgets.QHBoxLayout()
        v.addLayout(h)
        h.addWidget(QtWidgets.QLabel("Distribution type:"))
        self.distribution_combo = QtWidgets.QComboBox()
        self.distribution_combo.addItems([
            "Gaussian", "Cauchy", "Mexican Hat", "Exponential",
            "Plateau", "Anisotropic Gaussian", "Multi-Lobe", "Ridge", "Perlin Noise"
        ])
        h.addWidget(self.distribution_combo)
        h.addStretch(1)
        self.btn_close = QtWidgets.QPushButton("Close")
        h.addWidget(self.btn_close)

        # signals
        self.ms_btn.clicked.connect(self._on_merge_split)
        self.sep_btn.clicked.connect(self._on_separate)
        self.sv_btn.clicked.connect(self._on_sink_vanish)
        self.me_btn.clicked.connect(self._on_many_ends)
        self.btn_close.clicked.connect(self.close)

    def _emit_scene(self, scene, vf, vector_field_type):
        """Store and emit the generated scene."""
        self.current_scene = scene
        # ensure scene carries chosen distribution type
        scene.distribution_type = str(self.distribution_combo.currentText())
        # emit to main application
        self.scene_generated.emit(scene, vf,vector_field_type)

    def _on_merge_split(self):
        n = int(self.ms_count.value())
        #steps = int(self.ms_steps.value())
        rad = int(self.ms_splitrad.value())
        dist = str(self.distribution_combo.currentText())
        scene, vf = ScenarioGenerator.scenario_merge_split(num_distributions=n, width=200, height=200,
                                                          spacing=1.0, merge_point=None,
                                                          split_radius=rad, steps=2,
                                                          distribution=dist)
        QtWidgets.QMessageBox.information(self, "Generated", f"Merge & Split with {n} distributions generated.")
        self._emit_scene(scene, vf,"Custom")

    def _on_separate(self):
        n = int(self.sep_count.value())
        dist = str(self.distribution_combo.currentText())
        scene, vf = ScenarioGenerator.scenario_separate_paths(num_distributions=n, width=200, height=200,
                                                             spacing=1.0, distribution=dist)
        QtWidgets.QMessageBox.information(self, "Generated", f"Separate path scenario with {n} distributions generated.")
        self._emit_scene(scene, vf,"Custom")

    def _on_sink_vanish(self):
        n = int(self.sv_count.value())
        dist = str(self.distribution_combo.currentText())
        scene, vf = ScenarioGenerator.scenario_sink_and_vanish(num_distributions=n, width=200, height=200,
                                                               spacing=1.0, sink_point=None, distribution=dist)
        QtWidgets.QMessageBox.information(self, "Generated", f"Sink & vanish scenario with {n} distributions generated.")
        self._emit_scene(scene, vf,"Custom")

    def _on_many_ends(self):
        n = int(self.me_count.value())
        dist = str(self.distribution_combo.currentText())
        scene, vf = ScenarioGenerator.scenario_many_starts_many_ends(num_distributions=n, width=200, height=200,
                                                                    spacing=1.0, distribution=dist)
        QtWidgets.QMessageBox.information(self, "Generated", f"Many starts/ends scenario with {n} distributions generated.")
        self._emit_scene(scene, vf, "Custom")


# ---------------- Example integration snippet (for your MainWindow) ----------------
#
# In your MainWindow class:
#
# from scenario_generator import ScenarioGUI
#
# def open_scenario_generator(self):
#     if not hasattr(self, 'scenario_gui') or self.scenario_gui is None:
#         self.scenario_gui = ScenarioGUI(parent=self)
#         self.scenario_gui.scene_generated.connect(self.on_scenario_generated)
#     self.scenario_gui.show()
#     self.scenario_gui.raise_()
#
# def on_scenario_generated(self, scene, vector_field):
#     # replace your current gaussian_scene with the new scene
#     self.gaussian_scene = scene
#     # update internal grid sizes if needed
#     self.grid_w = scene.width
#     self.grid_h = scene.height
#     self.gaussian_scene.spacing = scene.spacing
#     # set vector field if any
#     self.vector_field_data = vector_field
#
#     # remove existing visual actors safely (you may want to only remove actors you added previously)
#     # e.g., self.renderer.RemoveActor(self.glyph_actor) etc.
#
#     # update contour and gaussian centers
#     img = self.gaussian_scene.generate_image_data()
#     self.contour.SetInputData(img)
#     self.contour.GenerateValues(30, img.GetScalarRange())
#     self.contour.Update()
#
#     # add vector field visualization if vector_field is not None
#     if vector_field is not None:
#         self.generate_vector_field(self.grid_w, self.grid_h, self.gaussian_scene.spacing, field_type='Sink')
#
#     self._update_gaussian_centers()
#     self.reset_camera()
#     self.vtk_widget.GetRenderWindow().Render()
#
# ----------------------------------------------------------------------------------

# end of file
