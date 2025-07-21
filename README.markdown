# IBKR Live Streaming 5 Second Candles with Latency Monitor

A Python application for streaming real-time market data from Interactive Brokers (IBKR) and monitoring latency with an interactive graphical interface.

## Overview

This project consists of two Python scripts:

- **livedata.py**: Connects to the Interactive Brokers API to stream 5-second realtime bars for selected tickers and saves the data to CSV files.
- **latencyapp.py**: Displays an interactive latency plot with a 30-second moving average, min/max/avg statistics, and hover details using PyQt5 and pyqtgraph.

## Prerequisites

- **Python 3.7+**
- **Interactive Brokers TWS** or **IB Gateway** with API access enabled
- **Required pip packages**:
  - `ibapi`
  - `PyQt5`
  - `pyqtgraph`
  - `numpy`

## Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/OmarAbdeljabar/IBKR_Stream.git
   cd ibkr-latency-monitor
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Configuration

Set the following environment variables (defaults shown):

- `IB_HOST` (default: `127.0.0.1`)
- `IB_PORT` (default: `7496` for TWS, `7497` for IB Gateway)
- `IB_CLIENT_ID` (default: `1`)
- `OUTPUT_DIR` (default: `./candles`)

To monitor different symbols, edit the `TICKERS` list in `livedata.py`.

## Usage

1. **Start data streaming**:
   ```bash
   python livedata.py
   ```
   - Streams 5-second realtime bars and appends data to CSV files (`<SYMBOL>.csv`) in the `candles/` directory.

2. **Launch latency monitor**:
   ```bash
   python latencyapp.py
   ```
   - Opens a PyQt5 window displaying live latency (in milliseconds) versus time.
   - Includes a 30-second moving average, min/max/avg statistics, and hover details for data points.
   - Press `Ctrl+C` or close the window to shut down gracefully and disconnect from the IBKR API.

## File Structure

```
.
├── livedata.py          # Streams realtime bars to CSV
├── latencyapp.py        # GUI for live latency plotting
├── requirements.txt     # pip dependencies
└── candles/             # CSV output directory
    └── *.csv            # Raw realtime bar data
```

## License

Released under the [MIT License](LICENSE). Feel free to use and modify as needed.
