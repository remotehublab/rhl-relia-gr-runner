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

from relia_gr_runner.grc_manager import GrcManager

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('-i', '--input', type=pathlib.Path, required=True)
    parser.add_argument('--host', default="localhost")
    parser.add_argument('--base-url', default=None)
    parser.add_argument('--device-id', default='my-device-id')
    parser.add_argument('--session-id', default='my-session-id')
    args = parser.parse_args()

    grc_content_serialized = open(args.input).read()

    target_filename = 'target_file'

    grc_processor = GrcManager(grc_content_serialized, target_filename)

    # TODO
    if args.base_url:
        uploader_base_url = args.base_url
    else:
        uploader_base_url = f'http://{args.host}:6001'
    session_id = args.session_id
    device_id = args.device_id

    print(f"Resetting device {device_id}")
    print(requests.delete(uploader_base_url + f"/api/download/sessions/{session_id}/devices/{device_id}").json())

    with tempfile.TemporaryDirectory(prefix='relia-') as tmpdir:
        grc_filename = os.path.join(tmpdir, 'user_file.grc')
        py_filename = os.path.join(tmpdir, f'{target_filename}.py')

        grc_processor.save(tmpdir, 'user_file.grc')

        open(os.path.join(tmpdir, 'relia.json'), 'w').write(json.dumps({
            'uploader_base_url': uploader_base_url,
            'session_id': session_id,
            'device_id': device_id,
        }))

        # Create the "files" directory
        os.mkdir(os.path.join(tmpdir, "files"))

        # TODO: at some point copy the INPUT files (if any)

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
