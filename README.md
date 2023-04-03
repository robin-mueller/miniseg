# MiniSeg Project
Source code for the MiniSeg Real-Time Systems course project of Lund University. 
It enables a the MiniSeg robot to balance itself and to follow positional setpoints in a single direction.
Additionally, a graphical user interface to communicate with the robot and to tune the controller is provided. The communication takes place via Bluetooth.

# Setup
The graphical user interface is built using the Qt framework and its python bindings. The python environment can be built using [mamba](https://mamba.readthedocs.io/en/latest/installation.html), 
a Python-based CLI conceived as a drop-in replacement for conda, offering higher speed and more reliable environment solutions by typing:
```
mamba env create -f environment.yml
```
