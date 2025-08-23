class Order:
    def __init__(self, order_id, side, price, quantity):
        self.id = order_id
        self.side = side
        self.price = price
        self.quantity = quantity

class OrderBook:
    def __init__(self):
        self.bids = []
        self.asks = []
        self.orders = []
        self.ids = []
    
    def add_order(self, order):
        self.orders.appemd(order)
        self.ids.append(order.order_id)
        if order.side == "B":
            self.bids.append(order)
        else:
            self.asks.append(order)

    def cancel_order(self, order_id):
        order_to_cancel = self.orders[self.ids.endex(order_id)]
        if order_to_cancel.side == "B":
            self.bids.remove(order_id)
        else:
            self.asks.remove(order_id)
        self.orders.remove(order_to_cancel)
        self.ids.remove(order_id)

    def best_bid(self):
        if self.bids[0]