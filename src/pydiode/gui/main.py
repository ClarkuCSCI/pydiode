import configparser
from pathlib import Path
import signal
import sys
from tkinter import BooleanVar, IntVar, Listbox, StringVar, Tk, ttk

from pydiode.gui.receive import (
    receive_or_cancel,
    receive_test,
    set_target_directory,
    RECEIVE_PIPELINE,
    RECEIVE_TEST_PIPELINE,
    SavedWindow,
)
from pydiode.gui.send import (
    add_source_files,
    remove_source_files,
    send_or_cancel,
    send_test,
    update_tx_btn,
    SEND_PIPELINE,
    SEND_TEST_PIPELINE,
)

# These modules' main methods are run in subprocesses
import pydiode.decrypt
import pydiode.pydiode
import pydiode.tar

# Save the configuration file in the user's home folder
CONFIG = Path("~/.pydiode.ini").expanduser()


def gui_main():
    # Load configuration
    config = configparser.ConfigParser()
    config.read(CONFIG)
    if "pydiode" not in config:
        config["pydiode"] = {}

    # Create the main window
    root = Tk(className="diodeTransfer")
    root.title("Diode Transfer")
    # We can't tell whether screen scaling is enabled on Linux. When 200%
    # scaling is used, the window is too small. As a workaround, increase the
    # window size on 4K screens. This won't affect macOS, since macOS presents
    # 4K screens as having fewer pixels.
    # https://stackoverflow.com/q/78529732/3043071
    root.minsize(
        width=(500 if root.winfo_screenwidth() < 3000 else 700), height=400
    )

    # Create three tabs
    nb = ttk.Notebook(root)
    tx_outer = ttk.Frame(nb, padding=10)
    rx_outer = ttk.Frame(nb, padding=10)
    settings_outer = ttk.Frame(nb, padding=10)
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
        command=lambda: send_or_cancel(
            root,
            sources_list,
            send_ip.get(),
            receive_ip.get(),
            port.get(),
            key_id.get(),
            bitrate.get(),
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
    target.set(
        config["pydiode"].get("target", Path("~/Downloads").expanduser())
    )
    ttk.Button(
        rx_inner,
        text="Browse...",
        command=lambda: set_target_directory(target),
    ).grid(column=1, row=1)
    rx_btn = ttk.Button(
        rx_inner,
        text="Start Receiving",
        command=lambda: receive_or_cancel(
            root,
            target.get(),
            receive_ip.get(),
            port.get(),
            key_id.get(),
            rx_btn,
            rx_progress,
            rx_cancelled,
            receive_repeatedly,
            decrypt_received,
        ),
    )
    rx_btn.grid(column=0, row=2, pady=5, columnspan=2)
    rx_progress = ttk.Progressbar(rx_inner, length=200)
    rx_progress.grid(column=0, row=3, columnspan=2)
    rx_cancelled = BooleanVar(value=False)

    # Configure receive's SavedWindow
    SavedWindow.should_show = BooleanVar()
    SavedWindow.should_show.set(
        config["pydiode"].get("saved_window_should_show", True)
    )

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
    receive_ip.set(config["pydiode"].get("receive_ip", "10.0.1.255"))
    ttk.Label(settings_inner, text="Port:").grid(column=0, row=2, sticky="E")
    port = StringVar()
    ttk.Entry(settings_inner, textvariable=port).grid(column=1, row=2)
    port.set(config["pydiode"].get("port", "1234"))
    ttk.Label(settings_inner, text="PGP Key ID:").grid(
        column=0, row=3, sticky="E"
    )
    key_id = StringVar()
    ttk.Entry(settings_inner, textvariable=key_id).grid(column=1, row=3)
    key_id.set(config["pydiode"].get("key_id", ""))
    ttk.Label(settings_inner, text="Bitrate:").grid(column=0, row=4, sticky="E")
    bitrate = StringVar()
    ttk.Combobox(
        settings_inner,
        textvariable=bitrate,
        values=(
            "100 Mbit/s",
            "250 Mbit/s",
            "500 Mbit/s",
            "750 Mbit/s",
            "1 Gbit/s",
        ),
        width=12,
        state="readonly",
    ).grid(column=1, row=4, sticky="W")
    bitrate.set(config["pydiode"].get("bitrate", "100 Mbit/s"))
    receive_repeatedly = BooleanVar()
    ttk.Checkbutton(
        settings_inner,
        text="Receive continuously",
        variable=receive_repeatedly,
        onvalue=True,
        offvalue=False,
    ).grid(column=0, row=5, columnspan=2, sticky="W")
    receive_repeatedly.set(config["pydiode"].get("receive_repeatedly", True))
    decrypt_received = BooleanVar()
    ttk.Checkbutton(
        settings_inner,
        text="Decrypt received files",
        variable=decrypt_received,
        onvalue=True,
        offvalue=False,
    ).grid(column=0, row=6, columnspan=2, sticky="W")
    decrypt_received.set(config["pydiode"].get("decrypt_received", True))
    rx_test_cancelled = BooleanVar(value=False)
    rx_test_btn = ttk.Button(
        settings_inner,
        text="Test Receiving",
        command=lambda: receive_test(
            root,
            receive_ip.get(),
            port.get(),
            rx_test_btn,
            rx_test_cancelled,
        ),
    )
    rx_test_btn.grid(column=0, row=7, columnspan=2)
    tx_test_cancelled = BooleanVar(value=False)
    ttk.Button(
        settings_inner,
        text="Test Sending",
        command=lambda: send_test(
            root,
            send_ip.get(),
            receive_ip.get(),
            port.get(),
            bitrate.get(),
            tx_test_cancelled,
        ),
    ).grid(column=0, row=8, columnspan=2)

    # Override the default behavior of the Quit menu, so it doesn't cause the
    # application to exit immediately
    root.createcommand("tk::mac::Quit", root.quit)

    # Start handling user input
    root.mainloop()

    # Terminate send and receive subprocesses
    SEND_PIPELINE.send_signal(signal.SIGTERM)
    SEND_TEST_PIPELINE.send_signal(signal.SIGTERM)
    RECEIVE_PIPELINE.send_signal(signal.SIGTERM)
    RECEIVE_TEST_PIPELINE.send_signal(signal.SIGTERM)

    # Save settings
    config["pydiode"] = {
        "tab": active_tab.get(),
        "target": target.get(),
        "send_ip": send_ip.get(),
        "receive_ip": receive_ip.get(),
        "port": port.get(),
        "key_id": key_id.get(),
        "bitrate": bitrate.get(),
        "receive_repeatedly": receive_repeatedly.get(),
        "decrypt_received": decrypt_received.get(),
        "saved_window_should_show": SavedWindow.should_show.get(),
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
        # Based on the first argument, run the appropriate main method
        if sys.argv[0] == "decrypt":
            pydiode.decrypt.main()
        elif sys.argv[0] == "pydiode":
            pydiode.pydiode.main()
        elif sys.argv[0] == "tar":
            pydiode.tar.main()
        else:
            print(f"Invalid arguments: {sys.argv}", file=sys.stderr)
            sys.exit(1)


if __name__ == "__main__":
    main()
