import requests
from typing import NamedTuple

from flask import current_app

class TaskAssignment(NamedTuple):
    task_identifier: str
    # ...




class SchedulerClient:
    def __init__(self):
        self.base_url = current_app.config['SCHEDULER_BASE_URL']
        self.device_id = current_app.config['DEVICE_ID']
        self.device_type = current_app.config['DEVICE_TYPE']
        self.password = current_app.config['PASSWORD']


    def get_assignments(self) -> TaskAssignment:
        # TODO: add try..except, custom exceptions, etc., maybe sleeps (if the error is 5XX), etc.
        device_data = requests.get(f"{self.base_url}scheduler/devices/tasks/{self.device_type}?max_seconds=5", headers={'relia-device': self.device_id, 'relia-password': self.password}, timeout=(30,30)).json()
        # TODO: take device_data and convert it to TaskAssignment
        return device_data


