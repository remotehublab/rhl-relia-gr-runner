import os
import sys
import json
import time
import shutil
import pathlib
import tempfile
import argparse
import subprocess

import requests

import yaml
try:
    from yaml import CLoader as Loader, CDumper as Dumper
except ImportError:
    from yaml import Loader, Dumper

# From gnuradio.core.Constants
DEFAULT_HIER_BLOCK_LIB_DIR = os.path.expanduser('~/.grc_gnuradio')

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('-i', '--input', type=pathlib.Path, required=True)
    parser.add_argument('--host')
    args = parser.parse_args()

    grc_content = yaml.load(open(args.input).read(), Loader=Loader)

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

    # TODO
    uploader_base_url = f'http://{args.host or "localhost"}:6001'
    session_id = 'my-session-id'
    device_id = 'my-device-id'

    print(f"Resetting device {device_id}")
    print(requests.delete(uploader_base_url + f"/api/download/sessions/{session_id}/devices/{device_id}").json())

    with tempfile.TemporaryDirectory(prefix='relia-') as tmpdir:
        grc_filename = os.path.join(tmpdir, 'user_file.grc')
        py_filename = os.path.join(tmpdir, f'{target_filename}.py')

        open(grc_filename, 'w').write(yaml.dump(grc_content, Dumper=Dumper))

        open(os.path.join(tmpdir, 'relia.json'), 'w').write(json.dumps({
            'uploader_base_url': uploader_base_url,
            'session_id': session_id,
            'device_id': device_id,
        }))

        command = ['grcc', grc_filename, '-o', tmpdir]

        try:
            print(subprocess.check_output(command, cwd=tmpdir, text=True))
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

        print(tmpdir)

        subprocess.run([sys.executable, py_filename], cwd=tmpdir)

        input("Press any key to finish")

if __name__ == '__main__':
    main()
