#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstddef>
#include <queue>
#include <tuple>
#include <unordered_map>
#include <vector>

namespace {

constexpr int SIDE_BUY = 0;
constexpr int SIDE_SELL = 1;
constexpr int ORDER_LIMIT = 0;
constexpr int ORDER_MARKET = 1;

struct OrderInput {
    int order_id;
    int side;
    double price;
    int quantity;
    int order_type;
    int timestamp;
    double reference_price;
    int is_seed;
};

struct TradeOutput {
    int buy_order_id;
    int sell_order_id;
    double price;
    int quantity;
    int timestamp;
    int aggressor_side;
};

struct SnapshotOutput {
    int timestamp;
    int trade_count;
    double reference_price;
    double last_trade_price;
    double best_bid;
    double best_ask;
    double mid_price;
    double spread;
    int resting_orders;
};

struct Order {
    int order_id;
    int side;
    double price;
    int quantity;
    int order_type;
    int timestamp;

    bool is_filled() const { return quantity == 0; }
};

using HeapEntry = std::tuple<double, int, std::size_t>;

struct BidCompare {
    bool operator()(const HeapEntry& left, const HeapEntry& right) const {
        if (std::get<0>(left) != std::get<0>(right)) {
            return std::get<0>(left) < std::get<0>(right);
        }
        return std::get<1>(left) > std::get<1>(right);
    }
};

struct AskCompare {
    bool operator()(const HeapEntry& left, const HeapEntry& right) const {
        if (std::get<0>(left) != std::get<0>(right)) {
            return std::get<0>(left) > std::get<0>(right);
        }
        return std::get<1>(left) > std::get<1>(right);
    }
};

struct MatchingState {
    std::vector<Order> orders;
    std::priority_queue<HeapEntry, std::vector<HeapEntry>, BidCompare> bids;
    std::priority_queue<HeapEntry, std::vector<HeapEntry>, AskCompare> asks;
    std::unordered_map<int, std::size_t> active_orders;
    int sequence = 0;
    double last_trade_price = 0.0;
    bool has_last_trade = false;
};

void clean_top_bids(MatchingState& state) {
    while (!state.bids.empty()) {
        const auto order_index = std::get<2>(state.bids.top());
        if (!state.orders[order_index].is_filled()) {
            break;
        }
        state.bids.pop();
    }
}

void clean_top_asks(MatchingState& state) {
    while (!state.asks.empty()) {
        const auto order_index = std::get<2>(state.asks.top());
        if (!state.orders[order_index].is_filled()) {
            break;
        }
        state.asks.pop();
    }
}

Order* best_bid(MatchingState& state) {
    clean_top_bids(state);
    if (state.bids.empty()) {
        return nullptr;
    }
    return &state.orders[std::get<2>(state.bids.top())];
}

Order* best_ask(MatchingState& state) {
    clean_top_asks(state);
    if (state.asks.empty()) {
        return nullptr;
    }
    return &state.orders[std::get<2>(state.asks.top())];
}

void add_resting_order(MatchingState& state, const Order& order) {
    state.orders.push_back(order);
    const auto order_index = state.orders.size() - 1;
    state.active_orders[order.order_id] = order_index;
    if (order.side == SIDE_BUY) {
        state.bids.emplace(order.price, state.sequence++, order_index);
    } else {
        state.asks.emplace(order.price, state.sequence++, order_index);
    }
}

bool can_match(const Order& incoming, const Order& resting) {
    if (incoming.order_type == ORDER_MARKET) {
        return true;
    }
    if (incoming.side == SIDE_BUY) {
        return incoming.price >= resting.price;
    }
    return incoming.price <= resting.price;
}

TradeOutput record_trade(MatchingState& state, const Order& incoming, const Order& resting, int trade_qty) {
    state.last_trade_price = resting.price;
    state.has_last_trade = true;
    TradeOutput trade{};
    trade.buy_order_id = incoming.side == SIDE_BUY ? incoming.order_id : resting.order_id;
    trade.sell_order_id = incoming.side == SIDE_SELL ? incoming.order_id : resting.order_id;
    trade.price = resting.price;
    trade.quantity = trade_qty;
    trade.timestamp = incoming.timestamp;
    trade.aggressor_side = incoming.side;
    return trade;
}

void process_order(
    MatchingState& state,
    const OrderInput& input,
    TradeOutput* trades_out,
    int max_trades,
    int& trade_count
) {
    Order incoming{input.order_id, input.side, input.price, input.quantity, input.order_type, input.timestamp};

    while (incoming.quantity > 0) {
        Order* resting = incoming.side == SIDE_BUY ? best_ask(state) : best_bid(state);
        if (resting == nullptr) {
            break;
        }
        if (!can_match(incoming, *resting)) {
            break;
        }

        const int trade_qty = std::min(incoming.quantity, resting->quantity);
        incoming.quantity -= trade_qty;
        resting->quantity -= trade_qty;

        if (trade_count < max_trades) {
            trades_out[trade_count] = record_trade(state, incoming, *resting, trade_qty);
        }
        ++trade_count;

        if (resting->is_filled()) {
            state.active_orders.erase(resting->order_id);
        }
    }

    if (incoming.order_type == ORDER_LIMIT && incoming.quantity > 0) {
        add_resting_order(state, incoming);
    }
}

SnapshotOutput capture_snapshot(const MatchingState& state, int timestamp, int trade_count, double reference_price) {
    SnapshotOutput snapshot{};
    snapshot.timestamp = timestamp;
    snapshot.trade_count = trade_count;
    snapshot.reference_price = reference_price;
    snapshot.last_trade_price = state.has_last_trade ? state.last_trade_price : -1.0;
    snapshot.resting_orders = static_cast<int>(state.active_orders.size());

    MatchingState copy = state;
    Order* bid = best_bid(copy);
    Order* ask = best_ask(copy);
    snapshot.best_bid = bid ? bid->price : -1.0;
    snapshot.best_ask = ask ? ask->price : -1.0;
    snapshot.spread = (bid && ask) ? ask->price - bid->price : -1.0;
    if (bid && ask) {
        snapshot.mid_price = (bid->price + ask->price) / 2.0;
    } else if (state.has_last_trade) {
        snapshot.mid_price = state.last_trade_price;
    } else {
        snapshot.mid_price = -1.0;
    }
    return snapshot;
}

}  // namespace

extern "C" {

#ifdef _WIN32
__declspec(dllexport)
#endif
int simulate_order_flow(
    const OrderInput* inputs,
    int input_count,
    TradeOutput* trades_out,
    int max_trades,
    SnapshotOutput* snapshots_out,
    int max_snapshots,
    int* trades_written,
    int* snapshots_written
) {
    if (inputs == nullptr || trades_out == nullptr || snapshots_out == nullptr || trades_written == nullptr || snapshots_written == nullptr) {
        return 1;
    }

    MatchingState state;
    int trade_count = 0;
    int snapshot_count = 0;
    bool initial_snapshot_written = false;
    int last_seed_timestamp = 0;
    double initial_reference_price = 0.0;

    for (int i = 0; i < input_count; ++i) {
        const auto& input = inputs[i];
        if (input.is_seed) {
            add_resting_order(state, Order{input.order_id, input.side, input.price, input.quantity, input.order_type, input.timestamp});
            last_seed_timestamp = input.timestamp;
            initial_reference_price = input.reference_price;
            continue;
        }

        if (!initial_snapshot_written) {
            if (snapshot_count < max_snapshots) {
                snapshots_out[snapshot_count] = capture_snapshot(state, last_seed_timestamp, trade_count, initial_reference_price);
            }
            ++snapshot_count;
            initial_snapshot_written = true;
        }

        process_order(state, input, trades_out, max_trades, trade_count);
        if (snapshot_count < max_snapshots) {
            snapshots_out[snapshot_count] = capture_snapshot(state, input.timestamp, trade_count, input.reference_price);
        }
        ++snapshot_count;
    }

    if (!initial_snapshot_written) {
        if (snapshot_count < max_snapshots) {
            snapshots_out[snapshot_count] = capture_snapshot(state, last_seed_timestamp, trade_count, initial_reference_price);
        }
        ++snapshot_count;
    }

    *trades_written = trade_count;
    *snapshots_written = snapshot_count;
    return (trade_count > max_trades || snapshot_count > max_snapshots) ? 2 : 0;
}

#ifdef _WIN32
__declspec(dllexport)
#endif
int simulate_order_flow_stats(
    const OrderInput* inputs,
    int input_count,
    int* trades_written,
    int* resting_orders
) {
    if (inputs == nullptr || trades_written == nullptr || resting_orders == nullptr) {
        return 1;
    }

    auto run_once = [&]() {
        MatchingState state;
        int trade_count = 0;

        for (int i = 0; i < input_count; ++i) {
            const auto& input = inputs[i];
            if (input.is_seed) {
                add_resting_order(state, Order{input.order_id, input.side, input.price, input.quantity, input.order_type, input.timestamp});
                continue;
            }

            Order incoming{input.order_id, input.side, input.price, input.quantity, input.order_type, input.timestamp};

            while (incoming.quantity > 0) {
                Order* resting = incoming.side == SIDE_BUY ? best_ask(state) : best_bid(state);
                if (resting == nullptr) {
                    break;
                }
                if (!can_match(incoming, *resting)) {
                    break;
                }

                const int trade_qty = std::min(incoming.quantity, resting->quantity);
                incoming.quantity -= trade_qty;
                resting->quantity -= trade_qty;
                state.last_trade_price = resting->price;
                state.has_last_trade = true;
                ++trade_count;

                if (resting->is_filled()) {
                    state.active_orders.erase(resting->order_id);
                }
            }

            if (incoming.order_type == ORDER_LIMIT && incoming.quantity > 0) {
                add_resting_order(state, incoming);
            }
        }

        return std::make_pair(trade_count, static_cast<int>(state.active_orders.size()));
    };

    const auto result = run_once();
    *trades_written = result.first;
    *resting_orders = result.second;
    return 0;
}

#ifdef _WIN32
__declspec(dllexport)
#endif
int benchmark_simulate_order_flow_stats(
    const OrderInput* inputs,
    int input_count,
    int repeats,
    double* average_seconds,
    int* trades_written,
    int* resting_orders
) {
    if (inputs == nullptr || average_seconds == nullptr || trades_written == nullptr || resting_orders == nullptr || repeats <= 0) {
        return 1;
    }

    using clock = std::chrono::steady_clock;
    const auto start = clock::now();
    int last_trades_written = 0;
    int last_resting_orders = 0;

    for (int iteration = 0; iteration < repeats; ++iteration) {
        MatchingState state;
        int trade_count = 0;

        for (int i = 0; i < input_count; ++i) {
            const auto& input = inputs[i];
            if (input.is_seed) {
                add_resting_order(state, Order{input.order_id, input.side, input.price, input.quantity, input.order_type, input.timestamp});
                continue;
            }

            Order incoming{input.order_id, input.side, input.price, input.quantity, input.order_type, input.timestamp};

            while (incoming.quantity > 0) {
                Order* resting = incoming.side == SIDE_BUY ? best_ask(state) : best_bid(state);
                if (resting == nullptr) {
                    break;
                }
                if (!can_match(incoming, *resting)) {
                    break;
                }

                const int trade_qty = std::min(incoming.quantity, resting->quantity);
                incoming.quantity -= trade_qty;
                resting->quantity -= trade_qty;
                state.last_trade_price = resting->price;
                state.has_last_trade = true;
                ++trade_count;

                if (resting->is_filled()) {
                    state.active_orders.erase(resting->order_id);
                }
            }

            if (incoming.order_type == ORDER_LIMIT && incoming.quantity > 0) {
                add_resting_order(state, incoming);
            }
        }

        last_trades_written = trade_count;
        last_resting_orders = static_cast<int>(state.active_orders.size());
    }

    const auto finish = clock::now();
    *average_seconds = std::chrono::duration<double>(finish - start).count() / static_cast<double>(repeats);
    *trades_written = last_trades_written;
    *resting_orders = last_resting_orders;
    return 0;
}

}
