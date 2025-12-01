#!/usr/bin/env python3
"""
main.py

Entry point for the Temporal Scalar Field Generator application.
Initializes the PyQt5 application and creates the main window.

Dependencies:
- PyQt5
- VTK
- gui.py (MainWindow class)
"""

import sys
from PyQt5 import QtWidgets
from gui import MainWindow

def main(argv):
    """
    Initialize and run the PyQt5 application.

    Args:
        argv (list): Command-line arguments.

    Returns:
        int: Application exit code.
    """
    app = QtWidgets.QApplication(argv)
    window = MainWindow()
    window.show()
    return app.exec_()

if __name__ == '__main__':
    sys.exit(main(sys.argv))
