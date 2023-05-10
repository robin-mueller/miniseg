import itertools
import pandas as pd
import configuration as config

from functools import partial
from collections import UserDict
from typing import Optional
from pathlib import Path
from application.helper import KeepMenuOpen
from application.plotting import MonitoringGraph, GraphDict, CurveLibrary, CurveDefinition, ColouredCurve
from resources.monitoring_window_ui import Ui_MonitoringWindow
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QMainWindow, QFileDialog
from PySide6.QtCore import Qt, QTime, SignalInstance


class MonitoringWindow(QMainWindow):
    def __init__(self, currently_receiving: bool, receive_start_signal: SignalInstance, receive_stop_signal: SignalInstance):
        super().__init__()
        self.rx_start_sig = receive_start_signal
        self.rx_stop_sig = receive_stop_signal
        receive_start_signal.connect(lambda: self.set_allow_plot_start(True))
        receive_stop_signal.connect(lambda: self.set_allow_plot_start(False))
        self.allow_plot_start = currently_receiving
        self.recording_start: Optional[QTime] = None
        self.keep_menu_open_filter = KeepMenuOpen(self)

        self.setAttribute(Qt.WA_DeleteOnClose)
        self.ui = Ui_MonitoringWindow()
        self.ui.setupUi(self)
        self.ui.graph_layout.setBackground(None)
        self.ui.menuGraphs.installEventFilter(self.keep_menu_open_filter)
        self.ui.actionAddGraph.triggered.connect(self.add_graph)
        self.ui.actionStartRecording.triggered.connect(self.start_recording)
        self.ui.actionStopRecording.triggered.connect(self.stop_recording)

        self.graphs: UserDict[int, MonitoringGraph] = GraphDict(self.ui.graph_layout)
        self.add_graph()

    def set_allow_plot_start(self, state: bool):
        self.allow_plot_start = state

    def update_curve_colors(self):
        curve_defs: list[CurveDefinition] = list(itertools.chain(*[graph.curves_dict.keys() for graph in self.graphs.values()]))
        color_map = {coloured_curve.definition: coloured_curve.color for coloured_curve in CurveLibrary.colorize(curve_defs)}
        for graph in self.graphs.values():
            for curve_definition, curve in graph.curves_dict.items():
                curve.setPen(color_map[curve_definition])

    def add_graph(self):
        graph_id = 0
        while graph_id in self.graphs:
            graph_id += 1
        graph_title = f"Graph {graph_id + 1}"
        graph_menu = self.ui.menuGraphs.addMenu(graph_title)
        graph_menu.installEventFilter(self.keep_menu_open_filter)
        remove_action = graph_menu.addAction("Remove")
        graph_menu.addSection("Curves")
        curve_actions: dict[str, QAction] = {name: graph_menu.addAction(name) for name in CurveLibrary.definitions()}

        def toggle_curve(curve_definition: CurveDefinition, show: bool):
            if show:
                self.graphs[graph_id].add_curve(ColouredCurve(curve_definition))
            else:
                self.graphs[graph_id].remove_curve(curve_definition)
            self.update_curve_colors()

        def delete_graph():
            graph_menu.deleteLater()
            del self.graphs[graph_id]
            self.update_curve_colors()

        remove_action.triggered.connect(delete_graph)
        for name, action in curve_actions.items():
            action.setCheckable(True)
            action.toggled.connect(partial(toggle_curve, CurveLibrary.definitions(name)))

        self.graphs[graph_id] = MonitoringGraph(start_signal=self.rx_start_sig, stop_signal=self.rx_stop_sig, title=graph_title)
        if self.allow_plot_start:
            self.graphs[graph_id].start_updating()

    def start_recording(self):
        if any([graph.curves_dict for graph in self.graphs.values()]):  # Only start recording if any curves have been defined
            for graph in self.graphs.values():
                for curve in graph.curves_dict.values():
                    curve.recording = True
            self.ui.actionStartRecording.setEnabled(False)
            self.ui.actionStopRecording.setEnabled(True)
            self.recording_start = QTime.currentTime()

    def stop_recording(self):
        for graph in self.graphs.values():
            for curve in graph.curves_dict.values():
                curve.recording = False
        self.ui.actionStartRecording.setEnabled(True)
        self.ui.actionStopRecording.setEnabled(False)

        # Save recording
        rec_dir = config.DEFAULT_RECORDING_DIR
        if not rec_dir.exists():
            rec_dir.mkdir()
        path, _ = QFileDialog.getSaveFileName(self, "Save Monitoring Data", str(rec_dir), "CSV (*.csv)")
        if path:
            df = []
            for graph in self.graphs.values():
                for curve_def, curve in graph.curves_dict.items():
                    df.append(pd.DataFrame(curve.recording_array.T, columns=pd.MultiIndex.from_product([[graph.title], [curve_def.label], ['Time', 'Value']])))
            df = pd.concat(df, axis=1)

            if Path(path).suffix != '.csv':
                path += '.csv'
            df.to_csv(path)
