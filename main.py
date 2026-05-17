import argparse

from analytics import plot_simulation, print_engine_comparison, print_summary, summarize_result
from cpp_engine import build_matching_engine
from simulation import Simulation


def parse_args():
    parser = argparse.ArgumentParser(description="Run a limit order book simulation.")
    parser.add_argument("--steps", type=int, default=500)
    parser.add_argument("--start-price", type=float, default=100.0)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--orders-per-step", type=int, default=2)
    parser.add_argument("--limit-order-probability", type=float, default=0.8)
    parser.add_argument("--buy-probability", type=float, default=0.5)
    parser.add_argument("--max-quantity", type=int, default=10)
    parser.add_argument("--price-band", type=int, default=5)
    parser.add_argument("--engine", choices=["python", "cpp", "compare"], default="python")
    parser.add_argument("--benchmark-repeats", type=int, default=3)
    parser.add_argument("--build-cpp", action="store_true", help="Build the C++ engine before running.")
    parser.add_argument("--force-rebuild-cpp", action="store_true", help="Rebuild the C++ engine even if the DLL already exists.")
    parser.add_argument("--plot-path", type=str, default=None)
    parser.add_argument("--no-show", action="store_true", help="Do not open the plot window.")
    return parser.parse_args()


def _build_cpp_if_requested(args):
    if args.build_cpp or args.force_rebuild_cpp:
        build_matching_engine(force=args.force_rebuild_cpp)


def _print_sample_trades(result):
    for trade in result.trades[:10]:
        print(
            "Trade: "
            f"ts={trade.timestamp} "
            f"buy_id={trade.buy_order_id} "
            f"sell_id={trade.sell_order_id} "
            f"price={trade.price} "
            f"qty={trade.quantity} "
            f"aggressor={trade.aggressor_side}"
        )


if __name__ == "__main__":
    args = parse_args()
    _build_cpp_if_requested(args)

    sim = Simulation(
        steps=args.steps,
        start_price=args.start_price,
        seed=args.seed,
        orders_per_step=args.orders_per_step,
        limit_order_probability=args.limit_order_probability,
        buy_probability=args.buy_probability,
        max_quantity=args.max_quantity,
        price_band=args.price_band,
    )

    if args.engine == "compare":
        comparison = sim.compare_engines(build_if_needed=True, benchmark_repeats=args.benchmark_repeats)
        print_engine_comparison(comparison)
        print("\nPython engine")
        print_summary(summarize_result(comparison.python_result))
        print("\nC++ engine")
        print_summary(summarize_result(comparison.cpp_result))
        _print_sample_trades(comparison.python_result)

        if args.plot_path:
            python_plot = args.plot_path.replace(".png", "_python.png")
            cpp_plot = args.plot_path.replace(".png", "_cpp.png")
            plot_simulation(comparison.python_result, output_path=python_plot, show=False)
            plot_simulation(comparison.cpp_result, output_path=cpp_plot, show=False)
    else:
        result = sim.run(engine=args.engine, build_if_needed=True)
        print_summary(summarize_result(result))
        _print_sample_trades(result)
        plot_simulation(result, output_path=args.plot_path, show=not args.no_show)
