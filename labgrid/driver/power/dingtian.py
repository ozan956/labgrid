"""
This driver implements a power port for Dingtian DT-R00x Ethernet relay
boards (the 2/4/8/16/24/32 channel family) using the board's HTTP GET CGI
protocol.

The board acts as an HTTP server:
  * set relay:  GET /relay_cgi.cgi?type=0&relay=<index-1>&on=<0|1>&time=0&pwd=0&
                response: &<result>&<type>&<relay>&<on>&<time>&
  * read state: GET /relay_cgi_load.cgi
                response: &<result>&<count>&<r1>&<r2>&...&<rN>&

Fields are delimited by '&', <result> is 0 on success, and each relay field
is '1' (ON) or '0' (OFF). Relay indices in the CGI protocol are 0-based, so
labgrid channel N maps to relay=N-1.

The "HTTP GET CGI" protocol has to be enabled for the relay channel in the
board's web configuration (Setting -> Relay Connect).

Driver has been developed against:
* DT-R004 - 4 relay outputs
"""

import requests

from ..exception import ExecutionError

PORT = 80


def _parse_cgi(text):
    return [field for field in text.strip().split("&") if field != ""]


def power_set(host, port, index, value):
    index = int(index)
    assert 1 <= index <= 32
    on = 1 if value else 0
    response = requests.get(
        f"http://{host}:{port}/relay_cgi.cgi"
        f"?type=0&relay={index - 1}&on={on}&time=0&pwd=0&"
    )
    response.raise_for_status()

    # response fields: result, type, relay, on, time
    fields = _parse_cgi(response.text)
    if len(fields) < 5 or fields[0] != "0":
        raise ExecutionError(
            f"failed to set relay {index} on {host}:{port}: {response.text!r}"
        )
    if fields[3] != str(on):
        raise ExecutionError(
            f"relay {index} did not reach requested state on {host}:{port}: "
            f"{response.text!r}"
        )


def power_get(host, port, index):
    index = int(index)
    assert 1 <= index <= 32
    response = requests.get(f"http://{host}:{port}/relay_cgi_load.cgi")
    response.raise_for_status()

    # response fields: result, count, relay1, relay2, ...
    fields = _parse_cgi(response.text)
    if len(fields) < 2 or fields[0] != "0":
        raise ExecutionError(
            f"failed to read relay status from {host}:{port}: {response.text!r}"
        )
    relays = fields[2:]
    if index > len(relays):
        raise ExecutionError(
            f"relay {index} not in status reply from {host}:{port}: "
            f"{response.text!r}"
        )
    return relays[index - 1] == "1"
