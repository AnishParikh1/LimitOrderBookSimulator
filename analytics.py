from __future__ import annotations

import math
import statistics

import matplotlib.pyplot as plt


def summarize_result(result) -> dict:
    trades = result.trades
    snapshots = result.snapshots

    executed_volume = sum(trade.quantity for trade in trades)
    traded_notional = sum(trade.price * trade.quantity for trade in trades)
    vwap = traded_notional / executed_volume if executed_volume else None

    spreads = [snapshot["spread"] for snapshot in snapshots if snapshot["spread"] is not None]
    mids = [snapshot["mid_price"] for snapshot in snapshots if snapshot["mid_price"] is not None]
    resting_orders = [snapshot["resting_orders"] for snapshot in snapshots]

    trade_prices = [trade.price for trade in trades]
    price_volatility = statistics.pstdev(trade_prices) if len(trade_prices) > 1 else 0.0
    mid_return_volatility = _return_volatility(mids)

    return {
        "engine": result.engine_name,
        "orders_submitted": result.orders_submitted,
        "resting_orders_final": result.orders_resting,
        "trade_count": len(trades),
        "executed_volume": executed_volume,
        "duration_ms": round(result.duration_seconds * 1000, 3),
        "orders_per_second": round(result.orders_submitted / result.duration_seconds, 2) if result.duration_seconds > 0 else None,
        "trades_per_second": round(len(trades) / result.duration_seconds, 2) if result.duration_seconds > 0 else None,
        "vwap": round(vwap, 4) if vwap is not None else None,
        "avg_spread": round(statistics.mean(spreads), 4) if spreads else None,
        "median_spread": round(statistics.median(spreads), 4) if spreads else None,
        "mid_price_start": mids[0] if mids else None,
        "mid_price_end": mids[-1] if mids else None,
        "mid_price_change": round(mids[-1] - mids[0], 4) if len(mids) >= 2 else None,
        "trade_price_volatility": round(price_volatility, 4),
        "mid_return_volatility": round(mid_return_volatility, 6),
        "max_resting_orders": max(resting_orders) if resting_orders else 0,
        "min_resting_orders": min(resting_orders) if resting_orders else 0,
    }


def _return_volatility(prices: list[float]) -> float:
    if len(prices) < 2:
        return 0.0
    returns = []
    for previous, current in zip(prices, prices[1:]):
        if previous > 0:
            returns.append(math.log(current / previous))
    return statistics.pstdev(returns) if len(returns) > 1 else 0.0


def print_summary(summary: dict):
    print("Simulation summary")
    for key, value in summary.items():
        print(f"  {key}: {value}")


def print_engine_comparison(comparison):
    print("Engine comparison")
    print(f"  trades_match: {comparison.trade_match}")
    print(f"  snapshots_match: {comparison.snapshot_match}")
    print(f"  python_trade_count: {len(comparison.python_result.trades)}")
    print(f"  cpp_trade_count: {len(comparison.cpp_result.trades)}")
    print(f"  python_snapshot_count: {len(comparison.python_result.snapshots)}")
    print(f"  cpp_snapshot_count: {len(comparison.cpp_result.snapshots)}")
    print(f"  python_duration_ms: {round(comparison.python_result.duration_seconds * 1000, 3)}")
    print(f"  cpp_duration_ms: {round(comparison.cpp_result.duration_seconds * 1000, 3)}")
    print(f"  cpp_speedup_vs_python: {round(comparison.speedup_vs_python, 3) if comparison.speedup_vs_python is not None else None}x")
    print(f"  benchmark_repeats: {comparison.benchmark_repeats}")
    print(f"  benchmark_python_ms: {round(comparison.benchmark_python_seconds * 1000, 3)}")
    print(f"  benchmark_cpp_ms: {round(comparison.benchmark_cpp_seconds * 1000, 3)}")
    print(
        f"  benchmark_cpp_speedup_vs_python: "
        f"{round(comparison.benchmark_speedup_vs_python, 3) if comparison.benchmark_speedup_vs_python is not None else None}x"
    )


def plot_simulation(result, output_path: str | None = None, show: bool = True):
    trades = result.trades
    snapshots = result.snapshots

    trade_times = [trade.timestamp for trade in trades]
    trade_prices = [trade.price for trade in trades]
    trade_sizes = [trade.quantity * 12 for trade in trades]
    snapshot_times = [snapshot["timestamp"] for snapshot in snapshots]
    mids = [snapshot["mid_price"] for snapshot in snapshots]
    spreads = [snapshot["spread"] for snapshot in snapshots]
    resting_orders = [snapshot["resting_orders"] for snapshot in snapshots]

    fig, axes = plt.subplots(3, 1, figsize=(12, 10), sharex=True)

    axes[0].plot(snapshot_times, mids, color="navy", linewidth=1.5, label="Mid price")
    if trades:
        axes[0].scatter(trade_times, trade_prices, s=trade_sizes, alpha=0.45, color="darkorange", label="Trades")
    axes[0].set_ylabel("Price")
    axes[0].set_title("Price Path And Executions")
    axes[0].legend(loc="best")

    axes[1].plot(snapshot_times, spreads, color="crimson", linewidth=1.2)
    axes[1].set_ylabel("Spread")
    axes[1].set_title("Quoted Spread")

    axes[2].plot(snapshot_times, resting_orders, color="forestgreen", linewidth=1.2)
    axes[2].set_ylabel("Orders")
    axes[2].set_xlabel("Simulation time")
    axes[2].set_title("Resting Order Count")

    fig.tight_layout()

    if output_path:
        fig.savefig(output_path, dpi=150, bbox_inches="tight")
    if show:
        plt.show()
    else:
        plt.close(fig)
