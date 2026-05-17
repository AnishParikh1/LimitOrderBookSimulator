from __future__ import annotations

from ctypes import CDLL, POINTER, Structure, byref, c_double, c_int
from pathlib import Path
import subprocess

from orderbook import Trade


SIDE_MAP = {"buy": 0, "sell": 1}
ORDER_TYPE_MAP = {"limit": 0, "market": 1}
REVERSE_SIDE_MAP = {0: "buy", 1: "sell"}
LIBRARY_NAME = "matching_engine.dll"


class COrderInput(Structure):
    _fields_ = [
        ("order_id", c_int),
        ("side", c_int),
        ("price", c_double),
        ("quantity", c_int),
        ("order_type", c_int),
        ("timestamp", c_int),
        ("reference_price", c_double),
        ("is_seed", c_int),
    ]


class CTradeOutput(Structure):
    _fields_ = [
        ("buy_order_id", c_int),
        ("sell_order_id", c_int),
        ("price", c_double),
        ("quantity", c_int),
        ("timestamp", c_int),
        ("aggressor_side", c_int),
    ]


class CSnapshotOutput(Structure):
    _fields_ = [
        ("timestamp", c_int),
        ("trade_count", c_int),
        ("reference_price", c_double),
        ("last_trade_price", c_double),
        ("best_bid", c_double),
        ("best_ask", c_double),
        ("mid_price", c_double),
        ("spread", c_double),
        ("resting_orders", c_int),
    ]


def build_matching_engine(force: bool = False) -> Path:
    repo_root = Path(__file__).resolve().parent
    library_path = repo_root / LIBRARY_NAME
    if library_path.exists() and not force:
        return library_path
    if library_path.exists() and force:
        library_path.unlink()

    source_path = repo_root / "matching_engine.cpp"
    command = [
        "g++",
        "-O3",
        "-std=c++17",
        "-shared",
        "-static",
        "-static-libgcc",
        "-static-libstdc++",
        "-o",
        str(library_path),
        str(source_path),
    ]
    subprocess.run(command, check=True, cwd=repo_root)
    return library_path


def _load_library(build_if_needed: bool = True):
    repo_root = Path(__file__).resolve().parent
    library_path = repo_root / LIBRARY_NAME
    if not library_path.exists():
        if not build_if_needed:
            raise FileNotFoundError(f"{LIBRARY_NAME} does not exist. Build it first.")
        library_path = build_matching_engine()

    library = CDLL(str(library_path))
    library.simulate_order_flow.argtypes = [
        POINTER(COrderInput),
        c_int,
        POINTER(CTradeOutput),
        c_int,
        POINTER(CSnapshotOutput),
        c_int,
        POINTER(c_int),
        POINTER(c_int),
    ]
    library.simulate_order_flow.restype = c_int
    library.simulate_order_flow_stats.argtypes = [
        POINTER(COrderInput),
        c_int,
        POINTER(c_int),
        POINTER(c_int),
    ]
    library.simulate_order_flow_stats.restype = c_int
    library.benchmark_simulate_order_flow_stats.argtypes = [
        POINTER(COrderInput),
        c_int,
        c_int,
        POINTER(c_double),
        POINTER(c_int),
        POINTER(c_int),
    ]
    library.benchmark_simulate_order_flow_stats.restype = c_int
    return library


def _pack_inputs(order_flow: list):
    order_count = len(order_flow)
    inputs = (COrderInput * order_count)()
    for index, generated in enumerate(order_flow):
        inputs[index] = COrderInput(
            order_id=generated.order.order_id,
            side=SIDE_MAP[generated.order.side],
            price=-1.0 if generated.order.price is None else generated.order.price,
            quantity=generated.order.quantity,
            order_type=ORDER_TYPE_MAP[generated.order.order_type],
            timestamp=generated.order.timestamp,
            reference_price=generated.reference_price,
            is_seed=1 if generated.is_seed else 0,
        )
    return inputs, order_count


def _normalize_snapshot(snapshot: CSnapshotOutput) -> dict:
    last_trade_price = None if snapshot.last_trade_price < 0 else snapshot.last_trade_price
    best_bid = None if snapshot.best_bid < 0 else snapshot.best_bid
    best_ask = None if snapshot.best_ask < 0 else snapshot.best_ask
    mid_price = None if snapshot.mid_price < 0 else snapshot.mid_price
    spread = None if snapshot.spread < 0 else snapshot.spread
    return {
        "timestamp": snapshot.timestamp,
        "trade_count": snapshot.trade_count,
        "reference_price": snapshot.reference_price,
        "last_trade_price": last_trade_price,
        "best_bid": best_bid,
        "best_ask": best_ask,
        "mid_price": mid_price,
        "spread": spread,
        "bid_levels": [],
        "ask_levels": [],
        "resting_orders": snapshot.resting_orders,
    }


def run_cpp_order_flow(order_flow: list, build_if_needed: bool = True):
    library = _load_library(build_if_needed=build_if_needed)
    inputs, order_count = _pack_inputs(order_flow)
    max_trades = max(1, order_count * 2)
    max_snapshots = max(1, order_count + 1)
    trades_out = (CTradeOutput * max_trades)()
    snapshots_out = (CSnapshotOutput * max_snapshots)()
    trades_written = c_int()
    snapshots_written = c_int()

    status = library.simulate_order_flow(
        inputs,
        order_count,
        trades_out,
        max_trades,
        snapshots_out,
        max_snapshots,
        byref(trades_written),
        byref(snapshots_written),
    )
    if status != 0:
        raise RuntimeError(f"C++ engine failed with status {status}")

    trades = [
        Trade(
            buy_order_id=trades_out[index].buy_order_id,
            sell_order_id=trades_out[index].sell_order_id,
            price=trades_out[index].price,
            quantity=trades_out[index].quantity,
            timestamp=trades_out[index].timestamp,
            aggressor_side=REVERSE_SIDE_MAP[trades_out[index].aggressor_side],
        )
        for index in range(trades_written.value)
    ]
    snapshots = [_normalize_snapshot(snapshots_out[index]) for index in range(snapshots_written.value)]
    orders_resting = snapshots[-1]["resting_orders"] if snapshots else 0
    return trades, snapshots, orders_resting


def run_cpp_order_flow_stats(order_flow: list, build_if_needed: bool = True):
    library = _load_library(build_if_needed=build_if_needed)
    inputs, order_count = _pack_inputs(order_flow)
    trades_written = c_int()
    resting_orders = c_int()

    status = library.simulate_order_flow_stats(
        inputs,
        order_count,
        byref(trades_written),
        byref(resting_orders),
    )
    if status != 0:
        raise RuntimeError(f"C++ stats engine failed with status {status}")

    return trades_written.value, resting_orders.value


def benchmark_cpp_order_flow(order_flow: list, repeats: int, build_if_needed: bool = True):
    library = _load_library(build_if_needed=build_if_needed)
    inputs, order_count = _pack_inputs(order_flow)
    average_seconds = c_double()
    trades_written = c_int()
    resting_orders = c_int()

    status = library.benchmark_simulate_order_flow_stats(
        inputs,
        order_count,
        repeats,
        byref(average_seconds),
        byref(trades_written),
        byref(resting_orders),
    )
    if status != 0:
        raise RuntimeError(f"C++ benchmark engine failed with status {status}")

    return average_seconds.value, trades_written.value, resting_orders.value
