from flask import Blueprint
from flask import current_app
from flask import g
from flask import jsonify
from flask import request

from .. import errors
from .. import consts

from . import docker_instance


instance_api = Blueprint("instance_api", __name__)


OPERATION = dict(
    GET="get {0}'s stats",
    POST="pull {0} up",
    DELETE="put {0} down"
)


@instance_api.errorhandler(errors.AgentError)
def agent_error(error):
    current_app.logger.error(error)
    res = jsonify(error.to_dict())
    res.status_code = error.status_code
    return res


@instance_api.url_value_preprocessor
def set_g_instance(endpoint, value):
    """set docker_instance to global variable"""
    op_fmt = OPERATION.get(request.method)
    if op_fmt is None:
        raise errors.AgentError("unknown operation", 405)

    instance_id = value.get("instance_id")
    if instance_id is None:
        tip = "missing instance id"
        raise errors.ChulaiError(tip, 400)

    g.instance = docker_instance.DockerInstance(instance_id)
    current_app.logger.info(op_fmt.format(g.instance))


@instance_api.route("/instances/<instance_id>", methods=["POST"])
def pull_up(instance_id):
    if g.instance.exists:
        raise errors.AgentError("{0} already exists".format(g.instance), 409)

    try:
        message = g.instance.pull_up(
            str(request.json["app-id"]),
            request.json["commit"],
            request.json["image-tag"],
            request.json["environments"],
            request.json["worker"],
            int(request.json["port"])
        )
    except KeyError as exc:
        raise errors.AgentError("missing {0}".format(exc), 400)

    current_app.logger.info("going to deploy {0}".format(g.instance))
    return jsonify(status=consts.SUCCESS, message=message)


@instance_api.route("/instances/<instance_id>")
def show_stats(instance_id):
    """show instance's stats [cpu, memory usage, etc.]

    :query instance_id: instance_id

    :statuscode 200: show stats json
    :statuscode 404: instance not found
    :statuscode 500: instance not running

    :>header Content-Type: application/json

    :>json string status: ``success`` or ``failed``
    :>json string message: if status is ``failed``, error reason goes here
    :>json dict config: if status is ``success``, instance config goes here

    **Example response**:

    .. sourcecode:: http

        {
            "status": "success",
            "stats": {
                "cpu_percent": 20,
                "voluntary_switches": 100,
                "involuntary_switches": 50,
                "threads": 2,
                "rss_in_mb": 100,
                "vms_in_mb": 100,
                "user_time": 30,
                "system_time": 40,
                "children": ["child-process-cmd-0", "child-process-cmd-1"]
            }
        }
    """
    return jsonify(
        status=consts.SUCCESS,
        stats=g.instance.stats
    )


@instance_api.route("/instances/<instance_id>", methods=["DELETE"])
def put_down(instance_id):
    """destroy a instance, upload it's log, and cleanup the playground

    :query instance_id: instance_id

    :header Content-Type: application/json
    :>json string status: ``success`` or ``error``
    **Example Response:**

    .. sourcecode:: http

        {
            "status": "success"
        }
    """
    message = g.instance.put_down()
    return jsonify(status=consts.SUCCESS, message=message)
