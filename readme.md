# Limit Order Book Simulator Guide

## Overview

This repo implements a simple event-driven limit order book simulator with two interchangeable matching engines:

- A pure Python engine in `orderbook.py`
- A C++ engine in `matching_engine.cpp`, exposed to Python through `cpp_engine.py`

Both engines run against the same generated order flow, so their outputs can be compared directly for correctness and performance.

## How The Simulator Works

The simulation is driven from `simulation.py`.

### 1. Order flow generation

For each run, the simulator:

- Seeds the order book with initial bid and ask depth around `start_price`
- Evolves a reference price with a simple random walk
- Generates new incoming orders for each step
- Marks each generated order as either:
  - `limit`: can rest on the book if not fully matched
  - `market`: consumes available liquidity and never rests

Each order includes:

- `order_id`
- `side` (`buy` or `sell`)
- `price` for limit orders
- `quantity`
- `timestamp`

### 2. Matching logic

The matching engine is event-driven:

- A new order arrives
- It checks the best price on the opposite side of the book
- If the order is marketable, it trades immediately
- Trades execute at the resting order's price
- Remaining quantity continues matching until:
  - the order is fully filled, or
  - no more crossing liquidity remains
- Unfilled limit orders rest on the book

This logic is implemented in:

- Python: `OrderBook.process_order(...)`
- C++: `simulate_order_flow(...)`

### 3. Snapshots and analytics

After each non-seed order, the simulator captures a snapshot containing:

- best bid
- best ask
- mid price
- spread
- resting order count
- last trade price
- trade count

Analytics in `analytics.py` summarize:

- total trades
- executed volume
- VWAP
- spread statistics
- mid-price change
- trade-price volatility
- runtime
- orders/second
- trades/second

## Engine Modes

The simulator supports three modes in `main.py`:

- `python`: run the Python order book only
- `cpp`: run the C++ engine only
- `compare`: run both and compare correctness and speed

## Speedup Analysis

### What was measured

There are now two different speed metrics in compare mode:

1. `cpp_speedup_vs_python`

This is the full end-to-end speedup. It includes:

- matching
- Python trade object creation
- Python snapshot object creation
- result marshaling back into Python

2. `benchmark_cpp_speedup_vs_python`

This is the core engine benchmark. It measures the hot matching loop more directly:

- Python benchmark: repeated matching runs in Python
- C++ benchmark: repeated matching runs inside native code, with the repeat loop timed in C++

This second metric is the better representation of raw engine speed.

### Verified benchmark result

The following command was run:

```powershell
python main.py --engine compare --steps 4000 --orders-per-step 3 --benchmark-repeats 20 --no-show
```

Observed output:

- `trades_match: True`
- `snapshots_match: True`
- `python_duration_ms: 4780.099`
- `cpp_duration_ms: 766.434`
- `cpp_speedup_vs_python: 6.237x`
- `benchmark_python_ms: 28.148`
- `benchmark_cpp_ms: 1.889`
- `benchmark_cpp_speedup_vs_python: 14.902x`

### Interpretation

The C++ engine is much faster at the actual matching work than Python, but the full-run speedup is lower because compare mode still has to:

- convert C++ outputs into Python objects
- build Python dictionaries for snapshots
- preserve identical output structure across both engines

So:

- raw matching speedup is about `14.9x`
- end-to-end simulation speedup is about `6.2x`

Both engines were verified to produce identical trades and identical snapshots on the same generated order flow.

## How To Use

### Run the Python simulator

```powershell
python main.py --engine python
```

### Run the C++ simulator

```powershell
python main.py --engine cpp
```

### Compare Python vs C++

```powershell
python main.py --engine compare --no-show
```

### Rebuild the C++ engine

```powershell
python main.py --engine cpp --force-rebuild-cpp --no-show
```

### Run a larger benchmark

```powershell
python main.py --engine compare --steps 4000 --orders-per-step 3 --benchmark-repeats 20 --no-show
```

### Save plots without opening a window

```powershell
python main.py --engine compare --plot-path compare_report.png --no-show
```

This writes:

- `compare_report_python.png`
- `compare_report_cpp.png`

### Useful arguments

- `--steps`: number of simulation time steps
- `--orders-per-step`: number of generated orders at each step
- `--start-price`: initial reference price
- `--seed`: random seed for reproducible runs
- `--limit-order-probability`: fraction of generated orders that are limit orders
- `--buy-probability`: probability of generating a buy order
- `--max-quantity`: maximum generated order size
- `--price-band`: max distance from reference price for generated limit orders
- `--benchmark-repeats`: repeated runs for the benchmark-only timing in compare mode
- `--no-show`: do not open the plot window

## Validation

The repo was validated with:

```powershell
python -m unittest discover -s tests -v
```

The current test suite checks:

- price-time matching behavior
- market order handling
- Python/C++ output parity
- direct C++ engine execution
- summary metric generation
