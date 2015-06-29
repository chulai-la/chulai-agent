'''
Chulai Errors
'''


class ChulaiError(Exception):
    '''
    Base Error of Chulai
    '''

    status_code = 500

    def __init__(self, message, status_code=None, payload=None):
        super(Exception, self).__init__()
        self.message = message
        if status_code is not None:
            self.status_code = status_code
        self.payload = payload

    def __str__(self):
        return '<ChulaiError:{0} {1}>'.format(self.status_code, self.message)

    def to_dict(self):
        '''
        pack this exception to dict [including message and it's payload]
        '''
        rv = dict(self.payload or ())
        rv['status'] = 'error'
        rv['message'] = self.message
        return rv


class ChulaiIOError(ChulaiError):
    '''
    Some low-level io error happend
    '''


class ChulaiNotInitedError(ChulaiError):
    '''
    Instance not ready
    '''
    status_code = 404  # not found


class ChulaiAlreadyInitedError(ChulaiError):
    '''
    Instance already inited
    '''
    status_code = 409  # conflict
