from simulation import Simulation
from analytics import plot_trades

if __name__ == "__main__":
    sim = Simulation(steps=200, start_price=100)
    trades = sim.run()

    print(f"Total trades executed: {len(trades)}")
    for t in trades[:10]:  # print first 10 trades
        print(f"Trade: BuyID={t[0]}, SellID={t[1]}, Price={t[2]}, Qty={t[3]}")

    plot_trades(trades)
