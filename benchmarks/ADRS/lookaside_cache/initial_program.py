"""High-freedom seed for workload-adaptive storage-system design.

The evaluator scores systems that invent new devices or alter existing device
behavior, but it canonicalizes pricing during scoring. Known device archetypes
map to fixed cost anchors, and unknown devices can be inserted between anchors
by an evaluator-side device judge that can inspect device code. The only fixed contract is that
`build_system(...)` must return an object that can serve reads and writes over
a workload.
"""

from collections import Counter, OrderedDict, deque
from typing import Deque, Dict, List, Optional, Sequence, Tuple


CACHE_HIT_COST = 1.0
CACHE_MISS_PROBE_COST = 0.35
CACHE_FILL_COST = 0.75
CACHE_UPDATE_COST = 0.90
CACHE_INVALIDATE_COST = 0.30
DB_READ_COST = 8.0
DB_WRITE_COST = 10.0

assert CACHE_HIT_COST < DB_READ_COST
assert CACHE_MISS_PROBE_COST < DB_READ_COST
assert CACHE_FILL_COST < DB_READ_COST
assert CACHE_UPDATE_COST < DB_WRITE_COST
assert CACHE_INVALIDATE_COST < DB_WRITE_COST


def _normalize_workload(workload: Sequence[dict]) -> List[dict]:
    normalized: List[dict] = []
    for index, item in enumerate(workload):
        if not isinstance(item, dict):
            raise TypeError(f"Workload item {index} must be a dict, got {type(item).__name__}")
        op = item.get("op")
        key = item.get("key")
        if op not in {"read", "write"}:
            raise ValueError(f"Unsupported operation at index {index}: {op!r}")
        if not isinstance(key, int):
            raise TypeError(f"Workload key at index {index} must be an int, got {type(key).__name__}")
        value = item.get("value", 0)
        pod_id = item.get("pod_id", 0)
        normalized.append({"op": op, "key": key, "value": int(value), "pod_id": int(pod_id)})
    return normalized


class GenericKVDevice:
    """Composable KV device with LRU capacity handling."""

    def __init__(
        self,
        name: str,
        read_latency: float,
        write_latency: float,
        capacity: Optional[int] = None,
    ) -> None:
        self.name = name
        self.read_latency = float(read_latency)
        self.write_latency = float(write_latency)
        self.capacity = capacity
        self.store: "OrderedDict[int, int]" = OrderedDict()

    def contains(self, key: int) -> bool:
        return key in self.store

    def peek_local(self, key: int, default: int = 0, touch: bool = True) -> int:
        if key in self.store:
            if touch:
                self.store.move_to_end(key)
            return self.store[key]
        return default

    def put_local(self, key: int, value: int) -> None:
        self.store[key] = value
        self.store.move_to_end(key)
        if self.capacity is None:
            return
        while len(self.store) > self.capacity:
            self.store.popitem(last=False)

    def evict_local(self, key: int) -> None:
        self.store.pop(key, None)

    def on_read(self, key: int, pod_id: int, system: "ProgrammableStorageSystem") -> int:
        return self.peek_local(key)

    def on_write(self, key: int, value: int, pod_id: int, system: "ProgrammableStorageSystem") -> int:
        self.put_local(key, value)
        return value


class AuthoritativeStoreDevice(GenericKVDevice):
    """Authoritative backing store."""

    def __init__(self, name: str = "db") -> None:
        super().__init__(name=name, read_latency=DB_READ_COST, write_latency=DB_WRITE_COST, capacity=None)

    def peek_local(self, key: int, default: int = 0, touch: bool = True) -> int:
        return self.store.get(key, default)

    def put_local(self, key: int, value: int) -> None:
        self.store[key] = value


class ProgrammableStorageSystem:
    """Base class for high-freedom system designs.

    Subclasses are free to add devices, metadata, control planes, or entirely
    new routing behavior. The evaluator expects:
    - `handle_read(key, pod_id) -> int`
    - `handle_write(key, value, pod_id) -> None`
    - `current_authoritative_value(key) -> int`

    During evaluation, device latency is canonicalized by the evaluator rather
    than trusted from the literal values declared here. Known device archetypes
    map to fixed anchors, and evaluator-side placement may use device names,
    docstrings, and class source to position newly invented devices between
    those anchors. The evaluator also keeps its own authoritative ground truth
    for LSI checking and meters direct device-state access during scoring,
    including cache fills or other writes hidden inside a device read path. To
    make those canonical costs count toward the score, subclasses should route
    accesses through `read_device(...)` and `write_device(...)`.
    """

    def __init__(self) -> None:
        self.devices: Dict[str, GenericKVDevice] = {}
        self.authoritative_device_name: Optional[str] = None
        self.total_latency = 0.0
        self.device_read_counts: Counter = Counter()
        self.device_write_counts: Counter = Counter()

    def add_device(self, device: GenericKVDevice, authoritative: bool = False) -> None:
        self.devices[device.name] = device
        self.device_read_counts.setdefault(device.name, 0)
        self.device_write_counts.setdefault(device.name, 0)
        if authoritative:
            self.authoritative_device_name = device.name

    def get_device(self, device_name: str) -> GenericKVDevice:
        if device_name not in self.devices:
            raise KeyError(f"Unknown device: {device_name}")
        return self.devices[device_name]

    def read_device(self, device_name: str, key: int, pod_id: int = 0) -> int:
        device = self.get_device(device_name)
        self.total_latency += device.read_latency
        self.device_read_counts[device_name] += 1
        return device.on_read(key, pod_id, self)

    def write_device(self, device_name: str, key: int, value: int, pod_id: int = 0) -> int:
        device = self.get_device(device_name)
        self.total_latency += device.write_latency
        self.device_write_counts[device_name] += 1
        return device.on_write(key, value, pod_id, self)

    def current_authoritative_value(self, key: int) -> int:
        if self.authoritative_device_name is None:
            raise ValueError("System must register one authoritative device")
        authoritative = self.get_device(self.authoritative_device_name)
        return authoritative.peek_local(key, default=0, touch=False)

    def describe_design(self) -> dict:
        return {
            "devices": {
                name: {
                    "read_latency": device.read_latency,
                    "write_latency": device.write_latency,
                    "capacity": device.capacity,
                }
                for name, device in self.devices.items()
            },
            "authoritative_device": self.authoritative_device_name,
        }

    def handle_read(self, key: int, pod_id: int) -> int:
        raise NotImplementedError

    def handle_write(self, key: int, value: int, pod_id: int) -> None:
        raise NotImplementedError


def run_system_workload(system: ProgrammableStorageSystem, workload: Sequence[dict]) -> dict:
    normalized = _normalize_workload(workload)
    observed_reads: List[int] = []
    lsi_violations = 0
    lsi_violation_details: List[dict] = []
    total_reads = 0

    for item in normalized:
        if item["op"] == "read":
            total_reads += 1
            value = system.handle_read(item["key"], item["pod_id"])
            observed_reads.append(value)
            current_db_value = system.current_authoritative_value(item["key"])
            if value != current_db_value:
                lsi_violations += 1
                lsi_violation_details.append(
                    {
                        "pod_id": item["pod_id"],
                        "key": item["key"],
                        "served_value": value,
                        "db_value": current_db_value,
                    }
                )
        else:
            system.handle_write(item["key"], item["value"], item["pod_id"])

    lsi_violation_rate = 0.0 if total_reads == 0 else lsi_violations / total_reads
    return {
        "total_latency": system.total_latency,
        "lsi_violations": lsi_violations,
        "lsi_violation_rate": lsi_violation_rate,
        "lsi_safety_score": 1.0 - lsi_violation_rate,
        "device_read_counts": dict(system.device_read_counts),
        "device_write_counts": dict(system.device_write_counts),
        "observed_reads": observed_reads,
        "lsi_violation_details": lsi_violation_details,
        "design": system.describe_design(),
    }


def _window_unique_ratio(window_counts: Counter, window_size: int) -> float:
    if window_size <= 0:
        return 0.0
    return len(window_counts) / float(window_size)


# EVOLVE-BLOCK-START
class HotReplicaDevice(GenericKVDevice):
    """Fast replica for hot keys."""

    def __init__(self, name: str, capacity: int) -> None:
        super().__init__(name=name, read_latency=CACHE_HIT_COST, write_latency=CACHE_UPDATE_COST, capacity=capacity)


class StagingDevice(GenericKVDevice):
    """Very fast edge tier for frequently rewritten keys."""

    def __init__(self, name: str, capacity: int) -> None:
        super().__init__(name=name, read_latency=0.55, write_latency=0.65, capacity=capacity)


class AdaptiveFabricSystem(ProgrammableStorageSystem):
    def __init__(self, workload: Sequence[dict], cache_capacity: int = 64, hot_threshold: int = 2, scan_window: int = 16):
        super().__init__()
        self.workload = _normalize_workload(workload)
        self.cache_capacity = max(0, int(cache_capacity))
        self.hot_threshold = int(hot_threshold)
        self.scan_window = max(1, int(scan_window))

        self.add_device(AuthoritativeStoreDevice("db"), authoritative=True)
        self.add_device(HotReplicaDevice("hot_replica", capacity=max(1, self.cache_capacity)))
        self.add_device(StagingDevice("staging", capacity=max(1, self.cache_capacity // 2)))

        self.recent_ops: Deque[Tuple[str, int]] = deque()
        self.recent_reads: Counter = Counter()
        self.recent_writes: Counter = Counter()
        self.recent_keys: Counter = Counter()

    def _advance_window(self, op: str, key: int) -> None:
        self.recent_ops.append((op, key))
        self.recent_keys[key] += 1
        if op == "read":
            self.recent_reads[key] += 1
        else:
            self.recent_writes[key] += 1

        while len(self.recent_ops) > self.scan_window:
            old_op, old_key = self.recent_ops.popleft()
            self.recent_keys[old_key] -= 1
            if self.recent_keys[old_key] <= 0:
                del self.recent_keys[old_key]
            if old_op == "read":
                self.recent_reads[old_key] -= 1
                if self.recent_reads[old_key] <= 0:
                    del self.recent_reads[old_key]
            else:
                self.recent_writes[old_key] -= 1
                if self.recent_writes[old_key] <= 0:
                    del self.recent_writes[old_key]

    def _read_pressure(self, key: int) -> int:
        return self.recent_reads[key]

    def _write_pressure(self, key: int) -> int:
        return self.recent_writes[key]

    def _hot_score(self, key: int) -> int:
        return self._read_pressure(key) + (2 * self._write_pressure(key))

    def _scan_pressure(self) -> float:
        return _window_unique_ratio(self.recent_keys, len(self.recent_ops))

    def handle_read(self, key: int, pod_id: int) -> int:
        staging = self.get_device("staging")
        replica = self.get_device("hot_replica")
        unique_ratio = self._scan_pressure()
        hot_score = self._hot_score(key)

        if staging.contains(key):
            value = self.read_device("staging", key, pod_id)
        elif replica.contains(key):
            value = self.read_device("hot_replica", key, pod_id)
        else:
            value = self.read_device("db", key, pod_id)
            if hot_score >= self.hot_threshold and unique_ratio < 0.85:
                self.write_device("hot_replica", key, value, pod_id)

        self._advance_window("read", key)
        return value

    def handle_write(self, key: int, value: int, pod_id: int) -> None:
        staging = self.get_device("staging")
        replica = self.get_device("hot_replica")
        hot_score = self._hot_score(key)
        unique_ratio = self._scan_pressure()

        self.write_device("db", key, value, pod_id)

        if staging.contains(key) or hot_score >= self.hot_threshold + 1:
            self.write_device("staging", key, value, pod_id)
        else:
            staging.evict_local(key)

        if replica.contains(key):
            if hot_score >= self.hot_threshold or unique_ratio < 0.80:
                self.write_device("hot_replica", key, value, pod_id)
            else:
                replica.evict_local(key)
        elif hot_score >= self.hot_threshold + 1 and unique_ratio < 0.85:
            self.write_device("hot_replica", key, value, pod_id)

        self._advance_window("write", key)


def build_system(workload, cache_capacity=64):
    """Return a programmable system object for the evaluator to execute."""

    return AdaptiveFabricSystem(workload=workload, cache_capacity=cache_capacity)


# EVOLVE-BLOCK-END


def _demo_workload() -> List[dict]:
    return [
        {"op": "read", "key": 1, "pod_id": 0},
        {"op": "write", "key": 1, "value": 7, "pod_id": 0},
        {"op": "read", "key": 1, "pod_id": 1},
        {"op": "read", "key": 1, "pod_id": 2},
        {"op": "write", "key": 2, "value": 9, "pod_id": 0},
        {"op": "read", "key": 2, "pod_id": 1},
    ]


if __name__ == "__main__":
    demo = _demo_workload()
    system = build_system(demo, cache_capacity=4)
    print(run_system_workload(system, demo))
