from PySide6.QtWidgets import QFrame, QHBoxLayout
from .qml.pybackend import QMLWidgetBackend, QMLProperty
        
        
class StatusSection(QMLWidgetBackend):
    SOURCE = "qrc:/qml/application/qml/Status.qml"

    connection_state = QMLProperty(int)
    calibration_state = QMLProperty(int)
    controller_switch_state = QMLProperty(bool)
    
    def __init__(self, widget_frame: QFrame):
        super().__init__(widget_frame, self.SOURCE)
        self.connection_state = 0
        self.calibration_state = 0
        self.controller_switch_state = False


class ParameterGroup(QMLWidgetBackend):
    SOURCE = "qrc:/qml/application/qml/Parameters.qml"

    value = QMLProperty(dict)

    def __init__(self, widget_frame: QFrame, title: str, names: list[str], initial: dict[str, float]):
        super().__init__(widget_frame, self.SOURCE)
        self.widget.rootObject().setProperty("title", title)
        self.widget.rootObject().setProperty("names", names)
        self.value = initial


class ParameterSection:
    def __init__(self, widget_frame: QFrame, **parameters: list[str]):
        self.groups = {}
        layout = QHBoxLayout(widget_frame)
        layout.setContentsMargins(0, 0, 0, 0)
        for key, names in parameters.items():
            frame = QFrame(widget_frame)
            frame.setFrameShape(QFrame.NoFrame)
            widget = ParameterGroup(frame, key, names, {'a1': 100})
            self.groups[key] = widget
            layout.addWidget(frame)


class SetpointSlider(QMLWidgetBackend):
    SOURCE = "qrc:/qml/application/qml/SetpointSlider.qml"
    value = QMLProperty(int)

    def __init__(self, widget_frame: QFrame):
        super().__init__(widget_frame, self.SOURCE)
        self.value = 0
        
