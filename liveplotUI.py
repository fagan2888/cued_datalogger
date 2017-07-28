# -*- coding: utf-8 -*-
"""
Created on Wed Jul  5 13:12:34 2017

@author: eyt21
"""
import sys,traceback
from PyQt5.QtWidgets import (QWidget,QVBoxLayout,QHBoxLayout,QMainWindow,
    QPushButton, QDesktopWidget,QStatusBar, QLabel,QLineEdit, QFormLayout,
    QGroupBox,QRadioButton,QSplitter,QFrame, QComboBox,QScrollArea,QGridLayout,
    QCheckBox,QButtonGroup)
from PyQt5.QtGui import QValidator,QIntValidator,QDoubleValidator,QBrush,QColor
from PyQt5.QtCore import Qt, QTimer, pyqtSignal
import pyqtgraph as pg
import numpy as np
import functools as fct

import myRecorder as mR
try:
    import NIRecorder as NIR
    NI_drivers = True
except NotImplementedError:
    print("Seems like you don't have National Instruments drivers")
    NI_drivers = False
except ModuleNotFoundError:
    print("Seems like you don't have pyDAQmx modules")
    NI_drivers = False

# Theo's channel implementation, will probably use it later
from channel import DataSet, Channel, ChannelSet

# GLOBAL CONSTANTS
PLAYBACK = False
MAX_SAMPLE = 1e6
WIDTH = 900
HEIGHT = 500

#++++++++++++++++++++++++ The LivePlotApp Class +++++++++++++++++++++++++++
class LiveplotApp(QMainWindow):
#-------------------------- METADATA ----------------------------------  
    # Signal for when data has finished acquired
    dataSaved = pyqtSignal()
    
#---------------------- CONSTRUCTOR METHOD------------------------------    
    def __init__(self,parent = None):
        super().__init__()
        self.parent = parent
        
        # Set window parameter
        self.setGeometry(500,300,WIDTH,HEIGHT)
        self.setWindowTitle('LiveStreamPlot')
        
        # Set recorder object
        self.playing = False
        self.rec = mR.Recorder(channels = 15,
                                num_chunk = 6,
                                device_name = 'Line (U24XL with SPDIF I/O)')
        # Connect the recorder Signals
        self.connect_rec_signals()
        
        # Set up the TimeSeries and FreqSeries
        self.timedata = None 
        self.freqdata = None
        
        self.plot_colourmap = self.gen_plot_col()
        
        try:
            # Construct UI        
            self.initUI()
            self.config_setup()
        except Exception as e:
            print(e)
            t,v,tb = sys.exc_info()
            print(t)
            print(v)
            print(traceback.format_tb(tb))
            self.close()
            return
        
        # Attempt to start streaming
        self.init_and_check_stream()
            
        # Center and show window
        self.center()
        self.setFocus()
        self.show()

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++        
#++++++++++++++++++++++++ UI CONSTRUCTION START ++++++++++++++++++++++++++++++     
    def initUI(self):
        # Set up the main widget        
        self.main_widget = QWidget(self)
        main_layout = QHBoxLayout(self.main_widget)
        main_splitter = QSplitter(self.main_widget,orientation = Qt.Horizontal)
        main_layout.addWidget(main_splitter)
        
    #-------------------- ALL SPLITTER ------------------------------
        left_splitter = QSplitter(main_splitter,orientation = Qt.Vertical)
        mid_splitter = QSplitter(main_splitter,orientation = Qt.Vertical)
        right_splitter = QSplitter(main_splitter,orientation = Qt.Vertical)
        
        main_splitter.addWidget(left_splitter)
        main_splitter.addWidget(mid_splitter)
        main_splitter.addWidget(right_splitter)
        
    #---------------------CHANNEL TOGGLE UI----------------------------------
        chantoggle_UI = QWidget(left_splitter)
        #chanUI_layout = QHBoxLayout(chanUI)        
        # Set up the channel tickboxes widget
        chans_toggle_layout = QVBoxLayout(chantoggle_UI)
        
        # Make the button tickboxes scrollable
        scroll = QScrollArea(left_splitter)
        
        self.channels_box = QWidget(scroll)
        self.checkbox_layout = QGridLayout(self.channels_box)
        
        # Set up the QbuttonGroup to manage the Signals
        self.chan_btn_group = QButtonGroup(self.channels_box)
        self.chan_btn_group.setExclusive(False)
                
        self.ResetChanBtns()
        self.chan_btn_group.buttonClicked.connect(self.display_channel_plots)
        
        #scroll.ensureVisible(50,50)
        scroll.setWidget(self.channels_box)
        scroll.setWidgetResizable(True)
        
        chans_toggle_layout.addWidget(scroll)
      
        # Set up the selection toggle buttons
        sel_btn_layout = QVBoxLayout()    
        sel_all_btn = QPushButton('Select All', left_splitter)
        sel_all_btn.clicked.connect(lambda: self.toggle_all_checkboxes(Qt.Checked))
        desel_all_btn = QPushButton('Deselect All',left_splitter)
        desel_all_btn.clicked.connect(lambda: self.toggle_all_checkboxes(Qt.Unchecked))
        inv_sel_btn = QPushButton('Invert Selection',left_splitter)
        inv_sel_btn.clicked.connect(self.invert_checkboxes)
        for y,btn in zip((0,1,2),(sel_all_btn,desel_all_btn,inv_sel_btn)):
            btn.resize(btn.sizeHint())
            sel_btn_layout.addWidget(btn)
            
        chans_toggle_layout.addLayout(sel_btn_layout)
        #chanUI_layout.addLayout(chans_settings_layout)
        
        
        #main_layout.addLayout(chans_settings_layout,10)
        left_splitter.addWidget(chantoggle_UI)
        
    #----------------CHANNEL CONFIGURATION WIDGET---------------------------    
        chanconfig_UI = QWidget(left_splitter)
        chans_prop_layout = QVBoxLayout(chanconfig_UI)
        chans_prop_layout.setContentsMargins(5,5,5,5)
        
        self.sig_hold = [Qt.Unchecked]* self.rec.channels
        
        chan_num_sel_layout = QHBoxLayout()
        self.chans_num_box = QComboBox(chanconfig_UI)
        chan_num_sel_layout.addWidget(QLabel('Channel',chanconfig_UI))
        chan_num_sel_layout.addWidget(self.chans_num_box)
        self.chans_num_box.currentIndexChanged.connect(self.display_chan_config)        
        self.hold_tickbox = QCheckBox('Hold',chanconfig_UI)
        self.hold_tickbox.stateChanged.connect(self.signal_hold)
        chan_num_sel_layout.addWidget(self.hold_tickbox)
        
        chans_prop_layout.addLayout(chan_num_sel_layout)
        
        self.chanprop_config = []
        
        chan_col_sel_layout = QHBoxLayout()
        colbox = pg.ColorButton(chanconfig_UI,(0,255,0))
        chan_col_sel_layout.addWidget(QLabel('Colour',chanconfig_UI))
        chan_col_sel_layout.addWidget(colbox)
        colbox.sigColorChanging.connect(self.set_plot_colour)
        self.chanprop_config.append(colbox)
        chans_prop_layout.addLayout(chan_col_sel_layout)
        
        
        chan_settings_layout = QHBoxLayout()
        chan_settings_layout.setSpacing(0)
        
        
        configs = ['XMove','YMove']
        
        # TODO: Maybe allow changeable step size
        for set_type in ('Time','DFT'):
            settings_gbox = QGroupBox(set_type, chanconfig_UI)
            settings_gbox.setFlat(True)
            gbox_layout = QFormLayout(settings_gbox)
            for c in configs:
                cbox = pg.SpinBox(parent= settings_gbox, value=0.0, bounds=[None, None],step = 0.1)
                gbox_layout.addRow(QLabel(c,chanconfig_UI),cbox)
                if c == 'XMove':
                    cbox.sigValueChanging.connect(fct.partial(self.set_plot_offset,'x',set_type))
                elif c == 'YMove':
                    cbox.sigValueChanging.connect(fct.partial(self.set_plot_offset,'y',set_type))
                self.chanprop_config.append(cbox)
                    
            settings_gbox.setLayout(gbox_layout)
            chan_settings_layout.addWidget(settings_gbox)
             
        chans_prop_layout.addLayout(chan_settings_layout)
        self.ResetChanConfigs()
        
        left_splitter.addWidget(chanconfig_UI)
    #----------------DEVICE CONFIGURATION WIDGET---------------------------   
        configUI = QWidget(left_splitter)
        
        # Set the device settings form
        config_form = QFormLayout(configUI)
        config_form.setSpacing (2)
        
        # Set up the device type radiobuttons group
        self.typegroup = QGroupBox('Input Type', configUI)
        typelbox = QHBoxLayout(self.typegroup)
        pyaudio_button = QRadioButton('SoundCard',self.typegroup)
        NI_button = QRadioButton('NI',self.typegroup)
        typelbox.addWidget(pyaudio_button)
        typelbox.addWidget(NI_button)
        
        # Set that to the layout of the group
        self.typegroup.setLayout(typelbox)
        
        # TODO: Give id to the buttons
        # Set up QbuttonGroup to manage the buttons' Signals
        typebtngroup = QButtonGroup(self.typegroup)
        typebtngroup.addButton(pyaudio_button)
        typebtngroup.addButton(NI_button)
        typebtngroup.buttonReleased.connect(self.display_sources)
        
        config_form.addRow(self.typegroup)
        
        # Add the remaining settings to Acquisition settings form
        configs = ['Source','Rate','Channels','Chunk Size','Number of Chunks']
        self.configboxes = []
        
        for c in configs:
            if c == 'Source':
                cbox = QComboBox(configUI)
                config_form.addRow(QLabel(c,configUI),cbox)
                self.configboxes.append(cbox)
                
            else:
                cbox = QLineEdit(configUI)
                config_form.addRow(QLabel(c,configUI),cbox)
                self.configboxes.append(cbox)  
        
        # Add a button to device setting form
        self.config_button = QPushButton('Set Config', configUI)
        self.config_button.clicked.connect(self.ResetRecording)
        config_form.addRow(self.config_button)
        
        left_splitter.addWidget(configUI)
        
    #----------------------PLOT WIDGETS------------------------------------        
        self.plotlines = []
        # Set up time domain plot, add to splitter
        self.timeplotcanvas = pg.PlotWidget(mid_splitter, background = 'default')
        self.timeplot = self.timeplotcanvas.getPlotItem()
        self.timeplot.setLabels(title="Time Plot", bottom = 'Time(s)') 
        self.timeplot.disableAutoRange(axis=None)
        self.timeplot.setMouseEnabled(x=False,y = True)
        
        # Set up FFT plot, add to splitter
        self.fftplotcanvas = pg.PlotWidget(mid_splitter, background = 'default')
        self.fftplot = self.fftplotcanvas.getPlotItem()
        self.fftplot.setLabels(title="FFT Plot", bottom = 'Freq(Hz)')
        self.fftplot.disableAutoRange(axis=None)
        
        self.ResetPlots()
        mid_splitter.addWidget(self.timeplotcanvas)
        mid_splitter.addWidget(self.fftplotcanvas)
        
    #-------------------------STATUS+PAUSE+SNAPSHOT----------------------------
        stps = QWidget(mid_splitter)
        stps_layout = QHBoxLayout(stps)
        
     #-------------------------STATUS BAR WIDGET--------------------------------
        # Set up the status bar
        self.statusbar = QStatusBar(stps)
        self.statusbar.showMessage('Streaming')
        self.statusbar.messageChanged.connect(self.default_status)
        self.statusbar.clearMessage()
        stps_layout.addWidget(self.statusbar)
        
    #---------------------PAUSE & SNAPSHOT BUTTONS-----------------------------
        #freeze_btns = QWidget(stps)
        # Set up the button layout to display horizontally
        #btn_layout = QHBoxLayout(freeze_btns)
        # Put the buttons in
        self.togglebtn = QPushButton('Pause',stps)
        self.togglebtn.resize(self.togglebtn.sizeHint())
        self.togglebtn.pressed.connect(lambda: self.toggle_rec())
        stps_layout.addWidget(self.togglebtn)
        self.sshotbtn = QPushButton('Get Snapshot',stps)
        self.sshotbtn.resize(self.sshotbtn.sizeHint())
        self.sshotbtn.pressed.connect(self.get_snapshot)
        stps_layout.addWidget(self.sshotbtn)

        mid_splitter.addWidget(stps)
        

    #---------------------------RECORDING WIDGET-------------------------------
        RecUI = QWidget(right_splitter)
        
        rec_settings_layout = QFormLayout(RecUI)
        
        # Add the recording setting UIs with the Validators
        configs = ['Samples','Seconds','Pretrigger','Ref. Channel','Trig. Level']
        default_values = ['','1.0', str(self.rec.pretrig_samples),
                          str(self.rec.trigger_channel),
                          str(self.rec.trigger_threshold)]
        validators = [QIntValidator(self.rec.chunk_size,MAX_SAMPLE),
                      QDoubleValidator(0.1,MAX_SAMPLE*self.rec.rate,1),
                      QIntValidator(-1,MAX_SAMPLE),
                      QIntValidator(0,self.rec.channels-1),
                      QDoubleValidator(0,5,2)]
        
        self.rec_boxes = []
        for c,v,vd in zip(configs,default_values,validators):
            cbox = QLineEdit(configUI)
            cbox.setText(v)
            cbox.setValidator(vd)
            rec_settings_layout.addRow(QLabel(c,configUI),cbox)
            self.rec_boxes.append(cbox)  
        
        # Connect the sample and time input check
        self.autoset_record_config('Time')
        self.rec_boxes[0].editingFinished.connect(lambda: self.autoset_record_config('Samples'))
        self.rec_boxes[1].editingFinished.connect(lambda: self.autoset_record_config('Time'))
        self.rec_boxes[2].editingFinished.connect(lambda: self.set_input_limits(self.rec_boxes[2],-1,self.rec.chunk_size,int))
        self.rec_boxes[4].textEdited.connect(self.change_threshold)
        
        # Add the record and cancel buttons
        rec_buttons_layout = QHBoxLayout()
        
        self.recordbtn = QPushButton('Record',RecUI)
        self.recordbtn.resize(self.recordbtn.sizeHint())
        self.recordbtn.pressed.connect(self.start_recording)
        rec_buttons_layout.addWidget(self.recordbtn)
        self.cancelbtn = QPushButton('Cancel',RecUI)
        self.cancelbtn.resize(self.cancelbtn.sizeHint())
        self.cancelbtn.setDisabled(True)
        self.cancelbtn.pressed.connect(self.cancel_recording)
        rec_buttons_layout.addWidget(self.cancelbtn)
        
        rec_settings_layout.addRow(rec_buttons_layout)
        
        right_splitter.addWidget(RecUI)
        
    #-----------------------CHANNEL LEVELS WIDGET------------------------------
        chanlevel_UI = QWidget(right_splitter)
        chanlevel_UI_layout = QVBoxLayout(chanlevel_UI)
        self.chanelvlcvs = pg.PlotWidget(mid_splitter, background = 'default')
        
        chanlevel_UI_layout.addWidget(self.chanelvlcvs)
        
        self.chanelvlplot = self.chanelvlcvs.getPlotItem()
        self.chanlvl_pts = self.chanelvlplot.plot()
        
        self.chanlvl_bars = pg.ErrorBarItem(x=np.arange(self.rec.channels),
                                            y =np.arange(self.rec.channels),
                                            pen = pg.mkPen(width = 5))
        
        self.chanelvlplot.addItem(self.chanlvl_bars)
        
        self.threshold_line = pg.InfiniteLine(pos = 0.0, movable = True)
        self.threshold_line.sigPositionChanged.connect(self.change_threshold)
        self.chanelvlplot.addItem(self.threshold_line)
        
        
        self.ResetChanLvls()
        right_splitter.addWidget(chanlevel_UI)
    
    #------------------------FINALISE THE SPLITTERS-----------------------------
        #main_splitter.addWidget(acqUI)
        
        main_splitter.setSizes([WIDTH*0.25,WIDTH*0.55,WIDTH*0.2])        
        main_splitter.setStretchFactor(0, 0)
        main_splitter.setStretchFactor(1, 1)
        main_splitter.setStretchFactor(2, 0)
        
        
        #left_splitter.setSizes([HEIGHT*0.1,HEIGHT*0.8])
        mid_splitter.setSizes([HEIGHT*0.48,HEIGHT*0.48,HEIGHT*0.04])
        right_splitter.setSizes([HEIGHT*0.05,HEIGHT*0.85])
        
    #-----------------------EXPERIMENTAL STYLING---------------------------- 
        main_splitter.setFrameShape(QFrame.Panel)
        main_splitter.setFrameShadow(QFrame.Sunken)
        self.main_widget.setStyleSheet('''
        .QWidget{
            background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                stop:0 #eee, stop:1 #ccc);
            border: 1px solid #777;
            width: 13px;
            margin-top: 2px;
            margin-bottom: 2px;
            border-radius: 4px;
        }
        .QSplitter::handle{
                background: solid green;
        }
        .QGroupBox{
                border: 1px solid black;
        }                   
        ''')
        
    #-----------------------FINALISE THE MAIN WIDGET------------------------- 
        #Set the main widget as central widget
        self.main_widget.setFocus()
        self.setCentralWidget(self.main_widget)
        
        # Set up a timer to update the plot
        #self.plottimer = QTimer(self)
        #self.plottimer.timeout.connect(self.update_line)
        #self.plottimer.start(self.rec.chunk_size*1000//self.rec.rate + 2)
        
        self.show()
        
    #---------------------------UI ADJUSTMENTS----------------------------
        #h = 600 - chans_settings_layout.geometry().height()
        #main_splitter.setSizes([h*0.35,h*0.35,h*0.3])
        
#++++++++++++++++++++++++ UI CONSTRUCTION END +++++++++++++++++++++++++++++++++
#++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++        
#+++++++++++++++++++++ UI CALLBACK METHODS +++++++++++++++++++++++++++++++++++
    
#---------------------CHANNEL TOGGLE UI----------------------------------    
    def display_channel_plots(self, *args):
        for btn in args:
            chan_num = self.chan_btn_group.id(btn)
            if btn.isChecked():
                self.plotlines[2*chan_num].setPen(self.plot_colours[chan_num])
                self.plotlines[2*chan_num+1].setPen(self.plot_colours[chan_num])
            else:
                self.plotlines[2*chan_num].setPen(None)
                self.plotlines[2*chan_num+1].setPen(None)
                
    def invert_checkboxes(self):
        for btn in self.channels_box.findChildren(QCheckBox):
            btn.click()
         
    def toggle_all_checkboxes(self,state):
        for btn in self.channels_box.findChildren(QCheckBox):
            if not btn.checkState() == state:
                btn.click()
                
#----------------CHANNEL CONFIGURATION WIDGET---------------------------    
    def display_chan_config(self, num):
        self.chanprop_config[0].setColor(self.plot_colours[num])
        self.chanprop_config[1].setValue(self.plot_xoffset[0,num])
        self.chanprop_config[2].setValue(self.plot_yoffset[0,num])
        self.chanprop_config[3].setValue(self.plot_xoffset[1,num])
        self.chanprop_config[4].setValue(self.plot_yoffset[1,num])
        self.hold_tickbox.setCheckState(self.sig_hold[num])
    
    def set_plot_offset(self, offset,set_type, sp,num):
        chan = self.chans_num_box.currentIndex()
        if set_type == 'Time':
            data_type = 0
        elif set_type == 'DFT':
            data_type = 1
            
        if offset == 'x':
            self.plot_xoffset[data_type,chan] = num
        elif offset == 'y':
            self.plot_yoffset[data_type,chan] = num
        
    def signal_hold(self,state):
        chan = self.chans_num_box.currentIndex()
        self.sig_hold[chan] = state
    
    def set_plot_colour(self):
        chan = self.chans_num_box.currentIndex()
        chan_btn = self.chan_btn_group.button(chan)
        col = self.chanprop_config[0].color()
        
        self.plot_colours[chan] = col;
        if chan_btn.isChecked():
            self.plotlines[2*chan].setPen(col)
            self.plotlines[2*chan+1].setPen(col)
        self.chanlvl_pts.scatter.setBrush(self.plot_colours)
     
#---------------------PAUSE & SNAPSHOT BUTTONS-----------------------------
    # Pause/Resume the stream, unless explicitly specified to stop or not       
    def toggle_rec(self,stop = None):
        if not stop == None:
            self.playing = stop
            
        if self.playing:
            self.rec.stream_stop()
            self.togglebtn.setText('Resume')
            self.recordbtn.setDisabled(True)
        else:
            self.rec.stream_start()
            self.togglebtn.setText('Pause')
            self.recordbtn.setEnabled(True)
        self.playing = not self.playing
        # Clear the status, allow it to auto update itself
        self.statusbar.clearMessage()
        
    # Get the current instantaneous plot and transfer to main window     
    def get_snapshot(self):
        snapshot = self.rec.get_buffer()
        self.save_data(data = snapshot[:,0])
        self.statusbar.showMessage('Snapshot Captured!', 1500)
        
#----------------------PLOT WIDGETS-----------------------------------        
    # Updates the plots    
    def update_line(self):
        data = self.rec.get_buffer()
        window = np.hanning(data.shape[0])
        weightage = np.exp(2* self.timedata / self.timedata[-1])
        for i in range(data.shape[1]):
            plotdata = data[:,i].reshape((len(data[:,i]),))
            
            zc = 0
            if self.sig_hold[i] == Qt.Checked:
                zero_crossings = np.where(np.diff(np.sign(plotdata))>0)[0]
                if zero_crossings.shape[0]:
                    zc = zero_crossings[0]+1
                
            self.plotlines[2*i].setData(x = self.timedata[:len(plotdata)-zc] + 
            self.plot_xoffset[0,i], y = plotdata[zc:] + self.plot_yoffset[0,i])

            fft_data = np.fft.rfft(plotdata* window * weightage)
            psd_data = abs(fft_data)
            self.plotlines[2*i+1].setData(x = self.freqdata + self.plot_xoffset[1,i], y = psd_data** 0.5  + self.plot_yoffset[1,i])

#----------------DEVICE CONFIGURATION WIDGET---------------------------    
    def config_setup(self):
        rb = self.typegroup.findChildren(QRadioButton)
        if type(self.rec) == mR.Recorder:
            rb[0].setChecked(True)
        elif type(self.rec) == NIR.Recorder:
            rb[1].setChecked(True)
            
        self.display_sources()
        
        info = [self.rec.rate,self.rec.channels,
                self.rec.chunk_size,self.rec.num_chunk]
        for cbox,i in zip(self.configboxes[1:],info):
            cbox.setText(str(i))
    
    def display_sources(self):
        # TODO: make use of the button input in callback?
        rb = self.typegroup.findChildren(QRadioButton)
        if not NI_drivers and rb[1].isChecked():
            print("You don't seem to have National Instrument drivers/modules")
            rb[0].setChecked(True)
            return 0
        
        if rb[0].isChecked():
            selR = mR.Recorder()
        elif rb[1].isChecked():
            selR = NIR.Recorder()
        else:
            return 0
        
        source_box = self.configboxes[0]
        source_box.clear()
        
        try:
            full_device_name = []
            s,b =  selR.available_devices()
            for a,b in zip(s,b):
                if type(b) == str:
                    full_device_name.append(a + ' - ' + b)
                else:
                    full_device_name.append(a)
                    
            source_box.addItems(full_device_name)
        except Exception as e:
            print(e)
            source_box.addItems(selR.available_devices()[0])
            
        if self.rec.device_name:
            source_box.setCurrentText(self.rec.device_name)
        del selR
                
    def read_device_config(self, *arg):
        recType =  [rb.isChecked() for rb in self.typegroup.findChildren(QRadioButton)]
        configs = []
        for cbox in self.configboxes:
            if type(cbox) == QComboBox:
                #configs.append(cbox.currentText())
                configs.append(cbox.currentIndex())
            else:
                #notnumRegex = re.compile(r'(\D)+')
                config_input = cbox.text().strip(' ')
                configs.append(int(float(config_input)))
                    
        print(recType,configs)
        return(recType, configs)
    
#---------------------------RECORDING WIDGET-------------------------------    
    # Start the data recording        
    def start_recording(self):
        rec_configs = self.read_record_config()
        
        if rec_configs[2]>=0:
            # Set up the trigger
            if self.rec.trigger_start(posttrig = rec_configs[0],
                                      duration = rec_configs[1],
                                      pretrig = rec_configs[2],
                                      channel = rec_configs[3],
                                      threshold = rec_configs[4]):
                self.statusbar.showMessage('Trigger Set!')
                for btn in self.main_widget.findChildren(QPushButton):
                    btn.setDisabled(True)
        else:
            self.rec.record_init(samples = rec_configs[0], duration = rec_configs[1])
            # Start the recording immediately
            if self.rec.record_start():
                self.statusbar.showMessage('Recording...')
                # Disable buttons
                for btn in [self.togglebtn, self.config_button, self.recordbtn]:
                    btn.setDisabled(True)
                
        self.cancelbtn.setEnabled(True)
    
    # Stop the data recording and transfer the recorded data to main window    
    def stop_recording(self):
        #self.rec.recording = False
        for btn in self.main_widget.findChildren(QPushButton):
            btn.setEnabled(True)
        self.cancelbtn.setDisabled(True)
        data = self.rec.flush_record_data()
        print(data[0,:])
        self.save_data(data[:,0])
        self.statusbar.clearMessage()
    
    # Cancel the data recording
    def cancel_recording(self):
        self.rec.record_cancel()
        for btn in self.main_widget.findChildren(QPushButton):
            btn.setEnabled(True)
        self.cancelbtn.setDisabled(True)
        self.statusbar.clearMessage()
        
    # Read the recording setting inputs
    def read_record_config(self, *arg):
        try:
            rec_configs = []
            data_type = [int,float,int,int,float]
            for cbox,dt in zip(self.rec_boxes,data_type):
                if type(cbox) == QComboBox:
                    #configs.append(cbox.currentText())
                    rec_configs.append(cbox.currentIndex())
                else:
                    config_input = cbox.text().strip(' ')
                    rec_configs.append(dt(float(config_input)))
            print(rec_configs)
            return(rec_configs)
        
        except Exception as e:
            print(e)
            return False
    
    # Auto set the time and samples based on recording limitations    
    def autoset_record_config(self, setting):
        sample_validator = self.rec_boxes[0].validator()
        time_validator = self.rec_boxes[1].validator()
        
        if setting == "Time":
            valid = time_validator.validate(self.rec_boxes[1].text(),0)[0]
            if not valid == QValidator.Acceptable:
                self.rec_boxes[1].setText(str(time_validator.bottom()))
                
            samples = int(float(self.rec_boxes[1].text())*self.rec.rate)
            valid = sample_validator.validate(str(samples),0)[0]
            if not valid == QValidator.Acceptable:
                samples = sample_validator.top()
        elif setting == 'Samples':
            samples = int(self.rec_boxes[0].text())        
        
        #samples = samples//self.rec.chunk_size  *self.rec.chunk_size
        duration = samples/self.rec.rate
        self.rec_boxes[0].setText(str(samples))
        self.rec_boxes[1].setText(str(duration))

#-------------------------CHANNEL LEVELS WIDGET--------------------------------
    def update_chanlvls(self):
        data = self.rec.get_buffer()
        currentdata = data[len(data)-self.rec.chunk_size:,:]
        rms = np.sqrt(np.mean(currentdata ** 2,axis = 0))
        maxs = np.amax(abs(currentdata),axis = 0)
        
        self.chanlvl_bars.setData(x = rms,right = maxs-rms,left = rms)
        self.chanlvl_pts.setData(x = rms,y = np.arange(self.rec.channels))
        
    def change_threshold(self,arg):
        if type(arg) == str:
            self.threshold_line.setValue(float(arg))
        else:
            self.rec_boxes[4].setText('%.2f' % arg.value())
        
#-------------------------STATUS BAR WIDGET--------------------------------
    # Set the status message to the default messages if it is empty (ie when cleared)       
    def default_status(self,*arg):
        if not arg[0]:
            if self.playing:
                self.statusbar.showMessage('Streaming')
            else:
                self.statusbar.showMessage('Stream Paused')
        
#+++++++++++++++++++++++++ UI CALLBACKS END++++++++++++++++++++++++++++++++++++   
#++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++   

#++++++++++++++++++++++++++ OTHER METHODS +++++++++++++++++++++++++++++++++++++        
#----------------------- APP ADJUSTMENTS METHODS-------------------------------               
    # Center the window
    def center(self):
        pr = self.parent.frameGeometry()
        qr = self.frameGeometry()
        print(qr.width())
        cp = QDesktopWidget().availableGeometry().center()
        qr.moveCenter(cp)
        self.move(pr.topLeft())
        self.move(qr.left() - qr.width(),qr.top())
        
#--------------------------- RESET METHODS-------------------------------------    
    def ResetRecording(self):
        self.statusbar.showMessage('Resetting...')
        
        # Stop the update and close the stream
        self.playing = False
        #self.plottimer.stop()
        self.rec.close()
        del self.rec
                
        try:    
            # Get Input from the Acquisition settings UI
            Rtype, settings = self.read_device_config()
            # Delete and reinitialise the recording object
            if Rtype[0]:
                self.rec = mR.Recorder()
            elif Rtype[1]:
                self.rec = NIR.Recorder()
            # Set the recorder parameters
            self.rec.set_device_by_name(self.rec.available_devices()[0][settings[0]])
            self.rec.rate = settings[1]
            self.rec.channels = settings[2]
            self.rec.chunk_size = settings[3]
            self.rec.num_chunk = settings[4]
        except Exception as e:
            print(e)
            print('Cannot set up new recorder')
        
        try:
            # Open the stream, plot and update
            self.init_and_check_stream()
            # Reset channel configs
            self.ResetChanConfigs()
            self.ResetPlots()
            self.ResetChanLvls()
            #self.plottimer.start(self.rec.chunk_size*1000//self.rec.rate + 1)
        except:
            t,v,tb = sys.exc_info()
            print(t)
            print(v)
            print(traceback.format_tb(tb))
            print('Cannot stream,restart the app')
        
        try:
            # Reset recording configuration Validators and inputs checks
            self.ResetRecConfigs()
            self.autoset_record_config('Samples')
        except:
            t,v,tb = sys.exc_info()
            print(t)
            print(v)
            print(traceback.format_tb(tb))
            print('Cannot recording configs')
        
        try:
            # Reset and change channel toggles
            self.ResetChanBtns()
        except:
            t,v,tb = sys.exc_info()
            print(t)
            print(v)
            print(traceback.format_tb(tb))
            print('Cannot reset buttons')
        
        self.connect_rec_signals()
        
    def ResetPlots(self):
            n_plotlines = len(self.plotlines)
            self.ResetXdata()
            
            for _ in range(n_plotlines):
                line = self.plotlines.pop()
                line.clear()
                #del line
                
            for i in range(self.rec.channels):
                self.plotlines.append(self.timeplot.plot(pen = self.plot_colours[i]))
                self.plotlines.append(self.fftplot.plot(pen = self.plot_colours[i]))
            
            self.timeplot.setRange(xRange = (0,self.timedata[-1]),yRange = (-1,1))
            self.fftplot.setRange(xRange = (0,self.freqdata[-1]),yRange = (0, 2**4))
            self.fftplot.setLimits(xMin = 0,xMax = self.freqdata[-1],yMin = -20)
            self.update_line()
    
    def ResetXdata(self):
        data = self.rec.get_buffer()
        self.timedata = np.arange(data.shape[0]) /self.rec.rate 
        self.freqdata = np.arange(int(data.shape[0]/2)+1) /data.shape[0] * self.rec.rate
        
    def ResetChanLvls(self): 
        self.chanlvl_pts.clear()
        #del self.chanlvl_pts
        
        self.chanlvl_pts = self.chanelvlplot.plot(pen = None,symbol='o',
                                                  symbolBrush = self.plot_colours,
                                                  symbolPen = None)
 
        self.update_chanlvls()
        
    def ResetChanBtns(self):
        for btn in self.chan_btn_group.buttons():
            btn.setCheckState(Qt.Checked)
        
        n_buttons = self.checkbox_layout.count()
        extra_btns = abs(self.rec.channels - n_buttons)
        if extra_btns:
            if self.rec.channels > n_buttons:
                columns_limit = 4
                current_y = (n_buttons-1)//columns_limit
                current_x = (n_buttons-1)%columns_limit
                for n in range(n_buttons,self.rec.channels):
                    current_x +=1
                    if current_x%columns_limit == 0:
                        current_y +=1
                    current_x = current_x%columns_limit
                    
                    chan_btn = QCheckBox('Channel %i' % n,self.channels_box)
                    chan_btn.setCheckState(Qt.Checked)
                    self.checkbox_layout.addWidget(chan_btn,current_y,current_x)
                    self.chan_btn_group.addButton(chan_btn,n)
            else:
                for n in range(n_buttons-1,self.rec.channels-1,-1):
                    chan_btn = self.chan_btn_group.button(n)
                    self.checkbox_layout.removeWidget(chan_btn)
                    self.chan_btn_group.removeButton(chan_btn)
                    chan_btn.deleteLater()
                    
    def ResetRecConfigs(self):
           validators = [QIntValidator(self.rec.chunk_size,MAX_SAMPLE),
                         QDoubleValidator(0.1,MAX_SAMPLE*self.rec.rate,1),
                         QIntValidator(-1,self.rec.chunk_size),
                         QIntValidator(0,self.rec.channels-1)]
           
           for cbox,vd in zip(self.rec_boxes[:-1],validators):
                cbox.setValidator(vd)    
                
    def ResetChanConfigs(self):
        self.plot_xoffset = np.zeros(shape = (2,self.rec.channels))
        self.plot_yoffset = np.repeat(np.arange(float(self.rec.channels)).reshape(1,self.rec.channels),2,axis = 0) * [[1],[50]]
        c_list = self.plot_colourmap.getLookupTable(nPts = self.rec.channels)
        self.plot_colours = []
        for i in range(self.rec.channels):
            r,g,b = c_list[i]
            self.plot_colours.append(QColor(r,g,b))

        self.chans_num_box.clear()
        self.chans_num_box.addItems([str(i) for i in range(self.rec.channels)])
        self.chans_num_box.setCurrentIndex(0)
        
        self.display_chan_config(0)
    
#----------------------- DATA TRANSFER METHODS -------------------------------    
    # Transfer data to main window      
    def save_data(self,data = None):
        print('Saving data...')

        # Save the time series
        self.parent.cs.chans[0].set_data('t', np.arange(data.size)/self.rec.rate)
        # Save the values
        self.parent.cs.chans[0].set_data('y', data.reshape(data.size))
        
        self.dataSaved.emit()        
        print('Data saved!')

#-------------------------- STREAM METHODS ------------------------------------        
    def init_and_check_stream(self):
         if self.rec.stream_init(playback = PLAYBACK):
            self.togglebtn.setEnabled(True)
            self.toggle_rec(stop = False)
            self.statusbar.showMessage('Streaming')
         else:
            self.togglebtn.setDisabled(True)
            self.toggle_rec(stop = True)
            self.statusbar.showMessage('Stream not initialised!')
            
    def connect_rec_signals(self):
            self.rec.rEmitter.recorddone.connect(self.stop_recording)
            self.rec.rEmitter.triggered.connect(self.trigger_message)
            self.rec.rEmitter.newdata.connect(self.update_line)
            self.rec.rEmitter.newdata.connect(self.update_chanlvls)
            
            
    def trigger_message(self):
        self.statusbar.showMessage('Triggered! Recording...')
 #-------------------------- COLOUR METHODS ------------------------------------       
    def gen_plot_col(self):
        val = [0.0,0.5,1.0]
        colour = np.array([[255,0,0,255],[0,255,0,255],[0,0,255,255]], dtype = np.ubyte)
        return pg.ColorMap(val,colour)
     
    def set_input_limits(self,linebox,low,high,in_type):
        val = in_type(linebox.text())
        print(val)
        linebox.setText( str(min(max(val,low),high)) )
        
        
#----------------------OVERRIDDEN METHODS------------------------------------
    # The method to call when the mainWindow is being close       
    def closeEvent(self,event):
        #if self.plottimer.isActive():
        #    self.plottimer.stop()
        self.rec.close()
        event.accept()
        if self.parent:
            self.parent.liveplot = None
            self.parent.liveplotbtn.setText('Open Oscilloscope')
            
           