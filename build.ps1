# This scripts generates all necessary resources for the gui
# and the arduino microcontroller application compilation

Set-Location $PSScriptRoot

# Embed interface definition information as a resource for arduino compilation
$JSON_OBJECT_SIZE = 8  # Json object size on an AVR microchip architecture as used in Arduino MEGA
function CalculateJsonDocSize($arr)
{
    $nestedSize = 0
    $members = 0
    foreach ($item in $arr)
    {
        if ($item.GetType().Name -eq "String")
        {
            $members++
        }
        elseif ($item.GetType().Name -eq "PSCustomObject")
        {
            foreach ($property in $item.psobject.Properties)
            {
                $members++
                $nestedSize += CalculateJsonDocSize $property.Value
            }
        }
    }
    return $members * $JSON_OBJECT_SIZE + $nestedSize
}
$interfaceJsonContentString = Get-Content -Path ".\interface.json"
$interfaceJsonObject = $interfaceJsonContentString | ConvertFrom-Json
$interfaceHPath = ".\controller\interface.h"
Set-Content -NoNewline -Path $interfaceHPath -Value "#ifndef INTERFACE_H
#define INTERFACE_H

#define JSON_DOC_SIZE_RX $(CalculateJsonDocSize $interfaceJsonObject.to_device)
#define JSON_DOC_SIZE_TX $(CalculateJsonDocSize $interfaceJsonObject.from_device)

char interface_json[] = `"$([string]::Concat($interfaceJsonContentString.Trim().Replace(' ', '').Replace('"', '\"')) )`";

#endif
"

# Generate gui resources
Set-Location gui
resources\generate.ps1
Set-Location ..
