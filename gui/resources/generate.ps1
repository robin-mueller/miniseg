# This script loads Qt resources and ui files to provide them for usage in PySide6

Set-Location $PSScriptRoot/..

Write-Output "Running resource generation ..."

# Load Qt resources
venv/Scripts/pyside6-rcc.exe resources.qrc -o resources/rc_resources.py

# Load ui files
venv/Scripts/pyside6-uic.exe include/ui/main_window.ui -o resources/main_window_ui.py
venv/Scripts/pyside6-uic.exe include/ui/monitoring_window.ui -o resources/monitoring_window_ui.py

Write-Output "Resource generation finished!"
