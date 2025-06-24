import os
from pathlib import Path
import subprocess
import sys
from tkinter.filedialog import askopenfilenames

from pydiode.gui.common import check_subprocesses, ProcessPipeline, SLEEP

# Number of bits in a byte
BYTE = 8
# pydiode's default setting. We might make this configurable.
REDUNDANCY = 2
# Extra time needed for transfers, considering more than just bitrate and
# redundancy. Determined experimentally with a 1 Gbit transfer.
OVERHEAD = 1.085
# Increment progress bars every 25 milliseconds, for smooth animation.
INCREMENT_INTERVAL = 25
# Test message
TEST_MESSAGE = b"Testing pydiode"
# Information about our subprocesses
SEND_PIPELINE = ProcessPipeline()
SEND_TEST_PIPELINE = ProcessPipeline()


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


def get_increment_size(sources_list, progress_bar, bitrate_int):
    """
    By how much should we increment the progress bar?

    :param sources_list: A list of filenames to send through the data diode
    :param progress_bar: Progress bar widget
    :param bitrate_int: Maximum number of bits transferred per second
    """
    # Sum of file sizes (bytes) for time estimate
    size = 0
    for source in sources_list:
        size += os.path.getsize(source)
    # How much time will the transfer take, in milliseconds?
    est_time = size * BYTE / bitrate_int * REDUNDANCY * OVERHEAD * 1000
    # By how much do we increment each time?
    n_increments = est_time / INCREMENT_INTERVAL
    return progress_bar["maximum"] / n_increments


def bitrate_str_to_int(bitrate_str):
    """
    Convert human-readable metric bitrate to number of bits per second.

    :param bitrate_str: Human-readable metric bitrate (e.g., "100 Mbit/s")
    :returns: Number of bits per second (e.g., 100000000)
    """
    suffix_mult = {" Mbit/s": 1_000_000, " Gbit/s": 1_000_000_000}
    for suffix, mult in suffix_mult.items():
        if bitrate_str.endswith(suffix):
            return int(bitrate_str.replace(suffix, "")) * mult
    raise ValueError(f"Unknown bitrate format: {bitrate_str}")


def send_or_cancel(
    root,
    sources_list,
    send_ip,
    receive_ip,
    port,
    key_id,
    bitrate_str,
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
    :param key_id: Key ID of the PGP key used to encrypt pydiode's STDIN
    :param bitrate_str: Maximum number of bits transferred per second
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
        SEND_PIPELINE.append("tar", tar)

        if key_id:
            gpg = subprocess.Popen(
                [
                    "gpg",
                    "--batch",
                    "--encrypt",
                    "--trust-model",
                    "always",
                    "--recipient",
                    key_id,
                ],
                stdin=tar.stdout,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            SEND_PIPELINE.append("gpg", gpg)

        bitrate_int = bitrate_str_to_int(bitrate_str)
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
                str(bitrate_int),
                "--redundancy",
                str(REDUNDANCY),
            ],
            stdin=gpg.stdout if key_id else tar.stdout,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        SEND_PIPELINE.append("pydiode", pydiode)

        check_subprocesses(root, cancelled, SEND_PIPELINE)

        increment_size = get_increment_size(
            sources_list, progress_bar, bitrate_int
        )

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
        animate()


def send_test(
    root,
    send_ip,
    receive_ip,
    port,
    bitrate_str,
    cancelled,
):
    """
    Send a test message. Since the test message is short, there is no way to
    cancel it.
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
            str(bitrate_str_to_int(bitrate_str)),
            "--redundancy",
            str(REDUNDANCY),
        ],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    pydiode.stdin.write(TEST_MESSAGE)
    pydiode.stdin.close()
    SEND_TEST_PIPELINE.append("pydiode", pydiode)
    check_subprocesses(root, cancelled, SEND_TEST_PIPELINE)
