import subprocess
import sys
from tkinter.filedialog import askdirectory

from pydiode.gui.common import check_subprocesses, SLEEP

# Arrays of tuples, each containing a subprocess's name and its popen object
RECEIVE_PROCESSES = []
RECEIVE_TEST_PROCESSES = []


def set_target_directory(target):
    """
    Ask the user for a directory, then update the target text field to display
    this directory.

    :param target: A text field depicting the target
    """
    target_directory = askdirectory(initialdir=target.get())
    if target_directory:
        target.set(target_directory)


def receive_or_cancel(
    root,
    target_dir,
    receive_ip,
    port,
    button,
    progress_bar,
    cancelled,
    receive_repeatedly,
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
    :param receive_repeatedly: Boolean variable indicating whether to receive
                               again after the subprocesses exit.
    """

    if button["text"] == "Cancel Receiving":
        cancelled.set(True)
    else:
        receive_files(
            root,
            target_dir,
            receive_ip,
            port,
            button,
            progress_bar,
            cancelled,
            receive_repeatedly,
        )


def receive_files(
    root,
    target_dir,
    receive_ip,
    port,
    button,
    progress_bar,
    cancelled,
    receive_repeatedly,
):
    def repeat():
        if receive_repeatedly.get():
            # Receive another batch of files
            receive_files(
                root,
                target_dir,
                receive_ip,
                port,
                button,
                progress_bar,
                cancelled,
                receive_repeatedly,
            )

    def animate():
        # An "indeterminate" progress bar will animate until its value is 0
        progress_bar["value"] += 5
        # If either subprocess hasn't exited, keep animating
        if (tar.poll() is None) or (pydiode.poll() is None):
            button["text"] = "Cancel Receiving"
            progress_bar["mode"] = "indeterminate"
            root.after(SLEEP, animate)
        # When tar exits, prepare to receive again
        else:
            # Allow receiving more files
            button["text"] = "Start Receiving"
            # Empty the progress bar by switching modes
            progress_bar["value"] = 0
            progress_bar["mode"] = "determinate"

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
        lambda: check_subprocesses(
            root, cancelled, RECEIVE_PROCESSES, on_exit=repeat
        ),
    )
    root.after(SLEEP, animate)


def receive_test(
    root,
    receive_ip,
    port,
    button,
    cancelled,
):
    """
    Start receiving the test message, or cancel receiving the test message.
    """

    def update_button():
        # If pydiode hasn't exited
        if pydiode.poll() is None:
            button["text"] = "Cancel Receiving Test"
            root.after(SLEEP, update_button)
        else:
            button["text"] = "Test Receiving"

    if button["text"] == "Cancel Receiving Test":
        cancelled.set(True)
    else:
        # pydiode will exit with a non-zero exit code if the received data's
        # digest doesn't match the EOF packet's digest. Thus, we can ignore
        # stdout.
        pydiode = subprocess.Popen(
            sys.argv + ["pydiode", "receive", receive_ip, "--port", port],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )
        RECEIVE_TEST_PROCESSES.extend([("pydiode", pydiode)])

        root.after(
            SLEEP,
            lambda: check_subprocesses(root, cancelled, RECEIVE_TEST_PROCESSES),
        )
        root.after(SLEEP, update_button)
