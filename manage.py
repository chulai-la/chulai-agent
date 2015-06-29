# -*- coding: utf8 -*-

import os

import flask.ext.script
import jinja2
import shcmd


from chulai_agent import create_app

__curdir__ = os.path.realpath(os.path.dirname(__file__))

app = create_app(os.path.join(__curdir__, "config.cfg"))
manager = flask.ext.script.Manager(app)


if __name__ == "__main__":
    manager.run()
