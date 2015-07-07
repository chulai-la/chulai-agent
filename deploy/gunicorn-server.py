import multiprocessing
import os

__curdir__ = os.path.dirname(os.path.realpath(__file__))

workers = multiprocessing.cpu_count() * 2 + 1
logconfig = os.path.join(__curdir__, "gunicorn-log.conf")
