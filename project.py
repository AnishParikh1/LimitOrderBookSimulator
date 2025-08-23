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
    
    def add_order(self, order):
        self.orders.appemd([order.order_id, order])
        if order.side == "B":
            self.bids.append(order.order_id)
        else:
            self.asks.append(order.order_id)

    def cancel_order(self, order_id):
        order_to_cancel = None
        for order in self.orders:
            if order[0].order_id == order_id:
                order_to_cancel = order[1]
                break
        if order_to_cancel.side == "B":
            self.bids.remove(order_id)
        else:
            self.asks.remove(order_id)
        self.orders.remove[order_id, order_to_cancel]

        def match_orders(self):
            if self.bids[0]