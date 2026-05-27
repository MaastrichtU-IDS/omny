FROM python:3.12-slim

# System deps: git is needed by some owlready2 paths; build-essential is a safety
# net for any wheel that lacks a manylinux build.
RUN apt-get update \
    && apt-get install -y --no-install-recommends git build-essential \
    && rm -rf /var/lib/apt/lists/*

# JupyterLab + jupytext + an HTTP client for the remote-endpoint notebook.
RUN pip install --no-cache-dir jupyterlab==4.* jupytext==1.* requests

WORKDIR /workspace

# pymos is installed editable at container start (see compose command), because
# the repo is bind-mounted. We pre-install the heavy extras here so startup is fast.
RUN pip install --no-cache-dir \
    "parsimonious>=0.10" "owlready2>=0.46" \
    "rdflib>=7.0" "pyoxigraph>=0.4" "SPARQLWrapper>=2.0"

EXPOSE 8888

# Install pymos editable, then launch JupyterLab with no token (demo only).
# NOTE: do NOT run `jupytext --sync` here — the .ipynb files are committed WITH
# executed outputs (a later task), and a startup sync from the output-less .py would
# blank them. The jupytext.toml pairing handles sync when editing inside Jupyter.
CMD ["bash", "-lc", "pip install -e . && jupyter lab --ip=0.0.0.0 --port=8888 --no-browser --allow-root --ServerApp.token='' --ServerApp.password='' --notebook-dir=/workspace"]
