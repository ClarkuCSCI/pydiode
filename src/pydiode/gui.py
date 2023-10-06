import configparser
import os
import pathlib
import subprocess
import sys
from tkinter import BooleanVar, IntVar, Listbox, StringVar, Tk, ttk
from tkinter.filedialog import askdirectory, askopenfilenames
from tkinter.messagebox import showerror

import pydiode.pydiode
import pydiode.tar

# Save the configuration file in the user's home folder
CONFIG = pathlib.Path().home() / ".pydiode.ini"
# Check subprocesses every SLEEP milliseconds
SLEEP = 250
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


def set_target_directory(target):
    """
    Ask the user for a directory, then update the target text field to display
    this directory.

    :param target: A text field depicting the target
    """
    target_directory = askdirectory(initialdir=target.get())
    if target_directory:
        target.set(target_directory)


def add_source_files(sources_var, sources_list):
    """
    Ask the user to select files to transfer, then updated the Listbox.

    :param sources_var: A StringVar representing the list of sources, which is
                        linked to the Listbox
    :param sources_list: A list of the source files currently in the Listbox
    """
    # If files have been added, the dialogue will remember the directory.
    # If no files have been added, start at the current working directory.
    initialdir = None if sources_list else os.getcwd()
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


def get_process_error(name, popen):
    """
    Get a message describing a subprocess that exited irregularly.

    :param name: The name of the process
    :param popen: The subprocess.Popen object of a terminated process
    :returns: A string describing the return code and stderr
    """
    trimmed_stderr = popen.stderr.read().decode("utf-8").strip()
    error_msg = f'"{name}" exited with code {popen.returncode}'
    if trimmed_stderr:
        error_msg += f' and stderr "{trimmed_stderr}".'
    else:
        error_msg += "."
    return error_msg


def check_subprocesses(widget, cancelled, *args):
    """
    Check whether all the subprocesses have exited. If so, display their error
    messages and clean up after them.

    :param widget: Used to schedule another check
    :param cancelled: Boolean variable indicating cancellation request
    :param args: An array of tuples, each containing a subprocess's name and
                 its popen object.
    """
    # If requested, cancel subprocesses
    if cancelled.get():
        # Signal each process to exit
        for name, popen in args:
            popen.terminate()
        # Mark this cancellation request as handled
        cancelled.set(False)
        # At the next check, hopefully the processes will have exited
        widget.after(
            SLEEP, lambda: check_subprocesses(widget, cancelled, *args)
        )
    else:
        # Are any of the subprocesses still running?
        still_running = False
        for name, popen in args:
            still_running = still_running or (popen.poll() is None)
        # If subprocesses are still running, keep waiting for them
        if still_running:
            widget.after(
                SLEEP, lambda: check_subprocesses(widget, cancelled, *args)
            )
        else:
            # If a subprocess exited irregularly, describe the issue
            error_msgs = []
            for name, popen in args:
                if popen.returncode:
                    error_msgs.append(get_process_error(name, popen))
            if error_msgs:
                error_msgs.insert(0, "Error:")
                showerror(
                    title="Error",
                    message="\n".join(error_msgs),
                )
            # Clean up
            for name, popen in args:
                popen.stdout.close()
                popen.stderr.close()


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


def send_files(
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
        root.after(
            SLEEP,
            lambda: check_subprocesses(
                root,
                cancelled,
                ("tar", tar),
                ("pydiode", pydiode),
            ),
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
        root.after(
            SLEEP,
            lambda: check_subprocesses(
                root, cancelled, ("pydiode", pydiode), ("tar", tar)
            ),
        )

        def animate():
            # An "indeterminate" progress bar will animate until its value is 0
            progress_bar["value"] = 1
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


def gui_main():
    # Load configuration
    config = configparser.ConfigParser()
    config.read(CONFIG)
    if "pydiode" not in config:
        config["pydiode"] = {}

    # Create the main window
    root = Tk()
    root.title("pydiode GUI")
    root.minsize(width=500, height=400)

    # Create three tabs
    nb = ttk.Notebook(root)
    tx_outer = ttk.Frame(nb)
    rx_outer = ttk.Frame(nb)
    settings_outer = ttk.Frame(nb)
    nb.add(tx_outer, text="Send")
    nb.add(rx_outer, text="Receive")
    nb.add(settings_outer, text="Settings")
    # Allow the notebook to grow
    nb.grid(sticky="nsew")
    root.columnconfigure(0, weight=1)
    root.rowconfigure(0, weight=1)
    # Allow each tab's outer frame to grow
    tx_outer.columnconfigure(0, weight=1)
    tx_outer.rowconfigure(0, weight=1)
    rx_outer.columnconfigure(0, weight=1)
    rx_outer.rowconfigure(0, weight=1)
    settings_outer.columnconfigure(0, weight=1)
    settings_outer.rowconfigure(0, weight=1)
    # Switch to the last used tab
    nb.select(config["pydiode"].get("tab", 0))
    # Keep track of the active tab
    active_tab = IntVar()
    nb.bind(
        "<<NotebookTabChanged>>",
        lambda *args: active_tab.set(nb.index(nb.select())),
    )

    # Configure the send tab
    tx_inner = ttk.Frame(tx_outer)
    tx_inner.grid(column=0, row=0, sticky="NSEW", pady=5)
    ttk.Label(tx_inner, text="File transfer queue:").grid(column=0, row=0)
    sources_list = []
    sources_var = StringVar(value=sources_list)
    sources_var.trace("w", lambda *args: update_tx_btn(tx_btn, sources_list))
    sources_box = Listbox(
        tx_inner,
        listvariable=sources_var,
        selectmode="extended",
    )
    sources_box.grid(column=0, row=1, sticky="NSEW")
    tx_inner.columnconfigure(0, weight=1)
    tx_inner.rowconfigure(1, weight=1)
    pm_frame = ttk.Frame(tx_inner)
    pm_frame.grid(column=0, row=2, sticky="W")
    ttk.Button(
        pm_frame,
        text="+",
        width=1,
        command=lambda: add_source_files(sources_var, sources_list),
    ).grid(column=0, row=0)
    ttk.Button(
        pm_frame,
        text="-",
        width=1,
        command=lambda: remove_source_files(
            sources_var, sources_list, sources_box
        ),
    ).grid(column=1, row=0)
    tx_btn = ttk.Button(
        tx_inner,
        text="Start Sending",
        command=lambda: send_files(
            root,
            sources_list,
            send_ip.get(),
            receive_ip.get(),
            port.get(),
            tx_btn,
            tx_progress,
            tx_cancelled,
        ),
    )
    tx_btn.grid(column=0, row=3, pady=5)
    tx_progress = ttk.Progressbar(tx_inner, length=200, maximum=1000)
    tx_progress.grid(column=0, row=4)
    tx_cancelled = BooleanVar(value=False)
    update_tx_btn(tx_btn, sources_list)

    # Configure the receive tab
    rx_inner = ttk.Frame(rx_outer)
    rx_inner.grid(column=0, row=0, sticky="NEW", pady=5)
    ttk.Label(rx_inner, text="Save files to:").grid(column=0, row=0)
    target = StringVar()
    ttk.Entry(rx_inner, textvariable=target).grid(column=0, row=1, sticky="EW")
    rx_inner.columnconfigure(0, weight=1)
    rx_inner.rowconfigure(1, weight=1)
    target.set(config["pydiode"].get("target", os.getcwd()))
    ttk.Button(
        rx_inner,
        text="Browse...",
        command=lambda: set_target_directory(target),
    ).grid(column=1, row=1)
    rx_btn = ttk.Button(
        rx_inner,
        text="Start Receiving",
        command=lambda: receive_files(
            root,
            target.get(),
            receive_ip.get(),
            port.get(),
            rx_btn,
            rx_progress,
            rx_cancelled,
        ),
    )
    rx_btn.grid(column=0, row=2, pady=5)
    rx_progress = ttk.Progressbar(rx_inner, length=200)
    rx_progress.grid(column=0, row=3)
    rx_cancelled = BooleanVar(value=False)

    # Configure the settings tab
    settings_inner = ttk.Frame(settings_outer)
    settings_inner.grid(column=0, row=0, sticky="N", pady=5)
    settings_inner.grid_columnconfigure(0, weight=1)
    settings_inner.grid_rowconfigure(0, weight=1)
    ttk.Label(settings_inner, text="Sender IP:").grid(
        column=0, row=0, sticky="E"
    )
    send_ip = StringVar()
    ttk.Entry(settings_inner, textvariable=send_ip).grid(column=1, row=0)
    send_ip.set(config["pydiode"].get("send_ip", "10.0.1.2"))
    ttk.Label(settings_inner, text="Receiver IP:").grid(
        column=0, row=1, sticky="E"
    )
    receive_ip = StringVar()
    ttk.Entry(settings_inner, textvariable=receive_ip).grid(column=1, row=1)
    receive_ip.set(config["pydiode"].get("receive_ip", "10.0.1.1"))
    ttk.Label(settings_inner, text="Port:").grid(column=0, row=2, sticky="E")
    port = StringVar()
    ttk.Entry(settings_inner, textvariable=port).grid(column=1, row=2)
    port.set(config["pydiode"].get("port", "1234"))
    # TODO Add options for maximum bitrate and redundancy

    # Start handling user input
    root.mainloop()

    # Save settings
    config["pydiode"] = {
        "tab": active_tab.get(),
        "target": target.get(),
        "send_ip": send_ip.get(),
        "receive_ip": receive_ip.get(),
        "port": port.get(),
    }
    with open(CONFIG, "w") as configfile:
        config.write(configfile)


def main():
    """
    Running Python subprocess from a frozen app is complicated, because the
    frozen app doesn't have a regular a python interpreter. However, the frozen
    app can create a subprocess of its executable, with alternate arguments.
    This executable can call the appropriate methods, based on its arguments.
    """
    if len(sys.argv) == 1:
        # Without arguments, just launch the GUI
        gui_main()
    else:
        # Remove the executable from argv for compatibility with argparse
        sys.argv.pop(0)
        if sys.argv[0] == "pydiode":
            # With pydiode as the first argument, launch pydiode
            pydiode.pydiode.main()
        elif sys.argv[0] == "tar":
            # With tar as the first argument, launch tar
            pydiode.tar.main()
        else:
            print(f"Invalid arguments: {sys.argv}", file=sys.stderr)
            sys.exit(1)


if __name__ == "__main__":
    main()
