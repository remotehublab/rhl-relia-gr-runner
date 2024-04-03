import os
import sys
import glob
import json
import time
import platform
import tempfile
import threading
import traceback
import subprocess

from typing import List, Optional

import requests

from flask import current_app

from .scheduler import AbstractSchedulerClient, NoSchedulerClient, SchedulerClient, TaskAssignment
from .grc_manager import GrcManager

class Processor:
    def __init__(self, running_single_task: bool = False):
        self.device_id: str = current_app.config['DEVICE_ID']
        self.password: str = current_app.config['PASSWORD']
        self.device_type: str = current_app.config['DEVICE_TYPE']
        self.uploader_base_url: str = current_app.config['DATA_UPLOADER_BASE_URL']
        self.default_hier_block_lib_dir: str = os.environ.get('RELIA_GR_BLOCKS_PATH')
        if not self.default_hier_block_lib_dir:
            self.default_hier_block_lib_dir: str = os.path.expanduser("~/.grc_gnuradio")
        
        if not os.path.exists(self.default_hier_block_lib_dir):
            print(f"Error: RELIA_GR_BLOCKS_PATH not properly configured, path: {self.default_hier_block_lib_dir} not found.", file=sys.stderr, flush=True)
            sys.exit(1)

        adalm_pluto_ip_address = current_app.config['ADALM_PLUTO_IP_ADDRESS']
        if adalm_pluto_ip_address is None:
            print(f"Error: ADALM_PLUTO_IP_ADDRESS environment variable is required")
            sys.exit(1)

        if self.device_type not in ('receiver', 'transmitter'):
            print(f"Error: Unsupported device type: {self.device_type}", file=sys.stderr, flush=True)
            sys.exit(1)

        self.task_is_running_event: threading.Event = threading.Event()
        self.running_single_task = running_single_task
        if running_single_task:
            self.scheduler: AbstractSchedulerClient = NoSchedulerClient()
        else:
            self.scheduler: AbstractSchedulerClient = SchedulerClient()
        self.scheduler_polling_thread: Optional[threading.Thread] = None

    def run_in_sandbox(self, command: List[str], directory: str) -> subprocess.Popen:
        """
        Run the command in a firejail sandbox
        """
        use_firejail = current_app.config['USE_FIREJAIL']
        if use_firejail:
            ip_address = current_app.config['FIREJAIL_IP_ADDRESS']
            interface = current_app.config['FIREJAIL_INTERFACE']
            user = os.getenv('USER') or 'relia'
            profile = '\n'.join([
                        f"net {interface}",
                        f"ip {ip_address}",
                        f"whitelist /home/{user}/.gr_fftw_wisdom",
                        f"whitelist /home/{user}/relia-blocks",
                        f"read-only /home/{user}/relia-blocks",
                        f"whitelist /home/{user}/.gnuradio/prefs",
                        f"read-only /home/{user}/.gnuradio/prefs",
                        f"read-only /home/{user}/.bashrc",
                        f"read-only /home/{user}/.profile",
                        f"whitelist /home/{user}/.grc_gnuradio",
                        f"read-only /home/{user}/.grc_gnuradio",
                        f"whitelist /home/{user}/.cache/grc_gnuradio",                        
                        f"whitelist {directory}",
                    ])
            # net br0
            # ip 10.10.20.2

            # include /etc/firejail/disable-common.inc
            # include /etc/firejail/disable-devel.inc
            # include /etc/firejail/disable-exec.inc
            # include /etc/firejail/disable-passwdmgr.inc
            # include /etc/firejail/disable-xdg.inc
            # whitelist /tmp/relia-*

            # blacklist /home/relia/relia-gr-runner
            # read-only /home/relia/.bashrc
            # read-only /home/relia/.profile
            open(os.path.join(directory, 'firejail.profile'), 'w').write(profile)

            print(f"[{time.asctime()}] firejail.profile generated at {os.path.join(directory, 'firejail.profile')}")
            print(f"[{time.asctime()}] The content:")
            print(profile)

            print(f"[{time.asctime()}] The contents of the folder now are:")
            print(glob.glob(f"{directory}/*"))

            firejail_command = ['firejail', '--profile=firejail.profile']
            firejail_command.extend(command)
            print(f"[{time.asctime()}] Running command inside the firejail sandbox: {' '.join(command)}")
            print(f"[{time.asctime()}] So in reality it looks like: {' '.join(firejail_command)}")
            print(f"[{time.asctime()}] Running command inside the firejail sandbox: {' '.join(command)}", file=sys.stderr)
            print(f"[{time.asctime()}] So in reality it looks like: {' '.join(firejail_command)}", file=sys.stderr, flush=True)
            command_to_run = firejail_command
        else:
            print(f"[{time.asctime()}] Running command outside any sandbox: {' '.join(command)}")
            print(f"[{time.asctime()}] Running command outside any sandbox: {' '.join(command)}", file=sys.stderr, flush=True)
            command_to_run = command

        return subprocess.Popen(command_to_run, cwd=directory, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
    
    def compile_grc_filename_into_python(self, directory: str, grc_manager: GrcManager, device_data: TaskAssignment, init_time: float) -> bool:
        """
        Compile the GRC into Python code

        Return True if we have to finish this task immediately.
        """
        grc_filename = os.path.join(directory, 'user_file.grc')
        grc_manager.save(directory, 'user_file.grc')

        command = ['grcc', grc_filename, '-o', directory]

        if self.must_stop_task(device_data, init_time):
            self.report_and_stop_task(device_data, init_time)
            return True

        p = self.run_in_sandbox(command, directory)
        while p.poll() is None:
            if self.must_stop_task(device_data, init_time):
                p.terminate()
                self.report_and_stop_task(device_data, init_time)
                return True
            
            time.sleep(0.1)

        stdout, stderr = p.communicate()
        if p.returncode != 0:                 
            print(f"[{time.asctime()}] The process (GNU Radio Compiler) stopped with return code: {p.returncode}. Calling self.early_terminate...", file=sys.stderr, flush=True)
            print(f"[{time.asctime()}] Output: {stdout}", file=sys.stderr, flush=True)
            print(f"[{time.asctime()}] Error: {stderr}", file=sys.stderr, flush=True)
            self.scheduler.error_message_delivery(device_data.taskIdentifier, stdout + "\n" + stderr)
            self.early_terminate(device_data.taskIdentifier)
            return True
        
        print(f"[{time.asctime()}] The process (GNU Radio Compiler) finished successfully.", file=sys.stderr, flush=True)
        
        return False

    def run_task_in_directory(self, directory: str, grc_manager: Optional[GrcManager], device_data: TaskAssignment, init_time: float, target_filename: str):
        """
        Run a particular GRC file (from grc_manager) in a directory.
        """
        py_filename = os.path.join(directory, f'{target_filename}.py')

        relia_json = json.dumps({
            'uploader_base_url': self.uploader_base_url,
            'session_id': device_data.sessionIdentifier,
            'task_id': device_data.taskIdentifier,
            'device_id': self.device_id,
        }, indent=4)

        print(f"[{time.asctime()}] relia.json generated in directory {directory}", file=sys.stderr, flush=True)
        print(relia_json, file=sys.stderr, flush=True)

        open(os.path.join(directory, 'relia.json'), 'w').write(relia_json) 

        if device_data.fileType == 'py':
            file_content = device_data.fileContent
            if current_app.config['ADALM_PLUTO_IP_ADDRESS']:
                file_content = file_content.replace("**RELIA_REPLACE_WITH_ADALM_PLUTO_IP_ADDRESS**", current_app.config['ADALM_PLUTO_IP_ADDRESS'])
            if current_app.config['RED_PITAYA_IP_ADDRESS']:
                file_content = file_content.replace("**RELIA_REPLACE_WITH_RED_PITAYA_IP_ADDRESS**", current_app.config['RED_PITAYA_IP_ADDRESS'])
            # It was already compiled, no need to re-compile
            open(py_filename, 'w').write(file_content)
        else:
            if self.compile_grc_filename_into_python(directory, grc_manager, device_data, init_time):
                return

        # TODO: in the future, instead of waiting a fixed time, stop the process 10 seconds AFTER the t.start() in the Python code inside the code
        gr_python_initial_time: float = time.time()
        p = self.run_in_sandbox([sys.executable, py_filename], directory)
        if p.poll() is None:
            print(f"[{time.asctime()}] The process ({py_filename}) started.", file=sys.stderr, flush=True)

        last_message = time.time()

        while p.poll() is None:
            if self.must_stop_task(device_data, init_time):
                p.terminate()
                self.report_and_stop_task(device_data, init_time)
                break
            
            if time.time() - last_message > 5:
                print(f"[{time.asctime()}] The process ({py_filename}) is still running.", file=sys.stderr, flush=True)
                last_message = time.time()
            
            time.sleep(0.1)
            elapsed = time.time() - gr_python_initial_time
            max_gr_python_execution_time = current_app.config['MAX_GR_PYTHON_EXECUTION_TIME']
            if elapsed > max_gr_python_execution_time:
                p.terminate()
                print(f"[{time.asctime()}] Running the GR Python code for over {max_gr_python_execution_time} seconds (value from MAX_GR_PYTHON_EXECUTION_TIME)... Calling self.early_terminate...", file=sys.stderr, flush=True)
                self.early_terminate(device_data.taskIdentifier)
                break

        print(f"[{time.asctime()}] Waiting for the process to finish...", file=sys.stderr, flush=True)
        try:
            p.wait(timeout=10)
        except Exception as err:
            traceback.print_exc()

        # If terminate() was not enough, kill it
        if p.poll() is None:
            try:
                p.kill()
                p.wait(timeout=10)
            except:
                traceback.print_exc()

        stdout, stderr = p.communicate()
        if p.returncode != 0:
            print(f"[{time.asctime()}] The process (GNU Radio) stopped with return code: {p.returncode}. Calling self.early_terminate...", file=sys.stderr, flush=True)
            print(f"[{time.asctime()}] Output: {stdout}", file=sys.stderr, flush=True)
            print(f"[{time.asctime()}] Error: {stderr}", file=sys.stderr, flush=True)
            self.scheduler.error_message_delivery(device_data.taskIdentifier, stdout + "\n" + stderr)
            self.early_terminate(device_data.taskIdentifier)
            return
        
        print(f"[{time.asctime()}] The process ({py_filename}) finished successfully.", file=sys.stderr, flush=True)
        print(f"[{time.asctime()}] Output: {stdout}", file=sys.stderr, flush=True)
        print(f"[{time.asctime()}] Error: {stderr}", file=sys.stderr, flush=True)
        
    def must_stop_task(self, device_data: TaskAssignment, init_time: float) -> bool:
        """
        If the scheduler has cancelled the task for any reason (user, other device, whatever)
        OR if the max time has passed, then this task must stop.
        """
        if not self.scheduler_reports_task_still_active() or time.perf_counter() - init_time > device_data.maxTime:
            return True
        return False
    
    def report_and_stop_task(self, device_data: TaskAssignment, init_time: float):
        """
        Print a message indicating that the task has finished and call early_terminate()
        """
        if not self.scheduler_reports_task_still_active():
            print(f"[{time.asctime()}] Scheduler stopped. Stopping task {device_data.taskIdentifier}...", file=sys.stderr, flush=True)
        else:
            print(f"[{time.asctime()}] Timed out (time elapsed: {time.perf_counter() - init_time}; max time: {device_data.maxTime}", file=sys.stderr, flush=True)
        self.early_terminate(device_data.taskIdentifier)

    def scheduler_reports_task_still_active(self) -> bool:
        """
        Returns true if the RELIA Scheduler is still saying that the task is active.

        For example, if the student cancels the task, or the other device (transmitter/receiver) cancels the task
        or there is an error this will return False.
        """
        if self.running_single_task:
            return True
        
        # TODO: clean this logic at some point
        if self.scheduler_polling_thread.is_alive():
            return True
        return False
    
    def _delete_existing_data_from_server(self, device_data: TaskAssignment):
        """
        The device might have still some data stored in the server, from previous executions or similar. 
        This method deletes all the data.
        """
        session_id = device_data.sessionIdentifier

        delete_url = self.uploader_base_url + f"api/download/sessions/{session_id}/devices/{self.device_id}"
        print(f"[{time.asctime()}] Resetting device {self.device_id}: {delete_url}", flush=True)
        print(f"[{time.asctime()}] Resetting device {self.device_id}: {delete_url}", file=sys.stderr, flush=True)
        delete_response = requests.delete(delete_url, timeout=(30,30))
        try:
            delete_response.raise_for_status()
        except Exception as err:
            print(f"[{time.asctime()}] Error deleting previous device data: {err}; {delete_response.content}", file=sys.stderr, flush=True)
        else:
            print(f"[{time.asctime()}] Result of resetting device {self.device_id}:")
            print(f"[{time.asctime()}] Result of resetting device {self.device_id}:", file=sys.stderr, flush=True)
            print(json.dumps(delete_response.json(), indent=4))
            print(json.dumps(delete_response.json(), indent=4), file=sys.stderr, flush=True)

    def run_task(self, device_data: TaskAssignment):
        """
        Runs a task on this device.
        """
        init_time = time.perf_counter()

        # Launch a separate thread that polls on the scheduler (to notify that we are processing the request)
        self.task_is_running_event.clear()
        self.scheduler_polling_thread = threading.Thread(target=self.scheduler_poll, args=(device_data.taskIdentifier, self.task_is_running_event), daemon=True)
        self.scheduler_polling_thread.start()

        target_filename = 'target_file'
        if device_data.fileType == 'py':
            grc_manager = None
        else:
            grc_file_content = device_data.fileContent
            
            # Create a GRC Manager that will modify the YAML as needed to adapt to RELIA
            grc_manager = GrcManager(grc_file_content, target_filename, self.default_hier_block_lib_dir)

        # Report to the server that we are starting fresh and therefore we do want to delete any existing data
        # of the particular device in the particular session
        # self._delete_existing_data_from_server(device_data)
        # TODO: Maybe we do not need to delete data anymore in this step

        tmpdir_kwargs = {}
        if os.name == 'nt' or "microsoft" in platform.platform().lower():
            tmpdir_kwargs['ignore_cleanup_errors'] = True
        
        # Create a temporary directory and run the task inside
        with tempfile.TemporaryDirectory(prefix='relia-', **tmpdir_kwargs) as tmpdir:
            print(f"[{time.asctime()}] {self.device_type.title()} running in temporary directory {tmpdir}...", flush=True)
            print(f"[{time.asctime()}] {self.device_type.title()} running in temporary directory {tmpdir}...", file=sys.stderr, flush=True)
            self.run_task_in_directory(tmpdir, grc_manager, device_data, init_time, target_filename)
        
        # We have finished: notify other threads that this is over and report to the scheduler server that this is over
        self.task_is_running_event.set()
        print(f"{self.device_type.title()} completing task", flush=True)
        print(f"{self.device_type.title()} completing task", file=sys.stderr, flush=True)
        self.scheduler.complete_assignments(device_data.taskIdentifier)

    def run_forever(self):
        while True:
            print(f"[{time.asctime()}] {self.device_type.title()} requesting assignment...", flush=True)
            print(f"[{time.asctime()}] {self.device_type.title()} requesting assignment...", file=sys.stderr, flush=True)
            try:
                if self.scheduler_polling_thread is not None:
                    self.task_is_running_event.set()
                    self.scheduler_polling_thread.join()
                    self.scheduler_polling_thread = None
                    print(f"[{time.asctime()}] Scheduler polling thread stopped.", file=sys.stderr, flush=True)

                self.task_is_running_event.clear()

                device_data: Optional[TaskAssignment] = self.scheduler.get_assignments()
                if not device_data:
                    print(f"Error trying to get assignments. Waiting a bit...")
                    time.sleep(5)
                    continue

                if device_data.taskIdentifier:
                    self.run_task(device_data)
                else:
                    print("No assignments", file=sys.stderr, flush=True)

            except Exception as err:
                print(f"Uncaught processing tasks: {err}", file=sys.stderr, flush=True)
                traceback.print_exc()
                sys.stderr.flush()
                time.sleep(2)

    def early_terminate(self, task_identifier):
        """
        Terminate the current execution and report to the scheduler and to the scheduler poll thread.
        """
        print(f"[{time.asctime()}] Task being purged due to deletion", flush=True)
        print(f"[{time.asctime()}] Task being purged due to deletion", file=sys.stderr, flush=True)
        self.task_is_running_event.set()
        self.scheduler.complete_assignments(task_identifier)

    def scheduler_poll(self, task_identifier: str, task_is_running_event: threading.Event):
        """
        This function is launched in a different thread. It will be checking the status of the task.
        Whenever the statusi s delete or completed, it will stop running.

        If the server stops at any point, there are several points that are checking it to know if
        they should stop everything.
        """
        while not task_is_running_event.is_set():
            event_set = task_is_running_event.wait(timeout=5)
            if event_set:
                print(f"[{time.asctime()}] Thread event set. Stopping task status checking thread", flush=True)
                print(f"[{time.asctime()}] Thread event set. Stopping task status checking thread", file=sys.stderr, flush=True)
                break

            task_assignment_status = self.scheduler.check_assignment_status(task_identifier)
            print(f"[{time.asctime()}] Status of the task {task_identifier}: {task_assignment_status}", flush=True)
            print(f"[{time.asctime()}] Status of the task {task_identifier}: {task_assignment_status}", file=sys.stderr, flush=True)
            # If the status is completed or deleted, stop
            if task_assignment_status in ("deleted", "completed"):
                print(f"[{time.asctime()}] Stopping task polling thread", flush=True)
                print(f"[{time.asctime()}] Stopping task polling thread", file=sys.stderr,  flush=True)
                break
