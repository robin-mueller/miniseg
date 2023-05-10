"""
Inspired by the work from
https://stackoverflow.com/questions/48425316/how-to-create-pyqt-properties-dynamically/66266877#66266877
and
https://stackoverflow.com/questions/61318372/how-to-modularize-property-creation-in-pyside
this package offers functionality to drastically reduce the manual effort required to build working QML backends
by generically creating signals, getters and setters for the properties that are supposed to be interconnected with its associated QML objects.

The approach of notifying objects originating from one of the answers in the linked threads was understood, but knowingly not considered.
It simply offered too little advantages and wasn't used in favor of package simplicity and integrity.
"""

from .backend import NotifiedPropertyMeta, NotifiedProperty, QMLWidgetBackend

__all__ = ["NotifiedPropertyMeta", "NotifiedProperty", "QMLWidgetBackend"]
