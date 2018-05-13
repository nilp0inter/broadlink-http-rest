from BaseHTTPServer import BaseHTTPRequestHandler, HTTPServer
import json
import broadlink, configparser
import sys, getopt
import time, binascii
import netaddr
import settings
import signal
from os import path
from Crypto.Cipher import AES


class Server(BaseHTTPRequestHandler):

    def _set_headers(self):
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()

    def do_GET(self):

        if 'favicon' in self.path:
            return False

        self._set_headers()

        if 'learnCommand' in self.path:
            commandName = self.path.split('/')[2] 
            result = learnCommand(commandName)
            if result == False:
                self.wfile.write("Failed: No command learned")
            else:
                self.wfile.write("Learned: %s" % commandName)

        
        elif 'sendCommand' in self.path:
            commandName = "/".join(self.path.split('/')[2:])
            if 'on' in commandName or 'off' in commandName:
                status = commandName.rsplit('o', 1)[1]
                realcommandName = commandName.rsplit('o', 1)[0]
                print(status,realcommandName)
                if 'n' in status:
                    setStatus(realcommandName, '1', True)
                elif 'ff' in status:
                    setStatus(realcommandName, '0', True)
            result = sendCommand(commandName)
            if result == False:
                self.wfile.write("Failed: Unknonwn command")
            else:
                self.wfile.write("Sent: %s" % commandName)


        elif 'getStatus' in self.path:
            commandName = self.path.split('/')[2]
            if 'temp' in commandName:
                result = getTempRM()
                if result == False:
                    self.wfile.write("Failed: Cannot get temperature")
                else:
                    self.wfile.write('''{ "temperature": %s } ''' % result)
            else:
                status = getStatus(commandName)
                if (status):
                    self.wfile.write(status)
                else:
                    self.wfile.write("Failed: Unknown command")
        
        elif 'setStatus' in self.path:
            commandName = self.path.split('/')[2]
            status = self.path.split('/')[3]
            result = setStatus(commandName, status)
            print('Setting status %s of %s' % (commandName,status))
            if (result):
                self.wfile.write("Set status of %s to %s" % (commandName, status))
            else:
                self.wfile.write("Failed: Unknown command")

        elif 'getCommands' in self.path:
            self.wfile.write(json.dumps([x[0] for x in settingsFile.items('Commands')]))
        else:
            self.wfile.write("Failed")

serverPort = ''

def sendCommand(commandName):
    device = broadlink.rm((RMIPAddress, RMPort), RMMACAddress, 'RM2')
    device.auth()

    deviceKey = device.key
    deviceIV = device.iv

    if settingsFile.has_option('Commands', commandName):
        commandFromSettings = settingsFile.get('Commands', commandName)
    else:
        return False

    print('sending command %s' % commandName)
    if commandFromSettings.strip() != '':
        decodedCommand = binascii.unhexlify(commandFromSettings)
        AESEncryption = AES.new(str(deviceKey), AES.MODE_CBC, str(deviceIV))
        encodedCommand = AESEncryption.encrypt(str(decodedCommand))
        
        finalCommand = encodedCommand[0x04:]    
        
        signal.signal(signal.SIGALRM, signal_handler)
        signal.alarm(4)   # Ten seconds
        try:
            device.send_data(finalCommand)
        except Exception, msg:
            print "Probably timed out.."
            return True

def learnCommand(commandName):
    device = broadlink.rm((RMIPAddress, RMPort), RMMACAddress, 'RM2')
    device.auth()

    deviceKey = device.key
    deviceIV = device.iv

    device.enter_learning()
    time.sleep(RealTimeout)
    LearnedCommand = device.check_data()

    if LearnedCommand is None:
        print('Command not received')
        return False

    AdditionalData = bytearray([0x00, 0x00, 0x00, 0x00])    
    finalCommand = AdditionalData + LearnedCommand

    AESEncryption = AES.new(str(deviceKey), AES.MODE_CBC, str(deviceIV))
    decodedCommand = binascii.hexlify(AESEncryption.decrypt(str(finalCommand)))

    broadlinkControlIniFile = open(path.join(settings.applicationDir, 'settings.ini'), 'w')    
    settingsFile.set('Commands', commandName, decodedCommand)
    settingsFile.write(broadlinkControlIniFile)
    broadlinkControlIniFile.close()
    return True

def setStatus(commandName, status, exist = False):
    if exist:
        broadlinkControlIniFile = open(path.join(settings.applicationDir, 'settings.ini'), 'w')    
        settingsFile.set('Status', commandName, status)
        settingsFile.write(broadlinkControlIniFile)
        broadlinkControlIniFile.close()
        return True

    if settingsFile.has_option('Status', commandName):
        commandFromSettings = settingsFile.get('Status', commandName)
    else:
        return False
    if commandFromSettings.strip() != '':
        broadlinkControlIniFile = open(path.join(settings.applicationDir, 'settings.ini'), 'w')    
        settingsFile.set('Status', commandName, status)
        settingsFile.write(broadlinkControlIniFile)
        broadlinkControlIniFile.close()
        return True
    else:
        return False

def getStatus(commandName):
    if settingsFile.has_option('Status', commandName):
        status = settingsFile.get('Status', commandName)
        return status
    else:
        return False

def getTempRM():
    device = broadlink.rm((RMIPAddress, RMPort), RMMACAddress)
    device.auth()
    temperature = device.check_temperature()
    if temperature:
        return temperature
    return False 


def signal_handler(signum, frame):
    print ("HTTP timeout, but the command should be already sent.")
        
def start(server_class=HTTPServer, handler_class=Server, port=serverPort):


    server_address = ('', port)
    httpd = server_class(server_address, handler_class)
    print 'Starting broadlink-rest server on port %s ...' % port
    httpd.serve_forever()

if __name__ == "__main__":

    settingsFile = configparser.ConfigParser()
    settingsFile.optionxform = str
    settingsFile.read(settings.settingsINI)

    RMIPAddress = settings.RMIPAddress
    if RMIPAddress.strip() == '':
        print('IP address must exist in settings.ini or it should be entered as a command line parameter')
        sys.exit(2)

    RMPort = settings.RMPort
    if RMPort.strip() == '':
        print('Port must exist in settings.ini or it should be entered as a command line parameter')
        sys.exit(2)
    else:
        RMPort = int(RMPort.strip())

    RMMACAddress = settings.RMMACAddress
    if RMMACAddress.strip() == '':
        print('MAC address must exist in settings.ini or it should be entered as a command line parameter')
        sys.exit(2)
    else:
        RMMACAddress = netaddr.EUI(RMMACAddress)

    RealTimeout = settings.Timeout
    if RealTimeout.strip() == '':
        print('Timeout must exist in settings.ini or it should be entered as a command line parameter')
        sys.exit(2)
    else:
        RealTimeout = int(RealTimeout.strip())    


    if settingsFile.has_option('General', 'serverPort'):
        serverPort = int(settingsFile.get('General', 'serverPort'))
    else:
        serverPort = 8080


    start(port=serverPort)
