import os
import sys
import time

import yaml
try:
    from yaml import CLoader as Loader, CDumper as Dumper
except ImportError:
    from yaml import Loader, Dumper

from werkzeug.utils import secure_filename

# From gnuradio.core.Constants
DEFAULT_HIER_BLOCK_LIB_DIR = os.path.expanduser('~/.grc_gnuradio')

class GrcManager:
    """
    GrcManager is a GNU Radio file parser that manages the utilities related to this file.
    """
    def __init__(self, grc_serialized_content: str, target_filename: str = 'target_file', gr_blocks_path: str = DEFAULT_HIER_BLOCK_LIB_DIR):
        self.grc_content = yaml.load(grc_serialized_content, Loader=Loader)
        self.target_filename = target_filename
        self.gr_blocks_path = gr_blocks_path

    def _apply_qt2relia_conversions(self):
        """
        Apply file conversions from QT blocks to Relia blocks
        """
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
            'qtgui_auto_correlator_sink': 'relia_autocorr_sink',            
        }

        for block in self.grc_content['blocks']:
            if block['id'] in conversions:
                block['id'] = conversions[block['id']]
                block_yml = os.path.join(self.gr_blocks_path, f"{block['id']}.block.yml")
                if not os.path.exists(block_yml):
                    print(f"[{time.asctime()}] The file {block_yml} does not exists. Have you recently installed relia-blocks?", file=sys.stdout, flush=True)
                    print(f"[{time.asctime()}] The file {block_yml} does not exists. Have you recently installed relia-blocks?", file=sys.stderr, flush=True)
                    raise Exception(f"The file {block_yml} does not exists. Have you recently installed relia-blocks?")

    def _apply_adalm_pluto(self):
        """
        If there is any ADALM Pluto module, reassign the IP address to the configured one.
        """
        for block in self.grc_content['blocks']:
            if block['id'] in ('iio_pluto_sink', 'iio_pluto_source'):
                block['parameters']['uri'] = f'"{os.environ.get("ADALM_PLUTO_IP_ADDRESS")}"'

    def process(self):
        self.grc_content['options']['parameters']['id'] = self.target_filename
        self.grc_content['options']['parameters']['generate_options'] = 'no_gui'

        self._apply_qt2relia_conversions()
        self._apply_adalm_pluto()

    def _apply_file_conversions(self, directory: str):
        """
        Apply file conversions to filesink and filesource
        """
        for block in self.grc_content['blocks']:
            if block['id'] == 'blocks_file_sink':
                secured_filename = secure_filename(block['parameters']['file'])
                block['parameters']['file'] = os.path.join(directory, 'files', secured_filename)

    def save(self, directory: str, filename: str):
        """
        Save the file with that filename in that directory
        """
        full_path = os.path.join(directory, filename)
        self.process()
        self._apply_file_conversions(directory)
        open(full_path, 'w').write(yaml.dump(self.grc_content, Dumper=Dumper))
