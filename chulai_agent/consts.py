import socket


VERSION = '1.0.0'

HOSTNAME = socket.gethostname()
UA = {'user-agent': 'chulai-agent {0}@{1}'.format(HOSTNAME, VERSION)}

OK = 'ok'
SUCCESS = 'success'
ERROR = 'error'

SUPERVISOR_STOPPED_STATES = (
    0,  # STOPPED
    100,  # EXITED
    200,  # FATAL
    1000  # UNKNOWN
)

SUPERVISOR_RUNNING_STATES = (
    10,  # STARTING
    20,  # RUNNING,
    30,  # BACKOFF,
)
