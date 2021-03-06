# -*- coding: utf-8 -*-
"""
Created on Wed Jul  5 13:12:34 2017

@author: eyt21
"""
import sys
from PyQt5.QtWidgets import (QWidget,QVBoxLayout,QMainWindow,
    QPushButton, QApplication, QMessageBox, QDesktopWidget)
#from PyQt5.QtGui import QIcon,QFont
from PyQt5.QtCore import QCoreApplication,QTimer

#from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
#from matplotlib.figure import Figure
import numpy as np

import pyqtgraph as pg
import myRecorder as rcd

#--------------------- The App Class------------------------------------
class Example(QMainWindow):
    def __init__(self):
        super().__init__()
        
        # Set window parameter
        self.setGeometry(500,500,500,500)
        self.setWindowTitle('LiveStreamPlot')
        
        # Set recorder object
        self.rec = rcd.Recorder(num_chunk = 6,
                                device_name = 'Line (U24XL with SPDIF I/O)')
        self.rec.stream_init(playback = True)
        self.playing = True
        data = self.rec.get_buffer()
        self.timedata = np.arange(data.shape[0]) /self.rec.rate #change to put sampling rate
        self.freqdata = np.arange(round(data.shape[0]/2)+1) /data.shape[0] * self.rec.rate
        # Construct UI        
        self.initUI()
        
        # Center and show window
        self.center()
        self.setFocus()
        self.show()
     #------------- App construction methods--------------------------------     
    def initUI(self):
        # Setup the plot canvas        
        self.main_widget = QWidget(self)
        vbox = QVBoxLayout(self.main_widget)
        
        # Set up time domain plot
        self.timeplotcanvas = pg.PlotWidget(self.main_widget, background = 'default')
        vbox.addWidget(self.timeplotcanvas)
        self.timeplot = self.timeplotcanvas.getPlotItem()
        self.timeplot.setLabels(title="Time Plot", bottom = 'Time(s)')
        self.timeplot.disableAutoRange(axis=None)
        self.timeplot.setRange(xRange = (0,self.timedata[-1]),yRange = (-2**7,2**7)) #change to put chunk size and all that
        self.timeplotline = self.timeplot.plot(pen='g')
        #self.timeplotline.setData()
        
        # Set up PSD plot
        self.fftplotcanvas = pg.PlotWidget(self.main_widget, background = 'default')
        vbox.addWidget(self.fftplotcanvas)
        self.fftplot = self.fftplotcanvas.getPlotItem()
        self.fftplot.setLabels(title="PSD Plot", bottom = 'Freq(Hz)')
        self.fftplot.disableAutoRange(axis=None)
        self.fftplot.setRange(xRange = (0,self.freqdata[-1]),yRange = (0, 2**8)) #change to put chunk size and all that
        self.fftplotline = self.fftplot.plot(pen = 'y')
        print(type(self.fftplotline))
        self.fftplotline.setDownsampling(auto = True) 
        
        self.update_line()
        
        # Set up the button
        self.btn = QPushButton('Pause',self.main_widget)
        self.btn.resize(self.btn.sizeHint())
        self.btn.pressed.connect(self.toggle_rec)
        vbox.addWidget(self.btn)
        self.main_widget.setFocus()
        self.setCentralWidget(self.main_widget)
        
        # Set up a timer to update the plot
        timer = QTimer(self)
        timer.timeout.connect(self.update_line)
        timer.start(23.2)
    
    def center(self):
        qr = self.frameGeometry()
        cp = QDesktopWidget().availableGeometry().center()
        qr.moveCenter(cp)
        self.move(qr.topLeft())
        
    #------------- UI callback methods--------------------------------       
    def toggle_rec(self):
        if self.playing:
            self.rec.stream_stop()
            self.btn.setText('Resume')
        else:
            self.rec.stream_start()
            self.btn.setText('Pause')
        self.playing = not self.playing
        
    def update_line(self):
        data = self.rec.get_buffer()
        data = data.reshape((len(data),))
        window = np.hanning(data.shape[0])
        fft_data = np.fft.rfft(window * data)
        psd_data = abs(fft_data)**2 / (np.abs(window)**2).sum()
        self.timeplotline.setData(x = self.timedata, y = data)
        #self.fftplotline.setData(abs(fft_data))
        self.fftplotline.setData(x = self.freqdata, y = psd_data** 0.5)
        #self.canvas.draw()
        
    #----------------Overrding methods------------------------------------
    # The method to call when the mainWindow is being close       
    def closeEvent(self,event):
        reply = QMessageBox.question(self,'Message',
        'Are you sure you want to quit?', QMessageBox.Yes|
        QMessageBox.No, QMessageBox.No)
        
        if reply == QMessageBox.Yes:
            self.rec.close()
            event.accept()
        else:
            event.ignore()
            
#----------------Main loop------------------------------------         
if __name__ == '__main__':
    app = QApplication(sys.argv)
    w = Example()
    sys.exit(app.exec_())
 