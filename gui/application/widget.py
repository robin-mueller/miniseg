from typing import Literal
from PySide6.QtQuickWidgets import QQuickWidget
from PySide6.QtCore import Qt, Signal, QObject, Property
from PySide6.QtWidgets import QFrame, QVBoxLayout, QHBoxLayout


# TODO: Interesting metaclass approach for dynamically defining backends
# -> https://stackoverflow.com/questions/61318372/how-to-modularize-property-creation-in-pyside
# -> https://stackoverflow.com/questions/48425316/how-to-create-pyqt-properties-dynamically/66266877#66266877


class QMLWidgetBackend(QObject):
    def __init__(self, widget_frame: QFrame, source: str):
        """
        Helper class to initialize quick widget objects from QML file.

        :param widget_frame: The frame that the referred quick widget centers in.
        """
        super().__init__()
        self.widget = QQuickWidget(widget_frame)
        self.widget.rootContext().setContextProperty("backend", self)
        self.widget.setSource(source)
        self.widget.setResizeMode(QQuickWidget.SizeRootObjectToView)
        self.widget.setAttribute(Qt.WA_AlwaysStackOnTop)
        self.widget.setAttribute(Qt.WA_TranslucentBackground)
        self.widget.setClearColor(Qt.transparent)
        layout = QVBoxLayout(widget_frame)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.widget)
        
        
class StatusSection(QMLWidgetBackend):
    SOURCE = "qrc:/qml/application/qml/Status.qml"
    connection_state_changed = Signal()
    calibration_state_changed = Signal()
    controller_switch_state_changed = Signal(bool)
    
    def __init__(self, widget_frame: QFrame, connection_state: Literal[0, 1, 2], calibration_state: Literal[0, 1, 2], control_state: bool):
        self._connection_state = connection_state
        self._calibration_state = calibration_state
        self._controller_switch_state = control_state
        super().__init__(widget_frame, self.SOURCE)

    @Property(bool, notify=connection_state_changed)
    def connection_state(self):
        return self._connection_state

    @connection_state.setter
    def connection_state(self, val: Literal[0, 1, 2]):
        self._connection_state = val
        self.connection_state_changed.emit()

    @Property(int, notify=calibration_state_changed)
    def calibration_state(self):
        return self._calibration_state

    @calibration_state.setter
    def calibration_state(self, val: Literal[0, 1, 2]):
        self._calibration_state = val
        self.calibration_state_changed.emit()
    
    @Property(bool, notify=controller_switch_state_changed)
    def controller_switch_state(self):
        return self._controller_switch_state
    
    @controller_switch_state.setter
    def controller_switch_state(self, val: bool):
        self._controller_switch_state = val
        self.controller_switch_state_changed.emit(val)


class ParameterSection:
    SOURCE = "qrc:/qml/application/qml/Parameters.qml"

    def __init__(self, widget_frame: QFrame, **parameters: list[str]):
        self.groups = {}
        layout = QHBoxLayout(widget_frame)
        layout.setContentsMargins(0, 0, 0, 0)
        for key, names in parameters.items():
            frame = QFrame(widget_frame)
            frame.setFrameShape(QFrame.NoFrame)
            widget = QMLWidgetBackend(frame, self.SOURCE).widget
            widget.rootObject().setProperty("title", key)
            widget.rootObject().setProperty("names", names)
            self.groups[key] = widget
            layout.addWidget(frame)


class SetpointSlider(QMLWidgetBackend):
    SOURCE = "qrc:/qml/application/qml/SetpointSlider.qml"
    changed = Signal(int)

    def __init__(self, widget_frame: QFrame, value: int):
        self._value = value
        super().__init__(widget_frame, self.SOURCE)

    @Property(int, notify=changed)
    def value(self):
        return self._value

    @value.setter
    def value(self, val: int):
        self._value = val
        self.changed.emit(val)
        
