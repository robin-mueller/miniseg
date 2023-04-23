from PySide6.QtCore import QObject, QEvent
from PySide6.QtWidgets import QMenu


class KeepMenuOpen(QObject):
    def eventFilter(self, obj: QObject, event: QEvent):
        if event.type() == QEvent.MouseButtonRelease and isinstance(obj, QMenu):
            if obj.activeAction() and not obj.activeAction().menu():  # if the selected action does not have a submenu
                # eat the event, but trigger the function
                obj.activeAction().trigger()
                return True
        
        # standard event processing
        return QObject.eventFilter(self, obj, event)
