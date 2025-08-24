import heapq
import itertools

class Order:
    def __init__(self, order_id, side, price, quantity):
        """
        side: 'buy' or 'sell'
        """
        self.order_id = order_id
        self.side = side
        self.price = price
        self.quantity = quantity

    def __repr__(self):
        return f"Order(id={self.order_id}, side={self.side}, price={self.price}, qty={self.quantity})"


class OrderBook:
    def __init__(self):
        # Bids = max-heap (store negative prices for Python's min-heap)
        self.bids = []
        # Asks = min-heap
        self.asks = []
        # Active orders
        self.orders = {}
        # Unique counter to avoid tie-breaking issues in heapq
        self.counter = itertools.count()

    def add_order(self, order: Order):
        """Add new order to book"""
        if order.side == "buy":
            entry = (-order.price, next(self.counter), order)
            heapq.heappush(self.bids, entry)
        else:
            entry = (order.price, next(self.counter), order)
            heapq.heappush(self.asks, entry)
        self.orders[order.order_id] = order

    def best_bid(self):
        while self.bids and self.bids[0][2].quantity == 0:
            heapq.heappop(self.bids)
        return self.bids[0][2] if self.bids else None

    def best_ask(self):
        while self.asks and self.asks[0][2].quantity == 0:
            heapq.heappop(self.asks)
        return self.asks[0][2] if self.asks else None

    def match_orders(self):
        """Match best bid and ask until no trades possible"""
        trades = []
        while True:
            best_bid = self.best_bid()
            best_ask = self.best_ask()

            if not best_bid or not best_ask:
                break
            if best_bid.price < best_ask.price:
                break  # No crossing

            # Trade happens at resting order’s price (ask for buy, bid for sell)
            trade_price = best_ask.price
            trade_qty = min(best_bid.quantity, best_ask.quantity)

            trades.append((best_bid.order_id, best_ask.order_id, trade_price, trade_qty))

            # Update quantities
            best_bid.quantity -= trade_qty
            best_ask.quantity -= trade_qty

            # Remove filled orders
            if best_bid.quantity == 0:
                heapq.heappop(self.bids)
                del self.orders[best_bid.order_id]
            if best_ask.quantity == 0:
                heapq.heappop(self.asks)
                del self.orders[best_ask.order_id]

        return trades
