import os

class Config:
    DEFAULT_HIER_BLOCK_LIB_DIR = os.path.expanduser('~/.grc_gnuradio')
    DEVICE_ID = os.environ.get('DEVICE_ID')
    PASSWORD = os.environ.get('PASSWORD')
    DATA_UPLOADER_BASE_URL = os.environ.get('DATA_UPLOADER_BASE_URL')
    SCHEDULER_BASE_URL = os.environ.get('SCHEDULER_BASE_URL')

class DevelopmentConfig(Config):
    DEBUG = True
    DEFAULT_HIER_BLOCK_LIB_DIR = os.path.expanduser('~/.grc_gnuradio')
    DEVICE_ID = os.environ.get('DEVICE_ID') or 'uw-s1i1:t'
    PASSWORD = os.environ.get('PASSWORD') or 'password'
    DATA_UPLOADER_BASE_URL = os.environ.get('DATA_UPLOADER_BASE_URL') or 'http://localhost:6001/'
    SCHEDULER_BASE_URL = os.environ.get('SCHEDULER_BASE_URL') or 'http://localhost:6002/'

class StagingConfig(Config):
    DEBUG = False

class ProductionConfig(Config):
    DEBUG = False

configurations = {
    'default': DevelopmentConfig,
    'development': DevelopmentConfig,
    'staging': StagingConfig,
    'production': ProductionConfig,
}
