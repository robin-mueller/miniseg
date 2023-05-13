from typing import Literal
from PySide6.QtCore import QObject, Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QSizePolicy
from application.plotting import CurveLibrary, ScheduledValue
from application.qml.pybackend import QMLWidgetBackend, NotifiedProperty, NotifiedPropertyMeta
        
        
class StatusSection(QMLWidgetBackend):
    SOURCE = "qrc:/qml/application/qml/Status.qml"

    connection_state = NotifiedProperty(int)
    byte_rate_s = NotifiedProperty(float)
    calibration_state = NotifiedProperty(int)
    control_switch_state = NotifiedProperty(bool)
    control_cycle_time = NotifiedProperty(float)
    loaded_param_state = NotifiedProperty(int)
    param_file_name = NotifiedProperty(str)
    
    def __init__(self, widget_frame: QFrame, connection_state: Literal[0, 1, 2], calibration_state: Literal[0, 1, 2], control_switch_state: bool, loaded_param_state: Literal[0, 1]):
        super().__init__(widget_frame, self.SOURCE)
        self.connection_state = connection_state
        self.calibration_state = calibration_state
        self.control_switch_state = control_switch_state
        self.control_cycle_time = 0.0
        self.loaded_param_state = loaded_param_state
        self.param_file_name = "Nothing Loaded"

        self._control_cycle_time = ScheduledValue(lambda: CurveLibrary.definitions("CONTROL/CYCLE_US").get_data().value * 1e-3, 1000)
        self._control_cycle_time.updated.connect(self.set_control_cycle_time)
        self._byte_rate = ScheduledValue(lambda: CurveLibrary.definitions("BYTES_RECEIVED").get_data().value, 500)
        self._byte_rate.updated.connect(self.set_byte_rate)

    def set_control_cycle_time(self, value: float):
        self.control_cycle_time = value

    def set_byte_rate(self, value: float):
        self.byte_rate_s = value * 1e3 / self._byte_rate.interval_ms

    def on_receive_start(self):
        self._control_cycle_time.start()
        self._byte_rate.start()

    def on_receive_stop(self):
        self._control_cycle_time.stop()
        self._byte_rate.stop()


class ParameterSection(QObject, metaclass=NotifiedPropertyMeta):
    SOURCE = "qrc:/qml/application/qml/Parameters.qml"

    # Two signals are used to respect the Qt Quick Property uni-directional implementation.
    loaded = NotifiedProperty(dict)  # Outgoing
    last_change = NotifiedProperty(dict)  # Incoming

    def __init__(self, widget_frame: QFrame, **available_parameters: list[str]):
        super().__init__()
        self.groups = {}
        layout = QHBoxLayout(widget_frame)
        layout.setContentsMargins(0, 0, 18, 0)
        layout.setAlignment(Qt.AlignmentFlag.AlignRight)
        layout.setSpacing(15)
        initial_parameters = {key: 0 for key in available_parameters.keys()}
        self.loaded = initial_parameters
        for key, param_names in available_parameters.items():
            frame = QFrame(widget_frame)
            frame.setSizePolicy(QSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding))
            frame.setFrameShape(QFrame.Shape.NoFrame)
            widget = QMLWidgetBackend.create(frame, self.SOURCE, self, title=key, param_names=param_names)
            self.groups[key] = widget
            layout.addWidget(frame)


class SetpointSlider(QMLWidgetBackend):
    SOURCE = "qrc:/qml/application/qml/SetpointSlider.qml"
    value = NotifiedProperty(int)

    def __init__(self, widget_frame: QFrame, value: int):
        super().__init__(widget_frame, self.SOURCE)
        self.value = value
        
