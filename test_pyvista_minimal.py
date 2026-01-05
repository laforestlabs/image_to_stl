#!/usr/bin/env python3
"""
Minimal test for PyVista Qt integration
"""
import sys
from PySide6.QtWidgets import QApplication, QMainWindow
import pyvista as pv
from pyvistaqt import QtInteractor

def main():
    print("Starting PyVista Qt test...")

    app = QApplication(sys.argv)

    window = QMainWindow()
    window.setWindowTitle("PyVista Test")
    window.resize(800, 600)

    print("Creating QtInteractor...")
    plotter = QtInteractor(window)
    window.setCentralWidget(plotter)

    print("Creating simple mesh...")
    mesh = pv.Cube()

    print("Adding mesh to plotter...")
    plotter.add_mesh(mesh, color='lightblue')

    print("Showing window...")
    window.show()

    print("Rendering...")
    plotter.render()

    print("Application running - if you see a cube, PyVista is working!")
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
