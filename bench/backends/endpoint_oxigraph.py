"""Remote SPARQL endpoint backed by a docker-managed Oxigraph server.

Spawns its own container so tests don't depend on docker-compose state.
"""
import io
import socket
import subprocess
import time
import uuid

import requests


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class EndpointOxigraphBackend:
    is_persistent = True

    def __init__(self, image: str = "oxigraph/oxigraph:0.4.4"):
        self.name = f"endpoint_oxigraph[{image}]"
        self._port = _free_port()
        self._container = f"bench-oxigraph-{uuid.uuid4().hex[:8]}"
        self._url = f"http://127.0.0.1:{self._port}"
        subprocess.run(
            ["docker", "run", "-d", "--rm", "--name", self._container,
             "-p", f"{self._port}:7878", image, "serve", "--bind", "0.0.0.0:7878"],
            check=True, capture_output=True,
        )
        self._wait_ready(timeout=30.0)

    def _wait_ready(self, timeout: float) -> None:
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                if requests.get(f"{self._url}/", timeout=2).status_code in (200, 404):
                    return
            except requests.RequestException:
                time.sleep(0.5)
        raise RuntimeError("oxigraph endpoint did not become ready in time")

    def load(self, ontology):
        buf = io.BytesIO()
        ontology.save(file=buf, format="ntriples")
        r = requests.post(
            f"{self._url}/store?default",
            data=buf.getvalue(),
            headers={"Content-Type": "application/n-triples"},
            timeout=300,
        )
        r.raise_for_status()

    def construct(self, sparql: str):
        r = requests.post(
            f"{self._url}/query",
            data={"query": sparql},
            headers={"Accept": "application/n-triples"},
            timeout=300,
        )
        r.raise_for_status()
        return r.text.splitlines()

    def select(self, sparql: str):
        r = requests.post(
            f"{self._url}/query",
            data={"query": sparql},
            headers={"Accept": "application/sparql-results+json"},
            timeout=300,
        )
        r.raise_for_status()
        raw = r.json().get("results", {}).get("bindings", [])
        # Unwrap each binding cell from {"type":…,"value":…} to its plain value string
        return [{k: v["value"] for k, v in row.items()} for row in raw]

    def close(self):
        subprocess.run(["docker", "rm", "-f", self._container],
                       check=False, capture_output=True)
