from tkinter import Listbox, StringVar, Tk, ttk
from tkinter.filedialog import askdirectory, askopenfilenames


def set_target_directory(target):
    target_directory = askdirectory()
    if target_directory:
        target.set(target_directory)


def add_source_files(sources_var, sources_list):
    selected_sources = askopenfilenames()
    new_sources = set(selected_sources) - set(sources_list)
    if new_sources:
        sources_list.extend(sorted(new_sources))
        sources_var.set(sources_list)


def remove_source_files(sources_var, sources_list, sources_box):
    source_indices = sources_box.curselection()
    # Remove in reverse order, to avoid removing the wrong elements
    for i in sorted(source_indices, reverse=True):
        sources_list.pop(i)
    sources_var.set(sources_list)


def main():
    root = Tk()
    root.title("pydiode GUI")

    # Create three tabs
    nb = ttk.Notebook(root)
    tx_frame = ttk.Frame(nb)
    rx_frame = ttk.Frame(nb)
    settings_frame = ttk.Frame(nb)
    nb.add(tx_frame, text="Send")
    nb.add(rx_frame, text="Receive")
    nb.add(settings_frame, text="Settings")
    nb.grid()

    # Configure the send tab
    ttk.Label(tx_frame, text="File transfer queue:").grid(column=0, row=0)
    sources_list = []
    sources_var = StringVar(value=sources_list)
    sources_box = Listbox(
        tx_frame, listvariable=sources_var, selectmode="extended"
    )
    sources_box.grid(column=0, row=1)
    pm_frame = ttk.Frame(tx_frame)
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
    start = ttk.Button(tx_frame, text="Start Sending", command=root.destroy)
    start.grid(column=0, row=3, pady=5)
    start.state(["disabled"])

    # Configure the receive tab
    ttk.Label(rx_frame, text="Save files to:").grid(column=0, row=0)
    target = StringVar()
    ttk.Entry(rx_frame, textvariable=target).grid(column=0, row=1)
    target.set("~/Desktop")
    ttk.Button(
        rx_frame,
        text="Browse...",
        command=lambda: set_target_directory(target),
    ).grid(column=1, row=1)
    ttk.Button(rx_frame, text="Start Receiving", command=root.destroy).grid(
        column=0, row=2, pady=5
    )

    # Configure the settings tab
    ttk.Label(settings_frame, text="Sender IP:").grid(
        column=0, row=0, sticky="E"
    )
    send_ip = StringVar()
    ttk.Entry(settings_frame, textvariable=send_ip).grid(column=1, row=0)
    send_ip.set("10.0.1.2")
    ttk.Label(settings_frame, text="Receiver IP:").grid(
        column=0, row=1, sticky="E"
    )
    receive_ip = StringVar()
    ttk.Entry(settings_frame, textvariable=receive_ip).grid(column=1, row=1)
    receive_ip.set("10.0.1.1")
    ttk.Label(settings_frame, text="Port:").grid(column=0, row=2, sticky="E")
    port = StringVar()
    ttk.Entry(settings_frame, textvariable=port).grid(column=1, row=2)
    port.set("1234")
    # TODO Add options for maximum bitrate and redundancy

    # Start handling user input
    root.mainloop()


if __name__ == "__main__":
    main()
