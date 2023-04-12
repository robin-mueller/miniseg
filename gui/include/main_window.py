from functools import partial
from pathlib import Path
from include.communication import BTDevice, Interface
from resources.main_window_ui import Ui_MainWindow
from include.plotting import MonitoringGraph, GraphDict, CurveDefinition, CURVE_LIBRARY
from include.concurrent import ConcurrentTask
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
            self.bt_device.connect,
            on_success=self.on_bluetooth_connected,
            on_failed=self.on_bluetooth_connection_failed
        )
        self.bt_receive_task = ConcurrentTask(
            self.bt_device.receive,
            on_success=lambda data_available: self.on_bt_data_available(self.bt_device.rx_interface) if data_available else None,
            repeat_ms=200
        )
        self.bt_connect_progress_bar = QProgressBar()
        self.bt_connect_progress_bar.setMaximumSize(250, 15)
        self.bt_connect_progress_bar.setRange(0, 0)
        self.bt_connect_label = QLabel("Connecting ...")
        self.header_section = HeaderSection(self.ui.header_frame)
        self.parameter_section = ParameterSection(self.ui.parameter_frame)
        self.setpoint_slider = SetpointSlider(self.ui.setpoint_slider_frame)

        self.ui.actionNewMonitor.triggered.connect(self.on_open_monitor)
        self.ui.actionConnect.triggered.connect(self.on_bluetooth_connect)
        self.ui.actionDisconnect.triggered.connect(self.on_bluetooth_disconnect)

        # Write to TX interface
        self.header_section.controller_switch_state_changed.connect(lambda val: self.bt_device.send({"controller_state": val}))

        # Curve definitions
        # noinspection PyPropertyAccess
        CURVE_LIBRARY["POSITION_SETPOINT"] = CurveDefinition("Position Setpoint", lambda: self.setpoint_slider.value)

        def add_interface_curve_candidates(accessor: list[str], definition: dict[str, str | dict]):
            for key, val in definition.items():
                _accessor = accessor + [key]
                if isinstance(val, str):
                    if val in (type_string for type_string, p_type in Interface.VALID_TYPES.items() if p_type in [float, int, bool]):
                        CURVE_LIBRARY['.'.join(_accessor).upper()] = CurveDefinition('.'.join(_accessor), partial(self.bt_device.rx_interface.get, tuple(_accessor)))
                elif isinstance(val, dict):
                    add_interface_curve_candidates(_accessor, val)

        add_interface_curve_candidates([], self.bt_device.rx_interface.definition)

        # Add graphs
        self.graphs: GraphDict[str, MonitoringGraph] = GraphDict(self.ui.plot_overview)
        self.graphs[0] = MonitoringGraph(
            curves=[CURVE_LIBRARY["POSITION_SETPOINT"]]
        )
        self.graphs[0].start()

    def on_bluetooth_connect(self):
        self.ui.actionConnect.setEnabled(False)
        self.ui.statusbar.addWidget(self.bt_connect_label)
        self.ui.statusbar.addWidget(self.bt_connect_progress_bar)
        self.bt_connect_label.show()
        self.bt_connect_progress_bar.show()

        # Connect asynchronoulsy
        self.bt_connect_task.start()

    def on_bluetooth_connected(self):
        self.ui.statusbar.removeWidget(self.bt_connect_label)
        self.ui.statusbar.removeWidget(self.bt_connect_progress_bar)
        self.ui.statusbar.showMessage("Connection successful!", 3000)
        self.ui.actionDisconnect.setEnabled(True)

        # Start receiving
        self.bt_receive_task.start()

    def on_bluetooth_connection_failed(self, exception: Exception):
        self.ui.statusbar.removeWidget(self.bt_connect_label)
        self.ui.statusbar.removeWidget(self.bt_connect_progress_bar)
        self.ui.actionConnect.setEnabled(True)
        self.ui.statusbar.showMessage(f"Connecting failed - {exception.__class__.__name__}: {str(exception)}", 3000)

    def on_bluetooth_disconnect(self):
        self.bt_receive_task.stop()
        self.bt_device.disconnect()
        self.ui.actionConnect.setEnabled(True)
        self.ui.actionDisconnect.setEnabled(False)
        self.ui.statusbar.showMessage("Disconnected from device!", 3000)
        self.ui.console.clear()

    def on_open_monitor(self):
        new_monitor = MonitoringWindow()
        new_monitor.destroyed.connect(lambda: self.monitors.remove(new_monitor))
        self.monitors.append(new_monitor)
        new_monitor.show()

    def on_bt_data_available(self, rx_data: Interface):
        received_message: str = rx_data["msg"]
        if received_message:
            self.ui.console.append(f"{QTime.currentTime().toString()} -> {received_message}")

    def closeEvent(self, event: QCloseEvent):
        for monitor in self.monitors:
            monitor.close()
        self.bt_receive_task.stop()
        self.bt_device.disconnect()
        super().closeEvent(event)
