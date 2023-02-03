import os
from relia_gr_runner import create_app
application = create_app(os.environ.get('FLASK_CONFIG') or 'default')
