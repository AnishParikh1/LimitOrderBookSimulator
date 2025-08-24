import matplotlib.pyplot as plt

def plot_trades(trades):
    """Plot trade prices over time"""
    if not trades:
        print("No trades to plot.")
        return

    prices = [t[2] for t in trades]
    qtys = [t[3] for t in trades]
    times = list(range(len(trades)))

    plt.figure(figsize=(10,5))
    plt.scatter(times, prices, s=[q*10 for q in qtys], alpha=0.6)
    plt.xlabel("Trade Number")
    plt.ylabel("Trade Price")
    plt.title("Trade Prices Over Time (bubble size = quantity)")
    plt.show()
