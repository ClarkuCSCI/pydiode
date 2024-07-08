import signal
import sys
from tkinter.messagebox import showerror

# Check subprocesses every SLEEP milliseconds
SLEEP = 250


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
                showerror(title="Error", message=error_msgs)
            # Clear the pipeline, so it doesn't grow as more subprocesses are
            # started
            pipeline.clear()
            # Call the on_exit() function, if it was provided
            if on_exit and not error_msgs:
                on_exit()
