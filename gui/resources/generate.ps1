# This script loads Qt resources and ui files to provide them for usage in PySide6

$CONDA_INSTALL_DIR = "C:\Users\robin\mambaforge"  # Absolute path to the conda activation script of your conda installation
$ENV_NAME = "miniseg"  # Name of the conda environment to use for python interpretation

# Start conda environment
& "$($CONDA_INSTALL_DIR)\shell\condabin\conda-hook.ps1"
conda activate $($ENV_NAME)

# Load Qt resources
pyside6-rcc resources.qrc -o resources/rc_resources.py

# Load ui files
pyside6-uic include/ui/main_window.ui -o resources/main_window_ui.py
pyside6-uic include/ui/monitoring_window.ui -o resources/monitoring_window_ui.py
