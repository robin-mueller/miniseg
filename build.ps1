# This scripts generates all necessary resources for the gui
# and the arduino microcontroller application compilation

Set-Location $PSScriptRoot

# Embed interface definitions as a resource for arduino compilation
$InterfaceJsonContent = Get-Content -Path ".\interface.json"
$InterfaceHPath = ".\controller\interface.h"
Set-Content -NoNewline -Path $InterfaceHPath -Value "#ifndef INTERFACE_H
#define INTERFACE_H

const char interface_def[] = `"$([string]::Concat($InterfaceJsonContent.Trim().Replace(' ', '').Replace('"', '\"')) )`"

#endif
"

# Generate gui resources
Set-Location gui
resources\generate.ps1
Set-Location ..
