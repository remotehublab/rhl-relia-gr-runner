import abc
import sys
import requests
import time
import traceback
from typing import NamedTuple, Optional
from datetime import datetime

from flask import current_app

class TaskAssignment(NamedTuple):
    taskIdentifier: str
    sessionIdentifier: str
    file: str
    fileContent: str
    fileType: str
    maxTime: float

class AbstractSchedulerClient:
    __meta__ = abc.ABCMeta

    @abc.abstractmethod
    def get_assignments(self) -> Optional[TaskAssignment]:
        """
        Request an assignment from the RELIA Scheduler.
        """

    @abc.abstractmethod
    def check_assignment_status(self, task_identifier: str) -> str:
        """
        Check the status of the currently assigned task
        """

    @abc.abstractmethod
    def complete_assignments(self, task_identifier: str, session_identifier: str) -> None:
        """
        Report that the assignment has finished successfully.
        """

    @abc.abstractmethod
    def error_message_delivery(self, task_identifier: str, error_message: str) -> None:
        """
        Report an error in the assignment
        """
    
class SchedulerClient(AbstractSchedulerClient):
    """
    The SchedulerClient wraps all the communications with the RELIA Scheduler.
    """
    def __init__(self):
        self.base_url = current_app.config['SCHEDULER_BASE_URL']
        self.device_id = current_app.config['DEVICE_ID']
        self.device_type = current_app.config['DEVICE_TYPE']
        self.password = current_app.config['PASSWORD']

    def get_assignments(self) -> Optional[TaskAssignment]:
        try:
            url = f"{self.base_url}scheduler/devices/tasks/{self.device_type}?max_seconds=5"
            response = requests.get(url, headers={'relia-device': self.device_id, 'relia-password': self.password}, timeout=(30,30))
            try:
                device_data = response.json()
            except Exception as err:
                print("Error processing request {url}", file=sys.stdout)
                print("Error processing request {url}", file=sys.stderr)
                print(response.text, file=sys.stdout, flush=True)
                print(response.text, file=sys.stderr, flush=True)
                raise
        except Exception as e:
            if str(e)[0] == '5':
                time.sleep(2)
            print(f"Error in get_assignments(): {e}")
            print(f"Error in get_assignments(): {e}", file=sys.stderr, flush=True)
            traceback.print_exc()
            return None
        else:
            if device_data.get('success'):
                return TaskAssignment(taskIdentifier=device_data.get('taskIdentifier'),
                              sessionIdentifier=device_data.get('sessionIdentifier'),
                              file=device_data.get('file'),
                              fileContent=device_data.get('fileContent'),
                              fileType=device_data.get('filetype'),
                              maxTime=device_data.get('maxTime'))
            
            print(f"Scheduler server failed: {device_data}")
            return None
            
    def check_assignment_status(self, task_identifier: str) -> str:
        """
        Check the status of the currently assigned task
        """
        device_data = requests.get(f"{self.base_url}scheduler/devices/tasks/{self.device_type}/{task_identifier}", headers={'relia-device': self.device_id, 'relia-password': self.password}, timeout=(30,30)).json()
        return device_data.get('status')

    def complete_assignments(self, task_identifier: str) -> None:
        """
        Report that the assignment has finished successfully.
        """
        device_data = requests.post(f"{self.base_url}scheduler/devices/tasks/{self.device_type}/{task_identifier}", headers={'relia-device': self.device_id, 'relia-password': self.password}, timeout=(30,30)).json()

    def error_message_delivery(self, task_identifier: str, error_message: str) -> None:
        """
        Report an error in the assignment
        """
        now = datetime.now()
        device_data = requests.post(f"{self.base_url}scheduler/devices/tasks/error_message/{task_identifier}", \
                                    headers={'relia-device': self.device_id, 'relia-password': self.password}, \
                                    json={'errorMessage': error_message, 'errorTime': now.isoformat()}, \
                                    timeout=(30,30)).json()

class NoSchedulerClient(AbstractSchedulerClient):
    """
    The NoSchedulerClient is a dummy scheduler client that does nothing.
    """
    def get_assignments(self) -> Optional[TaskAssignment]:
        return None

    def check_assignment_status(self, task_identifier: str) -> None:
        pass

    def complete_assignments(self, task_identifier: str) -> None:
        pass

    def error_message_delivery(self, task_identifier: str, error_message: str) -> None:
        pass
