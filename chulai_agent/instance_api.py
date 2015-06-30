from flask import Blueprint
from flask import current_app
from flask import g
from flask import jsonify
from flask import request
from flask import Response
from flask import render_template

from . import docker_instance
from . import errors
from . import consts
from . import utils


instance_api = Blueprint("instance_api", __name__)


@instance_api.errorhandler(errors.ChulaiError)
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

    utils.get_docker_client(),
    utils.get_supervisor_client(),
    current_app.config["SUPERVISOR_DIR"],
    current_app.config["WORKSPACE_DIR"]


@instance_api.route("/<app_id>/init", methods=["PUT"])
def deploy_instance(app_id):
    current_app.logger.debug(request.json)
    try:
        chulai_info = utils.get_chulai_config()
        instance_info = {
            key: request.json[key]
            for key in consts.INSTANCE_INFO
        }
        instance_info["app_id"] = app_id
        instance_type = request.json["type"]

        if instance_type == "web":
            cmd_name = "rails.j2"
        elif instance_type == "worker":
            cmd_name = "sidekiq.j2"
    except KeyError as exc:
        tip = "missing required field [{0}]".format(exc)
        raise errors.ChulaiError(tip, status_code=400)

    supervisor_conf = render_template(
        "supervisor.j2",
        cmd_name=cmd_name,
        chulai=chulai_info,
        instance=instance_info
    )
    current_app.logger.info("going to deploy {0}".format(g.instance))
    current_app.logger.debug("supervisor conf:\n{0}".format(supervisor_conf))

    g.instance.deploy(supervisor_conf)

    return jsonify(status=consts.SUCCESS)


@instance_api.route("/<app_id>/stats")
def show_stats(app_id):
    """show instance's stats [cpu, memory usage, etc.]

    :query app_id: app_id

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
    g.instance.raise_not_inited()

    return jsonify(
        status=consts.SUCCESS,
        stats=g.instance.stats
    )


@instance_api.route("/<app_id>/config")
def show_config(app_id):
    """show instance's config [config, env, etc.]

    :query app: app
    :query app_id: app_id

    :statuscode 200: show config json
    :statuscode 404: instance not found

    :>header Content-Type: application/json

    :>json string status: ``success`` or ``failed``
    :>json string message: if status is ``failed``, error reason goes here
    :>json dict config: if status is ``success``, instance config goes here

    **Example response**:

    .. sourcecode:: http

        {
            "status": "success",
            "config": {
                "name": "app1-8000",
                "mem_limit": 100,
                "image": "chulai/app1:build-hash",
                "env": {
                    "HELLO": "world",
                    "NIHAO": "shijie"
                    "FOO": "bar"
                }
            }
        }
    """
    g.instance.raise_not_inited()
    return jsonify(
        status=consts.SUCCESS,
        config=g.instance.config
    )


@instance_api.route("/<app_id>/logs/<log_type>")
def cat_log(app_id, log_type):
    """tailf instance's log

    :query app: app name like `chulai`
    :query app_id: app_id
    :query log_type: log_type like ``production``, ``access``, etc.

    :>header Content-Type: text/event-stream

    :statuscode 200: return log line by line
    :statuscode 400: log type not found
    :statuscode 404: instance not found
    :statuscode 500: instance not running
    """
    g.instance.raise_not_inited()

    current_app.logger.info(
        'goging to tail {0}\'s {1}, args {2}'.format(
            g.instance, log_type, request.args
        )
    )

    log_path = g.instance.get_log_path(log_type)

    return Response(
        open(log_path, "rt"),
        mimetype="text/event-stream"
    )


@instance_api.route("/<app_id>/streaming/<log_type>")
def tailf_log(app_id, log_type):
    """tailf instance's log

    :query app: app name like `chulai`
    :query app_id: app_id
    :query log_type: log_type like ``production``, ``access``, etc.

    :>header Content-Type: text/event-stream

    :statuscode 200: return log line by line
    :statuscode 400: log type not found
    :statuscode 404: instance not found
    :statuscode 500: instance not running
    """
    g.instance.raise_not_inited()

    current_app.logger.info(
        'goging to tail {0}\'s {1}, args {2}'.format(
            g.instance, log_type, request.args
        )
    )

    app_log = g.instance.get_log(log_type)
    timeout = float(request.args.get('timeout', 0))
    #FIX
    return ""



@instance_api.route("/<app_id>/<operation>", methods=["PUT"])
def start_instance(app_id, operation):
    """make instance ``up`` or ``halt`` it

    :query app: app name like `chulai`
    :query app_id: app_id
    :query operation: ``up`` or ``halt``

    :header Content-Type: application/json
    :>json string status: ``success`` or ``error``
    **Example Response:**

    .. sourcecode:: http

        {
            "status": "success"
        }
    """
    g.instance.raise_not_inited()

    operation_func = getattr(g.instance, operation, None)
    if operation_func is not None:
        current_app.logger.info(
            "going to {0} {1}".format(operation, g.instance)
        )
        operation_func()
        return jsonify(status=consts.SUCCESS, operation=operation)
    else:
        raise errors.ChulaiError(
            "unknown operation [{0}]".format(operation),
            status_code=400
        )


@instance_api.route("/<app_id>/destroy", methods=["PUT"])
def destroy_instance(app_id):
    """destroy a instance, clean it's workspace, upload it's log"""
    g.instance.destroy()

    return jsonify(status=consts.SUCCESS)
