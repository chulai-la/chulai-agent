"""
Chulai Agent Errors
"""


class AgentError(Exception):
    """
    Base Error of Chulai
    """

    status_code = 500

    def __init__(self, message, status_code=None, payload=None):
        super(Exception, self).__init__()
        self.message = message
        if status_code is not None:
            self.status_code = status_code
        self.payload = payload

    def __str__(self):
        return "<ChulaiAgentError:{0} {1}>".format(
            self.status_code, self.message
        )

    def to_dict(self):
        """
        pack this exception to dict [including message and it's payload]
        """
        rv = dict(self.payload or ())
        rv["status"] = "error"
        rv["message"] = self.message
        return rv


class NotFoundError(Exception):
    """Image Not Found of Chulai"""
