from ibapi.client import EClient
from ibapi.wrapper import EWrapper
from ibapi.contract import Contract
import threading
import time
import csv
import os
import signal
import sys
from datetime import datetime, timezone
from PyQt5 import QtWidgets, QtCore, QtGui
import pyqtgraph as pg
from pyqtgraph import DateAxisItem
import numpy as np

# Configuration
DEFAULT_HOST = '127.0.0.1'
DEFAULT_PORT = 7496
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
        ts_recv = datetime.now(timezone.utc).timestamp()
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

class LatencyPlotter(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        pg.setConfigOption('background', '#121212')
        pg.setConfigOption('foreground', '#e0e0e0')
        pg.setConfigOption('antialias', True)
        self.x = []
        self.y = []
        self.ma_x = []
        self.ma_y = []
        self.min_latency = self.max_latency = self.avg_latency = 0
        self.f = open(os.path.join(OUTPUT_DIR, "SPY.csv"), 'r')
        self.f.readline()
        self.initUI()
        self.timer = QtCore.QTimer(self)
        self.timer.timeout.connect(self.update)
        self.timer.start(1000)

    def initUI(self):
        self.setWindowTitle("Interactive Brokers Live Data Streaming Latency")
        axis = DateAxisItem(orientation='bottom')
        self.plot = pg.PlotWidget(axisItems={'bottom': axis})
        self.plot.showGrid(x=True, y=True, alpha=0.2)
        self.plot.setLabel('left', 'Latency', units='ms')
        self.plot.setLabel('bottom', 'Time')
        self.plot.setYRange(-10, 100)
        self.threshold_line = pg.InfiniteLine(pos=50, angle=0, pen=pg.mkPen(width=1, style=QtCore.Qt.DashLine))
        self.plot.addItem(self.threshold_line)
        self.curve = pg.PlotDataItem(pen=pg.mkPen(width=2), fillLevel=0, fillBrush=pg.mkBrush(50))
        self.plot.addItem(self.curve)
        self.scatter = pg.ScatterPlotItem(size=8)
        self.plot.addItem(self.scatter)
        self.stats_label = QtWidgets.QLabel()
        self.stats_label.setAlignment(QtCore.Qt.AlignCenter)
        self.updateStatsLabel(0,0,0)
        self.status_bar = QtWidgets.QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Monitoring latency...")
        layout = QtWidgets.QVBoxLayout()
        layout.addWidget(self.plot)
        layout.addWidget(self.stats_label)
        widget = QtWidgets.QWidget()
        widget.setLayout(layout)
        self.setCentralWidget(widget)
        self.proxy = pg.SignalProxy(self.plot.scene().sigMouseMoved, rateLimit=60, slot=self.mouseMoved)
        self.resize(1000, 600)

    def updateStatsLabel(self, mn, mx, av):
        self.stats_label.setText(f"Min: {mn:.2f} ms | Max: {mx:.2f} ms | Avg: {av:.2f} ms")

    def mouseMoved(self, evt):
        pos = evt[0]
        if self.plot.sceneBoundingRect().contains(pos):
            mp = self.plot.getPlotItem().vb.mapSceneToView(pos)
            x = mp.x()
            if self.ma_x:
                idx = np.abs(np.array(self.ma_x) - x).argmin()
                if idx < len(self.ma_x):
                    xv, yv = self.ma_x[idx], self.ma_y[idx]
                    self.scatter.setData([xv], [yv])
                    tstr = datetime.fromtimestamp(xv).strftime('%Y-%m-%d %H:%M:%S')
                    self.status_bar.showMessage(f"Time: {tstr} | Latency: {yv:.2f} ms")
                    return
        self.scatter.setData([], [])
        self.status_bar.showMessage("Monitoring latency...")

    def update(self):
        old = len(self.x)
        while True:
            pos = self.f.tell()
            line = self.f.readline()
            if not line:
                self.f.seek(pos)
                break
            *_, ts_recv = line.strip().split(',')
            tbar = float(line.split(',')[0])
            trec = float(ts_recv)
            self.x.append(trec)
            self.y.append((trec - (tbar + 5.0)) * 1000.0)
        for i in range(old, len(self.x)):
            t = self.x[i]
            wstart = t - 30
            vals = [self.y[j] for j in range(len(self.x)) if self.x[j] >= wstart]
            if vals:
                self.ma_x.append(t)
                self.ma_y.append(sum(vals) / len(vals))
        if self.ma_x:
            self.curve.setData(self.ma_x, self.ma_y)
            if self.ma_y:
                self.min_latency = min(self.ma_y)
                self.max_latency = max(self.ma_y)
                self.avg_latency = sum(self.ma_y) / len(self.ma_y)
                self.updateStatsLabel(self.min_latency, self.max_latency, self.avg_latency)
                max_vis = max(self.ma_y[-100:]) if len(self.ma_y)>100 else self.max_latency
                if max_vis > self.plot.getViewBox().viewRange()[1][1] * 0.8:
                    self.plot.setYRange(-10, max_vis * 1.2)
            if len(self.ma_x) > 10000:
                self.x = self.x[-10000:]
                self.y = self.y[-10000:]
                self.ma_x = self.ma_x[-10000:]
                self.ma_y = self.ma_y[-10000:]

def main():
    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)
    if not connect_to_ib():
        sys.exit(1)
    if not setup_output_directory():
        sys.exit(1)
    setup_streaming()
    app_qt = QtWidgets.QApplication(sys.argv)
    window = LatencyPlotter()
    window.show()
    sys.exit(app_qt.exec_())

if __name__ == "__main__":
    main()
