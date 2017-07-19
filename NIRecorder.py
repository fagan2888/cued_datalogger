"""
- Essentially identical to the pyaudio version
"""

from RecorderParent import RecorderParent

import sys,traceback
# TODO: Add codes to install pyaudio if pyaudio is not installed???
import PyDAQmx as pdaq
from PyDAQmx import Task

import numpy as np
import pprint as pp


class Recorder(RecorderParent):
#---------------- INITIALISATION METHODS -----------------------------------
    def __init__(self,channels = 1,rate = 30000.0, chunk_size = 1000,
                 num_chunk = 4,device_name = None):

        super().__init__(channels = channels,rate = rate, 
             chunk_size = chunk_size,num_chunk = num_chunk)
        print('You are using National Instrument for recording')
        
        self.device_name = self.set_device_by_name(device_name);
               
        self.open_recorder()
        self.trigger_init()
            
#---------------- DEVICE SETTING METHODS -----------------------------------
    def set_device_by_name(self, name):
        devices = self.available_devices()[0]
        selected_device = None
        if not devices:
            print('No NI devices found')
            return selected_device
        
        if not name in devices:
            print('Input device name not found, using the first device')
            selected_device = devices[0]
        else:
            selected_device = name
            
        print('Selected devices: %s' % selected_device)
        return selected_device
    
     # Get audio device names 
    def available_devices(self):
        numBytesneeded = pdaq.DAQmxGetSysDevNames(None,0)
        databuffer = pdaq.create_string_buffer(numBytesneeded)
        pdaq.DAQmxGetSysDevNames(databuffer,numBytesneeded)
        devices_name = pdaq.string_at(databuffer).decode('utf-8').split(',')
        device_list = []
        device_list.append(devices_name)
        return(device_list)
    
    # Display the current selected device info      
    def current_device_info(self):
        device_info = {}
        info = ('Category', 'Type','Product', 'Number',
                'Analog Trigger','Analog Input Channels (ai)', 'Analog Output Channels (ao)',
                'Minimum Rate(Hz)', 'Maximum Rate(Single)(Hz)', 'Maximum Rate(Multi)(Hz)')
        funcs = (pdaq.DAQmxGetDevProductCategory, pdaq.DAQmxGetDevProductType,
                 pdaq.DAQmxGetDevProductNum, pdaq.DAQmxGetDevSerialNum,
                 pdaq.DAQmxGetDevAnlgTrigSupported, pdaq.DAQmxGetDevAIPhysicalChans,
                 pdaq.DAQmxGetDevAOPhysicalChans, pdaq.DAQmxGetDevAIMinRate,
                 pdaq.DAQmxGetDevAIMaxSingleChanRate, pdaq.DAQmxGetDevAIMaxMultiChanRate)
        var_types = (pdaq.int32, str, pdaq.uInt32, pdaq.uInt32, pdaq.bool32,
                    str,str, pdaq.float64, pdaq.float64, pdaq.float64)
        
        for i,f,v in zip(info,funcs,var_types):
            if v == str:
                nBytes = f(self.device_name,None,0)
                string_ptr = pdaq.create_string_buffer(nBytes)
                f(self.device_name,string_ptr,nBytes)
                if 'Channels' in i:
                    device_info[i] = len(string_ptr.value.decode().split(','))
                else:
                    device_info[i] = string_ptr.value.decode()
            else:
                data = v()
                f(self.device_name,data)
                device_info[i] = data.value
                           
        pp.pprint(device_info)
        
    # Return the channel names to be used when assigning task     
    def set_channels(self):
        if self.channels >1:
            channelname =  '%s/ai0:%s/ai%i' % (self.device_name, self.device_name,self.channels-1)
        elif self.channels == 1:
            channelname = '%s/ai0' % self.device_name
            
        print('Channels Name: %s' % channelname)
        return channelname
            
#---------------- STREAMING METHODS -----------------------------------
    # Callback function for audio streaming
    def stream_audio_callback(self):
        in_data = np.zeros(self.chunk_size*self.channels,dtype = np.int16)
        read = pdaq.int32()
        self.audio_stream.ReadBinaryI16(self.chunk_size,10.0,pdaq.DAQmx_Val_GroupByScanNumber,
                           in_data,self.chunk_size*self.channels,pdaq.byref(read),None)
        self.write_buffer(self.audiodata_to_array(in_data))
        if self.recording:
            self.record_data()
        return 0
    
    # TODO: Check for valid device, channels and all that before initialisation
    def stream_init(self, playback = False):
        if self.audio_stream == None:
            try:
                self.audio_stream = Task()
                self.audio_stream.stream_audio_callback = self.stream_audio_callback
                self.audio_stream.CreateAIVoltageChan(self.set_channels(),"",
                                         pdaq.DAQmx_Val_RSE,-10.0,10.0,
                                         pdaq.DAQmx_Val_Volts,None)
                self.audio_stream.CfgSampClkTiming("",self.rate,
                                      pdaq.DAQmx_Val_Rising,pdaq.DAQmx_Val_ContSamps,
                                      self.chunk_size)
                self.audio_stream.AutoRegisterEveryNSamplesEvent(pdaq.DAQmx_Val_Acquired_Into_Buffer,
                                                    1000,0,name = 'stream_audio_callback')
            except Exception as e:
                print(e)
                self.audio_stream = None
                return False
            
            self.stream_start()
            return True
        
    # Start the streaming
    def stream_start(self):
        if self.audio_stream: 
            task_done = pdaq.bool32()
            self.audio_stream.GetTaskComplete(task_done)
            if task_done.value:
                self.audio_stream.StartTask()
            else:
                print('Stream already started')
        else:
            print('No audio stream is set up')
    # Stop the streaming
    def stream_stop(self):
        if self.audio_stream: 
            task_done = pdaq.bool32()
            self.audio_stream.GetTaskComplete(task_done)
            if not task_done.value:
                self.audio_stream.StopTask()
            else:
                print('Stream already stopped')
        else:
            print('No audio stream is set up')
        
    # Close the stream, probably needed if any parameter of the stream is changed
    def stream_close(self):
        if self.audio_stream:
            self.audio_stream.ClearTask()
            self.audio_stream = None
            
    #---------------- RECORD TRIGGER METHODS ----------------------------------
    def trigger_init(self):
        self.trigger = False
        self.pretrig_samples = self.chunk_size;
        self.posttrig_samples = 0;
        
    def trigger_done_callback(self):
        read = pdaq.int32()
        
        pretrig_data = np.zeros(self.pretrig_samples*self.channels,dtype = np.int16)
        try:
            self.audio_stream.SetReadRelativeTo(pdaq.DAQmx_Val_FirstPretrigSamp)
            self.audio_stream.ReadBinaryI16(self.pretrig_samples,10.0,pdaq.DAQmx_Val_GroupByScanNumber,
                               pretrig_data,self.pretrig_samples*self.channels,pdaq.byref(read),None)
        except Exception as e:
            print(e)
        finally:
            self.recorded_data.append(pretrig_data)
                
        posttrig_data = np.zeros(self.posttrig_samples*self.channels,dtype = np.int16)
        try:
            self.audio_stream.SetReadRelativeTo(pdaq.DAQmx_Val_RefTrig)
            self.audio_stream.ReadBinaryI16(self.posttrig_samples,10.0,pdaq.DAQmx_Val_GroupByScanNumber,
                               posttrig_data,self.posttrig_samples*self.channels,pdaq.byref(read),None)
        except Exception as e:
            print(e)
        finally:
            self.recorded_data.append(posttrig_data)
            
        try:
            self.recorded_data.reshape((self.buffer.shape[0], self.buffer.shape[1],
                           self.buffer.shape[2]))
        except Exception as e:
                print(e)
            
        try:                                         
            self.audio_stream.SetSampQuantSampMode(pdaq.DAQmx_Val_ContSamps);
            self.audio_stream.SetSampQuantSampPerChan(self.chunk_size);
       
            self.audio_stream.DisableRefTrig()
            self.audio_stream.AutoRegisterDoneEvent(0)
            self.trigger = False
            self.stream_start()
        except Exception as e:
            print(e)
        
        print('Triggering done!')
        return 0
    
    def trigger_start(self,duration = 3, threshold = 2.0, channel = 0):
        if self.audio_stream:
            self.stream_stop()
        else:
            print('Please initialise a stream.')
            return False
        
        if not self.trigger:
            try:
                self.posttrig_samples = int(duration * self.rate // self.chunk_size *self.chunk_size)
                
                self.audio_stream.trigger_done_callback = self.trigger_done_callback
                
                self.audio_stream.SetSampQuantSampMode(pdaq.DAQmx_Val_FiniteSamps);
                self.audio_stream.SetSampQuantSampPerChan(pdaq.uInt64(self.posttrig_samples));
               
                trigger_channelname = '%s/ai%i' % (self.device_name, channel)
                self.audio_stream.CfgAnlgEdgeRefTrig(trigger_channelname,
                                                     pdaq.DAQmx_Val_RisingSlope,
                                                     threshold,
                                                     self.pretrig_samples)
                
                self.audio_stream.AutoRegisterDoneEvent(0, name = 'trigger_done_callback')
                
                self.audio_stream.SetReadRelativeTo(pdaq.DAQmx_Val_CurrReadPos);
                                                   
                self.trigger = True
            except Exception as e:
                print(e)
                t,v,tb = sys.exc_info()
                print(t)
                print(v)
                print(traceback.format_tb(tb))
                self.stream_close()
                print('Stream Closed!')
                return False
            
            self.stream_start()
            return True
        else:
            print('You have already started a trigger')
            return False
        