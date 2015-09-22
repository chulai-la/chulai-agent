"""
Docker Instance Class

for high-level chulai app controlling
"""

import configparser
import functools
import json
import logging
import os
import xmlrpc
import xmlrpc.client
import signal
import time

import docker
import psutil
import requests
import shcmd

from .. import consts
from .. import errors
from .. import utils
from ..agent import agent
from ..clients import docker_client, supervisor_client

from .template_loader import render_template


logger = logging.getLogger(__name__)


def get_repo_tag(image_tag):
    return image_tag.split(":", 1)


def pull_image(image_tag):
    repo, tag = get_repo_tag(image_tag)
    res = docker_client.pull(repo, tag, insecure_registry=True)
    last_log = json.loads(res.splitlines()[-1])
    msg = last_log.get("errorDetail", {}).get("message")
    if msg:
        raise errors.NotFoundError("pulling image error: {0}".format(msg))


class DockerInstance(object):
    def __init__(self, instance_id):
        """
        DockerApp Object
        :param instance_id: instance's id
        """
        self._instance_id = instance_id

    def __repr__(self):
        return "<DockerInstance {0}>".format(self.instance_id)

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
            raise errors.AgentError(
                "error reading supervisor conf [{0}]| {1}".format(
                    self.supervisor_conf_path, exc
                )
            )

        ini = configparser.ConfigParser()
        ini.read_string(supervisor_conf)
        section_name = "chulai:{0}".format(self.instance_id)
        if ini.has_section(section_name) is False:
            raise errors.AgentError(
                "config has no valid section:\n{0}\n".format(supervisor_conf)
            )
        return functools.partial(ini.get, section_name)

    def get_config(self, key, *args):
        try:
            return self.config(key)
        except configparser.NoOptionError:
            # if we have an default value, return it
            # otherwise we raise exception
            if len(args) == 0:
                raise errors.AgentError(
                    "invalid config fonud! missing [{0}]".format(key)
                )
            elif len(args) == 1:
                return args[0]
            else:
                raise errors.AgentError(
                    "too many default value for {0}={1}".format(key, args),
                    500
                )

    @property
    def cid(self):
        """
        Returns container id of current project
        """
        for container in docker_client.containers(all=True):
            name = "/{0}".format(self.instance_id)
            if name in container["Names"]:
                return container["Id"]
        raise errors.AgentError("can not find cid of {0}".format(self))

    @property
    def pid(self):
        """
        Returns the pid of current project
        Raises running error when project is not running
        """
        try:
            container_info = docker_client.inspect_container(self.cid)
            state = container_info["State"]
            running = state["Running"]
            pid = state["Pid"]
        except docker.errors.APIError as exc:
            if exc.response.status_code != 404:
                raise
            raise errors.AgentError(
                "can not find container with cid: [{0}]".format(self.cid)
            )
        except KeyError:
            raise errors.AgentError(
                "can not find pid from {0}".format(container_info)
            )

        if not running:
            raise errors.AgentError("{0} not running".format(self))
        else:
            return pid

    @property
    def running(self):
        state = self.state

        if state is None:
            raise errors.NotFoundError("{0} not found".format(self), 404)
        elif state in consts.SUPERVISOR_RUNNING_STATES:
            return True
        elif state in consts.SUPERVISOR_STOPPED_STATES:
            return False
        raise errors.AgentError(
            "{0} invalid state: {1}".format(self, state), 500
        )

    @property
    def is_http_app(self):
        return False

    @property
    def stats(self):
        """
        Show process info of this app
        """
        if not self.running:
            raise errors.AgentError(
                "{0} not running, stats is meaningless".format(self)
            )

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

    def pull_up(
        self,
        app_id,
        commit,
        image_tag,
        environments,
        worker,
        port
    ):
        if self.state is not None:
            raise errors.AgentError("{0} ".format(self), 409)
        app_id = str(app_id)
        # prepare image
        pull_image(image_tag)
        # prepare dirs
        for dir_path in self.dirs_to_make:
            shcmd.mkdir(dir_path)
        # prepare supervisor stuff
        supervisor_conf, debug_script = self.make_supervisor_conf(
            app_id,
            commit,
            image_tag,
            environments,
            worker,
            port
        )
        with open(self.supervisor_conf_path, "wt") as conf_f:
            conf_f.write(supervisor_conf)
        # create symlink for debug, we can view all config in playground
        with shcmd.cd(self.playground, create=True):
            shcmd.rm("supervisor.conf")
            os.symlink(self.supervisor_conf_path, "supervisor.conf")
            with open("go-to-docker.sh", "wt") as script_f:
                script_f.write(debug_script)
        try:
            supervisor_client.reloadConfig()
            supervisor_client.addProcessGroup(self.instance_id)
            if self.state is None:
                raise errors.AgentError(
                    "add {0} to supervisor failed".format(self)
                )
        except xmlrpc.client.Fault as exc:
            raise errors.AgentError(
                "deploy {0} error: {1}".format(self.instance_id, exc)
            )
        # done preparation

        return self.start()

    def start(self):
        status = "already running"
        if self.running is False:
            status = "started"
            try:
                supervisor_client.startProcess(self.instance_id)
            except xmlrpc.client.Fault as exc:
                raise errors.AgentError(
                    "start instance {0} failed: {1}".format(self, exc)
                )
        if self.is_http_app:
            self.check_http()
        return status

    def put_down(self):
        try:
            if not self.exists:
                return "{0} not exists".format(self)
            if self.running:
                supervisor_client.stopProcess(self.instance_id)
            supervisor_client.removeProcessGroup(self.instance_id)
            supervisor_client.reloadConfig()
            if self.exists:
                raise errors.AgentError("put down {0} failed".format(self))
            return "put down {0} success".format(self)
        except xmlrpc.client.Fault as exc:
            raise errors.AgentError(
                "stop {0} failed: {1}".format(self, exc), 409,
                payload=dict(instance=str(self), operation="put down")
            )
        finally:
            self.cleanup()

    def cleanup(self):
        try:
            docker_client.kill(self.cid, signal.SIGKILL)
        except errors.NotFoundError:
            logger.info("container already quited")
        except BaseException:
            logger.warn(
                "trying to kill {0}, but failed".format(self.instance_id),
                exc_info=True
            )
        # remove supervisor config
        shcmd.rm(self.supervisor_conf_path)
        # clean playground, TODO backup to object-storage
        shcmd.rm(self.playground, isdir=True)

    def check_http(self):
        timedout = time.time() + self.start_timeout
        check_interval = min(self.start_timeout / 10, 0.1)
        tip = None
        check_url = self.get_config("http-check-url")

        while time.time() < timedout:
            try:
                logger.info("goging to check {0}".format(check_url))
                res = requests.get(check_url, timeout=(timedout - time.time()))
                logger.info("examing {0}: {1}".format(self, res.status_code))
                break
            except requests.RequestException as exc:
                tip = "start {0} failed, timedout({1})s: {2}".format(
                    self, self.start_timeout, exc
                )
                logger.debug(tip, exc_info=True)
                time.sleep(check_interval)
        else:
            raise errors.AgentError(tip)

    @property
    def state(self):
        state = None
        try:
            state = supervisor_client.getProcessInfo(self.instance_id)["state"]
        except xmlrpc.client.Fault as exc:
            if exc.faultCode != 10:
                raise errors.AgentError(
                    "get {0} info error: {1}".format(self, exc),
                    500
                )
        finally:
            return state

    @property
    def playground(self):
        return os.path.join(agent.playground, self.instance_id)

    @property
    def logs_dir(self):
        return os.path.join(self.playground, "chulai-log.d")

    @property
    def stdlogs_dir(self):
        return os.path.join(self.playground, "stdout-log.d")

    @property
    def dirs_to_make(self):
        return [self.logs_dir, self.stdlogs_dir]

    @property
    def exists(self):
        return self.state is not None

    def make_supervisor_conf(
        self,
        app_id,
        commit,
        image_tag,
        environments,
        worker,
        port
    ):
        repo, tag = get_repo_tag(image_tag)
        instance_info = dict(
            instance_id=self.instance_id,
            app_id=app_id,
            commit=commit,
            repo=repo,
            tag=tag,
            image_tag=image_tag,
            environments=environments,
            worker=worker,
            port=port,
            environments_json=json.dumps(environments),
            start_sec=environments.pop("START_TIMEOUT", agent.start_timeout),
            stop_sec=environments.pop("STOP_TIMEOUT", agent.stop_timeout),
            memory_limit=environments.pop("MEMORY_LIMIT", agent.mem_limit),
            stdlogs_dir=self.stdlogs_dir,
            logs_dir=self.logs_dir,
            work_dir=os.path.join("/home", agent.paas_user, app_id),
            # FIXME: remove hardcodeed assets_dir
            assets_dir=os.path.join(
                "/mnt/data/chulai/central-perk/app-assets",
                app_id
            )
        )

        supervisor_conf = render_template(
            "supervisor.conf",
            instance=instance_info,
            agent=agent
        )
        debug_script = render_template(
            "go-to-docker.sh",
            instance=instance_info,
            agent=agent
        )
        return supervisor_conf, debug_script
