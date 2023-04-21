import configuration as config

from functools import partial
from resources.main_window_ui import Ui_MainWindow
from include.communication.bt_device import BTDevice
from include.communication.interface import InterfaceDefinition, JsonInterfaceReader
from include.plotting import MonitoringGraph, GraphDict, CurveDefinition, CurveLibrary, StampedData
from include.concurrent import ConcurrentTask, BTConnectWorker, BTReceiveWorker
from include.monitoring_window import MonitoringWindow
from include.widget import SetpointSlider, ParameterSection, HeaderSection
from PySide6.QtCore import QTime
from PySide6.QtGui import QCloseEvent, QGuiApplication
from PySide6.QtWidgets import QMainWindow, QProgressBar, QLabel


class MiniSegGUI(QMainWindow):
    INTERFACE_JSON = JsonInterfaceReader(config.JSON_INTERFACE_DEFINITION_PATH)

    def __init__(self):
        super().__init__(None)
        self.start_time = QTime.currentTime()
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)
        self.ui.plot_overview.setBackground(None)
        self.ui.console_splitter.setSizes([  # Set initial space distribution beween console and overview plot
            2 * QGuiApplication.primaryScreen().virtualSize().height(),
            1 * QGuiApplication.primaryScreen().virtualSize().height()]
        )

        self.monitors: list[MonitoringWindow] = []
        self.bt_device = BTDevice(
            address=config.HC06_BLUETOOTH_ADDRESS,
            rx_interface_def=InterfaceDefinition(self.INTERFACE_JSON.from_device, ("msg", str), ("ts", int)),
            tx_interface_def=InterfaceDefinition(self.INTERFACE_JSON.to_device, ("sync_ts", int))
        )
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
        self.bt_connect_progress_bar = QProgressBar()
        self.bt_connect_progress_bar.setMaximumSize(250, 15)
        self.bt_connect_progress_bar.setRange(0, 0)
        self.bt_connect_label = QLabel("Connecting ...")
        self.header_section = HeaderSection(self.ui.header_frame)
        self.parameter_section = ParameterSection(self.ui.parameter_frame)
        self.setpoint_slider = SetpointSlider(self.ui.setpoint_slider_frame)

        self.ui.actionNewMonitor.triggered.connect(self.on_open_monitor)
        self.ui.actionConnect.triggered.connect(self.on_bt_connect)
        self.ui.actionDisconnect.triggered.connect(self.on_bt_disconnect)
        self.ui.actionStartCalibration.triggered.connect(self.on_start_calibration)

        # Write to TX interface
        self.header_section.controller_switch_state_changed.connect(lambda val: self.bt_device.send(control_state=(val, self.up_time)))

        # Curve definitions
        # noinspection PyPropertyAccess
        CurveLibrary.add_definition("POSITION_SETPOINT", CurveDefinition("Position Setpoint", lambda: StampedData(self.setpoint_slider.value, self.up_time)))

        def add_interface_curve_candidates(accessor: list[str], definition: InterfaceDefinition):
            for key, val in definition.items():
                _accessor = accessor + [key]
                if val in [float, int, bool]:
                    CurveLibrary.add_definition('/'.join(_accessor).upper(), CurveDefinition('/'.join(_accessor), partial(self.bt_device.rx_interface.get, tuple(_accessor))))
                elif isinstance(val, InterfaceDefinition):
                    add_interface_curve_candidates(_accessor, val)

        add_interface_curve_candidates([], self.bt_device.rx_interface.definition)

        # Add graphs
        self.graphs: GraphDict[str, MonitoringGraph] = GraphDict(self.ui.plot_overview)
        self.graphs[0] = MonitoringGraph(
            curves=[CurveLibrary.definitions("POSITION_SETPOINT", config.THEME.primary)]
        )
        self.graphs[0].start()

    @property
    def up_time(self):
        return self.start_time.msecsTo(QTime.currentTime()) / 1e3

    def on_bt_connect(self):
        self.ui.actionConnect.setEnabled(False)
        self.ui.statusbar.addWidget(self.bt_connect_label)
        self.ui.statusbar.addWidget(self.bt_connect_progress_bar)
        self.bt_connect_label.show()
        self.bt_connect_progress_bar.show()

        # Connect asynchronoulsy
        self.bt_connect_task.start()

    def on_bt_connected(self):
        self.ui.statusbar.removeWidget(self.bt_connect_label)
        self.ui.statusbar.removeWidget(self.bt_connect_progress_bar)
        self.ui.statusbar.showMessage("Connection successful!", 3000)
        self.ui.actionDisconnect.setEnabled(True)

        # Start receiving
        self.bt_receive_task.start()

    def on_bt_connection_failed(self, exception: Exception):
        self.ui.statusbar.removeWidget(self.bt_connect_label)
        self.ui.statusbar.removeWidget(self.bt_connect_progress_bar)
        self.ui.actionConnect.setEnabled(True)
        self.ui.statusbar.showMessage(f"Connecting failed - {exception.__class__.__name__}: {str(exception)}", 3000)

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

        # Update RX interface
        self.bt_device.deserialize(received)

        # Reset calibration flags
        if self.bt_device.tx_interface["calibration"] and self.bt_device.rx_interface["calibrated"]:
            self.bt_device.tx_interface["calibration"] = False
            self.ui.actionStartCalibration.setEnabled(True)
            self.bt_device.send(calibration=False)

        # Write received message to terminal
        msg = self.bt_device.rx_interface["msg"]
        if msg:
            self.ui.console.append(f"{QTime.currentTime().toString()} -> {msg}")
            self.bt_device.rx_interface["msg"] = ""  # Clear message buffer

    def on_start_calibration(self):
        self.bt_device.rx_interface["calibrated"] = False
        self.ui.actionStartCalibration.setEnabled(False)
        self.bt_device.send(calibration=True)

    def on_open_monitor(self):
        new_monitor = MonitoringWindow()
        new_monitor.destroyed.connect(lambda: self.monitors.remove(new_monitor))
        self.monitors.append(new_monitor)
        new_monitor.show()

    def closeEvent(self, event: QCloseEvent):
        for monitor in self.monitors:
            monitor.close()
        self.bt_receive_task.stop()
        self.bt_device.disconnect()
        super().closeEvent(event)
