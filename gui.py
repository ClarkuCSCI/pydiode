import os
import subprocess
import sys
from tkinter import Listbox, StringVar, Tk, ttk
from tkinter.filedialog import askdirectory, askopenfilenames


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


def send_files(sources_list, send_ip, receive_ip, port):
    """
    Send the listed files through the data diode.

    :param sources_list: A list of filenames to send through the data diode
    :param send_ip: Send data from this IP
    :param receive_ip: Send data to this IP
    :param port: Send data using this port
    """
    tar = subprocess.Popen(
        [sys.executable, "-m", "pydiode.tar", "create"] + sources_list,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    pydiode = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "pydiode.main",
            "send",
            receive_ip,
            send_ip,
            "--port",
            port,
        ],
        stdin=tar.stdout,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    # TODO Use poll, and include a status indicator
    tar.wait()
    pydiode.wait()
    # Clean up
    tar.stdout.close()
    tar.stderr.close()
    pydiode.stdout.close()
    pydiode.stderr.close()


def receive_files(target_dir, receive_ip, port):
    """
    Receive files from the data diode.

    :param target_dir: Where to save the files received
    :param receive_ip: Receive data using this IP
    :param port: Receive data using this port
    """
    pydiode = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "pydiode.main",
            "receive",
            receive_ip,
            "--port",
            port,
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    tar = subprocess.Popen(
        [sys.executable, "-m", "pydiode.tar", "extract", target_dir],
        stdin=pydiode.stdout,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    # TODO Use poll, and include a status indicator
    pydiode.wait()
    tar.wait()
    # Clean up
    tar.stdout.close()
    tar.stderr.close()
    pydiode.stdout.close()
    pydiode.stderr.close()


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


def main():
    root = Tk()
    root.title("pydiode GUI")

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

    # Configure the send tab
    tx_inner = ttk.Frame(tx_outer)
    tx_inner.grid(column=0, row=0, sticky="N", pady=5)
    ttk.Label(tx_inner, text="File transfer queue:").grid(column=0, row=0)
    sources_list = []
    sources_var = StringVar(value=sources_list)
    sources_var.trace("w", lambda *args: update_start(start, sources_list))
    sources_box = Listbox(
        tx_inner,
        listvariable=sources_var,
        selectmode="extended",
        width=50,
    )
    sources_box.grid(column=0, row=1)
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
            sources_list, send_ip.get(), receive_ip.get(), port.get()
        ),
    )
    start.grid(column=0, row=3, pady=5)
    update_start(start, sources_list)

    # Configure the receive tab
    rx_inner = ttk.Frame(rx_outer)
    rx_inner.grid(column=0, row=0, sticky="N", pady=5)
    ttk.Label(rx_inner, text="Save files to:").grid(column=0, row=0)
    target = StringVar()
    ttk.Entry(rx_inner, textvariable=target, width=35).grid(column=0, row=1)
    target.set(os.getcwd())
    ttk.Button(
        rx_inner,
        text="Browse...",
        command=lambda: set_target_directory(target),
    ).grid(column=1, row=1)
    ttk.Button(
        rx_inner,
        text="Start Receiving",
        command=lambda: receive_files(
            target.get(), receive_ip.get(), port.get()
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
    send_ip.set("10.0.1.2")
    ttk.Label(settings_inner, text="Receiver IP:").grid(
        column=0, row=1, sticky="E"
    )
    receive_ip = StringVar()
    ttk.Entry(settings_inner, textvariable=receive_ip).grid(column=1, row=1)
    receive_ip.set("10.0.1.1")
    ttk.Label(settings_inner, text="Port:").grid(column=0, row=2, sticky="E")
    port = StringVar()
    ttk.Entry(settings_inner, textvariable=port).grid(column=1, row=2)
    port.set("1234")
    # TODO Add options for maximum bitrate and redundancy

    # Start handling user input
    root.mainloop()


if __name__ == "__main__":
    main()
