"""Reusable Qt components that know nothing about the main window.

Nothing is re-exported eagerly on purpose: ``pyqtgraph.opengl`` needs a working
GL stack, and importing a hex-table model should not drag that in. Import the
submodules directly.
"""
