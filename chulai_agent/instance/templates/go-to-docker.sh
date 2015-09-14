#!/bin/bash

docker run -it \
    -h {{ agent.host_name }}.{{ agent.paas_domain }} \
    --rm=true \
    --memory-swap=-1 \
    -m {{ instance.memory_limit }}m \
    {%- for env_name, env_val in instance.environments.items() %}
    -e {{ "%r=%r"|format(env_name, env_val) }} \
    {%- endfor %}
    -v {{ instance.assets_dir }}:{{ instance.work_dir }}/public/assets \
    {{ instance.image_tag }} \
    /bin/bash
