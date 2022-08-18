import os
import sys
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

        print(subprocess.check_output(['grcc', grc_filename, '-o', tmpdir]))

        print(tmpdir)

        subprocess.run([sys.executable, py_filename])

        input("Press any key to finish")

if __name__ == '__main__':
    main()
