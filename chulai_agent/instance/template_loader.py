import os
from jinja2 import Environment, FileSystemLoader, StrictUndefined


__all__ = ["render_template"]
__curdir__ = os.path.dirname(os.path.realpath(__file__))

env = Environment(
    loader=FileSystemLoader(os.path.join(__curdir__, "templates")),
    undefined=StrictUndefined
)


def render_template(template_name, **kwargs):
    template = env.get_template(template_name)
    return template.render(kwargs)
