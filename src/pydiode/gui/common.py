import sys
from tkinter.messagebox import showerror

# Check subprocesses every SLEEP milliseconds
SLEEP = 250


def get_process_errors(name_popen):
    """
    Get a error message describing subprocesses that exited irregularly.

    :param name_popen: A list of tuples. Each tuple contains the process name
                       and the subprocess.Popen object. All processes have
                       terminated.
    :returns: A string describing the return code and stderr for subprocesses
              that exited irregularly.
    """
    error_msgs = []
    for name, popen in name_popen:
        # 0: normal exit.
        # -15: SIGTERM, likely from user-initiated cancellation.
        if popen.returncode not in {-15, 0}:
            trimmed_stderr = popen.stderr.read().decode("utf-8").strip()
            error_msg = f'"{name}" exited with code {popen.returncode}'
            if trimmed_stderr:
                error_msg += f' and stderr "{trimmed_stderr}"'
            error_msgs.append(error_msg)
    if error_msgs:
        error_msgs.insert(0, "Error:")
    return "\n".join(error_msgs)


def print_premature_errors(name_code):
    """
    Print a description of subprocesses that exited prematurely.

    :param name_code: A list of tuples. Each tuple contains the process name
                      and the return code of the process. Some processes have
                      terminated, others have not.
    """
    returncodes = [code for name, code in name_code]
    try:
        earliest_running = returncodes.index(None)
        for name, code in name_code[(earliest_running + 1) :]:
            if code is not None:
                print(f'"{name}" exited prematurely.', file=sys.stderr)
    except ValueError:
        pass


def stuck_running(returncodes):
    """
    Based on process returncodes, is the pipeline stuck? In a pipeline, earlier
    processes should exit first. If a later process exits first, an earlier
    process's STDOUT cannot be consumed, so it will never exit. Thus, the
    pipeline is stuck if a running process comes before an exited process.

    :param: A list of returncodes from a process pipeline. A None returncode
            indicates that a process is still running. A numeric returncode
            indicates that a process exited.
    :return: A boolean, indicating if the pipeline is stuck.
    """
    try:
        # The index of the earliest still-running process in the pipeline
        earliest_running = returncodes.index(None)
        # Have any subsequent processes already exited?
        return any(c is not None for c in returncodes[(earliest_running + 1) :])
    except ValueError:
        # None won't be found if all the processes have exited.
        # If so, the pipeline isn't stuck.
        return False


def check_subprocesses(widget, cancelled, processes, on_exit=None):
    """
    Check whether all the subprocesses have exited. If so, display their error
    messages and clean up after them.

    :param widget: Used to schedule another check
    :param cancelled: Boolean variable indicating cancellation request
    :param processes: An array of tuples, each containing a subprocess's name
                      and its popen object.
    :param on_exit: Function to call after all subprocesses have exited. Do
                    not call the function if the subprocesses exited with a
                    non-zero exit code, due to cancellation, or due to getting
                    stuck.
    """
    # If requested, cancel subprocesses
    if cancelled.get():
        # Signal each process to exit
        for name, popen in processes:
            popen.terminate()
        # Mark this cancellation request as handled
        cancelled.set(False)
        # At the next check, hopefully the processes will have exited
        widget.after(
            SLEEP, lambda: check_subprocesses(widget, cancelled, processes)
        )
    else:
        # Get returncodes for exited processes, None for running processes
        returncodes = [popen.poll() for name, popen in processes]
        # Are any of the subprocesses still running?
        still_running = any(code is None for code in returncodes)

        # If subprocesses are stuck
        if stuck_running(returncodes):
            # Signal each process to exit
            for name, popen in processes:
                popen.terminate()
            # At the next check, hopefully the processes will have exited
            widget.after(
                SLEEP,
                lambda: check_subprocesses(
                    widget, cancelled, processes, on_exit=on_exit
                ),
            )
            # Describe the issue
            process_names = [name for name, popen in processes]
            print_premature_errors(list(zip(process_names, returncodes)))
        # If subprocesses are still running, keep waiting for them
        elif still_running:
            widget.after(
                SLEEP,
                lambda: check_subprocesses(
                    widget, cancelled, processes, on_exit=on_exit
                ),
            )
        # Otherwise, all subprocesses have exited
        else:
            # If any subprocesses exited irregularly, describe the issue
            error_msgs = get_process_errors(processes)
            if error_msgs:
                showerror(title="Error", message=error_msgs)
            # Clean up
            for name, popen in processes:
                if popen.stdout:
                    popen.stdout.close()
                if popen.stderr:
                    popen.stderr.close()
            # The array of subprocesses should be cleared, so it doesn't grow
            # each time more subprocesses are started
            processes.clear()
            # Call the on_exit() function, if it was provided
            if on_exit and not error_msgs:
                on_exit()
