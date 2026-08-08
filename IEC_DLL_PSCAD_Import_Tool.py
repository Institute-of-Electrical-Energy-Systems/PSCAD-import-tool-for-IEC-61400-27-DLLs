"""Entry point for the IEC 61400-27 DLL -> PSCAD import tool.

Launching this script opens the Tkinter GUI (``Application``) that lets
a user pick an IEC 61400-27 (Ext-SimEnv) DLL and generate a matching
Fortran wrapper plus PSCAD component/project for it.
"""

import os
import sys

from Application import Application

if __name__ == '__main__':

    # Resolve the directory this tool runs from, whether launched as a
    # plain script or as a frozen executable (e.g. PyInstaller), and make
    # it the current working directory so relative paths (e.g. the
    # Fortran template file) resolve correctly regardless of the
    # directory the tool was launched from.
    if getattr(sys, 'frozen', False):
        application_path = os.path.dirname(sys.executable)
    elif __file__:
        application_path = os.path.dirname(__file__)
    else:
        raise RuntimeError

    os.chdir(application_path)

    # Application inherits from the class tk.Tk (tkinter)
    num_version = '1.0'
    app = Application(num_version)
    app.start()
    app.title(
        "PSCAD Import Tool (IEC 61400-27 DLL format) FAU Erlangen-Nürnberg v"
        + num_version)
    app.mainloop()  # display window
