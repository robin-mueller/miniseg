# This scripts generates all necessary resources for the gui
# and the arduino microcontroller application compilation

Set-Location $PSScriptRoot

# Generate C++ communication interface code
controller\src\interface\generate.ps1
Set-Location $PSScriptRoot

# Generate gui resources
gui\resources\generate.ps1
Set-Location $PSScriptRoot
