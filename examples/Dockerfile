FROM python:3.12-slim

# System deps: git is needed by some owlready2 paths; build-essential is a safety
# net for any wheel that lacks a manylinux build; curl fetches the docker CLI.
RUN apt-get update \
    && apt-get install -y --no-install-recommends git build-essential default-jre-headless curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Docker *client* only (no daemon). Notebook 06's ROBOT/Konclude cells shell out
# to `docker run …` against a host socket mounted via docker-compose.reasoners.yml.
# Harmless without that override: the cells probe `docker info` and skip if no
# daemon answers. Pinned static binary keeps the image lean (just the CLI).
RUN curl -fsSL https://download.docker.com/linux/static/stable/x86_64/docker-27.3.1.tgz \
    | tar -xz -C /usr/local/bin --strip-components=1 docker/docker

# JupyterLab + jupytext + an HTTP client for the remote-endpoint notebook.
RUN pip install --no-cache-dir jupyterlab==4.* jupytext==1.* requests

WORKDIR /workspace

# omny is installed editable at container start (see compose command), because
# the repo is bind-mounted. Pre-install every dep + every optional extra used
# by the notebooks so startup is fast and notebook 06 (HermiT + owlrl) and
# notebook 05 (Jupyter magics) work out of the box:
#   - lark + parsimonious + owlready2 + rdflib  : core omny deps
#   - pyoxigraph + SPARQLWrapper                : notebook 02/03 backends
#   - owlrl                                     : notebook 06 OWL 2 RL closure
RUN pip install --no-cache-dir \
    "lark>=1.0" "parsimonious>=0.10" "owlready2>=0.46" \
    "rdflib>=7.0" "pyoxigraph>=0.4" "SPARQLWrapper>=2.0" \
    "owlrl>=6.0"

EXPOSE 8888

# Install omny editable, then launch JupyterLab with no token (demo only).
# NOTE: do NOT run `jupytext --sync` here — the .ipynb files are committed WITH
# executed outputs (a later task), and a startup sync from the output-less .py would
# blank them. The jupytext.toml pairing handles sync when editing inside Jupyter.
CMD ["bash", "-lc", "pip install -e . && jupyter lab --ip=0.0.0.0 --port=8888 --no-browser --allow-root --ServerApp.token='' --ServerApp.password='' --notebook-dir=/workspace"]
