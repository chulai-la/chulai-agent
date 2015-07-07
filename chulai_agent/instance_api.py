from flask import Blueprint
from flask import current_app
from flask import g
from flask import jsonify
from flask import request
from jinja2 import Template

from . import docker_instance
from . import errors
from . import consts


instance_api = Blueprint("instance_api", __name__)


@instance_api.errorhandler(errors.AgentError)
def not_inited_error(error):
    current_app.logger.error(error)
    res = jsonify(error.to_dict())
    res.status_code = error.status_code
    return res


@instance_api.url_value_preprocessor
def set_g_instance(endpoint, value):
    """set docker_instance to global variable"""
    instance_id = value.get("instance_id")
    if instance_id is None:
        tip = "missing instance id"
        raise errors.ChulaiError(tip, 400)
    g.instance = docker_instance.DockerInstance(instance_id)


@instance_api.route("/<instance_id>/deploy", methods=["PUT"])
def deploy_instance(instance_id):
    current_app.logger.debug(request.json)
    try:
        supervisor_template = request.json["supervisor-config"]
        dirs_to_make = request.json["dirs-to-make"]
    except KeyError as exc:
        raise errors.AgentError("missing {0}".format(exc), 400)

    current_app.logger.info("going to deploy {0}".format(g.instance))
    new_deploy = g.instance.deploy(
        Template(supervisor_template).render(
            agent=current_app.config["HOST_INFO"]
        ),
        dirs_to_make
    )

    return jsonify(status=consts.SUCCESS, new_deploy=new_deploy)


@instance_api.route("/<instance_id>/stats")
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


@instance_api.route("/<instance_id>/<operation>", methods=["PUT"])
def op_on_instance(instance_id, operation):
    """make instance ``up`` or ``halt`` it

    :query instance_id: instance_id

    :header Content-Type: application/json
    :>json string status: ``success`` or ``error``
    **Example Response:**

    .. sourcecode:: http

        {
            "status": "success"
        }
    """
    operation_func = getattr(g.instance, operation, None)
    if operation_func is not None:
        current_app.logger.info(
            "going to {0} {1}".format(operation, g.instance)
        )
        operation_func()
        return jsonify(status=consts.SUCCESS, operation=operation)
    else:
        raise errors.AgentError(
            "unknown operation [{0}]".format(operation),
            status_code=400
        )


@instance_api.route("/<instance_id>/destroy", methods=["PUT"])
def destroy_instance(instance_id):
    """destroy a instance, clean it's workspace, upload it's log"""
    g.instance.destroy()
    return jsonify(status=consts.SUCCESS)
