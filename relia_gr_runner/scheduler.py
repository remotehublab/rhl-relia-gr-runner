import requests
import time
from typing import NamedTuple

from flask import current_app

class TaskAssignment(NamedTuple):
    taskIdentifier: str
    sessionIdentifier: str
    grcFile: str
    grcFileContent: str
    
class SchedulerClient:
    def __init__(self):
        self.base_url = current_app.config['SCHEDULER_BASE_URL']
        self.device_id = current_app.config['DEVICE_ID']
        self.device_type = current_app.config['DEVICE_TYPE']
        self.password = current_app.config['PASSWORD']

    def get_assignments(self) -> TaskAssignment:
        try:
            device_data = requests.get(f"{self.base_url}scheduler/devices/tasks/{self.device_type}?max_seconds=5", headers={'relia-device': self.device_id, 'relia-password': self.password}, timeout=(30,30)).json()
        except Exception as e:
            if str(e)[0] == '5':
                time.sleep(2)

        return TaskAssignment(device_data.get('taskIdentifier'),
                              device_data.get('sessionIdentifier'),
                              device_data.get('grcFile'),
                              device_data.get('grcFileContent'))
            
    def check_assignment(self, taskIdentifier):
        device_data = requests.get(f"{self.base_url}scheduler/user/tasks/{taskIdentifier}?max_seconds=5", timeout=(30,30)).json()
        return device_data.get('status')

    def complete_assignments(self, taskIdentifier):
        device_data = requests.post(f"{self.base_url}scheduler/devices/tasks/{self.device_type}/{taskIdentifier}?max_seconds=5", headers={'relia-device': self.device_id, 'relia-password': self.password}, timeout=(30,30)).json()