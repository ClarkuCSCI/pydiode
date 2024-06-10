import json
import subprocess
import sys


def activate():
    """
    Check whether the GUI is already running. If so, activate the existing
    window. Uses the window-calls@domandoman.xyz Gnome extension.

    :returns: A boolean indicating whether an already running instance was
              activated
    """
    base_cmd = [
        "gdbus",
        "call",
        "--session",
        "--dest",
        "org.gnome.Shell",
        "--object-path",
        "/org/gnome/Shell/Extensions/Windows",
        "--method",
    ]
    completed = subprocess.run(
        base_cmd + ["org.gnome.Shell.Extensions.Windows.List"],
        stdout=subprocess.PIPE,
    )
    # Trim non-JSON characters from the front and back
    windows = json.loads(completed.stdout[2:-4])
    windows = list(filter(lambda w: w["wm_class"] == "Diodetransfer", windows))
    if windows:
        subprocess.run(
            base_cmd
            + [
                "org.gnome.Shell.Extensions.Windows.Activate",
                str(windows[0]["id"]),
            ],
        )
        return True
    else:
        return False
