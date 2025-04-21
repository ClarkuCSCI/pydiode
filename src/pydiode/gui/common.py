import os
from pathlib import Path
import signal
import subprocess
import sys
from tkinter import Toplevel, ttk
from tkinter.messagebox import showerror

# Check subprocesses every SLEEP milliseconds
SLEEP = 250


class SavedWindow:
    # A modal window shown after files were received
    top = None

    # Whether to show the window. Configured as a BooleanVar in gui_main().
    should_show = None

    @classmethod
    def on_ok(cls, event=None):
        if cls.top:
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


class ProcessPipeline:

    def __init__(self):
        self.names = []
        self.popens = []
        # Did the user cancel the pipeline?
        self.cancelled = False

    def append(self, name, popen):
        self.names.append(name)
        self.popens.append(popen)

    def send_signal(self, s):
        """
        :param s: Send this signal to each process in the pipeline.
        """
        if s == signal.SIGINT:
            self.cancelled = True
        for popen in self.popens:
            popen.send_signal(s)

    def clear(self):
        """
        Clear the pipeline, so it doesn't grow as more subprocesses are
        started. This method should be called after all processes have exited.
        """
        for popen in self.popens:
            if popen.stdout:
                popen.stdout.close()
            if popen.stderr:
                popen.stderr.close()
        self.names = []
        self.popens = []
        self.cancelled = False

    def poll(self):
        """
        poll each process for its returncode.
        """
        for popen in self.popens:
            # If a process has terminated, set returncode.
            # If a process is still running, returncode will be None.
            popen.poll()

    def still_running(self):
        """
        :returns: True if at least one process is still running,
                  False if all processes have exited.
        """
        return any(popen.returncode is None for popen in self.popens)

    def _returncodes(self):
        """
        :returns: A list of all processes' returncodes.
        """
        return [popen.returncode for popen in self.popens]

    def stuck_running(self):
        """
        Based on process returncodes, is the pipeline stuck? In a pipeline,
        earlier processes should exit first. If a later process exits first, an
        earlier process's STDOUT cannot be consumed, so it will never exit.
        Thus, the pipeline is stuck if a running process comes before an exited
        process.

        :return: A boolean, indicating if the pipeline is stuck.
        """
        try:
            # The index of the earliest still-running process in the pipeline
            earliest_running = self._returncodes().index(None)
            # Have any subsequent processes already exited?
            return any(
                c is not None
                for c in self._returncodes()[(earliest_running + 1) :]
            )
        except ValueError:
            # None won't be found if all the processes have exited.
            # If so, the pipeline isn't stuck.
            return False

    def print_premature_errors(self):
        """
        Print a description of subprocesses that exited prematurely.
        """
        try:
            earliest_running = self._returncodes().index(None)
            name_code = list(zip(self.names, self._returncodes()))
            for name, code in name_code[(earliest_running + 1) :]:
                if code is not None:
                    print(f'"{name}" exited prematurely.', file=sys.stderr)
        except ValueError:
            pass

    def get_process_errors(self):
        """
        Get an error message describing subprocesses that exited irregularly.

        Describe an error if:
        - The pipeline wasn't cancelled
        - The process exited abnormally (non-zero exit code)

        :returns: A string describing the return code and stderr for
                  subprocesses that exited irregularly.
        """
        error_msgs = []
        for name, popen in zip(self.names, self.popens):
            trimmed_stderr = popen.stderr.read().decode("utf-8").strip()
            # Show errors if:
            if not self.cancelled and popen.returncode != 0:
                error_msg = f'"{name}" exited with code {popen.returncode}'
                if trimmed_stderr:
                    error_msg += f' and stderr "{trimmed_stderr}"'
                error_msgs.append(error_msg)
        if error_msgs:
            error_msgs.insert(0, "Error:")
        return "\n".join(error_msgs)


def check_subprocesses(
    widget, cancelled, pipeline, on_exit=None, cancel_signal=signal.SIGINT
):
    """
    Check whether all the subprocesses have exited. If so, display their error
    messages and clean up after them.

    :param widget: Used to schedule another check
    :param cancelled: Boolean variable indicating cancellation request
    :param pipeline: A ProcessPipeline containing subprocess details
    :param on_exit: Function to call after all subprocesses have exited. Do
                    not call the function if the subprocesses exited with a
                    non-zero exit code, due to cancellation, or due to getting
                    stuck.
    :param cancel_signal: If cancellation was requested, send this signal to
                          all subprocesses. SIGINT is used for user-initiated
                          termination. SIGTERM is used for stuck subprocesses.
    """
    # If requested, cancel subprocesses
    if cancelled.get():
        # Signal each process to exit
        pipeline.send_signal(cancel_signal)
        # Mark this cancellation request as handled
        cancelled.set(False)
        # Don't call on_exit if the user requested cancellation
        on_exit = None if pipeline.cancelled else on_exit
        # At the next check, hopefully the processes will have exited
        widget.after(
            SLEEP,
            lambda: check_subprocesses(
                widget, cancelled, pipeline, on_exit=on_exit
            ),
        )
    else:
        # Check the status of subprocesses, updating returncodes
        pipeline.poll()

        # If subprocesses are stuck
        if pipeline.stuck_running():
            # Request cancellation
            cancelled.set(True)
            widget.after(
                SLEEP,
                lambda: check_subprocesses(
                    widget,
                    cancelled,
                    pipeline,
                    on_exit=on_exit,
                    cancel_signal=signal.SIGTERM,
                ),
            )
            # Describe the issue
            pipeline.print_premature_errors()
        # If subprocesses are still running, keep waiting for them
        elif pipeline.still_running():
            widget.after(
                SLEEP,
                lambda: check_subprocesses(
                    widget, cancelled, pipeline, on_exit=on_exit
                ),
            )
        # Otherwise, all subprocesses have exited
        else:
            # If any subprocesses exited irregularly, describe the issue
            error_msgs = pipeline.get_process_errors()
            if error_msgs:
                # Dismiss the "Received Files" window, if it's open
                SavedWindow.on_ok()
                # Show the error message
                showerror(title="Error", message=error_msgs)
            # Clear the pipeline, so it doesn't grow as more subprocesses are
            # started
            pipeline.clear()
            # Call the on_exit() function, if it was provided
            if on_exit and not error_msgs:
                on_exit()
