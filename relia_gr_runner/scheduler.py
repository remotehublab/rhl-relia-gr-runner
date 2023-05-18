import requests
import time
import traceback
from typing import NamedTuple, Optional
from datetime import datetime

from flask import current_app

class TaskAssignment(NamedTuple):
    taskIdentifier: str
    sessionIdentifier: str
    grcFile: str
    grcFileContent: str
    maxTime: float
    
class SchedulerClient:
    def __init__(self):
        self.base_url = current_app.config['SCHEDULER_BASE_URL']
        self.device_id = current_app.config['DEVICE_ID']
        self.device_type = current_app.config['DEVICE_TYPE']
        self.password = current_app.config['PASSWORD']

    def get_assignments(self) -> Optional[TaskAssignment]:
        try:
            device_data = requests.get(f"{self.base_url}scheduler/devices/tasks/{self.device_type}?max_seconds=5", headers={'relia-device': self.device_id, 'relia-password': self.password}, timeout=(30,30)).json()
        except Exception as e:
            if str(e)[0] == '5':
                time.sleep(2)
            traceback.print_exc()
            return None
        else:
            if device_data.get('success'):
                return TaskAssignment(taskIdentifier=device_data.get('taskIdentifier'),
                              sessionIdentifier=device_data.get('sessionIdentifier'),
                              grcFile=device_data.get('grcFile'),
                              grcFileContent=device_data.get('grcFileContent'),
                              maxTime=device_data.get('maxTime'))
            
            print(f"Scheduler server failed: {device_data}")
            return None
            
    def check_assignment(self, taskIdentifier):
        device_data = requests.get(f"{self.base_url}scheduler/devices/task-status/{taskIdentifier}?max_seconds=5", headers={'relia-device': self.device_id, 'relia-password': self.password}, timeout=(30,30)).json()
        return device_data.get('status')

    def complete_assignments(self, taskIdentifier):
        device_data = requests.post(f"{self.base_url}scheduler/devices/tasks/{self.device_type}/{taskIdentifier}?max_seconds=5", headers={'relia-device': self.device_id, 'relia-password': self.password}, timeout=(30,30)).json()

    def error_message_delivery(self, taskIdentifier, errorMessage):
        now = datetime.now()
        device_data = requests.post(f"{self.base_url}scheduler/devices/tasks/error_message/{taskIdentifier}?max_seconds=5", \
                                    headers={'relia-device': self.device_id, 'relia-password': self.password}, \
                                    json={'errorMessage': errorMessage, 'errorTime': now.isoformat()}, \
                                    timeout=(30,30)).json()
