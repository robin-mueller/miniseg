import pandas as pd
import configuration as config

from pathlib import Path
from plot import TimeSeriesPlot

FIGURE_EXPORT_DIR = Path(__file__).parent / "figure"


def main():
    record_file = config.DEFAULT_RECORDING_DIR / "balance.csv"
    df = pd.read_csv(record_file, header=[0, 1, 2], index_col=0)
    df.sort_index(axis=1, inplace=True)

    data = {
        "Position in mm": [
            ("Measurement", df["Graph 1", "observer/position/z_mm"]),
            ("Setpoint", df["Graph 1", "pos_setpoint_mm"]),
        ],
        "Tilt angle in rad": [
            ("Measurement", df["Graph 2", "observer/tilt/angle_rad"]),
            ("Setpoint", df["Graph 2", "ff_model/tilt/angle_rad"]),
        ]
    }

    plot = TimeSeriesPlot("Balance", **data)
    # plot.figure.show()

    if not FIGURE_EXPORT_DIR.exists():
        FIGURE_EXPORT_DIR.mkdir()
    plot.figure.savefig(FIGURE_EXPORT_DIR / (record_file.stem + ".pdf"))


if __name__ == '__main__':
    main()
