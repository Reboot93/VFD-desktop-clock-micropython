import framebuf, futaba_8md06inkm
from machine import Pin, freq, SPI
from pymg import *
from pymg_example import *
import time

freq(240000000)

hspi = SPI(1, 5000000)
en = Pin(4)  # data/command
rst = Pin(5)  # reset
cs = Pin(26)  # chip select, some modules do not have a pin for this
display = futaba_8md06inkm.VFD(hspi, rst, cs, en)
display.set_display_dimming(127)


class MainWindow(Pymg):

    def __init__(self, display, display_info, bt):
        super().__init__(display, display_info)
        self.button = Button(25)

        self.testWindow = RotaryPager(self, (0, 0, 40, 7), scrollSpeed=0.1)
        self.button.connect(self.testWindow.buttonCallback)
        self.button.setEnable(True)


mainWindow = MainWindow(display, (40, 7), 25)

while True:
    try:
        mainWindow.start()
    except:
        print('pymg error')
        time.sleep(1)
