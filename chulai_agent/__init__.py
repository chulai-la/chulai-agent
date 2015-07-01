import logging

from flask import Flask
from flask import jsonify


__all__ = ["create_app"]
logger = logging.getLogger(__name__)


def create_app(config_path):
    app = Flask(__name__)
    app.config.from_pyfile(config_path)

    from .clients import docker_client, supervisor_client
    docker_client.init_app(app)
    supervisor_client.init_app(app)

    from .instance_api import instance_api

    app.register_blueprint(instance_api)

    @app.errorhandler(400)
    def handle_400(error):
        message = "missing arguments: {0}".format(error.message)
        response = jsonify(
            status="error",
            message=message
        )
        response.status_code = 400
        logger.error(message)
        return response

    return app
