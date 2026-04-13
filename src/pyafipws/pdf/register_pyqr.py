import os
import sys

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
os.environ['PYTHONPATH'] = os.path.abspath(os.path.dirname(__file__))
import pyqr
import win32com.server.register

win32com.server.register.UseCommandLine(pyqr.PyQR)



