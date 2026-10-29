"""Road network model and validation (TMS-F-010).

A network is plain JSON:

    {"name": "...",
     "nodes": [{"id": "A", "type": "entry"}, {"id": "X", "type": "signal", "signal": {...}},
               {"id": "B", "type": "exit"}, {"id": "J", "type": "junction"}],
     "links": [{"id": "A_X", "from": "A", "to": "X", "length_m": 300, "speed_mps": 13.9}],
     "demand": [{"link": "A_X", "rate_per_hour": 600}]}

A signal node has ``"signal": {"yellow": 3, "all_red": 2, "offset": 0,
"phases": [{"name": "NS", "green": 30, "links": ["A_X"]}]}``.
``validate_network`` returns a list of problems (empty list = valid); orphan links and nodes
are reported before a run is allowed to start.
"""
from __future__ import annotations

import copy
from collections import defaultdict, deque

from tms.common.errors import TMSError

NODE_TYPES = ("entry", "exit", "signal", "junction")
DEFAULT_SPEED = 13.9  # metres per second, about 50 km/h


class NetworkValidationError(TMSError):
    status_code = 422
    code = "network_invalid"


def normalize(topology: dict) -> dict:
    """Return a copy with defaults filled in (lanes, speed, offset, yellow, all-red)."""
    net = copy.deepcopy(topology)
    for link in net.get("links", []):
        if isinstance(link, dict):
            link.setdefault("lanes", 1)
            link.setdefault("speed_mps", DEFAULT_SPEED)
    for node in net.get("nodes", []):
        if isinstance(node, dict) and isinstance(node.get("signal"), dict):
            node["signal"].setdefault("yellow", 3)
            node["signal"].setdefault("all_red", 2)
            node["signal"].setdefault("offset", 0)
    net.setdefault("demand", [])
    return net


def _positive(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and value > 0


def validate_network(topology: dict) -> list[str]:
    errors: list[str] = []
    if not isinstance(topology, dict):
        return ["network must be a JSON object"]
    nodes, links = topology.get("nodes"), topology.get("links")
    if not isinstance(nodes, list) or not nodes:
        return ["network needs a non-empty 'nodes' list"]
    if not isinstance(links, list) or not links:
        return ["network needs a non-empty 'links' list"]

    node_by_id: dict[str, dict] = {}
    for node in nodes:
        if not isinstance(node, dict) or not isinstance(node.get("id"), str) or not node["id"]:
            errors.append("every node needs a text id")
            continue
        if node["id"] in node_by_id:
            errors.append(f"duplicate node id {node['id']}")
        if node.get("type") not in NODE_TYPES:
            errors.append(f"node {node['id']} has type {node.get('type')!r}; use one of {list(NODE_TYPES)}")
        node_by_id[node["id"]] = node

    link_by_id: dict[str, dict] = {}
    incoming: dict[str, list[str]] = defaultdict(list)
    outgoing: dict[str, list[str]] = defaultdict(list)
    for link in links:
        if not isinstance(link, dict) or not isinstance(link.get("id"), str) or not link["id"]:
            errors.append("every link needs a text id")
            continue
        lid = link["id"]
        if lid in link_by_id:
            errors.append(f"duplicate link id {lid}")
        link_by_id[lid] = link
        if link.get("from") not in node_by_id:
            errors.append(f"orphan link {lid}: start node {link.get('from')!r} does not exist")
            continue
        if link.get("to") not in node_by_id:
            errors.append(f"orphan link {lid}: end node {link.get('to')!r} does not exist")
            continue
        if link["from"] == link["to"]:
            errors.append(f"link {lid} starts and ends at the same node")
        if not _positive(link.get("length_m")):
            errors.append(f"link {lid} needs a positive length_m")
        if "speed_mps" in link and not _positive(link["speed_mps"]):
            errors.append(f"link {lid} needs a positive speed_mps")
        if node_by_id[link["from"]].get("type") == "exit":
            errors.append(f"link {lid} starts at an exit node")
        if node_by_id[link["to"]].get("type") == "entry":
            errors.append(f"link {lid} ends at an entry node")
        outgoing[link["from"]].append(lid)
        incoming[link["to"]].append(lid)

    for nid, node in node_by_id.items():
        kind = node.get("type")
        if not incoming[nid] and not outgoing[nid]:
            errors.append(f"orphan node {nid}: no links attached")
        elif kind == "entry" and not outgoing[nid]:
            errors.append(f"entry node {nid} has no outgoing link")
        elif kind == "exit" and not incoming[nid]:
            errors.append(f"exit node {nid} has no incoming link")
        elif kind in ("signal", "junction") and (not incoming[nid] or not outgoing[nid]):
            errors.append(f"{kind} node {nid} needs at least one incoming and one outgoing link")
        if kind == "signal":
            errors.extend(_validate_signal(nid, node, incoming[nid]))

    for item in topology.get("demand", []) or []:
        link = link_by_id.get(item.get("link")) if isinstance(item, dict) else None
        if link is None:
            errors.append(f"demand refers to unknown link {item.get('link') if isinstance(item, dict) else item!r}")
        elif node_by_id.get(link.get("from"), {}).get("type") != "entry":
            errors.append(f"demand link {link['id']} must start at an entry node")
        elif not isinstance(item.get("rate_per_hour"), (int, float)) or item["rate_per_hour"] < 0:
            errors.append(f"demand on {link['id']} needs rate_per_hour of zero or more")

    if not errors:
        errors.extend(_reachability_errors(node_by_id, link_by_id, outgoing))
    return errors


def _validate_signal(nid: str, node: dict, incoming_links: list[str]) -> list[str]:
    signal = node.get("signal")
    if not isinstance(signal, dict) or not isinstance(signal.get("phases"), list) or not signal["phases"]:
        return [f"signal node {nid} needs a 'signal' object with a non-empty 'phases' list"]
    errors: list[str] = []
    covered: set[str] = set()
    for phase in signal["phases"]:
        if not isinstance(phase, dict) or not isinstance(phase.get("name"), str) or not phase["name"]:
            errors.append(f"every phase at {nid} needs a name")
            continue
        green = phase.get("green")
        if isinstance(green, bool) or not isinstance(green, int) or green < 1:
            errors.append(f"phase {phase['name']} at {nid} needs a whole-number green of at least 1 second")
        for lid in phase.get("links", []):
            if lid not in incoming_links:
                errors.append(f"phase {phase['name']} at {nid} serves {lid}, which is not an incoming link of {nid}")
            covered.add(lid)
    for lid in incoming_links:
        if lid not in covered:
            errors.append(f"incoming link {lid} of signal {nid} is not served by any phase")
    for key in ("yellow", "all_red", "offset"):
        value = signal.get(key, 0)
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            errors.append(f"signal {nid} needs {key} as a whole number of zero or more")
    return errors


def _reachability_errors(nodes: dict[str, dict], links: dict[str, dict], outgoing: dict[str, list[str]]) -> list[str]:
    errors: list[str] = []
    entries = [n for n, d in nodes.items() if d.get("type") == "entry"]
    if not entries:
        return ["network needs at least one entry node"]
    reached_links: set[str] = set()
    for entry in entries:
        seen, queue = {entry}, deque([entry])
        reached_exit = False
        while queue:
            node = queue.popleft()
            if nodes[node].get("type") == "exit":
                reached_exit = True
            for lid in outgoing.get(node, []):
                reached_links.add(lid)
                nxt = links[lid]["to"]
                if nxt not in seen:
                    seen.add(nxt)
                    queue.append(nxt)
        if not reached_exit:
            errors.append(f"entry node {entry} cannot reach any exit")
    for lid in links:
        if lid not in reached_links:
            errors.append(f"orphan link {lid}: not reachable from any entry")
    return errors


def check_or_raise(topology: dict) -> dict:
    errors = validate_network(topology)
    if errors:
        raise NetworkValidationError(errors)
    return normalize(topology)
