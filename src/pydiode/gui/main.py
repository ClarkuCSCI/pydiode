import configparser
import os
import pathlib
import sys
from tkinter import BooleanVar, IntVar, Listbox, StringVar, Tk, ttk


from pydiode.gui.receive import receive_files, set_target_directory
from pydiode.gui.send import (
    add_source_files,
    remove_source_files,
    send_files,
    update_tx_btn,
)
import pydiode.pydiode
import pydiode.tar

# Save the configuration file in the user's home folder
CONFIG = pathlib.Path().home() / ".pydiode.ini"


def gui_main():
    # Load configuration
    config = configparser.ConfigParser()
    config.read(CONFIG)
    if "pydiode" not in config:
        config["pydiode"] = {}

    # Create the main window
    root = Tk(className="diodeTransfer")
    root.title("Diode Transfer")
    root.minsize(width=500, height=400)

    # Create three tabs
    nb = ttk.Notebook(root)
    tx_outer = ttk.Frame(nb, padding=5)
    rx_outer = ttk.Frame(nb, padding=5)
    settings_outer = ttk.Frame(nb, padding=5)
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
    tx_inner.grid(column=0, row=0, sticky="NSEW")
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
        width=2,
        command=lambda: add_source_files(sources_var, sources_list),
    ).grid(column=0, row=0)
    ttk.Button(
        pm_frame,
        text="-",
        width=2,
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
    rx_inner.grid(column=0, row=0, sticky="NEW")
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
    settings_inner.grid(column=0, row=0, sticky="N")
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
