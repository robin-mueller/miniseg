# MiniSeg Project
Source code for the MiniSeg Real-Time Systems course project of Lund University. 
It enables a the MiniSeg robot to balance itself and to follow positional setpoints in a single direction.
Additionally, a graphical user interface to communicate with the robot and to tune the controller is provided. The communication takes place via Bluetooth.

# Setup
The graphical user interface is built using the Qt framework and its python bindings. The python environment can be 
built using Python 3.10 ([download](https://www.python.org/ftp/python/3.10.10/python-3.10.10-amd64.exe)) by 
typing:
```powershell
cd gui  # Source directory should be miniseg/gui!
<Python install dir>\python.exe -m venv venv
venv\Scripts\pip.exe install -r requirements.txt
```

Before running `main.py` some resources must be generated by running
```powershell
cd gui
resources\generate.ps1
```
