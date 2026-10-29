"""Traffic flow simulation (TMS-F-009).

A simple one-second-step model:
* vehicles arrive on entry links at random times (seeded, so a seed always gives the same run);
* each vehicle drives at the link speed unless the vehicle ahead is closer than ``MIN_GAP``;
* at a signal node the front vehicle waits at the stop line until its link has green, then
  leaves one vehicle every ``HEADWAY`` seconds;
* at a junction (no signal) or an exit vehicles pass freely.

The result is raw data (delays, queue statistics, sampled trajectories). ``metrics.compute_metrics``
turns it into delay, queue length and throughput. Results are estimates, not traffic-engineering
sign-off (SRS RSK-005).
"""
from __future__ import annotations

import math
import random
from collections import defaultdict, deque

from tms.common.errors import ValidationFailure
from tms.simulation.network import check_or_raise

MIN_GAP = 7.0         # metres, front bumper to front bumper
HEADWAY = 2.0         # seconds between vehicles leaving a stop line
TRAJECTORY_STEP = 5   # seconds between recorded trajectory points
MIN_DURATION, MAX_DURATION = 60, 7200

DEFAULT_PARAMS = {"duration_seconds": 3600, "seed": 42, "demand_scale": 1.0, "green_overrides": {}}


class _Vehicle:
    __slots__ = ("id", "link", "pos", "entered", "free_flow", "points", "moved")

    def __init__(self, vid: int, link: str, entered: float):
        self.id = vid
        self.link = link
        self.pos = 0.0
        self.entered = entered
        self.free_flow = 0.0
        self.points: list[list] = []
        self.moved = 0.0


def _signal_schedules(net: dict, overrides: dict) -> dict[str, tuple[int, int, list[frozenset]]]:
    """node id -> (cycle length, offset, allowed links for each second of the cycle)."""
    schedules: dict[str, tuple[int, int, list[frozenset]]] = {}
    for node in net["nodes"]:
        if node.get("type") != "signal":
            continue
        signal = node["signal"]
        changes = overrides.get(node["id"], {})
        slots: list[frozenset] = []
        for phase in signal["phases"]:
            green = int(changes.get(phase["name"], phase["green"]))
            if green < 1:
                raise ValidationFailure(f"green override for {phase['name']} at {node['id']} must be at least 1")
            slots.extend([frozenset(phase["links"])] * green)
            slots.extend([frozenset()] * (signal["yellow"] + signal["all_red"]))
        schedules[node["id"]] = (len(slots), signal["offset"], slots)
    return schedules


def run_simulation(network: dict, params: dict | None = None) -> dict:
    """Run one scenario and return raw results. Raises NetworkValidationError for a bad network."""
    net = check_or_raise(network)
    p = {**DEFAULT_PARAMS, **(params or {})}
    duration = p["duration_seconds"]
    if isinstance(duration, bool) or not isinstance(duration, int) or not MIN_DURATION <= duration <= MAX_DURATION:
        raise ValidationFailure(f"duration_seconds must be a whole number between {MIN_DURATION} and {MAX_DURATION}")
    if not isinstance(p["demand_scale"], (int, float)) or not 0 <= p["demand_scale"] <= 5:
        raise ValidationFailure("demand_scale must be between 0 and 5")

    rng = random.Random(p["seed"])
    nodes = {n["id"]: n for n in net["nodes"]}
    links = {l["id"]: l for l in net["links"]}
    outgoing: dict[str, list[str]] = defaultdict(list)
    for link in net["links"]:
        outgoing[link["from"]].append(link["id"])
    schedules = _signal_schedules(net, p["green_overrides"] or {})
    approach_links = [lid for lid, l in links.items() if nodes[l["to"]]["type"] == "signal"]

    # arrival process: exponential gaps for each demand entry
    rates = {d["link"]: d["rate_per_hour"] * p["demand_scale"] / 3600.0 for d in net["demand"]}
    next_arrival = {lid: rng.expovariate(r) for lid, r in rates.items() if r > 0}
    backlog: dict[str, deque] = {lid: deque() for lid in next_arrival}

    on_link: dict[str, list[_Vehicle]] = {lid: [] for lid in links}   # front vehicle first
    last_discharge: dict[str, float] = {}
    finished: list[_Vehicle] = []
    delays: list[float] = []
    entered_count = 0
    next_id = 1
    queue_sum = 0
    queue_max = 0
    trajectories: list[dict] = []

    def next_link(from_link: str) -> str | None:
        node = links[from_link]["to"]
        options = outgoing.get(node, [])
        if not options:
            return None
        turns = nodes[node].get("turns", {}).get(from_link)
        if turns:
            ids = [i for i in options if i in turns]
            if ids:
                return rng.choices(ids, [turns[i] for i in ids])[0]
        return rng.choice(options)

    for t in range(duration):
        # 1. new arrivals wait in a backlog outside the link until there is room
        for lid in list(next_arrival):
            while next_arrival[lid] <= t:
                backlog[lid].append(next_arrival[lid])
                next_arrival[lid] += rng.expovariate(rates[lid])
            queue = backlog[lid]
            vehicles = on_link[lid]
            if queue and (not vehicles or vehicles[-1].pos >= MIN_GAP):
                veh = _Vehicle(next_id, lid, queue.popleft())
                next_id += 1
                entered_count += 1
                veh.free_flow += links[lid]["length_m"] / links[lid]["speed_mps"]
                vehicles.append(veh)

        # 2. move vehicles; transfers are applied after every link was processed
        transfers: list[tuple[_Vehicle, str, str]] = []
        receiving: set[str] = set()
        leaving: list[tuple[_Vehicle, str]] = []
        queued_now = 0
        for lid, vehicles in on_link.items():
            if not vehicles:
                continue
            link = links[lid]
            speed = link["speed_mps"]
            node = nodes[link["to"]]
            leader_pos: float | None = None
            link_queued = 0
            for index, veh in enumerate(vehicles):
                before = veh.pos
                target = veh.pos + speed
                if leader_pos is not None:
                    target = min(target, leader_pos - MIN_GAP)
                crossed = False
                if index == 0 and target >= link["length_m"]:
                    can_cross = False
                    if node["type"] == "exit":
                        can_cross = True
                    elif node["type"] == "junction":
                        can_cross = True
                    elif node["type"] == "signal":
                        cycle, offset, slots = schedules[node["id"]]
                        can_cross = lid in slots[(t + offset) % cycle]
                    if can_cross and node["type"] != "exit":
                        if t - last_discharge.get(lid, -1e9) < HEADWAY:
                            can_cross = False
                    if can_cross and node["type"] != "exit":
                        dest = next_link(lid)
                        if dest is None:
                            can_cross = False
                        else:
                            rear = on_link[dest][-1].pos if on_link[dest] else None
                            if dest in receiving or (rear is not None and rear < MIN_GAP):
                                can_cross = False
                            else:
                                receiving.add(dest)
                                transfers.append((veh, lid, dest))
                                last_discharge[lid] = t
                                crossed = True
                    elif can_cross:
                        leaving.append((veh, lid))
                        last_discharge[lid] = t
                        crossed = True
                    if not crossed:
                        target = link["length_m"]
                elif index == 0:
                    target = min(target, link["length_m"])
                veh.pos = max(veh.pos, target) if not crossed else link["length_m"]
                veh.moved = veh.pos - before
                if not crossed and veh.moved < 0.5:
                    link_queued += 1
                leader_pos = veh.pos
                if t % TRAJECTORY_STEP == 0:
                    veh.points.append([t, lid, round(veh.pos, 1)])
            if lid in approach_links:
                queued_now += link_queued
                queue_max = max(queue_max, link_queued)
        queue_sum += queued_now

        for veh, lid in leaving:
            on_link[lid].remove(veh)
            veh.points.append([t + 1, lid, round(links[lid]["length_m"], 1)])
            delays.append(max(0.0, (t + 1 - veh.entered) - veh.free_flow))
            finished.append(veh)
        for veh, lid, dest in transfers:
            on_link[lid].remove(veh)
            veh.link = dest
            veh.pos = 0.0
            veh.free_flow += links[dest]["length_m"] / links[dest]["speed_mps"]
            on_link[dest].append(veh)

    for veh in finished:
        trajectories.append({"id": veh.id, "enteredAt": round(veh.entered, 1), "points": veh.points})
    still_driving = sum(len(v) for v in on_link.values())
    return {
        "params": p,
        "vehiclesEntered": entered_count,
        "vehiclesCompleted": len(finished),
        "vehiclesInNetwork": still_driving,
        "delays": delays,
        "queue": {"sumQueued": queue_sum, "ticks": duration, "approachLinks": len(approach_links), "maxQueue": queue_max},
        "trajectories": trajectories,
    }
