import numpy as np
import seaborn as sns
import pyqtgraph as pg
import configuration as config

from functools import partial
from typing import Callable, overload
from dataclasses import dataclass
from collections import UserDict
from PySide6.QtCore import QTimer, Signal, QObject, SignalInstance
from PySide6.QtGui import QFont
from .communication.interface import StampedData, DataInterface, DataInterfaceDefinition


@dataclass(frozen=True, eq=True)
class CurveDefinition:
    """
    Class for creating monitoring curve definitions.

    - label: Name of the curve.
    - get_func: Getter function of the respective value.
    """
    label: str
    get_data: Callable[[], StampedData]  # Has to return a tuple of value and timestamp in this order


@dataclass
class ColouredCurve:
    """
    Helper class to define an initial color together with the curve.

    - definition: CurveDefinition instance.
    - color: Pen color of the curve represented by one of b, g, r, c, m, y, k, w or other types specified here: https://pyqtgraph.readthedocs.io/en/latest/user_guide/style.html#line-fill-and-color.
             If None, color is chosen automatically.
    """
    definition: CurveDefinition
    color: any = None


class CurveLibrary:
    _DEFS: dict[str, CurveDefinition] = {}

    @classmethod
    def colorize(cls, curves: list[str] | list[CurveDefinition]):
        color_palette = sns.color_palette('husl', len(curves)).as_hex()
        return [ColouredCurve(curve, color_palette[index]) if isinstance(curve, CurveDefinition) else cls.definitions(curve, color_palette[index]) for index, curve in enumerate(curves)]

    @classmethod
    def add_definition(cls, key: str, curve_definition: CurveDefinition):
        cls._DEFS[key] = curve_definition

    @classmethod
    def parse_data_interface(cls, interface: DataInterface):
        def add_data_interface_curves(accessor: list[str], definition: DataInterfaceDefinition):
            for key, val in definition.items():
                _accessor = accessor + [key]
                if val in [float, int, bool]:
                    cls.add_definition('/'.join(_accessor).upper(), CurveDefinition('/'.join(_accessor), partial(interface.get, tuple(_accessor))))
                elif isinstance(val, DataInterfaceDefinition):
                    add_data_interface_curves(_accessor, val)

        add_data_interface_curves([], interface.definition)

    @classmethod
    @overload
    def definitions(cls) -> dict[str, CurveDefinition]:
        ...

    @classmethod
    @overload
    def definitions(cls, key: str) -> CurveDefinition:
        ...

    @classmethod
    @overload
    def definitions(cls, key: str, color: any) -> ColouredCurve:
        ...

    @classmethod
    def definitions(cls, key: str = None, color: any = None):
        if key is None:
            return cls._DEFS
        if color is None:
            return cls._DEFS[key]
        return ColouredCurve(cls._DEFS[key], color)


class ScheduledValue(QObject):
    updated = Signal(float)

    def __init__(self, getter: Callable[[], float], interval_ms: float):
        """
        This introduces a schedule for a value. This means, that a value is only updated,
        when the specified time interval since the last schedule update is exceeded.

        :param getter: Getter function for the associated value.
        :param interval_ms: Rate to update the value in milliseconds. The updated signal will be emitted at that rate.
        """
        super().__init__()
        self._register_arr = np.array([])
        self._register_timer = QTimer()
        self._register_timer.timeout.connect(lambda: self._register(getter()))
        self._register_timer.setInterval(round(1000 / config.PARAMETERS.plot_update_rate_ms))
        self._publish_value_timer = QTimer()
        self._publish_value_timer.timeout.connect(lambda: self.updated.emit(self._request()))
        self._publish_value_timer.setInterval(interval_ms)

    def start(self):
        self._register_timer.start()
        self._publish_value_timer.start()

    def stop(self):
        self._register_timer.stop()
        self._publish_value_timer.stop()

    def _register(self, value: float):
        """
        Registers a new value in the array.

        :param value: The new value to register.
        """
        self._register_arr = np.append(self._register_arr, [value])

    def _request(self):
        """
        Returns the average of all registered values.
        """
        value = np.mean(self._register_arr)
        self._register_arr = np.array([])
        return value


class TimeseriesCurve(pg.PlotDataItem):
    def __init__(self, label: str, color: any, window_size_sec: float):
        """
        A pyqtgraph PlotDataItem that scrolls the x axis when its data is being updated.

        :param label: The label of the curve.
        :param color: The color of the curve. Accepts everything that pg.mkPen accepts for color keyword.
        :param window_size_sec: The length of the plotted curve in seconds.
        """
        super().__init__(name=label, pen=pg.mkPen(color=color, width=1))
        self._window_duration = window_size_sec
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

    def append_data(self, value: float | None, ts: float | None):
        """
        Updates the curve of the plot by appending a new value at the provided frame timestamp ts.
        The initially defined window size in seconds will be respected.

        :param value: Value to append to the curve.
        :param ts: Timestamp of the value that indicates the time elapsed since the start of the application.
        """
        if ts is not None:
            # Initialize timeseries if first time calling
            _value = np.nan if value is None else value
            if not self._visible_timeseries.any():
                t = np.linspace(ts - self._window_duration, ts, round(self._window_duration * config.PARAMETERS.plot_update_rate_ms))  # Initial time axis which is subject to change
                self._visible_timeseries = np.array([t, np.full(t.shape[0], np.nan)])  # Initial values np.nan

            # Extend recording array
            if self._recording_active:
                self._recording_arr = np.append(self._recording_arr, [[ts], [_value]], axis=1)

            # Extend the timeseries data of the curve
            self._visible_timeseries = np.append(self._visible_timeseries, [[ts], [_value]], axis=1)
            while self._visible_timeseries[0, -1] - self._visible_timeseries[0, 0] > self._window_duration:
                self._visible_timeseries = np.delete(self._visible_timeseries, 0, axis=1)
            self.setData(self._visible_timeseries[0], self._visible_timeseries[1])


class MonitoringGraph(pg.PlotItem):
    """
    Class for defining real-time monitoring graphs.
    """
    NUMBER_FONT = QFont(config.THEME.number_font_family)

    def __init__(self, curves: list[ColouredCurve] = None,
                 *,
                 start_signal: SignalInstance = None, stop_signal: SignalInstance = None,
                 title: str = None, xlabel: str = 'Time elapsed in s', ylabel: str = None,
                 interval_ms: int = config.PARAMETERS.plot_update_rate_ms,
                 window_size_sec: float = 30,
                 **kwargs):

        super().__init__(**kwargs)

        self.title = title
        self.showGrid(y=True)
        self.addLegend(offset=(1, 1))
        self.setMouseEnabled(x=False)
        self.setLabel('left', ylabel, color=config.THEME.foreground)
        self.setLabel('bottom', xlabel)
        self.getAxis('left').setStyle(tickFont=self.NUMBER_FONT)
        self.getAxis('bottom').setStyle(tickFont=self.NUMBER_FONT)
        self._window_size = window_size_sec

        # Add data to plot
        self._curves_dict: dict[CurveDefinition, TimeseriesCurve] = {}
        if curves:
            for curve in curves:
                self.add_curve(curve)

        self._timer = QTimer()
        self._timer.setInterval(interval_ms)
        self._timer.timeout.connect(self._update)
        if start_signal is not None:
            start_signal.connect(self._timer.start)
        if stop_signal is not None:
            stop_signal.connect(self._timer.stop)

    def start_updating(self):
        self._timer.start()

    def stop_updating(self):
        self._timer.stop()

    def add_curve(self, curve: ColouredCurve):
        if not isinstance(curve, ColouredCurve):
            raise TypeError(f"Argument curve must be an instance of {ColouredCurve} not {type(curve)}.")
        _curve = TimeseriesCurve(curve.definition.label, curve.color, self._window_size)
        self._curves_dict[curve.definition] = _curve
        self.addItem(_curve)

    def remove_curve(self, curve_definition: CurveDefinition):
        self.removeItem(self._curves_dict[curve_definition])
        del self._curves_dict[curve_definition]

    @property
    def title(self):
        return self.titleLabel.text

    @title.setter
    def title(self, text: str):
        self.setTitle(text, color=config.THEME.foreground, size='18px')

    @property
    def curves_dict(self):
        return self._curves_dict

    def _update(self):
        for curve_def, time_curve in self._curves_dict.items():
            data = curve_def.get_data()
            time_curve.append_data(data.value, data.timestamp)


class GraphDict(UserDict):
    def __init__(self, graphics_layout_widget: pg.GraphicsLayoutWidget, dictionary=None, /, **kwargs):
        super().__init__(dictionary, **kwargs)
        self._layout = graphics_layout_widget.ci

    def __setitem__(self, key: int, item: MonitoringGraph):
        assert isinstance(key, int), TypeError("Keys have to be strings!")
        assert isinstance(item, MonitoringGraph), TypeError("Items have to be instances of MonitoringGraph!")

        # Remove old graph
        if key in self.keys():
            self._remove_graph_from_layout(key)

        # Assign item to dict
        super().__setitem__(key, item)

        # Add new graph to position of old graph
        self._layout.addItem(item, row=key, col=1)

    def __delitem__(self, key: int):
        self._remove_graph_from_layout(key)
        super().__delitem__(key)

    def _remove_graph_from_layout(self, key: int):
        self._layout.removeItem(self.data[key])
