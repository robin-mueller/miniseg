"""
Inspired by the work from
https://stackoverflow.com/questions/48425316/how-to-create-pyqt-properties-dynamically/66266877#66266877
and
https://stackoverflow.com/questions/61318372/how-to-modularize-property-creation-in-pyside
this package offers functionality to drastically reduce the manual effort required to build working QML backends
by generically creating signals, getters and setters for the properties that are supposed to be interconnected with its associated QML objects.

The approach of notifying objects originating from one of the answers in the linked threads was understood, but knowingly not considered.
It simply offered too little advantages in comparison to the advantages of the packages simplicity and integrity if it were left out.
Also it conflicts with the properties being class attributes and thus shared between objects. A notifying object managed by a specific instance would emit signals across all instances.
This is definitely not desirable and would lead to confusion.
"""

from .backend import QMLPropertyMeta, QMLProperty, QMLWidgetBackend

__all__ = ["QMLPropertyMeta", "QMLProperty", "QMLWidgetBackend"]
