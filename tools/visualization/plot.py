import pandas as pd

from . import plt


class TimeSeriesPlot:
    def __init__(self, title: str = None, **data: list[tuple[str, pd.DataFrame]]):
        self._fig, self._ax = plt.subplots(len(data), 1, sharex='all')
        for index, (label, timeseries) in enumerate(data.items()):
            for name, df in timeseries:
                self._ax[index].plot(df.iloc[:, 0] - df.iloc[:, 0].min(), df.iloc[:, 1], label=name)
            self._ax[index].set_ylabel(label)
            self._ax[index].grid(True)

            # Shrink xaxis by 20 % and fit legend beside
            box = self._ax[index].get_position()
            self._ax[index].set_position([box.x0, box.y0, box.width * 0.8, box.height])
            self._ax[index].legend(loc='center left', bbox_to_anchor=(1, 0.5))

        self._fig.supxlabel("Time in seconds")
        if title:
            self._fig.suptitle(title)

    @property
    def figure(self) -> plt.Figure:
        return self._fig
