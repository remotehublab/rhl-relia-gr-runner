import os

class Config:
    DEFAULT_HIER_BLOCK_LIB_DIR = os.path.expanduser('~/.grc_gnuradio')
    DEVICE_ID = os.environ.get('DEVICE_ID')
    PASSWORD = os.environ.get('PASSWORD')
    DATA_UPLOADER_BASE_URL = os.environ.get('DATA_UPLOADER_BASE_URL')
    SCHEDULER_BASE_URL = os.environ.get('SCHEDULER_BASE_URL')
    DEVICE_TYPE = os.environ.get('DEVICE_TYPE')
    ADALM_PLUTO_IP_ADDRESS = os.environ.get('ADALM_PLUTO_IP_ADDRESS')
    RED_PITAYA_IP_ADDRESS = os.environ.get('RED_PITAYA_IP_ADDRESS')
    RED_PITAYA_RATE = os.environ.get('RED_PITAYA_RATE')
    MAX_GR_PYTHON_EXECUTION_TIME = float(os.environ.get('MAX_GR_PYTHON_EXECUTION_TIME') or '20')
    USE_FIREJAIL = os.environ.get('USE_FIREJAIL') in ('1', 'true')
    FIREJAIL_IP_ADDRESS = os.environ.get('FIREJAIL_IP_ADDRESS') or '10.10.20.2'
    FIREJAIL_INTERFACE = os.environ.get('FIREJAIL_INTERFACE') or 'br0'

class DevelopmentConfig(Config):
    DEBUG = True
    DEFAULT_HIER_BLOCK_LIB_DIR = os.path.expanduser('~/.grc_gnuradio')
    DEVICE_ID = os.environ.get('DEVICE_ID') or 'uw-s1i1:r'
    PASSWORD = os.environ.get('PASSWORD') or 'password'
    DATA_UPLOADER_BASE_URL = os.environ.get('DATA_UPLOADER_BASE_URL') or 'http://localhost:6001/'
    SCHEDULER_BASE_URL = os.environ.get('SCHEDULER_BASE_URL') or 'http://localhost:6002/'

class StagingConfig(Config):
    DEBUG = False
    USE_FIREJAIL = os.environ.get('USE_FIREJAIL', '1') in ('1', 'true')

class ProductionConfig(Config):
    DEBUG = False
    USE_FIREJAIL = os.environ.get('USE_FIREJAIL', '1') in ('1', 'true')

configurations = {
    'default': DevelopmentConfig,
    'development': DevelopmentConfig,
    'staging': StagingConfig,
    'production': ProductionConfig,
}
