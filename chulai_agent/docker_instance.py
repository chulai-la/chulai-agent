"""
Docker Instance Class

for high-level chulai app controlling
"""

import configparser
import functools
import logging
import os
import xmlrpc
import signal
import time

import docker
import requests
import psutil
import shcmd

from . import consts
from . import utils

from .clients import docker_client, supervisor_client
from .errors import AgentError


logger = logging.getLogger(__name__)


class DockerInstance(object):
    def __init__(self, instance_id):
        """
        DockerApp Object
        :param instance_id: instance's id
        :param playground: instance's playground (parse supervisor-conf)
        """
        self._instance_id = instance_id

    @property
    def instance_id(self):
        return self._instance_id

    @property
    def supervisor_conf_path(self):
        return os.path.join(
            supervisor_client.conf_dir, "{0}.ini".format(self.instance_id)
        )

    @property
    def config(self):
        try:
            with open(self.supervisor_conf_path) as conf_f:
                supervisor_conf = conf_f.read()
        except (FileNotFoundError, PermissionError) as exc:
            raise AgentError("error reading supervisor conf [{0}]| {1}".format(
                self.supervisor_conf_path, exc
            ))

        ini = configparser.ConfigParser()
        ini.read_string(supervisor_conf)
        section_name = "chulai:{0}".format(self.instance_id)
        if ini.has_section(section_name) is False:
            raise AgentError("config has no valid section:\n{0}\n".format(
                supervisor_conf
            ))
        return functools.partial(ini.get, section_name)

    def get_config(self, key, *args):
        try:
            return self.config(key)
        except configparser.NoOptionError:
            # if we have an default value, return it
            # otherwise we raise exception
            if args:
                return args[0]
            raise AgentError("invalid config fonud! missing [{0}]".format(key))

    def __str__(self):
        """
        Return program friendly string of this instance
        """
        return "<DockerApp {0}>".format(self.instance_id)

    @property
    def cid(self):
        """
        Returns container id of current project
        """
        containers = docker_client.containers(
            all=True, filters=dict(label=self.instance_id)
        )
        cnt = len(containers)
        if cnt != 1:
            raise AgentError(
                "{0} containers found for {1}".format(cnt, self.instance_id)
            )
        try:
            return containers[0]["Id"]
        except KeyError:
            raise AgentError("error find cid from [{0}]".format(containers[0]))

    @property
    def pid(self):
        """
        Returns the pid of current project
        Raises running error when project is not running
        """
        try:
            container_info = docker_client.inspect_container(self.cid)
            pid = container_info["State"]["Pid"]
        except docker.errors.APIError as exc:
            if exc.response.status_code != 404:
                raise
            raise AgentError("can not find container with cid: [{0}]".format(
                self.cid
            ))
        except KeyError:
            raise AgentError("can not find pid from {0}".format(container_info))

        if pid == 0:
            raise AgentError("{0} not running".format(self.instance_id))
        else:
            return pid

    @property
    def running(self):
        try:
            info = supervisor_client.getProcessInfo(self.instance_id)
            state = info["state"]
        except xmlrpc.client.Fault as exc:
            raise AgentError(
                "get {0} info error: {1}".format(self.instance_id, exc)
            )

        if state in consts.SUPERVISOR_RUNNING_STATES:
            return True
        elif state in consts.SUPERVISOR_STOPPED_STATES:
            return False
        else:
            raise AgentError(
                "{0} invalid state: {1}".format(self.instance_id, state)
            )

    @property
    def is_http_app(self):
        return False

    def up(self):
        if self.running is False:
            try:
                supervisor_client.startProcess(self.instance_id)
            except xmlrpc.client.Fault as exc:
                raise AgentError(
                    "up instance [{0}] failed: {1}".format(
                        self.instance_id, exc
                    )
                )
        if self.is_http_app:
            self.check_http()

    def halt(self):
        if self.running:
            try:
                supervisor_client.stopProcess(self.instance_id)
            except xmlrpc.client.Fault as exc:
                raise AgentError(
                    "halt instance [{0}] failed: {1}".format(
                        self.instance_id, exc
                    ),
                    status_code=409,
                    payload=dict(instance=str(self), operation="halt")
                )

    @property
    def stats(self):
        """
        Show process info of this app
        """
        if not self.running:
            raise AgentError("{0} not running, stats is meaningless".format(
                self.instance_id
            ))

        proc = psutil.Process(self.pid)
        logger.info(
            "gathering metric for {0}[{1}]".format(self.instance_id, self.pid)
        )

        ctx_switches = proc.num_ctx_switches()
        mem_info = proc.memory_info()
        cpu_info = proc.cpu_times()

        metrics = {
            "cpu_percent": proc.cpu_percent(),
            "memroy_percent": proc.memory_percent(),
            "voluntary_switches": ctx_switches.voluntary,
            "involuntary_switches": ctx_switches.involuntary,
            "threads": proc.num_threads(),
            "rss_in_mb": utils.to_MB(mem_info.rss),
            "vms_in_mb": utils.to_MB(mem_info.vms),
            "user_time": cpu_info.user,
            "system_time": cpu_info.system,
            "children": [
                " ".join(child.cmdline())
                for child in proc.children()
            ]
        }
        return metrics

    def get_log(self, log_path, lastn, timeout):
        real_path = self.playground, log_path.lstrip("/")
        return shcmd.tailf(real_path, lastn=lastn, timeout=timeout)

    @property
    def playground(self):
        return os.path.join(self.get_config("playground"), self.instance_id)

    def deploy(self, supervisor_conf, dirs_to_make):
        process = [
            proc for proc in supervisor_client.getAllProcessInfo()
            if proc["name"] == self.instance_id
        ]
        if process:
            self.destroy()

        with open(self.supervisor_conf_path, "wt") as conf_f:
            conf_f.write(supervisor_conf)
        with shcmd.cd(self.playground, create=True):
            for dir_path in dirs_to_make:
                shcmd.mkdir(dir_path)
            # create symlink for debug, we can view all config in playground
            shcmd.rm("supervisor.conf")
            os.symlink(self.supervisor_conf_path, "supervisor.conf")

        try:
            supervisor_client.reloadConfig()
            supervisor_client.addProcessGroup(self.instance_id)
            supervisor_client.getProcessInfo(self.instance_id)
        except xmlrpc.client.Fault as exc:
            raise AgentError(
                "deploy {0} error: {1}".format(self.instance_id, exc)
            )

        # return true if new deploy
        return len(process) == 0

    def destroy(self):
        try:
            self.halt()
            supervisor_client.removeProcessGroup(self.instance_id)
            supervisor_client.reloadConfig()
        except AgentError:
            logger.warn("trying to delete {0}, but it's not inited".format(
                self.instance_id
            ))
        try:
            docker_client.kill(self.cid, signal.SIGKILL)
        except BaseException:
            logger.warn(
                "trying to kill {0}, but failed".format(self.instance_id),
                exc_info=True
            )

        # clean playground, TODO backup to object-storage
        shcmd.rm(self.playground, isdir=True)

        # check again for sure the proc is dead
        all_procs = [
            proc["name"]
            for proc in supervisor_client.getAllProcessInfo()
        ]
        if self.instance_id in all_procs:
            raise AgentError(
                "delete {0} failed:\n{1}\n".format(self.instance_id, all_procs)
            )

        shcmd.rm(self.supervisor_conf_path)
        return True

    def check_http(self):
        timedout = time.time() + self.start_timeout
        check_interval = min(self.start_timeout / 10, 0.1)
        tip = None

        while time.time() < timedout:
            try:
                logger.info("goging to check {0}".format(self._http))
                res = requests.get(self._http, timeout=(timedout - time.time()))
                logger.info("examing {0}: {1}".format(self, res.status_code))
                break
            except requests.RequestException as exc:
                tip = "start {0} failed, timedout({1})s: {2}".format(
                    self, self.start_timeout, exc
                )
                logger.debug(tip, exc_info=True)
                time.sleep(check_interval)
        else:
            raise AgentError(tip)
