#!/bin/bash

docker run \
    -h {{ agent.host_name }}.{{ agent.paas_domain }} \
    --rm=true \
    --memory-swap=-1 \
    -m {{ instance.memory_limit }}m \
    {%- for env_name, env_val in instance.environments.items() %}
    -e {{ "%r=%r"|format(env_name, env_val) }} \
    {%- endfor %}
    {{ instance.image_tag }} \
    /bin/bash
