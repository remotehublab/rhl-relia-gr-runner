import os
import sys
from flask import Flask, render_template, current_app
import json
import time
import shutil
import pathlib
import tempfile
import argparse
import subprocess
import requests
import yaml
import threading
try:
    from yaml import CLoader as Loader, CDumper as Dumper
except ImportError:
    from yaml import Loader, Dumper

from config import configurations

def create_app(config_name: str = 'default'):

    # Based on Flasky https://github.com/miguelgrinberg/flasky
    app = Flask(__name__)
    app.config.from_object(configurations[config_name])

    @app.cli.command('process-tasks')
    def process_tasks():
        """
        Process tasks
        """
        from .scheduler import SchedulerClient
        global TERMINAL_FLAG
        global SCHEDULER_BASE_URL
        global DEVICE_ID
        DEVICE_ID = current_app.config['DEVICE_ID']
        password = current_app.config['PASSWORD']
        SCHEDULER_BASE_URL = current_app.config['SCHEDULER_BASE_URL']
        DATA_UPLOADER_BASE_URL = current_app.config['DATA_UPLOADER_BASE_URL']
        DEFAULT_HIER_BLOCK_LIB_DIR = os.environ.get('RELIA_GR_BLOCKS_PATH')
        TERMINAL_FLAG = True

        thread_event = threading.Event()
        device_type = current_app.config['DEVICE_TYPE']
        x = {}
        d = 1

        scheduler = SchedulerClient()

        while (True):
             d += 1
             print(f"{device_type.title()} requesting assignment...")
             device_data = scheduler.get_assignments()
             if device_data.get('taskIdentifier'):
                  init_time = time.perf_counter()
                  thread_event.clear()
                  TERMINAL_FLAG = True
                  x["thread{0}".format(d)] = threading.Thread(target=thread_function, args=(device_data.get('taskIdentifier'), thread_event), daemon=True)
                  x["thread{0}".format(d)].start()
                  if device_type == 'receiver':
                      grc_file_content = device_data.get('grcReceiverFileContent')
                  elif device_type == 'transmitter':
                      grc_file_content = device_data.get('grcTransmitterFileContent')
                  else:
                      raise Exception(f"Unsupported type: {device_type}")
                  grc_content = yaml.load(grc_file_content, Loader=Loader)
                  target_filename = 'target_file'
                  grc_content['options']['parameters']['id'] = target_filename
                  grc_content['options']['parameters']['generate_options'] = 'no_gui'

                  conversions = {
                       'qtgui_time_sink_x': 'relia_time_sink_x',
                       'qtgui_const_sink_x': 'relia_const_sink_x',
                       'qtgui_vector_sink_f': 'relia_vector_sink_f',
                       'qtgui_histogram_sink_x': 'relia_histogram_sink_x',
                       'variable_qtgui_range': 'variable_relia_range',
                       'variable_qtgui_check_box': 'variable_relia_check_box',
                       'variable_qtgui_push_button': 'variable_relia_push_button',
                       'variable_qtgui_chooser': 'variable_relia_chooser',
                       'qtgui_number_sink': 'relia_number_sink',      
                       'eye_plot': 'relia_eye_plot_x',      
                  }

                  for block in grc_content['blocks']:
                       if block['id'] in conversions:
                            block['id'] = conversions[block['id']]
                            block_yml = os.path.join(DEFAULT_HIER_BLOCK_LIB_DIR, f"{block['id']}.block.yml")
                            if not os.path.exists(block_yml):
                                 raise Exception(f"The file {block_yml} does not exists. Have you recently installed relia-blocks?")

                  uploader_base_url = DATA_UPLOADER_BASE_URL
                  session_id = device_data.get('sessionIdentifier')

                  print(f"Resetting device {DEVICE_ID}")
                  print(requests.delete(uploader_base_url + f"api/download/sessions/{session_id}/devices/{DEVICE_ID}").json())

                  tmpdir = tempfile.TemporaryDirectory(prefix='relia-', ignore_cleanup_errors=True)
                  grc_filename = os.path.join(tmpdir.name, 'user_file.grc')
                  py_filename = os.path.join(tmpdir.name, f'{target_filename}.py')

                  open(grc_filename, 'w').write(yaml.dump(grc_content, Dumper=Dumper))

                  open(os.path.join(tmpdir.name, 'relia.json'), 'w').write(json.dumps({
                       'uploader_base_url': uploader_base_url,
                       'session_id': session_id,
                       'device_id': DEVICE_ID,
                  }))

                  command = ['grcc', grc_filename, '-o', tmpdir.name]
                  if not x["thread{0}".format(d)].is_alive() or time.perf_counter() - init_time > 120:
                       early_terminate(device_data.get('taskIdentifier'))
                       TERMINAL_FLAG = False

                  if TERMINAL_FLAG:
                       try:
                            p = subprocess.Popen(command, cwd=tmpdir.name)
                            while p.poll() is None:
                                 if not x["thread{0}".format(d)].is_alive() or time.perf_counter() - init_time > 120:
                                      p.terminate()
                                      early_terminate(device_data.get('taskIdentifier'))
                                      TERMINAL_FLAG = False
                                      break
                       except subprocess.CalledProcessError as err:
                            print("Error processing grcc:", file=sys.stderr)
                            print("", file=sys.stderr)
                            print(f" $ {' '.join(command)}", file=sys.stderr)
                            print(err.output, file=sys.stderr)
                            print(" $", file=sys.stderr)
                            print("", file=sys.stderr)

                            tmp_directory = pathlib.Path(tempfile.gettempdir())
                            error_tmp_directory = tmp_directory / f"relia-error-tmp-{time.time()}"

                            os.mkdir(error_tmp_directory)
                            shutil.copy(os.path.join(tmpdir, 'user_file.grc'), error_tmp_directory)
                            shutil.copy(os.path.join(tmpdir, 'relia.json'), error_tmp_directory)
                            print(f"You can reproduce it going to the directory {error_tmp_directory} and running the command:", file=sys.stderr)
                            print("", file=sys.stderr)
                            print(f" $ cd {error_tmp_directory}", file=sys.stderr)
                            print(f" $ grcc {error_tmp_directory / 'user_file.grc'} -o {error_tmp_directory}", file=sys.stderr)
                            print("", file=sys.stderr)
                            raise

                  if TERMINAL_FLAG:
                       p = subprocess.Popen([sys.executable, py_filename], cwd=tmpdir.name)
                       while p.poll() is None:
                            if not x["thread{0}".format(d)].is_alive() or time.perf_counter() - init_time > 120:
                                 p.terminate()
                                 early_terminate(device_data.get('taskIdentifier'))
                                 TERMINAL_FLAG = False
                                 break

                  if TERMINAL_FLAG:
                       thread_event.set()
                       tmpdir.cleanup()
                       print(f"{device_type.title()} completing task")
                       device_data = requests.post(SCHEDULER_BASE_URL + f"scheduler/devices/tasks/{device_type}/" + device_data.get('taskIdentifier'), headers={'relia-device': DEVICE_ID, 'relia-password': password}, timeout=(30,30)).json()
                       print(device_data.get('status'))
             else:
                  print("Previous assignment failed; do nothing")

    return app

def early_terminate(task_identifier):
    print("Task being purged due to deletion")
    device_data = requests.post(SCHEDULER_BASE_URL + "scheduler/devices/tasks/{current_app.config['DEVICE_TYPE']}/" + task_identifier, headers={'relia-device': DEVICE_ID, 'relia-password': current_app.config['PASSWORD']}, timeout=(30,30)).json()
    print(device_data.get('message'))

def thread_function(task_identifier, thread_event):
    while not thread_event.is_set():
        device_data = requests.get(SCHEDULER_BASE_URL + "scheduler/user/tasks/" + task_identifier, timeout=(30,30)).json()
        if device_data.get('status') == "deleted":
            break
        time.sleep(2)
