import configparser
import os
import pathlib
import subprocess
import sys
from tkinter import IntVar, Listbox, StringVar, Tk, ttk
from tkinter.filedialog import askdirectory, askopenfilenames
from tkinter.messagebox import showerror

import pydiode.main
import pydiode.tar

# Save the configuration file in the user's home folder
CONFIG = pathlib.Path().home() / ".pydiode.ini"
# Check subprocesses every SLEEP milliseconds
SLEEP = 250


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


def check_subprocesses(widget, *args):
    """
    Check whether all the subprocesses have exited. If so, display their error
    messages and clean up after them.

    :param widget: Used to schedule another check
    :param args: An array of tuples, each containing a subprocess's name and
                 its popen object.
    """
    # TODO Include a progress bar, and ensure we stop checking eventually.
    # Are any of the subprocesses still running?
    still_running = False
    for name, popen in args:
        still_running = still_running or (popen.poll() is None)
    # If subprocesses are still running, keep waiting for them
    if still_running:
        widget.after(SLEEP, lambda: check_subprocesses(widget, *args))
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


def send_files(root, sources_list, send_ip, receive_ip, port):
    """
    Send the listed files through the data diode.

    :param sources_list: A list of filenames to send through the data diode
    :param send_ip: Send data from this IP
    :param receive_ip: Send data to this IP
    :param port: Send data using this port
    """
    tar = subprocess.Popen(
        sys.argv + ["tar", "create"] + sources_list,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    pydiode = subprocess.Popen(
        sys.argv + ["pydiode", "send", receive_ip, send_ip, "--port", port],
        stdin=tar.stdout,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    root.after(
        SLEEP,
        lambda: check_subprocesses(
            root,
            ("tar", tar),
            ("pydiode", pydiode),
        ),
    )


def receive_files(root, target_dir, receive_ip, port):
    """
    Receive files from the data diode.

    :param target_dir: Where to save the files received
    :param receive_ip: Receive data using this IP
    :param port: Receive data using this port
    """
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
        lambda: check_subprocesses(root, ("pydiode", pydiode), ("tar", tar)),
    )


def update_start(start, sources_list):
    """
    Enable or disable the start button based on whether there are any source
    files to send.

    :param start: The start button
    :param sources_list: The files in the file transfer queue
    """
    if sources_list:
        start.state(["!disabled"])
    else:
        start.state(["disabled"])


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
    sources_var.trace("w", lambda *args: update_start(start, sources_list))
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
    start = ttk.Button(
        tx_inner,
        text="Start Sending",
        command=lambda: send_files(
            root, sources_list, send_ip.get(), receive_ip.get(), port.get()
        ),
    )
    start.grid(column=0, row=3, pady=5)
    update_start(start, sources_list)

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
    ttk.Button(
        rx_inner,
        text="Start Receiving",
        command=lambda: receive_files(
            root, target.get(), receive_ip.get(), port.get()
        ),
    ).grid(column=0, row=2, pady=5)

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
            pydiode.main.main()
        elif sys.argv[0] == "tar":
            # With tar as the first argument, launch tar
            pydiode.tar.main()
        else:
            print(f"Invalid arguments: {sys.argv}", file=sys.stderr)
            sys.exit(1)


if __name__ == "__main__":
    main()
