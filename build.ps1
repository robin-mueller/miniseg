# This scripts generates all necessary resources for the gui
# and the arduino microcontroller application compilation

Set-Location $PSScriptRoot

# Embed interface definitions as a resource for arduino compilation
$InterfaceJsonContent = Get-Content -Path ".\interface.json" -Raw
$InterfaceJsonContent = $InterfaceJsonContent | ForEach-Object {}
$InterfaceHPath = ".\controller\interface.h"
Set-Content -Path $InterfaceHPath -Value "#ifndef INTERFACE_H
#define INTERFACE_H

const char interface_def[] = `"$( $InterfaceJsonContent )`"

#endif
"

