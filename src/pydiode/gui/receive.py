import subprocess
import sys
from tkinter.filedialog import askdirectory

from pydiode.gui.common import check_subprocesses, SLEEP

# An array of tuples, each containing a subprocess's name and its popen object
RECEIVE_PROCESSES = []


def set_target_directory(target):
    """
    Ask the user for a directory, then update the target text field to display
    this directory.

    :param target: A text field depicting the target
    """
    target_directory = askdirectory(initialdir=target.get())
    if target_directory:
        target.set(target_directory)


def receive_files(
    root, target_dir, receive_ip, port, button, progress_bar, cancelled
):
    """
    Receive files from the data diode. If we are already receiving, calling
    this method again cancels receiving.

    :param target_dir: Where to save the files received
    :param receive_ip: Receive data using this IP
    :param port: Receive data using this port
    :param button: Start/Cancel button widget
    :param progress_bar: Progress bar widget
    :param cancelled: Boolean variable indicating cancellation request
    """
    if button["text"] == "Cancel Receiving":
        cancelled.set(True)
    else:
        pydiode = subprocess.Popen(
            sys.argv + ["pydiode", "receive", receive_ip, "--port", port],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        tar = subprocess.Popen(
            sys.argv + ["tar", "extract", target_dir],
            stdin=pydiode.stdout,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        RECEIVE_PROCESSES.extend([("pydiode", pydiode), ("tar", tar)])
        root.after(
            SLEEP,
            lambda: check_subprocesses(root, cancelled, RECEIVE_PROCESSES),
        )

        def animate():
            # An "indeterminate" progress bar will animate until its value is 0
            progress_bar["value"] += 5
            # If either subprocess hasn't exited, keep animating
            if (tar.poll() is None) or (pydiode.poll() is None):
                root.after(SLEEP, animate)
            # When tar exits, prepare to receive again
            else:
                # Allow receiving more files
                button["text"] = "Start Receiving"
                # Empty the progress bar by switching modes
                progress_bar["value"] = 0
                progress_bar["mode"] = "determinate"

        button["text"] = "Cancel Receiving"
        progress_bar["mode"] = "indeterminate"
        root.after(SLEEP, animate)
