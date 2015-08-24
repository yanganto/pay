import smbus
import socket
import threading
from time import *  
from datetime import datetime
# Commands
LCD_CLEARDISPLAY = 0x01
LCD_RETURNHOME = 0x02
LCD_ENTRYMODESET = 0x04
LCD_DISPLAYCONTROL = 0x08
LCD_CURSORSHIFT = 0x10
LCD_FUNCTIONSET = 0x20
LCD_SETCGRAMADDR  = 0x40
LCD_SETDDRAMADDR = 0x80

# display entry mode
LCD_ENTRYRIGHT = 0x00
LCD_ENTRYLEFT = 0x02
LCD_ENTRYSHIFTINCREMENT = 0x01
LCD_ENTRYSHIFTDECREMENT = 0x00


# display On/Off control
LCD_DISPLAYON = 0x04
LCD_DISPLAYOFF = 0x00
LCD_CURSORON = 0x02
LCD_CURSOROFF = 0x00
LCD_BLINKON = 0x01
LCD_BLINKOFF = 0x00

# flags for display/cursor shift
LCD_DISPLAYMOVE = 0x08
LCD_CURSORMOVE =  0x00
LCD_MOVERIGHT = 0x04
LCD_MOVELEFT = 0x00

# flags for function set
LCD_8BITMODE = 0x10
LCD_4BITMODE = 0x00
LCD_2LINE = 0x08
LCD_1LINE = 0x00
LCD_5x10DOTS = 0x04
LCD_5x8DOTS = 0x00


# Backlight control
LCD_NOBACKLIGHT = 0x00
LCD_BACKLIGHT = 0x08




En = 0x04 # Enable bit
Rw = 0x02 # Read/Write bit
Rs = 0x01 # Register select bit


class Lcd:
    def __init__(self, port, addr, col, row):
        self._addr = addr
        self.bus = smbus.SMBus(port)  
        self._col = col
        self._backlightval = LCD_NOBACKLIGHT
        self._row = row 
        self._displayfunction = LCD_4BITMODE | LCD_1LINE | LCD_5x8DOTS
        self.begin(col, row)
        
    def write(self, byte):
        self.send(byte, Rs)
    def read(self):  
        return self.bus.read_byte(self._addr)  
    def read_nbytes_data(self, data, n): # For sequential reads > 1 byte  
        return self.bus.read_i2c_block_data(self._addr, data, n)  
    def printIIC(self, byte):
        self.bus.write_byte(self._addr, byte)

    def begin(self, cols, lines, dotsize = 0):
        self._autoscroll = True
        if lines > 1:
            self._displayfunction |= LCD_2LINE
        self._numlines = lines
        
        # for some 1 line displays you can select a 10 pixel high font
        if dotsize != 0 and lines == 1:
            self._displayfunction |= LCD_5x10DOTS  

        # SEE PAGE 45/46 FOR INITIALIZATION SPECIFICATION!
        # according to datasheet, we need at least 40ms after power rises above 2.7V
        # before sending commands. Arduino can turn on way befer 4.5V so we'll wait 50
        sleep(0.05)
        
        # Now we pull both RS and R/W low to begin commands
        self.expanderWrite( self._backlightval) # reset expanderand turn backlight off (Bit 8 =1)
        sleep(1)
        
        
        # put the LCD into 4 bit mode
        # this is according to the hitachi HD44780 datasheet
        # figure 24, pg 46
    
        # we start in 8bit mode, try to set 4 bit mode
        self.write4bits(0x03 << 4)
        sleep(0.0045) #wait min 4.1ms
   
        # second try
        self.write4bits(0x03 << 4)
        sleep(0.0045) #wait min 4.1ms
   
        # third go!
        self.write4bits(0x03 << 4) 
        sleep(0.00015)
              
        # finally, set to 4-bit interface
        self.write4bits(0x02 << 4) 
   
        # set # lines, font size, etc.
        self.command(LCD_FUNCTIONSET | self._displayfunction)  
    
        # turn the display on with no cursor or blinking default
        self._displaycontrol = LCD_DISPLAYON | LCD_CURSOROFF | LCD_BLINKOFF
        self.display()
    
        # clear it off
        self.clear()
    
        # Initialize to default text direction (for roman languages)
        self._displaymode = LCD_ENTRYLEFT | LCD_ENTRYSHIFTDECREMENT
    
        # set the entry mode
        self.command(LCD_ENTRYMODESET | self._displaymode)
    
        self.home()

    ## HIGH LEVEL COMMANDS ##
    def clear(self):
        self.command(LCD_CLEARDISPLAY)
        sleep(0.002)
        
    def home(self):
        self.command(LCD_RETURNHOME)
        sleep(0.002)

    def setCursor(self, col, row):
        row_offsets = [ 0x00, 0x40, 0x14, 0x54]
        row = self._numlines if row > self._numlines else row
        self.command(LCD_SETDDRAMADDR | (col + row_offsets[row]) );

    # Turn the display on/off (quickly)
    def display(self, boolean = True):
        if boolean:
            self._displaycontrol |= LCD_DISPLAYON
        else:
            self._displaycontrol &= ~LCD_DISPLAYON;
        self.command(LCD_DISPLAYCONTROL | self._displaycontrol)
    def noDisplay(self):
        self.display(False)

    # Turns the underline cursor on/off
    def cursor(self, boolean = True):
        if boolean:
            self._displaycontrol |= LCD_CURSORON
        else:
            self._displaycontrol &= ~LCD_CURSORON
        self.command(LCD_DISPLAYCONTROL | self._displaycontrol)
    def noCursor(self):
        self.cursor(False)
    
    # Turn on and off the blinking cursor       
    def blink(self, boolean = True):
        if boolean:
            self._displaycontrol |= LCD_BLINKON
        else:
            self._displaycontrol &= ~LCD_BLINKON                
        self.command(LCD_DISPLAYCONTROL | self._displaycontrol)
    
    def noBlink(self):
        self.blink(False)
        
    # These commands scroll the display without changing the RAM
    def scrollDisplayLeft(self):
        self.command(LCD_CURSORSHIFT | LCD_DISPLAYMOVE | LCD_MOVELEFT)

    # These commands scroll the display without changing the RAM
    def scrollDisplayRight(self):
        self.command(LCD_CURSORSHIFT | LCD_DISPLAYMOVE | LCD_MOVERIGHT)

    # This is for text that flows Left to Right
    def leftToRight(self):
        self._displaymode |= LCD_ENTRYLEFT;
        self.command(LCD_ENTRYMODESET | self._displaymode);

    # This is for text that flows Right to Left
    def rightToLeft(self):
        self._displaymode &= ~LCD_ENTRYSHIFTINCREMENT
        self.command(LCD_ENTRYMODESET | self._displaymode)

    # This will 'right justify' text from the cursor
    def autoscroll(self, b = True):
        if b:
            self._autoscroll = True
            self._displaymode |= LCD_ENTRYSHIFTINCREMENT
        else:
            self._autoscroll = False
            self._displaymode &= ~LCD_ENTRYSHIFTINCREMENT
        self.command(LCD_ENTRYMODESET | self._displaymode)
        
    # This will 'left justify' text from the cursor
    def noAutoscroll(self):
        self.autoscroll(False)
    # Allows us to fill the first 8 CGRAM locations
    # with custom characters
    def createChar(self, location, bCharMap):
        location &= 0x07
        self.command(LCD_SETCGRAMADDR | (location << 3));
        for i in range(8):
            self.write(charmap[i])

    def backlight(self, boolean = True):
        if boolean:
            self._backlightval = LCD_BACKLIGHT
        else:
            self._backlightval = LCD_NOBACKLIGHT
        self.expanderWrite(0)
        
    def noBacklight(self):
        self.backlight(False)
        
    # Middle Level      
    def command(self, value):
        self.send(value, 0)

        
    #Low Level Commands
    def write4bits(self, value):    
        self.expanderWrite(value)
        self.pulseEnable(value)
        
    def send(self, value, mode):
        highnib = value & 0xf0
        lownib= (value << 4 ) & 0xf0
        self.write4bits( (highnib)|mode )
        self.write4bits( (lownib)|mode ) 
        
    def pulseEnable(self, data):
        self.expanderWrite( data | En)  #En high
        sleep(0.000001)     #enable pulse must be >450ns
        
        self.expanderWrite( data & ~En);    #En low
        sleep(0.00005)
            
    def expanderWrite(self, data):
        self.printIIC( data | self._backlightval)

    def print( self, line, col=0,  row=0, clear=True, backlight=True):
        row += col // self._col
        col = col % self._col
        if len(line) + row *self._col  + col > self._col * self._row:
            self.print("OverFlow")           
            return -1
        if clear:
            self.clear()
        if backlight and self._backlightval is LCD_NOBACKLIGHT:
            self.backlight()
        if not backlight and self._backlightval is LCD_BACKLIGHT:
            self.backlight(False)
        if not self._autoscroll:
            self.autoscroll()
        if col is 0 and row is 0:
            self.home()
        else:
            self.setCursor(col, row)
        for i in range(len(line)):
            if not (i + col) % self._col:
                self.setCursor(0, (i + col) // self._col)
            self.write(ord(line[i]))

        
class LoopDisplay( threading.Thread ):
    ''' Continue showing Message(msg) in queue, if msg is None, then showing IP + Time'''
    __regist = {} # store each I2C device, Key is a tuple (I2C_Port, I2C_Address), ex: (1, 0x27)

    def __new__(clz, port, addr, col=16, row=2 ):
        if (port, addr) in LoopDisplay.__regist:
            return LoopDisplay.__regist[(port, addr)]
        return object.__new__(clz)

    def __init__(self, port, addr, col=16, row=2):
        if (port, addr) not in LoopDisplay.__regist:
            super(LoopDisplay, self).__init__()
            self.setLcd(port, addr,  col, row)
            self._presentMsg = None 
            self.start()
            LoopDisplay.__regist[(port, addr)] = self 
                    
    def __del__(self):
        self.print("", clear=True)
        self.exit()
        self.lcd = None
        
    def setLcd(self, port, addr, col, row):
        self.lcd = Lcd( port, addr, col, row)
        self._msg = [] # Queue of List to show, each Element is ( Message, timeToShow), ex: ("msg", 5)
        self._col = col
        
    def show( self, msg, showSec=5):
        self._msg.append((msg, showSec))
        
    def run(self):
        while self.lcd:
            if self._msg:
                if self._msg[0][0] != self._presentMsg:
                    self.lcd.print(self._msg[0][0])
                    self._showInSec = self._msg[0][1] 
                self._showInSec -= 1 
                self._presentMsg = self._msg[0][0]
                if not self._showInSec: del self._msg[0]
            else:
                ip = socket.gethostbyname(socket.gethostname())
                if len(ip) < self._col:
                    ip += ' ' *  (self._col - len(ip)) 
                time = ' ' * (self._col - 8) + datetime.now().isoformat()[11:19]
                out = ip + time
                if self._presentMsg:
                    for i in range(len(out)):
                        if i == len(self._presentMsg) or out[i] != self._presentMsg[i]:
                            self.lcd.print( out[i:], col=i , clear=False, backlight=False)
                            break
                else:
                    self.lcd.print( out, backlight=False) 
                self._presentMsg = out
            sleep(1)
