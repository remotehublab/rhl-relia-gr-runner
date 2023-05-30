import os
import sys
import time
import json
import platform
import tempfile
import threading
import traceback
import subprocess

from typing import List, Optional

import requests

from flask import current_app

from .scheduler import SchedulerClient, TaskAssignment
from .grc_manager import GrcManager

class Processor:
    def __init__(self):
        self.device_id = current_app.config['DEVICE_ID']
        self.password = current_app.config['PASSWORD']
        self.device_type = current_app.config['DEVICE_TYPE']
        self.uploader_base_url = current_app.config['DATA_UPLOADER_BASE_URL']
        self.default_hier_block_lib_dir = os.environ.get('RELIA_GR_BLOCKS_PATH')
        if not self.default_hier_block_lib_dir:
            self.default_hier_block_lib_dir = os.path.expanduser("~/.grc_gnuradio")
        
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

        self.thread_event = threading.Event()
        self.scheduler = SchedulerClient()
        self.scheduler_polling_thread: Optional[threading.Thread] = None

    def run_in_sandbox(self, command: List[str], tmpdir: str) -> subprocess.Popen:
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
                        f"whitelist {tmpdir}"
                    ])
            open(os.path.join(tmpdir, 'firejail.profile'), 'w').write(profile)

            firejail_command = ['firejail', '--profile=firejail.profile']
            firejail_command.extend(command)
            print(f"[{time.asctime()}] Running command inside the firejail sandbox: {' '.join(command)}")
            print(f"[{time.asctime()}] So in reality it looks like: {' '.join(firejail_command)}")
            command_to_run = firejail_command
        else:
            print(f"[{time.asctime()}] Running command outside any sandbox: {' '.join(command)}")
            command_to_run = command

        return subprocess.Popen(command_to_run, cwd=tmpdir, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)


    def run_task_in_directory(self, tmpdir: str, grc_manager: GrcManager, session_id: str, device_data: dict, init_time: float, target_filename: str):
        grc_filename = os.path.join(tmpdir, 'user_file.grc')
        py_filename = os.path.join(tmpdir, f'{target_filename}.py')

        grc_manager.save(tmpdir, 'user_file.grc')

        open(os.path.join(tmpdir, 'relia.json'), 'w').write(json.dumps({
            'uploader_base_url': self.uploader_base_url,
            'session_id': session_id,
            'device_id': self.device_id,
        })) 

        command = ['grcc', grc_filename, '-o', tmpdir]
        if not self.scheduler_polling_thread.is_alive() or time.perf_counter() - init_time > device_data.maxTime:
            if not self.scheduler_polling_thread.is_alive():
                print(f"[{time.asctime()}] Scheduler polling thread stopped. Calling self.early_terminate...", file=sys.stderr, flush=True)
            else:
                print(f"[{time.asctime()}] Timed out (time elapsed: {time.perf_counter() - init_time}; max time: {device_data.maxTime}", file=sys.stderr, flush=True)
            self.early_terminate(device_data.taskIdentifier)
            return

        p = self.run_in_sandbox(command, tmpdir)
        while p.poll() is None:
            if not self.scheduler_polling_thread.is_alive() or time.perf_counter() - init_time > device_data.maxTime:
                p.terminate()
                if not self.scheduler_polling_thread.is_alive():
                    print(f"[{time.asctime()}] Scheduler polling thread stopped. Calling self.early_terminate...", file=sys.stderr, flush=True)
                else:
                    print(f"[{time.asctime()}] Timed out (time elapsed: {time.perf_counter() - init_time}; max time: {device_data.maxTime}", file=sys.stderr, flush=True)
                self.early_terminate(device_data.taskIdentifier)
                return
            time.sleep(0.1)

        output, error = p.communicate()
        if p.returncode != 0:                 
            print(f"[{time.asctime()}] The process (GNU Radio) stopped with return code: {p.returncode}. Calling self.early_terminate...", file=sys.stderr, flush=True)
            print(f"[{time.asctime()}] Output: {output}", file=sys.stderr, flush=True)
            print(f"[{time.asctime()}] Error: {error}", file=sys.stderr, flush=True)
            self.scheduler.error_message_delivery(device_data.taskIdentifier, output + "\n" + error)
            self.early_terminate(device_data.taskIdentifier)
            return

        # TODO: in the future, instead of waiting a fixed time, stop the process 10 seconds AFTER the t.start() in the Python code inside the code
        gr_python_initial_time: float = time.time()
        p = self.run_in_sandbox([sys.executable, py_filename], tmpdir)
        while p.poll() is None:
            if not self.scheduler_polling_thread.is_alive() or time.perf_counter() - init_time > device_data.maxTime:
                p.terminate()
                if not self.scheduler_polling_thread.is_alive():
                    print(f"[{time.asctime()}] Scheduler polling thread stopped. Calling self.early_terminate...", file=sys.stderr, flush=True)
                else:
                    print(f"[{time.asctime()}] Timed out (time elapsed: {time.perf_counter() - init_time}; max time: {device_data.maxTime}", file=sys.stderr, flush=True)

                self.early_terminate(device_data.taskIdentifier)
                return
            time.sleep(0.1)
            elapsed = time.time() - gr_python_initial_time
            max_gr_python_execution_time = current_app.config['MAX_GR_PYTHON_EXECUTION_TIME']
            if elapsed > max_gr_python_execution_time:
                p.terminate()
                print(f"[{time.asctime()}] Running the GR Python code for over {max_gr_python_execution_time}... Calling self.early_terminate...", file=sys.stderr, flush=True)
                self.early_terminate(device_data.taskIdentifier)
                return

        output, error = p.communicate()
        if p.returncode != 0:
            print(f"[{time.asctime()}] The process (GNU Radio) stopped with return code: {p.returncode}. Calling self.early_terminate...", file=sys.stderr, flush=True)
            print(f"[{time.asctime()}] Output: {output}", file=sys.stderr, flush=True)
            print(f"[{time.asctime()}] Error: {error}", file=sys.stderr, flush=True)
            self.scheduler.error_message_delivery(device_data.taskIdentifier, output + "\n" + error)
            self.early_terminate(device_data.taskIdentifier)
            return        

    def run_task(self, device_data: dict):
        """
        Runs a task on a device.
        """
        init_time = time.perf_counter()
        self.thread_event.clear()
        self.scheduler_polling_thread = threading.Thread(target=self.thread_function, args=(device_data.taskIdentifier, self.thread_event), daemon=True)
        self.scheduler_polling_thread.start()
        grc_file_content = device_data.grcFileContent
        
        target_filename = 'target_file'
        grc_manager = GrcManager(grc_file_content, target_filename, self.default_hier_block_lib_dir)

        session_id = device_data.sessionIdentifier

        print(f"[{time.asctime()}] Resetting device {self.device_id}", flush=True)
        delete_response = requests.delete(self.uploader_base_url + f"api/download/sessions/{session_id}/devices/{self.device_id}")
        try:
            delete_response.raise_for_status()
            print(delete_response.json())
        except Exception as err:
            print(f"[{time.asctime()}] Error deleting previous device data: {err}; {delete_response.content}", file=sys.stderr, flush=True)


        tmpdir_kwargs = {}
        if os.name == 'nt' or "microsoft" in platform.platform().lower():
            tmpdir_kwargs['ignore_cleanup_errors'] = True
        
        with tempfile.TemporaryDirectory(prefix='relia-', **tmpdir_kwargs) as tmpdir:
            self.run_task_in_directory(tmpdir, grc_manager, session_id, device_data, init_time, target_filename)
        
        self.thread_event.set()
        print(f"{self.device_type.title()} completing task", flush=True)
        self.scheduler.complete_assignments(device_data.taskIdentifier)

    def run_forever(self):
        while True:
            print(f"[{time.asctime()}] {self.device_type.title()} requesting assignment...", flush=True)
            print(f"[{time.asctime()}] {self.device_type.title()} requesting assignment...", file=sys.stderr, flush=True)
            try:
                if self.scheduler_polling_thread is not None:
                    self.thread_event.set()
                    self.scheduler_polling_thread.join()
                    self.scheduler_polling_thread = None
                    print(f"[{time.asctime()}] Scheduler polling thread stopped.", file=sys.stderr, flush=True)

                self.thread_event.clear()

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
        print(f"[{time.asctime()}] Task being purged due to deletion", flush=True)
        print(f"[{time.asctime()}] Task being purged due to deletion", file=sys.stderr, flush=True)
        self.thread_event.set()
        self.scheduler.complete_assignments(task_identifier)

    def thread_function(self, task_identifier, thread_event):
        while not thread_event.is_set():
            time.sleep(5)
            task_assignment_status = self.scheduler.check_assignment(task_identifier)
            print(f"[{time.asctime()}] Status of the task: {task_assignment_status}", flush=True)
            if task_assignment_status in ("deleted", "completed"):
                print(f"[{time.asctime()}] Stopping task status checking thread", flush=True)
                break
