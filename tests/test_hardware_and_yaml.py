import importlib.util
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]

def module(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'relia_gr_runner' / (name + '.py'))
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result

hardware = module('hardware')
GrcManager = module('grc_manager').GrcManager

class ReadinessTests(unittest.TestCase):
    def test_missing_or_disconnected_radio_is_unavailable(self):
        self.assertFalse(hardware.radio_ready({}))
        with patch.object(hardware.socket, 'create_connection', side_effect=OSError):
            self.assertFalse(hardware.radio_ready({'ADALM_PLUTO_IP_ADDRESS': '192.168.2.1'}))
            self.assertFalse(hardware.radio_ready({'RED_PITAYA_IP_ADDRESS': '192.168.1.174'}))

    def test_grc_rejects_python_yaml_tags(self):
        with self.assertRaises(Exception):
            GrcManager('!!python/object/apply:os.system ["false"]')

    def test_real_examples_remain_parseable(self):
        for path in (ROOT / 'examples').glob('*.grc'):
            with self.subTest(example=path.name):
                self.assertIsInstance(GrcManager(path.read_text()).grc_content['blocks'], list)

    def test_non_flowgraph_fails_with_clear_error(self):
        for value in ('null', '[]', '{blocks: 1}'):
            with self.assertRaisesRegex(ValueError, 'GNU Radio flowgraph'):
                GrcManager(value)

if __name__ == '__main__':
    unittest.main()
