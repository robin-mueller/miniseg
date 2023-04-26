"""
Inspired by the work from
https://stackoverflow.com/questions/48425316/how-to-create-pyqt-properties-dynamically/66266877#66266877
and
https://stackoverflow.com/questions/61318372/how-to-modularize-property-creation-in-pyside
this package offers functionality to drastically reduce the manual effort required to build working QML backends
by generically creating signals, getters and setters for the properties that are supposed to be interconnected with its associated QML objects.
"""

from .backend import QMLPropertyMeta, QMLProperty, QMLWidgetBackend

__all__ = ["QMLPropertyMeta", "QMLProperty", "QMLWidgetBackend"]
