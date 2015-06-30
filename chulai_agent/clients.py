import logging

import docker.client
import supervisor.childutils

from .errors import AgentError


__all__ = ["docker_client", "supervisor_client"]
logger = logging.getLogger(__name__)


class DockerClient(object):
    def __init__(self):
        self._dc = None

    def init_app(self, app):
        docker_config = dict(
            base_url=app.config["DOCKER_URL"],
            version=app.config["DOCKER_VERSION"],
            timeout=app.config["DOCKER_TIMEOUT"]
        )
        logger.debug("{0}".format(docker_config))
        docker_client = docker.client.Client(**docker_config)
        docker_client.info()
        self._dc = docker_client

    def __getattr__(self, attr):
        return getattr(self._dc, attr)


class SupervisorClient(object):
    def __init__(self):
        self._supervisor = None

    def init_app(self, app):
        rpc = supervisor.childutils.getRPCInterface({
            key: val for key, val in app.config.items()
            if key.startswith("SUPERVISOR_")
        })
        state = None
        try:
            state = rpc.supervisor.getState().get("statename")
        except BaseException as exc:
            state = exc
        if state != "RUNNING":
            raise AgentError(
                "supervisor not in right state [{0}]".format(state)
            )
        self._rpc = rpc.supervisor

    def __getattr__(self, attr):
        return getattr(self._rpc, attr)


docker_client = DockerClient()
supervisor_client = SupervisorClient()
