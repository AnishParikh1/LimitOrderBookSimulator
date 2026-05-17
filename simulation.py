from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter
import random

from orderbook import Order, OrderBook, Trade


@dataclass
class GeneratedOrder:
    order: Order
    reference_price: float
    is_seed: bool = False


@dataclass
class SimulationResult:
    trades: list[Trade]
    snapshots: list[dict]
    orders_submitted: int
    orders_resting: int
    config: dict
    engine_name: str
    duration_seconds: float


@dataclass
class EngineComparison:
    python_result: SimulationResult
    cpp_result: SimulationResult
    trade_match: bool
    snapshot_match: bool
    speedup_vs_python: float | None
    benchmark_python_seconds: float
    benchmark_cpp_seconds: float
    benchmark_speedup_vs_python: float | None
    benchmark_repeats: int


class Simulation:
    def __init__(
        self,
        steps: int = 1000,
        start_price: float = 100.0,
        seed: int = 7,
        limit_order_probability: float = 0.8,
        buy_probability: float = 0.5,
        max_quantity: int = 10,
        price_band: int = 5,
        orders_per_step: int = 1,
        initial_depth_levels: int = 3,
        initial_orders_per_level: int = 2,
    ):
        self.steps = steps
        self.start_price = float(start_price)
        self.current_reference_price = float(start_price)
        self.limit_order_probability = limit_order_probability
        self.buy_probability = buy_probability
        self.max_quantity = max_quantity
        self.price_band = price_band
        self.orders_per_step = orders_per_step
        self.initial_depth_levels = initial_depth_levels
        self.initial_orders_per_level = initial_orders_per_level
        self.random = random.Random(seed)
        self.order_id_counter = 1
        self.timestamp = 0

    def _next_order_id(self) -> int:
        order_id = self.order_id_counter
        self.order_id_counter += 1
        return order_id

    def _next_timestamp(self) -> int:
        self.timestamp += 1
        return self.timestamp

    def _seed_orders(self) -> list[GeneratedOrder]:
        generated_orders: list[GeneratedOrder] = []
        for level in range(1, self.initial_depth_levels + 1):
            bid_price = round(self.start_price - level, 2)
            ask_price = round(self.start_price + level, 2)
            for _ in range(self.initial_orders_per_level):
                generated_orders.append(
                    GeneratedOrder(
                        order=Order(
                            order_id=self._next_order_id(),
                            side="buy",
                            price=bid_price,
                            quantity=self.random.randint(1, self.max_quantity),
                            order_type="limit",
                            timestamp=self._next_timestamp(),
                        ),
                        reference_price=self.start_price,
                        is_seed=True,
                    )
                )
                generated_orders.append(
                    GeneratedOrder(
                        order=Order(
                            order_id=self._next_order_id(),
                            side="sell",
                            price=ask_price,
                            quantity=self.random.randint(1, self.max_quantity),
                            order_type="limit",
                            timestamp=self._next_timestamp(),
                        ),
                        reference_price=self.start_price,
                        is_seed=True,
                    )
                )
        return generated_orders

    def _evolve_reference_price(self):
        move = self.random.choice([-1, 0, 1])
        self.current_reference_price = max(1.0, self.current_reference_price + move)

    def _random_order(self) -> Order:
        side = "buy" if self.random.random() < self.buy_probability else "sell"
        quantity = self.random.randint(1, self.max_quantity)
        is_limit = self.random.random() < self.limit_order_probability

        if is_limit:
            offset = self.random.randint(0, self.price_band)
            price = round(self.current_reference_price - offset, 2) if side == "buy" else round(self.current_reference_price + offset, 2)
            order_type = "limit"
        else:
            price = None
            order_type = "market"

        return Order(
            order_id=self._next_order_id(),
            side=side,
            price=price,
            quantity=quantity,
            order_type=order_type,
            timestamp=self._next_timestamp(),
        )

    def generate_order_flow(self) -> list[GeneratedOrder]:
        generated_orders = self._seed_orders()
        for _ in range(self.steps):
            self._evolve_reference_price()
            for _ in range(self.orders_per_step):
                generated_orders.append(
                    GeneratedOrder(
                        order=self._random_order(),
                        reference_price=self.current_reference_price,
                        is_seed=False,
                    )
                )
        return generated_orders

    def _capture_snapshot(self, order_book: OrderBook, trades: list[Trade], timestamp: int, reference_price: float) -> dict:
        snapshot = order_book.book_snapshot()
        snapshot["timestamp"] = timestamp
        snapshot["trade_count"] = len(trades)
        snapshot["reference_price"] = reference_price
        snapshot["last_trade_price"] = order_book.last_trade_price
        return snapshot

    def _run_python_engine(self, order_flow: list[GeneratedOrder]) -> SimulationResult:
        start = perf_counter()
        order_book = OrderBook()
        trades: list[Trade] = []
        snapshots: list[dict] = []
        seed_orders = [generated for generated in order_flow if generated.is_seed]
        active_orders = [generated for generated in order_flow if not generated.is_seed]

        for generated in seed_orders:
            order_book.add_resting_order(
                Order(
                    order_id=generated.order.order_id,
                    side=generated.order.side,
                    price=generated.order.price,
                    quantity=generated.order.quantity,
                    order_type=generated.order.order_type,
                    timestamp=generated.order.timestamp,
                )
            )

        initial_timestamp = seed_orders[-1].order.timestamp if seed_orders else 0
        initial_reference = seed_orders[-1].reference_price if seed_orders else self.start_price
        snapshots.append(self._capture_snapshot(order_book, trades, initial_timestamp, initial_reference))

        for generated in active_orders:
            trades.extend(
                order_book.process_order(
                    Order(
                        order_id=generated.order.order_id,
                        side=generated.order.side,
                        price=generated.order.price,
                        quantity=generated.order.quantity,
                        order_type=generated.order.order_type,
                        timestamp=generated.order.timestamp,
                    )
                )
            )
            snapshots.append(self._capture_snapshot(order_book, trades, generated.order.timestamp, generated.reference_price))

        return SimulationResult(
            trades=trades,
            snapshots=snapshots,
            orders_submitted=len(order_flow),
            orders_resting=len(order_book.orders),
            config=self._config(),
            engine_name="python",
            duration_seconds=perf_counter() - start,
        )

    def _run_cpp_engine(self, order_flow: list[GeneratedOrder], build_if_needed: bool) -> SimulationResult:
        from cpp_engine import run_cpp_order_flow

        start = perf_counter()
        trades, snapshots, orders_resting = run_cpp_order_flow(order_flow, build_if_needed=build_if_needed)
        return SimulationResult(
            trades=trades,
            snapshots=snapshots,
            orders_submitted=len(order_flow),
            orders_resting=orders_resting,
            config=self._config(),
            engine_name="cpp",
            duration_seconds=perf_counter() - start,
        )

    def _run_python_engine_stats(self, order_flow: list[GeneratedOrder]) -> tuple[int, int]:
        order_book = OrderBook()
        trade_count = 0

        for generated in order_flow:
            order = Order(
                order_id=generated.order.order_id,
                side=generated.order.side,
                price=generated.order.price,
                quantity=generated.order.quantity,
                order_type=generated.order.order_type,
                timestamp=generated.order.timestamp,
            )
            if generated.is_seed:
                order_book.add_resting_order(order)
            else:
                trade_count += order_book.process_order_count(order)

        return trade_count, len(order_book.orders)

    def benchmark_engines(self, order_flow: list[GeneratedOrder], repeats: int = 3, build_if_needed: bool = True) -> tuple[float, float]:
        from cpp_engine import benchmark_cpp_order_flow

        python_total = 0.0

        for _ in range(repeats):
            start = perf_counter()
            self._run_python_engine_stats(order_flow)
            python_total += perf_counter() - start

        cpp_average_seconds, _, _ = benchmark_cpp_order_flow(order_flow, repeats=repeats, build_if_needed=build_if_needed)
        return python_total / repeats, cpp_average_seconds

    def _config(self) -> dict:
        return {
            "steps": self.steps,
            "start_price": self.start_price,
            "limit_order_probability": self.limit_order_probability,
            "buy_probability": self.buy_probability,
            "max_quantity": self.max_quantity,
            "price_band": self.price_band,
            "orders_per_step": self.orders_per_step,
            "initial_depth_levels": self.initial_depth_levels,
            "initial_orders_per_level": self.initial_orders_per_level,
        }

    def run(self, engine: str = "python", build_if_needed: bool = True) -> SimulationResult:
        order_flow = self.generate_order_flow()
        if engine == "python":
            return self._run_python_engine(order_flow)
        if engine == "cpp":
            return self._run_cpp_engine(order_flow, build_if_needed=build_if_needed)
        raise ValueError("engine must be 'python' or 'cpp'")

    def compare_engines(self, build_if_needed: bool = True, benchmark_repeats: int = 3) -> EngineComparison:
        order_flow = self.generate_order_flow()
        python_result = self._run_python_engine(order_flow)
        cpp_result = self._run_cpp_engine(order_flow, build_if_needed=build_if_needed)
        benchmark_python_seconds, benchmark_cpp_seconds = self.benchmark_engines(
            order_flow,
            repeats=benchmark_repeats,
            build_if_needed=build_if_needed,
        )
        return EngineComparison(
            python_result=python_result,
            cpp_result=cpp_result,
            trade_match=_trade_signature(python_result.trades) == _trade_signature(cpp_result.trades),
            snapshot_match=_snapshot_signature(python_result.snapshots) == _snapshot_signature(cpp_result.snapshots),
            speedup_vs_python=(python_result.duration_seconds / cpp_result.duration_seconds) if cpp_result.duration_seconds > 0 else None,
            benchmark_python_seconds=benchmark_python_seconds,
            benchmark_cpp_seconds=benchmark_cpp_seconds,
            benchmark_speedup_vs_python=(benchmark_python_seconds / benchmark_cpp_seconds) if benchmark_cpp_seconds > 0 else None,
            benchmark_repeats=benchmark_repeats,
        )


def _trade_signature(trades: list[Trade]) -> list[tuple]:
    return [
        (trade.buy_order_id, trade.sell_order_id, trade.price, trade.quantity, trade.timestamp, trade.aggressor_side)
        for trade in trades
    ]


def _snapshot_signature(snapshots: list[dict]) -> list[tuple]:
    return [
        (
            snapshot["timestamp"],
            snapshot["trade_count"],
            snapshot["reference_price"],
            snapshot["last_trade_price"],
            snapshot["best_bid"],
            snapshot["best_ask"],
            snapshot["mid_price"],
            snapshot["spread"],
            snapshot["resting_orders"],
        )
        for snapshot in snapshots
    ]
