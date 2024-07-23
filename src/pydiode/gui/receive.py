import os
from pathlib import Path
import subprocess
import sys
from tkinter import Toplevel, ttk
from tkinter.filedialog import askdirectory
from tkinter.messagebox import showinfo

from pydiode.gui.common import check_subprocesses, ProcessPipeline, SLEEP

# Information about our subprocesses
RECEIVE_PIPELINE = ProcessPipeline()
RECEIVE_TEST_PIPELINE = ProcessPipeline()


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
    decrypt_received,
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
    :param decrypt_received: Boolean variable indicating whether to decrypt
                             received files using gpg
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
            decrypt_received,
        )


class SavedWindow:
    # A modal window shown after files were received
    top = None

    # Whether to show the window. Configured as a BooleanVar in gui_main().
    should_show = None

    @classmethod
    def on_ok(cls, event=None):
        cls.top.destroy()

    @classmethod
    def on_show_files(cls, target_dir):
        # Based on: https://stackoverflow.com/a/17317468/3043071
        if sys.platform == "win32":
            os.startfile(target_dir)
        else:
            opener = "open" if sys.platform == "darwin" else "xdg-open"
            subprocess.run([opener, target_dir])
        cls.top.destroy()

    @classmethod
    def show_window(cls, root, target_dir):
        # Only create a window if:
        # - The user didn't permanently dismiss the window and
        # - The window hasn't yet been created, or it was destroyed
        if cls.should_show.get() and (
            not cls.top or not cls.top.winfo_exists()
        ):
            cls.top = Toplevel(root)
            cls.top.grid_rowconfigure(0, weight=1)
            cls.top.grid_columnconfigure(0, weight=1)
            cls.top.title("Received Files")

            ttk.Label(
                cls.top, text=f"Saved files to: {Path(target_dir).name}"
            ).grid(column=0, row=0, columnspan=3, pady=(15, 0))

            ttk.Checkbutton(
                cls.top,
                text="Do not show again",
                variable=cls.should_show,
                onvalue=False,
                offvalue=True,
            ).grid(column=0, row=1, padx=10, pady=10)

            show_files_button = ttk.Button(
                cls.top,
                text="Show Files",
                command=lambda: cls.on_show_files(target_dir),
            )
            show_files_button.grid(column=1, row=1, pady=10)

            ok_button = ttk.Button(
                cls.top, text="OK", default="active", command=cls.on_ok
            )
            ok_button.grid(column=2, row=1, padx=10, pady=10)

            # Dismiss if escape or return are pressed
            cls.top.bind("<Escape>", cls.on_ok)
            cls.top.bind("<Return>", cls.on_ok)

            # Use modal style on macOS
            if sys.platform == "darwin":
                cls.top.tk.call(
                    "::tk::unsupported::MacWindowStyle",
                    "style",
                    cls.top._w,
                    "modal",
                )

            # Set the modal's minimum size, and center it over the main window.
            # If the size exceeds these dimensions, the modal won't be
            # perfectly centered.
            width = 400
            height = 100
            cls.top.minsize(width=width, height=height)
            x = root.winfo_x() + (root.winfo_width() // 2) - (width // 2)
            y = root.winfo_y() + (root.winfo_height() // 2) - (height // 4)
            cls.top.geometry(f"+{x}+{y}")

            # Prevent resizing
            cls.top.resizable(False, False)

            # Stay on top of the main window
            cls.top.transient(root)

            # Take focus
            cls.top.grab_set()


def receive_files(
    root,
    target_dir,
    receive_ip,
    port,
    button,
    progress_bar,
    cancelled,
    receive_repeatedly,
    decrypt_received,
):
    def repeat():
        SavedWindow.show_window(root, target_dir)
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
                decrypt_received,
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
    RECEIVE_PIPELINE.append("pydiode", pydiode)
    RECEIVE_PIPELINE.append("tar", tar)

    if decrypt_received.get():
        decrypt = subprocess.Popen(
            sys.argv + ["decrypt"],
            stdin=tar.stdout,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        RECEIVE_PIPELINE.append("decrypt", decrypt)

    check_subprocesses(root, cancelled, RECEIVE_PIPELINE, on_exit=repeat)
    animate()


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
        RECEIVE_TEST_PIPELINE.append("pydiode", pydiode)

        check_subprocesses(root, cancelled, RECEIVE_TEST_PIPELINE)
        update_button()
