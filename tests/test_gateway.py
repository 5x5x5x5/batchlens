"""The demo's gateway: which server a path goes to, and one request per connection."""

import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "gateway", Path(__file__).parents[1] / "tools" / "gateway.py"
)
gateway = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gateway)

ROUTES = {"/batchlens/": 9100, "/hist/": 8100}


def test_a_path_goes_to_the_app_that_owns_its_prefix_and_the_rest_to_plantcraft():
    assert gateway.upstream("/batchlens/api/batches", ROUTES, 8060) == 9100
    assert gateway.upstream("/batchlens", ROUTES, 8060) == 9100
    assert gateway.upstream("/hist/", ROUTES, 8060) == 8100
    assert gateway.upstream("/history", ROUTES, 8060) == 8060
    assert gateway.upstream("/", ROUTES, 8060) == 8060


def test_each_connection_carries_one_request_unless_it_is_a_websocket():
    head = b"GET /hist/ HTTP/1.1\r\nHost: x\r\nConnection: keep-alive\r\n\r\n"
    assert (
        gateway.one_request(head) == b"GET /hist/ HTTP/1.1\r\nHost: x\r\nConnection: close\r\n\r\n"
    )
    socket = b"GET /ws HTTP/1.1\r\nConnection: Upgrade\r\nUpgrade: websocket\r\n\r\n"
    assert gateway.one_request(socket) == socket
