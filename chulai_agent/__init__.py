import logging
import os

from flask import Flask
from flask import jsonify


from . import misc_api
from . import instance_api


__all__ = ['create_app']
logger = logging.getLogger(__name__)


def create_app(config_path):
    app = Flask(__name__)
    app.config.from_pyfile(config_path)

    # inject env to config
    for key, val in os.environ.items():
        if key not in app.config:
            app.config[key] = val

    app.register_blueprint(misc_api.misc_api)
    app.register_blueprint(instance_api.instance_api, url_prefix="/instances")

    @app.errorhandler(400)
    def handle_400(error):
        message = 'missing arguments: {0}'.format(error.message)
        response = jsonify(
            status='error',
            message=message
        )
        response.status_code = 400
        logger.error(message)
        return response

    return app
