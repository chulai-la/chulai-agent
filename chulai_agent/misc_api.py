from flask import Blueprint
from flask import jsonify

from . import consts


misc_api = Blueprint('misc_api', __name__)


@misc_api.route('/status')
def show_status():
    """
    show server status

    :>json string status: ``success`` or ``failed``
    :>json string host: hostname of the server

    **Example Response:**

    .. sourcecode:: http

        {
            "status": "success",
            "host": "host-name"
        }
    """
    return jsonify(status='success', host=consts.HOSTNAME)
