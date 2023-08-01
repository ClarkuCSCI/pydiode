from tkinter import Listbox, Tk, ttk
from tkinter.filedialog import askdirectory, askopenfilenames


def main():
    root = Tk()

    # Create three tabs
    nb = ttk.Notebook(root)
    tx_frame = ttk.Frame(nb)
    rx_frame = ttk.Frame(nb)
    settings_frame = ttk.Frame(nb)
    nb.add(tx_frame, text="Send")
    nb.add(rx_frame, text="Receive")
    nb.add(settings_frame, text="Settings")
    nb.pack(expand=1, fill="both")

    # Configure the send tab
    ttk.Label(tx_frame, text="File transfer queue:").grid(column=0, row=0)
    Listbox(tx_frame).grid(column=0, row=1)
    ttk.Button(tx_frame, text="+", command=askopenfilenames).grid(
        column=0, row=2
    )
    ttk.Button(tx_frame, text="-", command=root.destroy).grid(column=1, row=2)
    ttk.Button(tx_frame, text="Start Sending", command=root.destroy).grid(
        column=0, row=3
    )

    # Configure the receive tab
    ttk.Label(rx_frame, text="Save files to:").grid(column=0, row=0)
    target = ttk.Entry(rx_frame)
    target.grid(column=0, row=1)
    target.insert(0, "~/Desktop")
    ttk.Button(rx_frame, text="Browse...", command=askdirectory).grid(
        column=1, row=1
    )
    ttk.Button(rx_frame, text="Start Receiving", command=root.destroy).grid(
        column=0, row=2
    )

    # Configure the settings tab
    ttk.Label(settings_frame, text="Sender IP:").grid(column=0, row=0)
    send_ip = ttk.Entry(settings_frame)
    send_ip.grid(column=1, row=0)
    send_ip.insert(0, "10.0.1.2")
    ttk.Label(settings_frame, text="Receiver IP:").grid(column=0, row=1)
    receive_ip = ttk.Entry(settings_frame)
    receive_ip.grid(column=1, row=1)
    receive_ip.insert(0, "10.0.1.1")
    ttk.Label(settings_frame, text="Port:").grid(column=0, row=2)
    port = ttk.Entry(settings_frame)
    port.grid(column=1, row=2)
    port.insert(0, "1234")
    # TODO Eventually add options for maximum bitrate and redundancy

    # Start handling user input
    root.mainloop()


if __name__ == "__main__":
    main()
