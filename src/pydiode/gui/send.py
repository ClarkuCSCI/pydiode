import os
from pathlib import Path
import subprocess
import sys
from tkinter.filedialog import askopenfilenames

from pydiode.gui.common import check_subprocesses, SLEEP, TEST_MESSAGE

# Number of bits in a byte
BYTE = 8
# pydiode's default settings. Eventually, these will be configurable.
MAX_BITRATE = 1000000000
REDUNDANCY = 2
# Extra time needed for transfers, considering more than just bitrate and
# redundancy. Determined experimentally with a 1 Gbit transfer.
OVERHEAD = 1.085
# Increment progress bars every 25 milliseconds, for smooth animation.
INCREMENT_INTERVAL = 25
# Arrays of tuples, each containing a subprocess's name and its popen object
SEND_PROCESSES = []
SEND_TEST_PROCESSES = []


def add_source_files(sources_var, sources_list):
    """
    Ask the user to select files to transfer, then updated the Listbox.

    :param sources_var: A StringVar representing the list of sources, which is
                        linked to the Listbox
    :param sources_list: A list of the source files currently in the Listbox
    """
    # If files have been added, the dialogue will remember the directory.
    # If no files have been added, start in the Downloads folder.
    initialdir = None if sources_list else Path("~/Downloads").expanduser()
    selected_sources = askopenfilenames(initialdir=initialdir)
    new_sources = set(selected_sources) - set(sources_list)
    if new_sources:
        sources_list.extend(sorted(new_sources))
        sources_var.set(sources_list)


def remove_source_files(sources_var, sources_list, sources_box):
    """
    Remove the selected source files from the Listbox.

    :param sources_var: A StringVar representing the list of sources, which is
                        linked to the Listbox
    :param sources_list: A list of the source files currently in the Listbox
    :param sources_box: A Listbox showing the source files
    """
    source_indices = sources_box.curselection()
    # Remove in reverse order, to avoid removing the wrong elements
    for i in sorted(source_indices, reverse=True):
        sources_list.pop(i)
    sources_var.set(sources_list)


def update_tx_btn(tx_btn, sources_list):
    """
    Enable or disable the Start Sending button based on whether there are any
    source files to send.

    :param tx_btn: The Start Sending button
    :param sources_list: The files in the file transfer queue
    """
    if sources_list:
        tx_btn.state(["!disabled"])
    else:
        tx_btn.state(["disabled"])


def get_increment_size(sources_list, progress_bar):
    """
    By how much should we increment the progress bar?

    :param sources_list: A list of filenames to send through the data diode
    :param progress_bar: Progress bar widget
    """
    # Sum of file sizes (bytes) for time estimate
    size = 0
    for source in sources_list:
        size += os.path.getsize(source)
    # How much time will the transfer take, in milliseconds?
    est_time = size * BYTE / MAX_BITRATE * REDUNDANCY * OVERHEAD * 1000
    # By how much do we increment each time?
    n_increments = est_time / INCREMENT_INTERVAL
    return progress_bar["maximum"] / n_increments


def send_or_cancel(
    root,
    sources_list,
    send_ip,
    receive_ip,
    port,
    button,
    progress_bar,
    cancelled,
):
    """
    Send the listed files through the data diode. If we are already sending,
    calling this method again cancels receiving.

    :param sources_list: A list of filenames to send through the data diode
    :param send_ip: Send data from this IP
    :param receive_ip: Send data to this IP
    :param port: Send data using this port
    :param button: Start/Cancel button widget
    :param progress_bar: Progress bar widget
    :param cancelled: Boolean variable indicating cancellation request
    """
    if button["text"] == "Cancel Sending":
        cancelled.set(True)
    else:
        tar = subprocess.Popen(
            sys.argv + ["tar", "create"] + sources_list,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        pydiode = subprocess.Popen(
            sys.argv
            + [
                "pydiode",
                "send",
                receive_ip,
                send_ip,
                "--port",
                port,
                "--max-bitrate",
                str(MAX_BITRATE),
                "--redundancy",
                str(REDUNDANCY),
            ],
            stdin=tar.stdout,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        SEND_PROCESSES.extend([("tar", tar), ("pydiode", pydiode)])
        root.after(
            SLEEP,
            lambda: check_subprocesses(root, cancelled, SEND_PROCESSES),
        )

        increment_size = get_increment_size(sources_list, progress_bar)

        def animate():
            # If either subprocess hasn't exited, keep animating
            if (tar.poll() is None) or (pydiode.poll() is None):
                progress_bar["value"] += increment_size
                # Ensure the value doesn't exceed the max, or the bar will loop
                if progress_bar["value"] > progress_bar["maximum"]:
                    progress_bar["value"] = progress_bar["maximum"]
                root.after(INCREMENT_INTERVAL, animate)
            # After both subprocesses exit, allow more transfers
            else:
                button["text"] = "Start Sending"
                # If either subprocess had a non-zero exit code
                if tar.poll() or pydiode.poll():
                    progress_bar["value"] = 0
                else:
                    progress_bar["value"] = progress_bar["maximum"]

        button["text"] = "Cancel Sending"
        progress_bar["value"] = 0
        root.after(INCREMENT_INTERVAL, animate)


def send_test(
    root,
    send_ip,
    receive_ip,
    port,
    cancelled,
):
    """
    Send a test message. Since the test message is short, there is no way to
    cancel it. For simplicity, we reuse the send tab's cancelled variable.
    """
    pydiode = subprocess.Popen(
        sys.argv
        + [
            "pydiode",
            "send",
            receive_ip,
            send_ip,
            "--port",
            port,
            "--max-bitrate",
            str(MAX_BITRATE),
            "--redundancy",
            str(REDUNDANCY),
        ],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    pydiode.stdin.write(TEST_MESSAGE)
    pydiode.stdin.close()
    SEND_TEST_PROCESSES.extend([("pydiode", pydiode)])
    root.after(
        SLEEP,
        lambda: check_subprocesses(root, cancelled, SEND_TEST_PROCESSES),
    )
