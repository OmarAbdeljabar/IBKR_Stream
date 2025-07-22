import sys
import os
from datetime import datetime
from PyQt5 import QtWidgets, QtCore, QtGui
import pyqtgraph as pg
from pyqtgraph import DateAxisItem
import numpy as np

pg.setConfigOption('background', '#000000')
pg.setConfigOption('foreground', '#FFFFFF')
pg.setConfigOption('antialias', True)

CSV_PATH = os.getenv('CSV_PATH', './candles/SPY.csv')
MA_WINDOW = 30

class LatencyPlotter(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.x, self.y = [], []
        self.ma_x, self.ma_y = [], []
        self.min_latency = self.max_latency = self.avg_latency = 0
        self.f = open(CSV_PATH, 'r')
        self.f.readline()
        for line in self.f:
            ts_bar, *_, ts_recv = line.strip().split(',')
            t_bar = float(ts_bar)
            t_recv = float(ts_recv) / 1e9  # <-- FIXED
            self.x.append(t_recv)
            self.y.append((t_recv - (t_bar + 5.0)) * 1000.0)
        for i in range(len(self.x)):
            t = self.x[i]
            ws = t - MA_WINDOW
            vals = [self.y[j] for j in range(i+1) if self.x[j] >= ws]
            if vals:
                self.ma_x.append(t)
                self.ma_y.append(sum(vals)/len(vals))
        if self.ma_y:
            self.min_latency = min(self.ma_y)
            self.max_latency = max(self.ma_y)
            self.avg_latency = sum(self.ma_y)/len(self.ma_y)
        self.y_range_max = self.max_latency * 1.2
        self.initUI()
        self.curve.setData(self.ma_x, self.ma_y)
        self.stats_label.setText(f"Min: {self.min_latency:.2f} ms | Max: {self.max_latency:.2f} ms | Avg: {self.avg_latency:.2f} ms")
        self.plot.setYRange(-10, self.y_range_max)
        self.f.seek(0, os.SEEK_END)
        self.timer = QtCore.QTimer(self)
        self.timer.timeout.connect(self.update_live)
        self.timer.start(1000)

    def initUI(self):
        self.setWindowTitle("Latency Dashboard")
        self.setStyleSheet("background-color: #000000; color: #FFFFFF;")
        layout = QtWidgets.QVBoxLayout()
        widget = QtWidgets.QWidget()
        widget.setLayout(layout)
        self.setCentralWidget(widget)
        axis = DateAxisItem(orientation='bottom')
        font = QtGui.QFont("Segoe UI", 9)
        axis.setStyle(tickFont=font)
        self.plot = pg.PlotWidget(axisItems={'bottom': axis})
        self.plot.showGrid(x=True, y=True, alpha=0.3)
        self.plot.setBackground('#000000')
        self.plot.setLabel('left', 'Latency (ms)', **{'color':'#FFFFFF','font-size':'11pt'})
        self.plot.setLabel('bottom', 'Time', **{'color':'#FFFFFF','font-size':'11pt'})
        self.plot.getAxis('left').enableAutoSIPrefix(False)
        self.plot.getAxis('left').setStyle(tickFont=font)
        self.plot.getAxis('bottom').setStyle(tickFont=font)
        self.plot.setTitle("Live Latency", color='#FFFFFF', size='14pt')
        self.plot.addItem(pg.InfiniteLine(pos=50, angle=0, pen=pg.mkPen(color='#FF5555', width=1, style=QtCore.Qt.DashLine)))
        self.curve = pg.PlotDataItem([], [], pen=pg.mkPen(color='#00FF00', width=2), fillLevel=0, fillBrush=pg.mkBrush(color=(0,255,0,50)))
        self.plot.addItem(self.curve)
        self.scatter = pg.ScatterPlotItem(size=8, brush=pg.mkBrush('#00FF00'), pen=None, symbol='o')
        self.scatter.setZValue(2)
        self.plot.addItem(self.scatter)
        self.stats_label = QtWidgets.QLabel()
        self.stats_label.setAlignment(QtCore.Qt.AlignCenter)
        self.stats_label.setStyleSheet("background-color: rgba(0,0,0,200); color:#FFFFFF; padding:8px; font-size:11pt;")
        layout.addWidget(self.plot, 1)
        layout.addWidget(self.stats_label)
        self.status_bar = QtWidgets.QStatusBar()
        self.status_bar.setStyleSheet("color: #00FF00; background-color: #000000;")
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Waiting for data...")
        self.proxy = pg.SignalProxy(self.plot.scene().sigMouseMoved, rateLimit=60, slot=self.mouseMoved)
        self.resize(1000, 600)

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
                    tstr = datetime.fromtimestamp(xv).strftime('%H:%M:%S')
                    self.status_bar.showMessage(f"Time: {tstr} | Latency: {yv:.2f} ms")
                    return
        self.scatter.setData([], [])

    def update_live(self):
        new = 0
        while True:
            pos = self.f.tell()
            line = self.f.readline()
            if not line:
                self.f.seek(pos)
                break
            ts_bar, *_, ts_recv = line.strip().split(',')
            t_bar = float(ts_bar)
            t_recv = float(ts_recv) / 1e9  # <-- FIXED
            lat = (t_recv - (t_bar + 5.0)) * 1000.0
            self.x.append(t_recv)
            self.y.append(lat)
            new += 1
        if new:
            for i in range(len(self.ma_x), len(self.x)):
                t = self.x[i]
                ws = t - MA_WINDOW
                vals = [self.y[j] for j in range(i+1) if self.x[j] >= ws]
                if vals:
                    self.ma_x.append(t)
                    self.ma_y.append(sum(vals)/len(vals))
            self.min_latency = min(self.ma_y)
            self.max_latency = max(self.ma_y)
            self.avg_latency = sum(self.ma_y)/len(self.ma_y)
            self.stats_label.setText(f"Min: {self.min_latency:.2f} ms | Max: {self.max_latency:.2f} ms | Avg: {self.avg_latency:.2f} ms")
            cap = self.max_latency * 1.2
            if cap > self.y_range_max:
                self.y_range_max = cap
                self.plot.setYRange(-10, self.y_range_max)
            self.curve.setData(self.ma_x, self.ma_y)
            if len(self.ma_x) > 10000:
                self.x = self.x[-10000:]
                self.y = self.y[-10000:]
                self.ma_x = self.ma_x[-10000:]
                self.ma_y = self.ma_y[-10000:]
            latest_t = self.x[-1]
            latest_lat = self.y[-1]
            tstr = datetime.fromtimestamp(latest_t).strftime('%H:%M:%S')
            self.status_bar.showMessage(f"Latest: {tstr} | {latest_lat:.2f} ms")

def main():
    if not os.path.isfile(CSV_PATH):
        sys.exit(1)
    app = QtWidgets.QApplication(sys.argv)
    app.setFont(QtGui.QFont("Segoe UI", 9))
    win = LatencyPlotter()
    win.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
