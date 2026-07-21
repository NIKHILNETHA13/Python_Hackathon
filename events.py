from collections import deque
from datetime import datetime


class EventLog:
    def __init__(self, maxlen=100):
        self._events = deque(maxlen=maxlen)

    def add(self, icon, message):
        now = datetime.now().strftime("%H:%M:%S")
        self._events.appendleft({"time": now, "icon": icon, "message": message})

    def get_all(self):
        return list(self._events)
