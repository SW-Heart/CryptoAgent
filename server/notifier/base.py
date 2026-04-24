from abc import ABC, abstractmethod

class NotificationChannel(ABC):
    @abstractmethod
    def send(self, title: str, body: str, level: str) -> bool:
        """
        Sends a notification.
        :param title: Title of the notification
        :param body: Body content in markdown
        :param level: INFO, WARN, URGENT, DAILY
        :return: True if successful, False otherwise
        """
        pass
