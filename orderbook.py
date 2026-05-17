from __future__ import annotations

from dataclasses import dataclass
import heapq
import itertools


@dataclass
class Order:
    order_id: int
    side: str
    quantity: int
    price: float | None = None
    order_type: str = "limit"
    timestamp: int = 0

    def __post_init__(self):
        if self.side not in {"buy", "sell"}:
            raise ValueError("side must be 'buy' or 'sell'")
        if self.order_type not in {"limit", "market"}:
            raise ValueError("order_type must be 'limit' or 'market'")
        if self.quantity <= 0:
            raise ValueError("quantity must be positive")
        if self.order_type == "limit" and self.price is None:
            raise ValueError("limit orders require a price")
        if self.order_type == "market":
            self.price = None

    @property
    def remaining(self) -> int:
        return self.quantity

    def is_filled(self) -> bool:
        return self.quantity == 0


@dataclass
class Trade:
    buy_order_id: int
    sell_order_id: int
    price: float
    quantity: int
    timestamp: int
    aggressor_side: str


class OrderBook:
    def __init__(self):
        self.bids: list[tuple[float, int, Order]] = []
        self.asks: list[tuple[float, int, Order]] = []
        self.orders: dict[int, Order] = {}
        self.counter = itertools.count()
        self.last_trade_price: float | None = None

    def _book_for_side(self, side: str) -> list[tuple[float, int, Order]]:
        return self.bids if side == "buy" else self.asks

    def _clean_top(self, heap: list[tuple[float, int, Order]]):
        while heap and heap[0][2].is_filled():
            heapq.heappop(heap)

    def best_bid(self) -> Order | None:
        self._clean_top(self.bids)
        return self.bids[0][2] if self.bids else None

    def best_ask(self) -> Order | None:
        self._clean_top(self.asks)
        return self.asks[0][2] if self.asks else None

    def add_resting_order(self, order: Order):
        if order.order_type != "limit":
            raise ValueError("only limit orders can rest on the book")
        priority = (-order.price, next(self.counter), order) if order.side == "buy" else (order.price, next(self.counter), order)
        heapq.heappush(self._book_for_side(order.side), priority)
        self.orders[order.order_id] = order

    def _can_match(self, incoming: Order, resting: Order) -> bool:
        if incoming.order_type == "market":
            return True
        if incoming.side == "buy":
            return incoming.price >= resting.price
        return incoming.price <= resting.price

    def _record_trade(self, incoming: Order, resting: Order, trade_qty: int, timestamp: int) -> Trade:
        trade_price = resting.price
        buy_order = incoming if incoming.side == "buy" else resting
        sell_order = incoming if incoming.side == "sell" else resting
        self.last_trade_price = trade_price
        return Trade(
            buy_order_id=buy_order.order_id,
            sell_order_id=sell_order.order_id,
            price=trade_price,
            quantity=trade_qty,
            timestamp=timestamp,
            aggressor_side=incoming.side,
        )

    def process_order(self, order: Order) -> list[Trade]:
        trades: list[Trade] = []
        opposite_heap = self.asks if order.side == "buy" else self.bids

        while order.remaining > 0:
            self._clean_top(opposite_heap)
            if not opposite_heap:
                break

            resting = opposite_heap[0][2]
            if not self._can_match(order, resting):
                break

            trade_qty = min(order.remaining, resting.remaining)
            order.quantity -= trade_qty
            resting.quantity -= trade_qty
            trades.append(self._record_trade(order, resting, trade_qty, order.timestamp))

            if resting.is_filled():
                heapq.heappop(opposite_heap)
                self.orders.pop(resting.order_id, None)

        if order.order_type == "limit" and order.remaining > 0:
            self.add_resting_order(order)

        return trades

    def process_order_count(self, order: Order) -> int:
        trade_count = 0
        opposite_heap = self.asks if order.side == "buy" else self.bids

        while order.remaining > 0:
            self._clean_top(opposite_heap)
            if not opposite_heap:
                break

            resting = opposite_heap[0][2]
            if not self._can_match(order, resting):
                break

            trade_qty = min(order.remaining, resting.remaining)
            order.quantity -= trade_qty
            resting.quantity -= trade_qty
            self.last_trade_price = resting.price
            trade_count += 1

            if resting.is_filled():
                heapq.heappop(opposite_heap)
                self.orders.pop(resting.order_id, None)

        if order.order_type == "limit" and order.remaining > 0:
            self.add_resting_order(order)

        return trade_count

    def book_snapshot(self, levels: int = 5) -> dict:
        bid_levels = self._aggregate_levels(self.bids, levels, side="buy")
        ask_levels = self._aggregate_levels(self.asks, levels, side="sell")
        best_bid = bid_levels[0][0] if bid_levels else None
        best_ask = ask_levels[0][0] if ask_levels else None
        mid_price = (best_bid + best_ask) / 2 if best_bid is not None and best_ask is not None else self.last_trade_price
        spread = best_ask - best_bid if best_bid is not None and best_ask is not None else None

        return {
            "best_bid": best_bid,
            "best_ask": best_ask,
            "mid_price": mid_price,
            "spread": spread,
            "bid_levels": bid_levels,
            "ask_levels": ask_levels,
            "resting_orders": len(self.orders),
        }

    def _aggregate_levels(self, heap: list[tuple[float, int, Order]], levels: int, side: str) -> list[tuple[float, int]]:
        self._clean_top(heap)
        aggregated: dict[float, int] = {}
        for _, _, order in sorted(heap):
            if order.is_filled():
                continue
            price = order.price
            aggregated[price] = aggregated.get(price, 0) + order.remaining

        prices = sorted(aggregated, reverse=(side == "buy"))
        return [(price, aggregated[price]) for price in prices[:levels]]
