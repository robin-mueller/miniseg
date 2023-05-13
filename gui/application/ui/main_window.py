import json
import configuration as config

from typing import Literal, Callable
from pathlib import Path
from application.communication.device import BluetoothDevice
from application.communication.interface import StampedData, DataInterface
from application.plotting import MonitoringGraph, GraphDict, CurveDefinition, CurveLibrary, UserDict
from application.concurrent import ConcurrentTask
from application.ui.monitoring_window import MonitoringWindow
from application.qml.widget import SetpointSlider, ParameterSection, StatusSection
from functools import partial
from resources.main_window_ui import Ui_MainWindow
from PySide6.QtCore import QTime
from PySide6.QtGui import QCloseEvent, QGuiApplication
from PySide6.QtWidgets import QMainWindow, QProgressBar, QLabel, QFileDialog


class MinSegGUI(QMainWindow):
    def __init__(self):
        super().__init__(None)
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)
        self.ui.plot_overview.setBackground(None)
        self.ui.console_splitter.setSizes([  # Set initial space distribution beween console and overview plot
            3 * QGuiApplication.primaryScreen().virtualSize().height(),
            1 * QGuiApplication.primaryScreen().virtualSize().height()]
        )

        self.monitors: list[MonitoringWindow] = []

        # Bluetooth data
        self.bt_device = BluetoothDevice(config.HC06_BLUETOOTH_ADDRESS)
        self.bt_connect_task = ConcurrentTask(
            self.bt_device.connect,
            on_success=self.on_bt_connected,
            on_failed=self.on_bt_connection_failed
        )
        self.bt_receive_task = ConcurrentTask(
            self.bt_device.receive,
            on_success=self.on_bt_received,
            on_failed=self.ui.actionDisconnect.trigger,
            repeat_ms=0
        )
        self.bt_bytes_received = 0
        self.bt_connect_progress_bar = QProgressBar()
        self.bt_connect_progress_bar.setMaximumSize(250, 15)
        self.bt_connect_progress_bar.setRange(0, 0)
        self.bt_connect_label = QLabel("Connecting ...")

        self.ui.actionNewMonitor.triggered.connect(self.on_open_monitor)
        self.ui.actionConnect.triggered.connect(self.on_bt_connect)
        self.ui.actionDisconnect.triggered.connect(self.on_bt_disconnect)
        self.ui.actionStartCalibration.triggered.connect(self.on_start_calibration)
        self.ui.actionTransmitState.triggered.connect(self.send_tx_data_state)
        self.ui.actionParamLoad.triggered.connect(self.load_parameters)
        self.ui.actionParamSaveAs.triggered.connect(self.save_parameters)
        self.ui.actionParamSend.triggered.connect(lambda: self.send_parameters("variable"))

        # Add interface set callbacks
        self.bt_device.rx_data.execute_when_set("calibrated", self.on_calibrated)
        self.bt_device.rx_data.execute_when_set("msg", lambda msg: self.ui.console.append(f"{QTime.currentTime().toString()} -> {msg.value}"))

        # Curve definitions
        CurveLibrary.add_definition("BYTES_RECEIVED", CurveDefinition("bytes_received", lambda: self.bt_bytes_received))
        CurveLibrary.add_definition("POS_SETPOINT_MM", CurveDefinition("pos_setpoint_mm", lambda: self.bt_device.tx_data["pos_setpoint_mm"].value))
        CurveLibrary.parse_data_interface(self.bt_device.rx_data)

        # Add QML sections
        self.status_section = StatusSection(self.ui.status_frame, 0, 0, False, 0)
        self.bt_receive_task.started.connect(self.status_section.on_receive_start)
        self.bt_receive_task.stopped.connect(self.status_section.on_receive_stop)
        self.parameter_section = ParameterSection(self.ui.parameter_frame, **{group: list(names.keys()) for group, names in self.bt_device.tx_data.definition["parameters", "variable"].items()})
        self.setpoint_slider = SetpointSlider(self.ui.setpoint_slider_frame, 0)

        # TX interface connections
        self.setpoint_slider.value_changed.connect(
            lambda val: self.do_catch_ex_in_statusbar(lambda: self.bt_device.send(pos_setpoint_mm=val * 10), self.bt_device.NotConnectedError, "Failed to Send Setpoint")
        )
        self.status_section.control_switch_state_changed.connect(self.on_control_state_change)
        self.parameter_section.last_change_changed.connect(lambda changed: self.update_parameters("variable", changed))

        # Add graphs to overview
        self.graphs: UserDict[int, MonitoringGraph] = GraphDict(self.ui.plot_overview)
        for index, curve_names in enumerate([
            ["POS_SETPOINT_MM", "OBSERVER/POSITION/Z_MM"],
        ]):
            self.graphs[index] = MonitoringGraph(
                start_signal=self.bt_receive_task.started, stop_signal=self.bt_receive_task.stopped,
                curves=CurveLibrary.colorize(curve_names)
            )

    def do_catch_ex_in_statusbar(self, do: Callable[[], None], catch: type[Exception] | list[type[Exception]], header: str = None):
        prepend = ""
        if header is not None:
            prepend = header + " - "
        try:
            do()
        except catch as e:
            self.ui.statusbar.showMessage(prepend + f"{e.__class__.__name__}: {str(e)}", 3000)
            return False
        else:
            return True

    def send_tx_data_state(self):
        self.bt_device.send(data=self.bt_device.tx_data)
        self.status_section.loaded_param_state = 1

    def on_bt_connect(self):
        self.ui.actionConnect.setEnabled(False)
        self.ui.statusbar.addWidget(self.bt_connect_label)
        self.ui.statusbar.addWidget(self.bt_connect_progress_bar)
        self.bt_connect_label.show()
        self.bt_connect_progress_bar.show()
        self.status_section.connection_state = 1

        # Connect asynchronoulsy
        self.bt_connect_task.start()

    def on_bt_connected(self):
        self.ui.statusbar.removeWidget(self.bt_connect_label)
        self.ui.statusbar.removeWidget(self.bt_connect_progress_bar)
        self.ui.statusbar.showMessage("Connection successful!", 3000)
        self.ui.actionDisconnect.setEnabled(True)
        self.ui.actionStartCalibration.setEnabled(True)
        self.ui.actionTransmitState.setEnabled(True)
        self.ui.actionParamSend.setEnabled(True)
        self.status_section.connection_state = 2

        # Start receiving
        self.bt_receive_task.start()

        self.ui.actionTransmitState.trigger()

    def on_bt_connection_failed(self, exception: Exception):
        self.ui.statusbar.removeWidget(self.bt_connect_label)
        self.ui.statusbar.removeWidget(self.bt_connect_progress_bar)
        self.ui.actionConnect.setEnabled(True)
        self.ui.statusbar.showMessage(f"Connecting failed - {exception.__class__.__name__}: {str(exception)}", 3000)
        self.status_section.connection_state = 0

    def on_bt_disconnect(self):
        self.bt_receive_task.stop()
        self.status_section.control_switch_state = False

        self.bt_device.disconnect()
        self.ui.actionConnect.setEnabled(True)
        self.ui.actionDisconnect.setEnabled(False)
        self.ui.actionStartCalibration.setEnabled(False)
        self.ui.actionTransmitState.setEnabled(False)
        self.ui.actionParamSend.setEnabled(False)
        self.ui.statusbar.showMessage("Disconnected from device!", 3000)
        self.ui.console.clear()
        self.status_section.connection_state = 0
        self.status_section.calibration_state = 0
        self.status_section.loaded_param_state = 0  # Change state to not yet sent
        self.status_section.control_cycle_time = 0.0

    def on_bt_received(self, received: bytes):
        self.bt_bytes_received = len(received)
        if not received:
            return

        self.bt_device.rx_data.update_receive_time()  # Update receive timestamp
        self.bt_device.deserialize(received)  # Update RX interface

    def on_start_calibration(self):
        self.status_section.calibration_state = 0
        self.bt_device.send(calibration=True)
        self.ui.actionStartCalibration.setEnabled(False)

    def on_calibrated(self, calibrated: StampedData):
        if self.status_section.calibration_state == 0 and self.bt_device.tx_data["calibration"].value is True and calibrated.value is False:
            self.status_section.calibration_state = 1
            return

        if self.status_section.calibration_state == 1 and calibrated.value is True:
            self.status_section.calibration_state = 2
            self.bt_device.tx_data["calibration"] = False
            self.ui.actionStartCalibration.setEnabled(True)
            return

    def on_open_monitor(self):
        new_monitor = MonitoringWindow(self.bt_receive_task.is_active, self.bt_receive_task.started, self.bt_receive_task.stopped)
        new_monitor.destroyed.connect(lambda: self.monitors.remove(new_monitor))
        self.monitors.append(new_monitor)
        new_monitor.show()

    def load_parameters(self):
        path, _ = QFileDialog.getOpenFileName(self, "Load Parameters", str(config.PARAMETERS_DIR), "JSON (*.json)")
        if path:
            path = Path(path)
            with path.open() as file:
                parameters = json.load(file)
            self.status_section.param_file_name = path.name

            # The signal connection of this property will update tx data automatically after this assignment.
            # However, if the same file is loaded, no signal would be emitted.
            # To make sure the changed number fields are also reset to the loaded values in such a case, the signal has to be emitted manually.
            self.parameter_section.blockSignals(True)
            self.parameter_section.loaded = parameters["variable"]
            self.parameter_section.blockSignals(False)
            self.parameter_section.loaded_changed.emit(parameters["variable"])  # Emit the signal now manually

            self.update_parameters("inferred", parameters["inferred"])
            self.send_parameters()

    def save_parameters(self):
        path, _ = QFileDialog.getSaveFileName(self, "Save Parameters", str(config.PARAMETERS_DIR), "JSON (*.json)")
        if path:
            path = Path(path)
            if path.suffix != '.json':
                path += '.json'
            with path.open('w') as file:
                json.dump(self.bt_device.tx_data["parameters"], file, cls=DataInterface.JSONEncoder, indent=2)

            # Update loaded param file name
            self.status_section.param_file_name = path.name
            self.status_section.loaded_param_state = self.status_section.loaded_param_state

    def send_parameters(self, subkey: Literal["variable", "inferred"] = None):
        do_send = partial(self.bt_device.send, key="parameters") if subkey is None else partial(self.bt_device.send, key=("parameters", subkey))
        if self.do_catch_ex_in_statusbar(do_send, self.bt_device.NotConnectedError, "Failed to Send Parameters"):
            self.status_section.loaded_param_state = 1

    def update_parameters(self, subkey: Literal["variable", "inferred"], changed: dict):
        self.bt_device.tx_data["parameters", subkey].update(changed)
        self.status_section.loaded_param_state = 0  # Change state to not yet sent

    def on_control_state_change(self, state: bool):
        self.do_catch_ex_in_statusbar(lambda: self.bt_device.send(control_state=state), self.bt_device.NotConnectedError, "Failed to Send Control State Change")
        if not state:
            self.setpoint_slider.value = 0

    def closeEvent(self, event: QCloseEvent):
        for monitor in self.monitors:
            monitor.close()
        self.on_bt_disconnect()

        # Stop qml engines before backends are destroyed to prevent errors
        self.status_section.widget.deleteLater()
        for sec in self.parameter_section.groups.values():
            sec.deleteLater()
        self.setpoint_slider.widget.deleteLater()

        super().closeEvent(event)
