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

        device_id = current_app.config['DEVICE_ID']
        password = current_app.config['PASSWORD']
        device_type = current_app.config['DEVICE_TYPE']

        SCHEDULER_BASE_URL = current_app.config['SCHEDULER_BASE_URL']
        DATA_UPLOADER_BASE_URL = current_app.config['DATA_UPLOADER_BASE_URL']
        DEFAULT_HIER_BLOCK_LIB_DIR = os.environ.get('RELIA_GR_BLOCKS_PATH')
        TERMINAL_FLAG = True

        thread_event = threading.Event()
        scheduler = SchedulerClient()
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
                       'qtgui_freq_sink_x': 'relia_freq_sink_x',
                      }

        while (True):
             print(f"{device_type.title()} requesting assignment...")
             device_data = scheduler.get_assignments()
             if device_data.taskIdentifier:
                  init_time = time.perf_counter()
                  thread_event.clear()
                  TERMINAL_FLAG = True
                  x = threading.Thread(target=thread_function, args=(scheduler, device_data.taskIdentifier, thread_event), daemon=True)
                  x.start()
                  if device_type == 'receiver' or device_type == 'transmitter':
                      grc_file_content = device_data.grcFileContent
                  else:
                      scheduler.error_message_delivery(device_data.taskIdentifier, f"Unsupported type: {device_type}")
                      early_terminate(scheduler, device_data.taskIdentifier)
                      TERMINAL_FLAG = False
                      
                  grc_content = yaml.load(grc_file_content, Loader=Loader)
                  target_filename = 'target_file'
                  grc_content['options']['parameters']['id'] = target_filename
                  grc_content['options']['parameters']['generate_options'] = 'no_gui'

                  for block in grc_content['blocks']:
                       if block['id'] in conversions:
                            block['id'] = conversions[block['id']]
                            block_yml = os.path.join(DEFAULT_HIER_BLOCK_LIB_DIR, f"{block['id']}.block.yml")
                            if not os.path.exists(block_yml):
                                 scheduler.error_message_delivery(device_data.taskIdentifier, f"The file {block_yml} does not exists. Have you recently installed relia-blocks?")
                                 early_terminate(scheduler, device_data.taskIdentifier)
                                 TERMINAL_FLAG = False

                  uploader_base_url = DATA_UPLOADER_BASE_URL
                  session_id = device_data.sessionIdentifier

                  print(f"Resetting device {device_id}")
                  print(requests.delete(uploader_base_url + f"api/download/sessions/{session_id}/devices/{device_id}").json())

                  tmpdir = tempfile.TemporaryDirectory(prefix='relia-', ignore_cleanup_errors=True)
                  grc_filename = os.path.join(tmpdir.name, 'user_file.grc')
                  py_filename = os.path.join(tmpdir.name, f'{target_filename}.py')

                  open(grc_filename, 'w').write(yaml.dump(grc_content, Dumper=Dumper))

                  open(os.path.join(tmpdir.name, 'relia.json'), 'w').write(json.dumps({
                       'uploader_base_url': uploader_base_url,
                       'session_id': session_id,
                       'device_id': device_id,
                  }))

                  command = ['grcc', grc_filename, '-o', tmpdir.name]
                  if not x.is_alive() or time.perf_counter() - init_time > device_data.maxTime:
                       early_terminate(scheduler, device_data.taskIdentifier)
                       TERMINAL_FLAG = False

                  if TERMINAL_FLAG:
                       p = subprocess.Popen(command, cwd=tmpdir.name, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
                       while p.poll() is None:
                            if not x.is_alive() or time.perf_counter() - init_time > device_data.maxTime:
                                 p.terminate()
                                 early_terminate(scheduler, device_data.taskIdentifier)
                                 TERMINAL_FLAG = False
                                 break

                       output, error = p.communicate()
                       if p.returncode != 0:                 
                            scheduler.error_message_delivery(device_data.taskIdentifier, output + "\n" + error)
                            early_terminate(scheduler, device_data.taskIdentifier)
                            TERMINAL_FLAG = False

                  if TERMINAL_FLAG:
                       p = subprocess.Popen([sys.executable, py_filename], cwd=tmpdir.name, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
                       while p.poll() is None:
                            if not x.is_alive() or time.perf_counter() - init_time > device_data.maxTime:
                                 p.terminate()
                                 early_terminate(scheduler, device_data.taskIdentifier)
                                 TERMINAL_FLAG = False
                                 break

                       output, error = p.communicate()
                       if p.returncode != 0:
                            scheduler.error_message_delivery(device_data.taskIdentifier, output + "\n" + error)
                            early_terminate(scheduler, device_data.taskIdentifier)
                            TERMINAL_FLAG = False
                            
                  if TERMINAL_FLAG:
                       thread_event.set()
                       tmpdir.cleanup()
                       print(f"{device_type.title()} completing task")
                       scheduler.complete_assignments(device_data.taskIdentifier)
             else:
                  print("Previous assignment failed; do nothing")
                  time.sleep(1)

    return app

def early_terminate(scheduler, task_identifier):
    print("Task being purged due to deletion")
    scheduler.complete_assignments(task_identifier)

def thread_function(scheduler, task_identifier, thread_event):
    while not thread_event.is_set():
        if scheduler.check_assignment(task_identifier) == "deleted":
            break
        time.sleep(2)
