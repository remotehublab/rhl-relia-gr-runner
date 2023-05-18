import os
import sys
from flask import Flask, render_template, current_app
import json
import time
import shutil
import pathlib
import tempfile
import platform
import argparse
import subprocess
import requests
import yaml
import threading
import traceback
try:
    from yaml import CLoader as Loader, CDumper as Dumper
except ImportError:
    from yaml import Loader, Dumper

from config import configurations

def create_app(config_name: str = 'default'):

    # Based on Flasky https://github.com/miguelgrinberg/flasky
    app = Flask(__name__)
    app.config.from_object(configurations[config_name])

    @app.cli.command('process-tasks')
    def process_tasks():
        """
        Process tasks
        """
        from .processor import Processor
        processor = Processor()
        processor.run_forever()
        
    return app

