from datalogger.api.pyqtgraph_extensions import InteractivePlotWidget
from datalogger.api.toolbox import Toolbox
from datalogger.api.numpy_extensions import to_dB

from PyQt5.QtWidgets import QWidget, QVBoxLayout, QPushButton, QComboBox
from PyQt5.QtCore import pyqtSignal

import scipy.fftpack
import numpy as np
import pyqtgraph as pg

class FrequencyDomainWidget(InteractivePlotWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.plot_types = ['Linear Magnitude',
                           'Log Magnitude',
                           'Phase',
                           'Real Part',
                           'Imaginary Part',
                           'Nyquist']
        self.current_plot_type = self.plot_types[0]
    
    def set_selected_channels(self, selected_channels):
        """Update which channels are plotted"""
        # If no channel list is given
        if not selected_channels:
            self.channels = []
        else:
            self.channels = selected_channels
        
        self.update_plot()
    
    def set_plot_type(self, index):
        self.current_plot_type = self.plot_types[index]
        self.update_plot()
    
    def update_plot(self):
        self.clear()
        
        for channel in self.channels:
            # If no spectrum exists, calculate one
            print("Recalculating spectrum...")
            units = channel.get_units("time_series")
            #spectrum = scipy.fftpack.rfft(channel.get_data("time_series"))
            spectrum = np.fft.rfft(channel.get_data("time_series"))
            if not channel.is_dataset("spectrum"):
                channel.add_dataset("spectrum", units, spectrum)
            else:
                channel.set_data("spectrum", spectrum)
                
            print("Done.")
                
            # Plot
            if self.current_plot_type == 'Linear Magnitude':
                print("Plotting Linear Magnitude.")
                self.plot(channel.get_data("frequency"), 
                          np.abs(channel.get_data("spectrum")),
                          pen=pg.mkPen(channel.colour))
                
            elif self.current_plot_type == 'Log Magnitude':
                print("Plotting Log Magnitude.")
                self.plot(channel.get_data("frequency"),
                          to_dB(np.abs(channel.get_data("spectrum"))),
                          pen=pg.mkPen(channel.colour))
                
            elif self.current_plot_type == 'Phase':
                print("Plotting Phase.")
                self.plot(channel.get_data("frequency"), 
                          np.angle(channel.get_data("spectrum")),
                          pen=pg.mkPen(channel.colour))
                
            elif self.current_plot_type == 'Real Part':
                print("Plotting Real Part.")
                self.plot(channel.get_data("frequency"),
                          np.real(channel.get_data("spectrum")),
                          pen=pg.mkPen(channel.colour))
                
            elif self.current_plot_type == 'Imaginary Part':
                print("Plotting Imaginary Part.")
                self.plot(channel.get_data("frequency"), 
                          np.imag(channel.get_data("spectrum")),
                          pen=pg.mkPen(channel.colour))
                
            elif self.current_plot_type == 'Nyquist':
                print("Plotting Nyquist.")
                self.plot(np.real(channel.get_data("spectrum")), 
                          np.imag(channel.get_data("spectrum")),
                          pen=pg.mkPen(channel.colour))

            
class FrequencyToolbox(Toolbox):
    """Toolbox containing the Frequency Domain controls"""
    
    sig_convert_to_circle_fit = pyqtSignal()
    sig_plot_type_changed = pyqtSignal(int)
    
    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.parent = parent
        
        self.init_ui()
    
    def init_ui(self):
        # # Conversion tab
        self.convert_tab = QWidget(self)
        convert_tab_layout = QVBoxLayout()

        self.circle_fit_btn = QPushButton("Convert to Circle Fit")
        self.circle_fit_btn.clicked.connect(self.sig_convert_to_circle_fit.emit)
        convert_tab_layout.addWidget(self.circle_fit_btn)
      
        self.convert_tab.setLayout(convert_tab_layout)
        
        self.addTab(self.convert_tab, "Conversion")
        
        # # Plot options tab
        self.plot_options_tab = QWidget(self)
        plot_options_tab_layout = QVBoxLayout()

        self.plot_type_combobox = QComboBox(self.plot_options_tab)
        self.plot_type_combobox.addItems(['Linear Magnitude',
                                          'Log Magnitude',
                                          'Phase',
                                          'Real Part',
                                          'Imaginary Part',
                                          'Nyquist'])
    
        self.plot_type_combobox.setCurrentIndex(0)
        self.plot_type_combobox.currentIndexChanged.connect(self.sig_plot_type_changed.emit)
        plot_options_tab_layout.addWidget(self.plot_type_combobox)
        
        self.plot_options_tab.setLayout(plot_options_tab_layout)
        
        self.addTab(self.plot_options_tab, "Plot Options")
