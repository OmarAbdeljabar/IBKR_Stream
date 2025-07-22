from ibapi.client import EClient
from ibapi.wrapper import EWrapper
from ibapi.contract import Contract
import threading
import csv
import os
import signal
import sys
from datetime import datetime, timezone
from time import time_ns

# Configuration
DEFAULT_HOST = '127.0.0.1'
DEFAULT_PORT = 4001
DEFAULT_CLIENT_ID = 1
DEFAULT_OUTPUT_DIR = r'./candles'

HOST = os.getenv('IB_HOST', DEFAULT_HOST)
PORT = int(os.getenv('IB_PORT', DEFAULT_PORT))
CLIENT_ID = int(os.getenv('IB_CLIENT_ID', DEFAULT_CLIENT_ID))
OUTPUT_DIR = os.getenv('OUTPUT_DIR', DEFAULT_OUTPUT_DIR)

TICKERS = ['SPY', 'QQQ', 'IWM', 'TSLA', 'AAPL']
app = None
api_thread = None

class IBKRWrapper(EWrapper):
    def __init__(self):
        super().__init__()
        self.next_valid_id_event = threading.Event()
        self.data_writers = {}

    def nextValidId(self, orderId):
        super().nextValidId(orderId)
        self.next_valid_id = orderId
        print(f"Received next valid order ID: {orderId}")
        self.next_valid_id_event.set()

    def realtimeBar(self, reqId, time, open, high, low, close, volume, wap, count):
        super().realtimeBar(reqId, time, open, high, low, close, volume, wap, count)
        bar_ts = time
        ts_recv = time_ns()
        if reqId in self.data_writers:
            w = self.data_writers[reqId]
            try:
                w['writer'].writerow([bar_ts, open, high, low, close, volume, ts_recv])
                w['file'].flush()
            except Exception as e:
                print(f"Error writing data: {e}")

    def error(self, reqId, errorCode, errorString):
        super().error(reqId, errorCode, errorString)
        if reqId != -1:
            print(f"Error {errorCode} for ReqID {reqId}: {errorString}")
        else:
            print(f"Error {errorCode}: {errorString}")

class IBKRClient(EClient):
    def __init__(self, wrapper):
        super().__init__(wrapper)
        self.wrapper = wrapper

def run_api():
    global app
    app.run()

def connect_to_ib():
    global app, api_thread
    app = IBKRClient(IBKRWrapper())
    app.connect(HOST, PORT, CLIENT_ID)
    if not app.isConnected():
        print(f"Failed to connect to IB at {HOST}:{PORT}")
        return False
    print(f"Connected to IB at {HOST}:{PORT}")
    api_thread = threading.Thread(target=run_api, daemon=True)
    api_thread.start()
    app.wrapper.next_valid_id_event.wait(timeout=10)
    if not app.wrapper.next_valid_id_event.is_set():
        print("Timeout waiting for next valid ID")
        return False
    return True

def setup_output_directory():
    try:
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        print(f"Output directory: {os.path.abspath(OUTPUT_DIR)}")
        return True
    except Exception as e:
        print(f"Failed to create output directory: {e}")
        return False

def setup_streaming():
    global app
    req_id = app.wrapper.next_valid_id
    for sym in TICKERS:
        try:
            c = Contract()
            c.symbol = sym
            c.secType = "STK"
            c.exchange = "SMART"
            c.currency = "USD"
            path = os.path.join(OUTPUT_DIR, f"{sym}.csv")
            f = open(path, 'a', newline='')
            writer = csv.writer(f)
            if f.tell() == 0:
                writer.writerow(['timestamp','open','high','low','close','volume','ts_recv'])
            app.wrapper.data_writers[req_id] = {'writer': writer, 'file': f}
            app.reqRealTimeBars(req_id, c, 5, "TRADES", False, [])
            print(f"Streaming {sym} on ReqID {req_id}")
            req_id += 1
        except Exception as e:
            print(f"Failed streaming {sym}: {e}")

def shutdown(sig, frame):
    global app, api_thread
    if app and hasattr(app.wrapper, 'data_writers'):
        for rid, ctx in app.wrapper.data_writers.items():
            try:
                app.cancelRealTimeBars(rid)
                ctx['file'].close()
            except:
                pass
    if app and app.isConnected():
        app.disconnect()
    if api_thread and api_thread.is_alive():
        api_thread.join(timeout=5)
    sys.exit(0)

if __name__ == "__main__":
    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)
    if not connect_to_ib():
        sys.exit(1)
    if not setup_output_directory():
        sys.exit(1)
    setup_streaming()
