import random
from orderbook import Order, OrderBook

class Simulation:
    def __init__(self, steps=1000, start_price=100):
        self.steps = steps
        self.start_price = start_price
        self.order_book = OrderBook()
        self.trades = []
        self.order_id_counter = 1

    def random_order(self):
        """Generate random buy/sell/market orders"""
        side = random.choice(["buy", "sell"])
        quantity = random.randint(1, 10)

        # Price centered around start_price ± 5
        price = self.start_price + random.randint(-5, 5)

        order = Order(self.order_id_counter, side, price, quantity)
        self.order_id_counter += 1
        return order

    def run(self):
        for _ in range(self.steps):
            # Randomly add order
            order = self.random_order()
            self.order_book.add_order(order)

            # Try to match
            new_trades = self.order_book.match_orders()
            self.trades.extend(new_trades)

        return self.trades
