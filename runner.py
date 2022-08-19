import os
import sys
import json
import shutil
import pathlib
import tempfile
import argparse
import subprocess

import yaml
try:
    from yaml import CLoader as Loader, CDumper as Dumper
except ImportError:
    from yaml import Loader, Dumper

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('-i', '--input', type=pathlib.Path, required=True)
    args = parser.parse_args()

    grc_content = yaml.load(open(args.input).read(), Loader=Loader)



    target_filename = 'target_file'

    grc_content['options']['parameters']['id'] = target_filename
    grc_content['options']['parameters']['generate_options'] = 'no_gui'

    for block in grc_content['blocks']:
        if block['id'] == 'qtgui_time_sink_x':
            block['id'] = 'relia_time_sink_x'

    with tempfile.TemporaryDirectory(prefix='relia-') as tmpdir:
        grc_filename = os.path.join(tmpdir, 'user_file.grc')
        py_filename = os.path.join(tmpdir, f'{target_filename}.py')

        open(grc_filename, 'w').write(yaml.dump(grc_content, Dumper=Dumper))

        open(os.path.join(tmpdir, 'relia.json'), 'w').write(json.dumps({
            'uploader_base_url': 'http://localhost:6001', # TODO
            'session_id': 'my-session-id', # TODO
            'device_id': 'my-device-id', # TODO
        }))

        print(subprocess.check_output(['grcc', grc_filename, '-o', tmpdir], cwd=tmpdir))

        print(tmpdir)

        subprocess.run([sys.executable, py_filename], cwd=tmpdir)

        input("Press any key to finish")

if __name__ == '__main__':
    main()
