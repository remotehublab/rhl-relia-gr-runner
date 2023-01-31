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

    if config_name in ['development', 'default'] and '--with-threads' not in sys.argv and 'run' in sys.argv:
        print("***********************************************************")
        print("*                                                         *")
        print("*               I M P O R T A N T                         *")
        print("*                                                         *")
        print("*   You must pass --with-threads when testing receiver    *")
        print("*                                                         *")
        print("***********************************************************")

    with app.app_context():
        global THREAD_EVENT
        global SCHEDULER_BASE_URL
        # NOTE: Cannot use environment variable if both the transmitter and receiver are operating on the same device
        # DEVICE_ID = current_app.config['DEVICE_ID']
        DEVICE_ID = 'uw-s1i1:r'
        PASSWORD = current_app.config['PASSWORD']
        SCHEDULER_BASE_URL = current_app.config['SCHEDULER_BASE_URL']
        DATA_UPLOADER_BASE_URL = current_app.config['DATA_UPLOADER_BASE_URL']
        DEFAULT_HIER_BLOCK_LIB_DIR = os.environ.get('RELIA_GR_BLOCKS_PATH')
        THREAD_EVENT = threading.Event()
        x = {}
        d = 1

    while (True):
         d += 1
         print("Receiver requesting assignment...")
         device_data = requests.get(SCHEDULER_BASE_URL + "scheduler/devices/tasks/receiver?max_seconds=5", headers={'relia-device': DEVICE_ID, 'relia-password': PASSWORD}, timeout=(30,30)).json()
         if device_data.get('taskIdentifier'):
              THREAD_EVENT.clear()
              x["thread{0}".format(d)] = threading.Thread(target=thread_function, args=(device_data.get('taskIdentifier'),), daemon=True)
              x["thread{0}".format(d)].start()
              grc_content = yaml.load(device_data.get('grcReceiverFileContent'), Loader=Loader)
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
              if not x["thread{0}".format(d)].is_alive():
                   print("Task being purged due to deletion")
                   device_data = requests.post(SCHEDULER_BASE_URL + "scheduler/devices/tasks/receiver/" + device_data.get('taskIdentifier'), headers={'relia-device': DEVICE_ID, 'relia-password': PASSWORD}, timeout=(30,30)).json()
                   print(device_data.get('status'))
              try:
                   p = subprocess.Popen(command, cwd=tmpdir.name)
                   while p.poll() is None:
                        if not x["thread{0}".format(d)].is_alive():
                             p.terminate()
                             print("Task being purged due to deletion")
                             device_data = requests.post(SCHEDULER_BASE_URL + "scheduler/devices/tasks/receiver/" + device_data.get('taskIdentifier'), headers={'relia-device': DEVICE_ID, 'relia-password': PASSWORD}, timeout=(30,30)).json()
                             print(device_data.get('status'))
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

              p = subprocess.Popen([sys.executable, py_filename], cwd=tmpdir.name)
              while p.poll() is None:
                   if not x["thread{0}".format(d)].is_alive():
                        p.terminate()
                        print("Task being purged due to deletion")
                        device_data = requests.post(SCHEDULER_BASE_URL + "scheduler/devices/tasks/receiver/" + device_data.get('taskIdentifier'), headers={'relia-device': DEVICE_ID, 'relia-password': PASSWORD}, timeout=(30,30)).json()
                        print(device_data.get('status'))
              THREAD_EVENT.set()
              tmpdir.cleanup()
              print("Receiver completing task")
              device_data = requests.post(SCHEDULER_BASE_URL + "scheduler/devices/tasks/receiver/" + device_data.get('taskIdentifier'), headers={'relia-device': DEVICE_ID, 'relia-password': PASSWORD}, timeout=(30,30)).json()
              print(device_data.get('status'))
         else:
              print("Previous assignment failed; do nothing")

    return app

def thread_function(task_identifier):
    while not THREAD_EVENT.is_set():
         device_data = requests.get(SCHEDULER_BASE_URL + "scheduler/user/tasks/" + task_identifier, timeout=(30,30)).json()
         if device_data.get('status') == "deleted":
              break
