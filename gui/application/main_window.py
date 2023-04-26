import json
import configuration as config

from pathlib import Path
from .communication.device import BluetoothDevice
from .communication.interface import DataInterfaceDefinition, StampedData, DataInterface
from .helper import program_uptime
from .plotting import MonitoringGraph, GraphDict, CurveDefinition, CurveLibrary, UserDict
from .concurrent import ConcurrentTask, BTConnectWorker, BTReceiveWorker
from .monitoring_window import MonitoringWindow
from .widget import SetpointSlider, ParameterSection, StatusSection
from functools import partial
from resources.main_window_ui import Ui_MainWindow
from PySide6.QtCore import QTime
from PySide6.QtGui import QCloseEvent, QGuiApplication
from PySide6.QtWidgets import QMainWindow, QProgressBar, QLabel, QFileDialog


class MinSegGUI(QMainWindow):
    def __init__(self):
        super().__init__(None)
        self.start_time: QTime = QTime.currentTime()
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
            BTConnectWorker,
            self.bt_device.connect,
            on_success=self.on_bt_connected,
            on_failed=self.on_bt_connection_failed
        )
        self.bt_receive_task = ConcurrentTask(
            BTReceiveWorker,
            self.bt_device.receive,
            on_success=self.on_bt_received,
            repeat_ms=0
        )
        self.bt_receive_time: QTime = self.start_time
        self.bt_connect_progress_bar = QProgressBar()
        self.bt_connect_progress_bar.setMaximumSize(250, 15)
        self.bt_connect_progress_bar.setRange(0, 0)
        self.bt_connect_label = QLabel("Connecting ...")
        self.status_section = StatusSection(self.ui.status_frame, 0, 0, False)
        self.parameter_section = ParameterSection(self.ui.parameter_frame, **{group: list(names.keys()) for group, names in self.bt_device.tx_data.definition["parameters"].items()})
        self.setpoint_slider = SetpointSlider(self.ui.setpoint_slider_frame, 0)

        self.ui.actionNewMonitor.triggered.connect(self.on_open_monitor)
        self.ui.actionConnect.triggered.connect(self.on_bt_connect)
        self.ui.actionDisconnect.triggered.connect(self.on_bt_disconnect)
        self.ui.actionStartCalibration.triggered.connect(self.on_start_calibration)
        self.ui.actionParamLoad.triggered.connect(self.load_parameters)
        self.ui.actionParamSaveAs.triggered.connect(self.save_parameters)
        self.ui.actionParamSend.triggered.connect(lambda: self.bt_device.send("parameters"))

        # Add receive callbacks
        self.bt_device.rx_data.execute_when_set("calibrated", self.on_calibrated)
        self.bt_device.rx_data.execute_when_set("msg", lambda msg: self.ui.console.append(f"{QTime.currentTime().toString()} -> {msg.value}"))

        # TX interface connections
        self.setpoint_slider.value_changed.connect(lambda val: self.bt_device.send(pos_setpoint=val))
        self.status_section.controller_switch_state_changed.connect(lambda val: self.bt_device.send(control_state=val))
        self.parameter_section.last_change_changed.connect(lambda val: self.bt_device.tx_data["parameters"].update(val))

        # Curve definitions
        CurveLibrary.add_definition("POSITION_SETPOINT", CurveDefinition("Position Setpoint", lambda: StampedData(self.bt_device.tx_data["pos_setpoint"].value, program_uptime())))

        def add_interface_curve_candidates(accessor: list[str], definition: DataInterfaceDefinition):
            for key, val in definition.items():
                _accessor = accessor + [key]
                if val in [float, int, bool]:
                    CurveLibrary.add_definition('/'.join(_accessor).upper(), CurveDefinition('/'.join(_accessor), partial(self.bt_device.rx_data.get, tuple(_accessor))))
                elif isinstance(val, DataInterfaceDefinition):
                    add_interface_curve_candidates(_accessor, val)

        add_interface_curve_candidates([], self.bt_device.rx_data.definition)

        # Add graphs
        self.graphs: UserDict[int, MonitoringGraph] = GraphDict(self.ui.plot_overview)
        self.graphs[0] = MonitoringGraph(
            curves=[CurveLibrary.definitions("POSITION_SETPOINT", config.THEME.primary)]
        )
        self.graphs[0].start()

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
        self.status_section.connection_state = 2

        # Start receiving
        self.bt_receive_task.start()

    def on_bt_connection_failed(self, exception: Exception):
        self.ui.statusbar.removeWidget(self.bt_connect_label)
        self.ui.statusbar.removeWidget(self.bt_connect_progress_bar)
        self.ui.actionConnect.setEnabled(True)
        self.ui.statusbar.showMessage(f"Connecting failed - {exception.__class__.__name__}: {str(exception)}", 3000)
        self.status_section.connection_state = 0

    def on_bt_disconnect(self):
        self.bt_receive_task.stop()
        self.bt_device.disconnect()
        self.ui.actionConnect.setEnabled(True)
        self.ui.actionDisconnect.setEnabled(False)
        self.ui.statusbar.showMessage("Disconnected from device!", 3000)
        self.ui.console.clear()

    def on_bt_received(self, received: bytes):
        if not received:
            return

        self.bt_device.rx_data.update_receive_time()  # Update receive time
        self.bt_device.deserialize(received)  # Update RX interface

    def on_start_calibration(self):
        self.bt_device.send(calibration=True)
        self.bt_device.rx_data["calibrated"] = False
        self.status_section.calibration_state = 1
        self.ui.actionStartCalibration.setEnabled(False)

    def on_calibrated(self, calibrated: StampedData):
        if calibrated.value is True:
            self.status_section.calibration_state = 2
            self.bt_device.tx_data["calibration"] = False
            self.ui.actionStartCalibration.setEnabled(True)
        else:
            self.status_section.calibration_state = 0

    def on_open_monitor(self):
        new_monitor = MonitoringWindow()
        new_monitor.destroyed.connect(lambda: self.monitors.remove(new_monitor))
        self.monitors.append(new_monitor)
        new_monitor.show()

    def load_parameters(self):
        path, _ = QFileDialog.getOpenFileName(self, "Load Parameters", str(config.PARAMETERS_DIR), "JSON (*.json)")
        if path:
            with Path(path).open() as file:
                parameters = json.load(file)
            self.parameter_section.loaded = parameters

    def save_parameters(self):
        path, _ = QFileDialog.getSaveFileName(self, "Save Parameters", str(config.PARAMETERS_DIR), "JSON (*.json)")
        if path:
            path = Path(path)
            if path.suffix != '.json':
                path += '.json'
            with path.open('w') as file:
                json.dump(self.bt_device.tx_data["parameters"], file, cls=DataInterface.JSONEncoder, indent=2)

    def closeEvent(self, event: QCloseEvent):
        for monitor in self.monitors:
            monitor.close()
        self.bt_receive_task.stop()
        self.bt_device.disconnect()
        super().closeEvent(event)
