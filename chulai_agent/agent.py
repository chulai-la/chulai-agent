import os


class Agent(object):
    def __init__(self):
        self._host_name = None
        self._host_ip = None
        self._paas_domain = None
        self._log_max_mb = None
        self._log_backups = None
        self._start_timeout = None
        self._stop_timeout = None
        self._mem_limit = None
        self._playground = None

    def init_app(self, app):
        self._hostname = app.config["HOSTNAME"]
        self._host_ip = app.config["HOST_IP"]
        self._paas_domain = app.config["PAAS_DOMAIN"]
        self._log_max_mb = app.config["LOG_MAX_MB"]
        self._log_backups = app.config["LOG_BACKUPS"]
        self._start_timeout = app.config["START_TIMEOUT"]
        self._stop_timeout = app.config["STOP_TIMEOUT"]
        self._mem_limit = app.config["MEMORY_LIMIT"]
        self._paas_user = app.config["PAAS_USER"]
        self.playground = app.config["PLAYGROUND"]

    @property
    def paas_user(self):
        return self._paas_user

    @property
    def playground(self):
        return self._playground

    @playground.setter
    def playground(self, new_path):
        self._playground = os.path.realpath(new_path)
        return self._playground

    @property
    def start_timeout(self):
        return self._start_timeout

    @property
    def stop_timeout(self):
        return self._stop_timeout

    @property
    def mem_limit(self):
        return self._mem_limit

    @property
    def host_name(self):
        return self._hostname

    @property
    def host_ip(self):
        return self._host_ip

    @property
    def paas_domain(self):
        return self._paas_domain

    @property
    def log_max_mb(self):
        return self._log_max_mb

    @property
    def log_backups(self):
        return self._log_backups


agent = Agent()
