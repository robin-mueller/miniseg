from functools import partial
from pathlib import Path
from configuration import THEME
from include.communication import BTDevice, InterfaceDefinition
from resources.main_window_ui import Ui_MainWindow
from include.plotting import MonitoringGraph, GraphDict, CurveDefinition, CurveLibrary
from include.concurrent import ConcurrentTask, BTConnectWorker, BTReceiveWorker
from include.monitoring_window import MonitoringWindow
from include.widget import SetpointSlider, ParameterSection, HeaderSection
from PySide6.QtCore import QTime
from PySide6.QtGui import QCloseEvent, QGuiApplication
from PySide6.QtWidgets import QMainWindow, QProgressBar, QLabel


class MiniSegGUI(QMainWindow):
    def __init__(self):
        super().__init__(None)
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)
        self.ui.plot_overview.setBackground(None)
        self.ui.console_splitter.setSizes([2 * QGuiApplication.primaryScreen().virtualSize().height(), 1 * QGuiApplication.primaryScreen().virtualSize().height()])

        self.monitors: list[MonitoringWindow] = []
        self.bt_device = BTDevice("98:D3:A1:FD:34:63", Path(__file__).parent.parent.parent / "interface.json")
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
        self.header_section.controller_switch_state_changed.connect(lambda val: self.bt_device.send(control_state=val))

        # Curve definitions
        # noinspection PyPropertyAccess
        CurveLibrary.add_definition("POSITION_SETPOINT", CurveDefinition("Position Setpoint", lambda: self.setpoint_slider.value))

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
            curves=[CurveLibrary.definitions("POSITION_SETPOINT", THEME.primary)]
        )
        self.graphs[0].start()

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
