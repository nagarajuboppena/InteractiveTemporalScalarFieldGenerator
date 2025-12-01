"""
gaussian_dock.py
----------------
Rich, themed Gaussian Controls Dock with Dark/Light mode toggle.

Integrates with a main GUI (e.g., PyQt5 QMainWindow with VTK visualization).
"""

from PyQt5 import QtCore, QtGui, QtWidgets


class GaussianDock(QtWidgets.QDockWidget):
    """
    A rich, styled dock widget for Gaussian controls and noise addition,
    supporting Dark/Light theme toggle.
    """

    def __init__(self, parent=None):
        super().__init__("🎛 Gaussian Controls", parent)
        self.setAllowedAreas(QtCore.Qt.LeftDockWidgetArea | QtCore.Qt.RightDockWidgetArea)

        # ----- UI Initialization -----
        self.theme_mode = "dark"
        self._init_ui()
        self.apply_dark_theme(self.widget)

    # -------------------------------------------------------------------------
    # 🧱 UI Construction
    # -------------------------------------------------------------------------
    def _init_ui(self):
        """Builds all controls and layout."""
        self.widget = QtWidgets.QWidget()
        layout = QtWidgets.QFormLayout()
        layout.setLabelAlignment(QtCore.Qt.AlignLeft)
        layout.setFormAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignTop)
        layout.setVerticalSpacing(10)

        # ===== Theme Toggle =====
        self.theme_btn = QtWidgets.QPushButton("🌙 Dark Mode")
        self.theme_btn.setCheckable(True)
        self.theme_btn.clicked.connect(self._on_theme_toggle)
        layout.addRow(self.theme_btn)

        section_font = QtGui.QFont('Segoe UI', 11, QtGui.QFont.Bold)

        # ===== Gaussian Section =====
        lbl_gaussian = QtWidgets.QLabel('Gaussian Settings')
        lbl_gaussian.setFont(section_font)
        layout.addRow(lbl_gaussian)

        self.spin_count = QtWidgets.QSpinBox()
        self.spin_count.setRange(1, 50)
        self.spin_count.setValue(1)

        self.spin_amp = QtWidgets.QDoubleSpinBox()
        self.spin_amp.setRange(0.01, 1000.0)
        self.spin_amp.setSingleStep(0.1)
        self.spin_amp.setValue(1.0)

        self.spin_var = QtWidgets.QDoubleSpinBox()
        self.spin_var.setRange(0.1, 10000.0)
        self.spin_var.setSingleStep(1.0)
        self.spin_var.setValue(2.0)

        # Gaussian position controls
        self.spin_x = QtWidgets.QDoubleSpinBox()
        self.spin_x.setRange(0.0, 10000.0)
        self.spin_x.setSingleStep(0.1)
        self.spin_x.setValue(0.0)

        self.spin_y = QtWidgets.QDoubleSpinBox()
        self.spin_y.setRange(0.0, 10000.0)
        self.spin_y.setSingleStep(0.1)
        self.spin_y.setValue(0.0)

        self.dist_type_combo = QtWidgets.QComboBox()
        self.dist_type_combo.addItems([
            "Gaussian",
            "Cauchy",
            "Mexican Hat",
            "Exponential",
            "Plateau",
            "Anisotropic Gaussian",
            "Multi-Lobe",
            "Ridge",
            "Perlin Noise",
        ])
        layout.addRow("Distribution Type:", self.dist_type_combo)


        layout.addRow('Number of Gaussians:', self.spin_count)
        layout.addRow('Amplitude:', self.spin_amp)
        layout.addRow('Variance:', self.spin_var)

        layout.addRow("Center X:", self.spin_x)
        layout.addRow("Center Y:", self.spin_y)


        # Buttons
        self.add_btn = QtWidgets.QPushButton('➕ Add Gaussian')
        self.clear_btn = QtWidgets.QPushButton('🗑 Clear All')
        self.plot_btn = QtWidgets.QPushButton('📈 Plot Timeline')

        layout.addRow(self.add_btn)
        layout.addRow(self.clear_btn)
        layout.addRow(self.plot_btn)

        # ===== Noise Section =====
        lbl_noise = QtWidgets.QLabel('Noise Injection')
        lbl_noise.setFont(section_font)
        layout.addRow(lbl_noise)

        self.noise_type_combo = QtWidgets.QComboBox()
        self.noise_type_combo.addItems([
            'None',
            'Salt',
            'Pepper',
            'Salt and Pepper',
            'Gaussian (White)',
            'Gaussian blobs',
            'Poisson',
            'Speckle',
            'Uniform',
            'Laplace',
            'Perlin'
        ])

        self.noise_amount_spin = QtWidgets.QDoubleSpinBox()
        self.noise_amount_spin.setRange(0.0, 1.0)
        self.noise_amount_spin.setSingleStep(0.01)
        self.noise_amount_spin.setValue(0.05)

        self.apply_noise_btn = QtWidgets.QPushButton('✨ Apply Noise')

        layout.addRow('Noise Type:', self.noise_type_combo)
        layout.addRow('Noise Amount:', self.noise_amount_spin)
        layout.addRow(self.apply_noise_btn)

        # ===== Gaussian List =====
        lbl_list = QtWidgets.QLabel('Active Gaussians')
        lbl_list.setFont(section_font)
        layout.addRow(lbl_list)

        self.gauss_list = QtWidgets.QListWidget()
        layout.addRow(self.gauss_list)


        # ===== Center Update Section =====
        self.update_x = QtWidgets.QDoubleSpinBox()
        self.update_x.setRange(0.0, 10000.0)
        self.update_x.setSingleStep(0.1)
        self.update_x.setValue(0.0)


        self.update_y = QtWidgets.QDoubleSpinBox()
        self.update_y.setRange(0.0, 10000.0)
        self.update_y.setSingleStep(0.1)
        self.update_y.setValue(0.0)


        self.btn_update_center = QtWidgets.QPushButton("🔄 Update Center (Direct)")
        self.btn_pick_center = QtWidgets.QPushButton("📌 Pick From VTK Window")


        layout.addRow("Update X:", self.update_x)
        layout.addRow("Update Y:", self.update_y)
        layout.addRow(self.btn_update_center)
        layout.addRow(self.btn_pick_center)

        self.path_btn = QtWidgets.QPushButton("🧭 Add Path for Selected Gaussian")
        layout.addRow(self.path_btn)


        #==== center update section end =====



        self.widget.setLayout(layout)

        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
        scroll.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
        scroll.setWidget(self.widget)

        self.setWidget(scroll)

        #self.setWidget(self.widget)

    # -------------------------------------------------------------------------
    # 🎨 THEME MANAGEMENT
    # -------------------------------------------------------------------------
    def _on_theme_toggle(self, checked):
        if checked:
            self.theme_mode = "light"
            self.theme_btn.setText("☀️ Light Mode")
            self.apply_light_theme(self.widget)
        else:
            self.theme_mode = "dark"
            self.theme_btn.setText("🌙 Dark Mode")
            self.apply_dark_theme(self.widget)

    def apply_dark_theme(self, widget):
        widget.setStyleSheet("""
            QWidget {
                background-color: #1e1e2e;
                color: #e0e0e0;
                font-family: 'Segoe UI';
                font-size: 11pt;
            }
            QLabel {
                color: #9cdcfe;
                font-weight: bold;
            }
            QSpinBox, QDoubleSpinBox, QComboBox {
                background-color: #2b2b3d;
                color: #e0e0e0;
                border: 1px solid #3c3f41;
                border-radius: 6px;
                padding: 3px 6px;
            }
            QPushButton {
                background-color: #3c3f41;
                color: #ffffff;
                border-radius: 8px;
                padding: 6px 10px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #4f8cc9;
            }
            QListWidget {
                background-color: #2b2b3d;
                border: 1px solid #3c3f41;
                border-radius: 6px;
                color: #ffffff;
            }
            QDockWidget::title {
                background: #252537;
                color: #ffffff;
                font-size: 12pt;
                font-weight: bold;
                padding: 6px;
            }
        """)

    def apply_light_theme(self, widget):
        widget.setStyleSheet("""
            QWidget {
                background-color: #fafafa;
                color: #202020;
                font-family: 'Segoe UI';
                font-size: 11pt;
            }
            QLabel {
                color: #1a4e8a;
                font-weight: bold;
            }
            QSpinBox, QDoubleSpinBox, QComboBox {
                background-color: #ffffff;
                color: #202020;
                border: 1px solid #b0b0b0;
                border-radius: 6px;
                padding: 3px 6px;
            }
            QPushButton {
                background-color: #e1ecf4;
                color: #1a4e8a;
                border-radius: 8px;
                padding: 6px 10px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #bcd2f1;
            }
            QListWidget {
                background-color: #ffffff;
                border: 1px solid #b0b0b0;
                border-radius: 6px;
                color: #202020;
            }
            QDockWidget::title {
                background: #e1ecf4;
                color: #1a4e8a;
                font-size: 12pt;
                font-weight: bold;
                padding: 6px;
            }
        """)
