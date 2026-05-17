from pathlib import Path
import unittest

from analytics import summarize_result
from cpp_engine import LIBRARY_NAME, build_matching_engine
from orderbook import Order, OrderBook
from simulation import Simulation


class OrderBookTests(unittest.TestCase):
    def test_limit_order_matches_resting_liquidity_at_resting_price(self):
        book = OrderBook()
        book.add_resting_order(Order(order_id=1, side="sell", price=101.0, quantity=4, timestamp=1))
        aggressive_buy = Order(order_id=2, side="buy", price=103.0, quantity=3, timestamp=2)

        trades = book.process_order(aggressive_buy)

        self.assertEqual(len(trades), 1)
        self.assertEqual(trades[0].price, 101.0)
        self.assertEqual(trades[0].quantity, 3)
        self.assertEqual(book.best_ask().remaining, 1)

    def test_market_order_does_not_rest(self):
        book = OrderBook()
        book.add_resting_order(Order(order_id=1, side="sell", price=100.0, quantity=2, timestamp=1))
        market_buy = Order(order_id=2, side="buy", price=None, quantity=5, order_type="market", timestamp=2)

        trades = book.process_order(market_buy)

        self.assertEqual(sum(trade.quantity for trade in trades), 2)
        self.assertEqual(len(book.orders), 0)
        self.assertIsNone(book.best_bid())
        self.assertIsNone(book.best_ask())


class SimulationTests(unittest.TestCase):
    def test_simulation_is_reproducible_with_seed(self):
        first = Simulation(steps=50, seed=11, orders_per_step=2).run(engine="python")
        second = Simulation(steps=50, seed=11, orders_per_step=2).run(engine="python")

        first_signature = [(trade.timestamp, trade.price, trade.quantity) for trade in first.trades]
        second_signature = [(trade.timestamp, trade.price, trade.quantity) for trade in second.trades]

        self.assertEqual(first_signature, second_signature)
        self.assertEqual(len(first.snapshots), len(second.snapshots))

    def test_summary_contains_useful_metrics(self):
        result = Simulation(steps=40, seed=3, orders_per_step=2).run(engine="python")

        summary = summarize_result(result)

        self.assertIn("trade_count", summary)
        self.assertIn("duration_ms", summary)
        self.assertIn("orders_per_second", summary)
        self.assertIn("avg_spread", summary)
        self.assertIn("vwap", summary)
        self.assertGreater(summary["orders_submitted"], 0)

    def test_cpp_engine_matches_python_engine(self):
        build_matching_engine()
        comparison = Simulation(steps=60, seed=5, orders_per_step=2).compare_engines(build_if_needed=True)

        self.assertTrue(Path(LIBRARY_NAME).exists())
        self.assertTrue(comparison.trade_match)
        self.assertTrue(comparison.snapshot_match)
        self.assertIsNotNone(comparison.speedup_vs_python)
        self.assertIsNotNone(comparison.benchmark_speedup_vs_python)
        self.assertGreater(comparison.benchmark_repeats, 0)

    def test_cpp_engine_can_run_directly(self):
        build_matching_engine()
        result = Simulation(steps=30, seed=13, orders_per_step=1).run(engine="cpp", build_if_needed=True)

        self.assertEqual(result.engine_name, "cpp")
        self.assertGreaterEqual(len(result.snapshots), 1)


if __name__ == "__main__":
    unittest.main()
