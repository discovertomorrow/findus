import getpass
import json


class CopernicusCredentials:
    def __init__(self):
        self.username = None
        self.password = None

    def add(self):
        self.username = getpass.getpass(
            prompt='Enter your Copernicus username: ', stream=None)
        self.password = getpass.getpass(
            prompt='Enter your password for Copernicus user ' + self.username + ': ', stream=None)
        return self

    def save(self, path):
        credentials = dict(username=self.username, password=self.password)
        with open(path, 'w') as f:
            json.dump(credentials, f)

    def load(self, path):
        with open(path, 'r') as f:
            credentials = json.load(f)
        self.username = credentials['username']
        self.password = credentials['password']
        return self


class PlantNetCredentials:
    def __init__(self, key=None):
        self.key = key

    @staticmethod
    def load(path):
        with open(path, 'r') as f:
            credentials = json.load(f)
        key = credentials['key']
        return PlantNetCredentials(key=key)
