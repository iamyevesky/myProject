# -*- coding: utf-8 -*-
"""
Created on Fri Jun 14 12:45:45 2019

@author: yeves
"""

import time
import pyvisa
import serial
import csv
import datetime
from pathlib import Path
import os
import xlsxwriter

"""
:brief Converts list data from scope to voltage values 
:param list data type raw_rata contains the values recorded
:from scope in ASCII format
:param  resourceManager object scope: access point of the oscilloscope
:return list data type voltage: recorded voltage values
"""
def convert_raw_voltage_data(raw_data, scope):
    #Query returns the y-axis scale on oscilloscope graph
    ymult = float(scope.query('WFMOutpre:YMULT?'))
    #Query returns the y-zero value of the oscilloscope graph
    yzero = float(scope.query('WFMOutpre:YZERO?'))
    #Query returns the offset value for the y-axis on the oscilloscope graph
    yoff = float(scope.query('WFMOutpre:YOFF?'))
    npoint=len(raw_data)
    voltage=['?']*npoint
    #Convert raw data values and fill into voltage list
    #Non-recorded data appears as '?' in voltage list
    for i in range(npoint):
        voltage[i]=ymult*(raw_data[i]-yoff)+yzero
    return voltage
"""
:brief sets the channel of the scope
:param  resourceManager object scope: access point of the oscilloscope
:param int data type channel: channel scope is to be set
"""
def set_channel(scope, channel):
    scope.write(":DATa:SOUrce CH"+str(channel))
"""
:brief obtains raw data from oscilloscope and converts it into voltage list
:param  resourceManager object scope: access point of the oscilloscope
:return list data type voltage: recorded voltage values
"""
def get_data(scope):
    scope.write("WFMOutpre:ENCdg ASCii")
    data = scope.query_ascii_values("CURVE?")
    voltage=convert_raw_voltage_data(data, scope)
    return voltage

"""
:brief prints recorded data into datasheet docuement with corresponding
 voltage and time recorded from each of the channels
:param  resourceManager object scope: access point of the oscilloscope
:param int data type numchan is number of channels
:param list data type voltage contains recorded voltage values
:param list data type times contains recorded time values corresponding
:with recorded voltage
:param float data type dt records the sampling time interval
:param file data type outfile: datasheet into which data would be stored 
:param stime data type String:Locale’s appropriate date and time representation
 param float data type timeins: time as a floating point number expressed in seconds since the epoch, in UTC.
""" 
"""
:brief obtains the times for which sampling data was recorded
:param  resourceManager object scope: access point of the oscilloscope
:param int data type record_length: number of sample data recorded
:return list data type times: the times at which sampling data was recorded
""" 
def get_time(scope, record_length):
    times=['?']*record_length
    xincr = float(scope.query('WFMOutpre:XINCR?'))
    print('xincr= '+str(xincr))
    for i in range(record_length):
        times[i]=float(i)*xincr
    return times  

"""
:brief obtains the recording time interval
:param  resourceManager object scope: access point of the oscilloscope
:return float data type xincr: the sampling time interval
""" 
def get_dt(scope):
    xincr = float(scope.query('WFMOutpre:XINCR?'))
    return xincr
"""
:brief obtains the total time for which data was recorded from oscillopscope
:param  resourceManager object scope: access point of the oscilloscope
:return float data type wait_time: total time taken for data sample collection
"""
def calc_wait_time(scope):
    record_length=float(scope.query(':HORIZONTAL:RECORDLENGTH?'))
    dt=get_dt(scope)
    wait_time=record_length*dt
    return wait_time

"""
:brief sets the scale for the graph of the data
:param  resourceManager object scope: the access point of the oscilloscope
:param int data type numchan: number of channels 
:param int data type short_record_length: unexplained
:param int data type long_record_length: unexplained
"""
def checkscale(scope, numchan, short_record_length, long_record_length):
    base_record_length=int(scope.query(':HORIZONTAL:RECORDLENGTH?')) 
    if short_record_length != base_record_length:
        scope.write(':Horizontal:Recordlength '+str(short_record_length)) #Why?
    hscale = 0.000000001*short_record_length*0.1 #Why?
    scope.write(":Horizontal:Scale "+str(hscale))
    #Sets the "from" part of the waveform to be captured. In this case from data point 1
    scope.write('DATA:START 1')
    #Sets the "to" part of the waveform to be captured. In this case to the last recordrd data point
    scope.write('DATA:STOP '+str(short_record_length))
    scope.write('ACQUIRE:STOPAFTER RUnsTOP')
    for i in range(numchan):
        okayscale = 0
        while okayscale == 0:
            set_channel(scope, i+1)
            scope.write("WFMOutpre:ENCdg ASCii")
            data = scope.query_ascii_values("CURVE?")
            highcount = 0
            lowcount = 0
            for j in range(short_record_length):
                if data[j] > 32760: #Why 32760?
                    highcount += 1
                elif data[j] < 32760/5:
                    lowcount += 1
            if highcount/short_record_length > 0.0001:
                chscale = float(scope.query("CH"+str(i+1)+":SCALE?"))
                """
                Oscilloscope has scales of 1mV, 2mV, 5mV, 0.1V, 0.2V, 0.5V up
                to 10V in a pattern of 1,2,5.
                To increase scale when it is a unit value of 1 or 5, multiply by 2
                else multiply by 2.5.
                If scale is at 10V, then that is the max.
                """
                if chscale in [0.001, 0.01, 0.1, 1.0, 0.005, 0.05, 0.5, 5.0]:
                    newchscale = chscale*2
                if chscale in [0.002, 0.02, 0.2, 2.0]:
                    newchscale = chscale*2.5
                if chscale == 10:
                    okayscale = 1
                    print('CH'+str(i+1)+': already at max scale')
                    break                    
                scope.write("CH"+str(i+1)+":SCALE "+str(newchscale))
                print('CH'+str(i+1)+': changing scale from '+str(chscale)+' to '+str(newchscale))
            if lowcount/short_record_length > 0.9999 and highcount/short_record_length < 0.0001:
                chscale = float(scope.query("CH"+str(i+1)+":SCALE?"))
                if chscale in [0.01, 0.1, 1.0, 10.0, 0.002, 0.02, 0.2, 2.0]:
                    newchscale = chscale/2
                if chscale in [ 0.005, 0.05, 0.5, 5.0]:
                    newchscale = chscale/2.5
                if chscale == 0.001:
                    okayscale = 1
                    print('CH'+str(i+1)+': already at min scale')
                    break                     
                scope.write("CH"+str(i+1)+":SCALE "+str(newchscale))
                print('CH'+str(i+1)+': changing scale from '+str(chscale)+' to '+str(newchscale))
            if highcount/short_record_length < 0.0001 and lowcount/short_record_length < 0.9999:
                okayscale = 1
        scope.write(":Horizontal:recordlength "+str(long_record_length))
        hscale = 0.000000001*long_record_length*0.1
        scope.write(":Horizontal:Scale "+str(hscale))

"""
:brief reads data from oscilloscope and returns recorded voltage
:param resourceManager object scope: the access point of the oscilloscope 
:param int data type numchan: number of channels 
:param int data type nstart: unexplained
:param String data type descriptor: describes the experiment undertaken
:param int data type short_record_length: unexplained
:param int data type long_record_length: unexplained
"""
def read_and_write_data_from_Nch(scope, numchan, nstart, short_record_length, long_record_length):
    checkscale(scope, numchan, short_record_length, long_record_length)    
    wait_time = calc_wait_time(scope)
    record_length=int(scope.query(':HORIZONTAL:RECORDLENGTH?'))
    scope.write('DATA:START 1')
    scope.write('DATA:STOP '+str(record_length))
    scope.write('acquire:stopafter sequence')
    voltage = [['?']*(record_length)]*numchan
    for i in range(numchan):
        set_channel(scope, i+1)
        voltage[i]=get_data(scope)                
        time.sleep(wait_time)
    set_channel(scope, 1)
    times=get_time(scope, record_length)
    scope.write('FPAnel:PRESS runstop')
    
    output = [times]
    for i in range(numchan):
        output+=[voltage[i]]
    scope.close()
    return output

"""
:brief plots the data received from oscilloscope
:param resourceManager object scope: the access point of the oscilloscope 
:param int data type nstart: unexplained
:param int data type i: channel from which data is read
:param list data type times: the times at which sampling data was recorded
:param list data type voltage: recorded voltage values
:param String data type figoutfile: adress where graphs plotted are stored
:param String data type descriptor: describes the experiment undertaken
:return
"""
"""
:brief
:param
:param
:return
"""
def mainforAmbrell(numchan, nstart, j, short_record_length, long_record_length):
    
    #Initialize system for data-taking
    rm = pyvisa.highlevel.ResourceManager()
    #Visa address for Tektronik Osciloscope
    visa_address = 'USB::0x0699::0x0408::C043120::INSTR'

    scope = rm.open_resource(visa_address)
    #Open channels
    scope.write(":SELECT:CH1 on")
    scope.write(":SELECT:CH2 on")
    scope.write(":SELECT:CH3 on")
    #Encodes oscilloscope data into ASCII format
    scope.write(":DATA:ENCDG ASCII")
    
    scope.write('Data:width 2')
    
    return read_and_write_data_from_Nch(scope, numchan, nstart, short_record_length, long_record_length)

def scopeRead(shortRecordLength, longRecordLength, numCollects, numChan):
    
    short_record_length = shortRecordLength
    long_record_length = longRecordLength
    #descriptor = 'CH1-Hcoil-CH2-Mcoil-empty-test'
    numcollects = numCollects
    numchan= numChan
    
    """
    note time between data collections is about 16 seconds already because of various oscilloscope data transfer wait times
    (which are probably overly conservative)
    so any nonzero pause value makes that wait time longer than 16 seconds
    """
    pause = 0
    nstart = 0
    output = []
    
    #startTime = time.time()
    for j in range(numcollects):
        output += [mainforAmbrell(numchan, nstart, j, short_record_length, long_record_length)]
        time.sleep(pause)    
    
    finalOutput = [['?']*len(output) for i in range(numchan)]
    for k in range(numchan):
        for i in range(len(output)):
            finalOutput[k][i] = (output[i][0], output[i][1+k])
    
    return finalOutput

def opsensRead(numCollects):
    """
    Delay is the amount of time taken for Opsens to record data
    for each data point.
    It takes the oscilloscope an average of 1.6 - 1.7 seconds for every run
    We decide on 1.8 seconds for each run because time is also needed for
    writing things ex cetera.
    Hence the value of 1.
    """
    delay = 0.02;
    dataPointsForEachScopeRun = int(1.80/delay)
    ntimes = numCollects*dataPointsForEachScopeRun
    ser = serial.Serial("COM3",9600, timeout=((ntimes*delay)+2))
    unicodestring = "measure:start "+str(ntimes)+"\n"

    ser.write(unicodestring.encode("ascii"))
    rawData0 = ser.read(ntimes*10)
    rawData0 = rawData0.decode("ascii")
    data0 = rawData0.split('\n')

    removeMisc = ['\4','CH1','']
    errors = ['Err -170','Err -201', 'Err -140','Err -160']
    data1 = []

    for y in range(len(removeMisc)):
        while removeMisc[y] in data0:
            data0.remove(removeMisc[y])
    
    for x in range(len(data0)):
        times = x*float(delay)
        temp = "?"
        if data0[x] not in errors:
            temp=float(data0[x])
        data1.append([times,temp])
    ser.close()
    output=['?']*numCollects
    
    index = 0
    for i in range(len(output)):
        indexRange = dataPointsForEachScopeRun+index
        times = []
        temp = []
        for j in range(index,indexRange):
            times.append(data1[j][0]) 
            temp.append(data1[j][1])
        output[i] = (times,temp)
        index+=dataPointsForEachScopeRun
    
    return output

def vnaRead(numTimes, start, end):
    numRecord = numTimes
    startFreq = start 
    endFreq = end 
    measuredValue = "'Z-S11'"
    trace = "'Trc1'"
    
    rm = pyvisa.highlevel.ResourceManager()
    visaAddress = 'TCPIP::139.147.54.111::inst0::INSTR'
    
    vna = rm.open_resource(visaAddress)
    vna.write_termination = '\r'
    vna.read_termination = '\n'
    vna.write('*rst')
    vna.write('display:window1:state on')
    vna.write('calculate:format polar')
    vna.write('sense1:sweep:points '+str(numRecord))
    delay = vna.query('sense1:sweep:time?')
    vna.write("calculate1:parameter:measure "+trace+", "+measuredValue)
    vna.write('sense1:frequency:start '+str(startFreq)+';stop '+str(endFreq))
    time.sleep(1)
    vna.write("display:window1:trace1:y:scale:auto once, "+trace)
    csv = vna.query('calculate1:data? fdata')
    time.sleep(float(delay))
    meas = csv.split(',')
    freq = ['?']*int(len(meas)/2.0)
    real = ['?']*int(len(meas)/2.0)
    imag = ['?']*int(len(meas)/2.0)
    moveIndex = 0
    for i in range(int(len(meas)/2.0)):
        freq[i] = startFreq+((endFreq-startFreq)/float(len(meas)/2))*i
        real[i] = float(meas[i+moveIndex])
        imag[i] = float(meas[i+1+moveIndex])
        moveIndex+=1
    output = [freq]+[real]+[imag]
    return output

def writeDataFiles(scopeData, tempData, numCollects, numChan, filepath): 
    delay = 0.02;
    dataPointsForEachScopeRun = int(1.80/delay)
    ntimes = numCollects*int(dataPointsForEachScopeRun)
    scopeValues = [['?']*3 for i in range(numCollects)]
    tempValues = [[] for i in range(2)]
    
    currentDate = datetime.datetime.now()
    date = str(currentDate.strftime("%Y%m%d"))
    time = str(currentDate.strftime('%H%M%S'))
    filepath = addDirectory(filepath, 'Data')
    filepath = addDirectory(filepath, 'MH')
    filepath = addDirectory(filepath, date)
    filepath = addDirectory(filepath, time)
    
    excelFilePath = addDirectory(filepath,'CompleteData'+date+time+'.xlsx')
    workbook = xlsxwriter.Workbook(excelFilePath)
    voltageWorksheet = []
    
    opsensFilePath = addDirectory(filepath, 'Opsens')
    scopeFilePath  = addDirectory(filepath, 'Oscilloscope')
    timeVTemp = addDirectory(opsensFilePath,'tempData'+date+' '+time+'.csv')
    runVTemp = addDirectory(opsensFilePath,'tempScopeRunData'+date+' '+time+'.csv')
    timeVTemp = Path(timeVTemp)
    runVTemp = Path(runVTemp)
    timeVVoltage = []
    for i in range(len(scopeValues)):
        timeVVoltage.append(Path(addDirectory(scopeFilePath,'voltageDataScopeRun'+date+' '+time+'('+str(i+1)+')'+'.csv')))
        voltageWorksheet.append(workbook.add_worksheet('voltageDataScopeRun'+str(i+1)))
    
    for k in range(numChan):
        for i in range(len(scopeValues)):
            scopeValues[i][0] = scopeData[k][i][0]
            scopeValues[i][1+k] = scopeData[k][i][1]
    for i in range(len(scopeValues)):
        with open(timeVVoltage[i], 'w', newline = '') as csvfile:
            headers = ['Time','Voltage(CH1)','Voltage(CH2)']
            writer = csv.DictWriter(csvfile, fieldnames = headers)
            writer.writeheader()
            voltageWorksheet[i].write(0,0,'Time')
            voltageWorksheet[i].write(0,1,'Voltage(CH1)')
            voltageWorksheet[i].write(0,2,'Voltage(CH2)')
            for j in range(len(scopeValues[0][0])):
                writer.writerow({'Time' : str(scopeValues[i][0][j]),'Voltage(CH1)' : str(scopeValues[i][1][j]), 'Voltage(CH2)': str(scopeValues[i][2][j])})        
                voltageWorksheet[i].write(j+1,0,scopeValues[i][0][j])
                voltageWorksheet[i].write(j+1,1,scopeValues[i][1][j])
                voltageWorksheet[i].write(j+1,2,scopeValues[i][2][j])
    
    tempWorksheet = workbook.add_worksheet('tempData')
    for k in range(len(tempData)):
        tempValues[0]+=tempData[k][0]
        tempValues[1]+=tempData[k][1]
    with open(timeVTemp, 'w', newline = '') as csvfile:
        headers = ['Time','Temp']
        writer = csv.DictWriter(csvfile, fieldnames = headers)
        writer.writeheader()
        tempWorksheet.write(0,0,'Time')
        tempWorksheet.write(0,1,'Temp')
        for i in range(len(tempValues[0])):
            writer.writerow({'Time' : str(tempValues[0][i]),'Temp': str(tempValues[1][i])})
            tempWorksheet.write(i+1,0,tempValues[0][i])
            tempWorksheet.write(i+1,1,tempValues[1][i])
    
    tempScopeWorksheet = workbook.add_worksheet('tempScopeRunData')
    avgTemp = []
    index = 0
    for i in range(index,dataPointsForEachScopeRun+index):
        avgTemp.append(sum(tempValues[1][index:dataPointsForEachScopeRun+index])/dataPointsForEachScopeRun)
        index+=dataPointsForEachScopeRun
        if (index>=len(tempValues[1])):
            break  
    with open(runVTemp, 'w', newline = '') as csvfile:
        headers = ['Oscilloscope Run','Temp']
        writer = csv.DictWriter(csvfile, fieldnames = headers)
        writer.writeheader()
        tempScopeWorksheet.write(0,0,'Oscilloscope Run')
        tempScopeWorksheet.write(0,1,'Temp')
        for i in range(len(avgTemp)):
            writer.writerow({'Oscilloscope Run' : i+1,'Temp': avgTemp[i]})
            tempScopeWorksheet.write(i+1,0,i+1)
            tempScopeWorksheet.write(i+1,1,avgTemp[i])
    workbook.close()

def writeImpeadanceData(vnaData, filepath):
    currentDate = datetime.datetime.now()
    date = str(currentDate.strftime("%Y%m%d"))
    time = str(currentDate.strftime('%H%M%S'))
    filepath = addDirectory(filepath, 'Data')
    filepath = addDirectory(filepath, 'MH')
    filepath = addDirectory(filepath, date)
    filepath = addDirectory(filepath, time)
    csvFilePath = addDirectory(filepath, 'Impeadance')
    csvFilePath = addDirectory(csvFilePath, 'ImpeadanceData'+date+time+'.csv')
    
    with open(csvFilePath, 'w', newline ='') as csvfile:
        headers = ['Frequency', 'Real','Imaginary']
        writer = csv.DictWriter(csvfile, fieldnames = headers)
        writer.writeheader()
        for i in range(len(vnaData[0])):
            writer.writerow({'Frequency': str(vnaData[0][i]), 'Real': str(vnaData[1][i]), 'Imaginary':str(vnaData[2][i])})

def addDirectory(iPath, newPath):
    if not os.path.exists(iPath):
        os.mkdir(iPath)
    return iPath+'\\'+newPath