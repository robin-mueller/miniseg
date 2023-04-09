import numpy as np
import pyqtgraph as pg

from collections import UserDict
from typing import Callable, Optional
from include.curve_definition import CurveDefinition
from configuration import THEME, PARAMETERS
from time import perf_counter
from PySide6.QtCore import QTime, QTimer, QObject, QEvent, Signal, QThread
from PySide6.QtWidgets import QMenu


# noinspection PyUnresolvedReferences
class ConcurrentTask:
    """
    A persistent handle (meaning the object doesn't have to be reinstantiated every time the task is supposed to start again)
    for a concurrent task using QThread which is defined by the constructor arguments.
    The approach used is based on the guide from https://realpython.com/python-pyqt-qthread/
    """

    class _ConcurrentWorker(QObject):
        success = Signal()
        failed = Signal(str)
        finished = Signal()
        quit = Signal()

        def __init__(self, do_work: Callable[[], None], repeat):
            super().__init__()
            self._do_work = do_work
            self._repeat = repeat
            self._loop = True
            self.quit.connect(self.on_quit)

        def run(self):
            try:
                while self._loop:
                    self._do_work()
                    self.success.emit()
                    if not self._repeat:
                        break
            except Exception as e:
                self.failed.emit(repr(e))
            finally:
                self.finished.emit()

        def on_quit(self):
            self._loop = False

    def __init__(self, do_work: Callable[[], None], on_success: Callable[[], None] = None, on_failed: Callable[[str], None] = None, repeat=False):

        # def create_worker():
        #     worker = self._ConcurrentWorker(do_work, repeat)
        #     if on_success:
        #         worker.success.connect(on_success)
        #     if on_failed:
        #         worker.failed.connect(on_failed)
        #     return worker

        # self.create_worker = create_worker
        self.worker = self._ConcurrentWorker(do_work, repeat)
        if on_success:
            self.worker.success.connect(on_success)
        if on_failed:
            self.worker.failed.connect(on_failed)
        self.thread = QThread()
        self._setup_task()

    def _setup_task(self):
        # self.worker = self.create_worker()
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.worker.finished.connect(self.thread.quit)
        # self.worker.finished.connect(self.worker.deleteLater)
        # self.thread.finished.connect(self.thread.deleteLater)


    def start(self):
        # self._setup_task()
        self.thread.start()

    # def quit(self):
    #     self.worker

class KeepMenuOpen(QObject):
    def eventFilter(self, obj: QObject, event: QEvent):
        if event.type() == QEvent.MouseButtonRelease and isinstance(obj, QMenu):
            if obj.activeAction() and not obj.activeAction().menu():  # if the selected action does not have a submenu
                # eat the event, but trigger the function
                obj.activeAction().trigger()
                return True
        
        # standard event processing
        return QObject.eventFilter(self, obj, event)


class ScheduledValue:
    def __init__(self, interval_sec: float, start_value: float = 0, initial_previous_value: float = None):
        """
        This introduces a schedule for a value. This means, that a value is only updated,
        when the specified time interval since the last schedule update is exceeded.

        :param interval_sec: Frequency to update the value schedules in seconds.
        :param start_value: Specifies the start value, which is returned by the request method until the first schedule has been initiated.
        :param initial_previous_value: Specifies the value that will be returned by accessing property previous_value before first schedule has timeouted.
        """
        self.interval_sec = interval_sec
        self._last_schedule_update = perf_counter()
        self._value = start_value
        self._prev_val = start_value if initial_previous_value is None else initial_previous_value
        self._register_arr = np.array([self._value])
    
    @property
    def previous_value(self):
        return self._prev_val
    
    @property
    def schedule_timeout(self):
        """
        Check whether the value's schedule timeout has been reached. This means, that a new value will be returned upon request.

        :return: True if timout is reached, False otherwise.
        """
        return perf_counter() - self._last_schedule_update > self.interval_sec
    
    def register(self, value: float):
        """
        Registers a new value in the array.

        :param value: The new value to register.
        """
        self._register_arr = np.append(self._register_arr, [value])
    
    def request(self, value: float = None):
        """
        Returns the average of all registered values if the last value update lies
        sufficiently long in the past.

        :param value: Optional. This is a shorthand for registering and requesting a value at the same time. The given value will be registered before the request is issued.
        :return: The value of the current schedule.
        """
        if value is not None:
            self.register(value)
        
        if self.schedule_timeout:
            self._prev_val = self._value
            self._value = np.mean(self._register_arr)
            self._register_arr = np.array([])
            self._last_schedule_update = perf_counter()
        return self._value


class TimeseriesCurve(pg.PlotDataItem):
    def __init__(self, curve_definition: CurveDefinition):
        """
        A pyqtgraph PlotDataItem that scrolls the x axis when its data is being updated.

        :param curve_definition: A set of definition parameters.
        """
        super().__init__(name=curve_definition.label, pen=curve_definition.color)
        self._window_duration = curve_definition.window_sec
        self._visible_timeseries = np.array([[], []])
        self._recording_active = False
        self._recording_arr = np.array([[], []])  # Store the entire data received inside an extra array
        
    @property
    def recording(self):
        return self._recording_active
    
    @recording.setter
    def recording(self, val: bool):
        if val:
            self._recording_arr = np.array([[], []])  # Reset recording array
        self._recording_active = val
        
    @property
    def recording_array(self):
        return self._recording_arr
    
    def append_data(self, ts: float, value: float, *, display=True):
        """
        Updates the curve of the plot by appending a new value at the provided frame timestamp ts.
        The initially defined window size in seconds will be respected.

        :param ts: Timestamp of the value that indicates the time elapsed since the start of the application.
        :param value: Value to append to the curve.
        :param display: Only updates the display if set to True. Otherwise, just stores the data.
        """
        # Initialize timeseries if first time calling
        if not self._visible_timeseries.any():
            t = np.linspace(ts - self._window_duration, ts, round(self._window_duration * PARAMETERS.refresh_rate_hz))  # Initial time axis which is subject to change
            self._visible_timeseries = np.array([t, np.full(t.shape[0], np.nan)])  # Initial values np.nan
        
        # Extend recording array
        if self._recording_active:
            self._recording_arr = np.append(self._recording_arr, [[ts], [value]], axis=1)
        
        # Extend the timeseries data of the curve
        self._visible_timeseries = np.append(self._visible_timeseries, [[ts], [value]], axis=1)
        while self._visible_timeseries[0, -1] - self._visible_timeseries[0, 0] > self._window_duration:
            self._visible_timeseries = np.delete(self._visible_timeseries, 0, axis=1)
        if display:
            self.setData(self._visible_timeseries[0], self._visible_timeseries[1])


class MonitoringGraph(pg.PlotItem):
    """Class for defining monitoring graphs"""
    
    earliest_start: QTime = QTime.currentTime()
    
    def __init__(self, curves: list[CurveDefinition], title: str, xlabel: str = 'Time elapsed in s', ylabel: str = None, **kwargs):
        super().__init__(**kwargs)
        self.setTitle(title, color=THEME.foreground, size='18px')
        self.showGrid(y=True)
        self.addLegend(offset=(1, 1))
        self.setMouseEnabled(x=False)
        self.setLabel('left', ylabel, color=THEME.foreground)
        self.setLabel('bottom', xlabel)
        
        # Add data to plot
        self._graph_curves: dict[CurveDefinition, TimeseriesCurve] = {curve_def: TimeseriesCurve(curve_def) for curve_def in curves}
        for curve in self._graph_curves.values():
            self.addItem(curve)
        
        self.timer = QTimer()
        # noinspection PyUnresolvedReferences
        self.timer.timeout.connect(self._update)
        
    @property
    def title(self):
        return self.titleLabel.text
    
    @title.setter
    def title(self, text: str):
        self.setTitle(text)
        
    @property
    def curve_dict(self):
        return self._graph_curves
    
    def _update(self):
        for curve_def, data in self._graph_curves.items():
            data.append_data(MonitoringGraph.earliest_start.msecsTo(QTime.currentTime()) / 1000, curve_def.get_func())
    
    def start(self, interval_hz: int = PARAMETERS.refresh_rate_hz):
        if self._graph_curves:
            current_time = QTime.currentTime()
            if MonitoringGraph.earliest_start > current_time:
                MonitoringGraph.earliest_start = current_time
            self.timer.start(round(1000 / interval_hz))


class GraphDict(UserDict):
    def __init__(self, grpahics_layout: pg.GraphicsLayout, dictionary=None, /, **kwargs):
        super().__init__(dictionary, **kwargs)
        self._layout = grpahics_layout
    
    def __setitem__(self, key: int, item: MonitoringGraph):
        assert isinstance(key, int), TypeError("Keys have to be strings!")
        assert isinstance(item, MonitoringGraph), TypeError("Items have to be instances of MonitoringGraph!")
        
        # Remove old graph
        if key in self.keys():
            self._remove_graph_from_layout(key)
        
        super().__setitem__(key, item)
        
        # Insert item to layout
        existing_item = self._layout.getItem(row=key, col=1)
        self._layout.addItem(item, row=key, col=1)  # Place item
        while existing_item is not None:
            existing_item = self._layout.getItem(row=key + 1, col=1)  # Copy item that occupies the slot for existing_item
            self._layout.addItem(existing_item, row=key + 1, col=1)  # Place existing_item
    
    def __delitem__(self, key: int):
        self._remove_graph_from_layout(key)
        super().__delitem__(key)
    
    def _remove_graph_from_layout(self, key: int):
        self._layout.removeItem(self.data[key])
