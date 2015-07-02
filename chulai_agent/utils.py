import logging

logger = logging.getLogger(__name__)


def percentlize(float_percent):
    '''
    Convert float to percentage

    :param float_percent: origin float number

    Usage::
        >>> percentlize(0.9111)
        91.11
    '''
    return int(float_percent * 100 * 100) / 100.0


def to_MB(bytes_):
    return bytes_ / 1024.0 / 1024
