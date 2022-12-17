from pymg import *
import ntptime
from machine import RTC
import yeelight, json


class RotaryPager(RotaryViewPager):

    def __init__(self, parant, window_info, scrollSpeed=0.1, back=2, back_count=100, insert=None, loc="Top"):
        super().__init__(parant, window_info, scrollSpeed, back, back_count, insert, loc)
        for i in range(0, 10):
            self.pbmManager.add_pbm(Pbm('%s.pbm' % i))
        self.pbmManager.add_pbm(Pbm('colon.pbm'))

        self.window_1 = TimeWindow(self, (0, 0, 40, 7))
        self.window_3 = SetBrightness(self, (0, 0, 40, 7))
        self.window_4 = YeelightView(self, (0, 0, 40, 7), scrollSpeed=0.1)
        self.window_2 = NtpWindow(self, (0, 0, 40, 7))
        self.window_5 = WifiWindow(self, (0, 0, 40, 7))
        self.window_1.setPbmManager(self.pbmManager)
        self.window_2.setPbmManager(self.pbmManager)
        self.window_3.setPbmManager(self.pbmManager)
        self.window_4.setPbmManager(self.pbmManager)
        self.window_5.setPbmManager(self.pbmManager)

        self.rotary.setEnable(True)

    def to_set_wifi(self):
        count = abs(self.widgets.index(self.window_5) - self.widgetsChecked)
        print('set_wifi', count)
        if self.widgets.index(self.window_5) < self.widgetsChecked:
            self._back_scroll_count = count
            self._back_scroll_flag = 'right'
        else:
            self._back_scroll_count = count
            self._back_scroll_flag = 'left'


class TimeWindow(Window):

    def __init__(self, parant, window_info, scrollSpeed=1, insert=None, loc="Top", flicker_interval=10, rotary_pin=(21, 22)):
        super().__init__(parant, window_info, insert, loc)
        self.pbmManager = None
        self._scrollSpeed = scrollSpeed
        self.flicker_interval = flicker_interval
        self.rtc = RTC()
        self._time = self._get_time()
        self._last_time = time.ticks_ms()
        self._numberList = []
        self._secCount = 0
        self._setMode = False
        self.isCheckable = True
        self._setCount = 0
        self.rotary = Rotary(rotary_pin[0], rotary_pin[1])
        self.rotary.setEnable(False)
        self.rotary.setRangeMode('MODE_WRAP')
        self.rotary.setValueMin(0)
        self.rotary.setValueMax(23)
        self.value_old = 0

    def setPbmManager(self, pbmManager):
        self.pbmManager = pbmManager
        self._numberList = [NumberGroup(self, (0, 0, 10, 7), self._scrollSpeed, first_digit_upper_limit=2),
                            NumberGroup(self, (15, 0, 10, 7), self._scrollSpeed, first_digit_upper_limit=5),
                            NumberGroup(self, (30, 0, 10, 7), self._scrollSpeed, first_digit_upper_limit=5)]
        for i in range(0, 3):
            self._numberList[i].setPbmManager(pbmManager)
            self._numberList[i].setDigit(2)

    def _get_time(self):
        return list(self.rtc.datetime()[4:7])

    def focus(self, msg):
        if msg == 0:
            self.parant.switch_siganl.emit()
        else:
            self._setMode = True
            self.rotary.setValueMin(0)
            self.rotary.setValueMax(23)
            self.rotary.setValue(self._time[self._setCount])
            self.rotary.setEnable(True)

    def buttonCallback(self, pin, msg):
        if msg == 0:
            print('wisget bt pushed', pin, self)
            if self._setMode:
                print(self._setCount)
                if self._setCount == 2:
                    timeList = list(self.rtc.datetime())
                    timeList[4] = self._numberList[0].getValue()
                    timeList[5] = self._numberList[1].getValue()
                    timeList[6] = self._numberList[2].getValue()
                    self.rtc.datetime(tuple(timeList))
                    self._setCount = 0
                    self._setMode = False
                    self.rotary.setEnable(False)
                    self.parant.switch_siganl.emit()
                else:
                    self._setCount += 1
                    self.rotary.setValueMin(0)
                    self.rotary.setValueMax(59)
                    self.rotary.setValue(self._time[self._setCount])
                    self.rotary.setValue(self._time[self._setCount])
            else:
                self.parant.switch_siganl.emit()
        else:
            print('wisget bt pushed', pin, self)
            self._setCount = 0
            self._setMode = False
            self.rotary.setEnable(False)
            self.parant.switch_siganl.emit()

    def update(self):
        new_time = self._get_time()
        now_time = time.ticks_ms()
        if time.ticks_diff(now_time, self._last_time) > self.flicker_interval:
            if self._secCount < 50:
                self._secCount += 1
            else:
                self._secCount = 0
            self._last_time = now_time
        if not self._setMode:
            if new_time != self._time:
                self._time = new_time
                for num in self._numberList:
                    new_num = new_time[self._numberList.index(num)]
                    if num.getValue() != new_num:
                        num.setValue(str(new_num))
        else:
            value = self.rotary.value()
            if self.value_old != value:
                self._numberList[self._setCount].setValue(str(value))
                self.value_old = value

    def show(self):
        colon = self.pbmManager.get_Pbm('colon.pbm')
        self.buffer.blit(colon.pbmPrint(), 10, 0)
        if self._secCount < 25:
            self.buffer.blit(colon.pbmPrint(), 25, 0)
        if self._setMode:
            if self._secCount > 35:
                self.buffer.fill_rect(self._numberList[self._setCount].x, self._numberList[self._setCount].y,
                                      self._numberList[self._setCount].w, self._numberList[self._setCount].h, 0)
        return (self.buffer, self.x, self.y, self.brackGround)

    def gui_show(self):
        self.buffer.fill(0)
        widgets = self.widgets
        if len(widgets) > 0:
            for widget in widgets:
                if not widget.hidden:
                    res = widget.gui_show()
                    self.buffer.blit(res[0], res[1], res[2], res[3])
        self.show()
        return (self.buffer, self.x, self.y, self.brackGround)


class SetBrightness(Window):

    def __init__(self, parant, window_info, insert=None, loc="Top"):
        super().__init__(parant, window_info, insert, loc)
        self.pbmManager = None
        self.isCheckable = True
        self.rotary = Rotary(21, 22)
        self.rotary.setEnable(False)
        self.rotary.setRangeMode('MODE_BOUNDED')
        self.rotary.setValueMin(5)
        self.rotary.setValueMax(100)
        self.rotary.setValue(50)
        self.value = 50
        self.display = self.getDisplay()
        self.inver_flag = False
        self.numberGroup = NumberGroup(self, (25, 0, 15, 7), 0.6)
        self.dimLable = Lable(self, (0, 0, 25, 7), 0.2)
        self.dimLable.setPbm(Pbm('/lum/dim_label.pbm'))
        self.old_dim = 50

    def setPbmManager(self, pbmManager):
        self.pbmManager = pbmManager
        self.numberGroup.setPbmManager(pbmManager)
        self.numberGroup.setDigit(3)
        self.numberGroup.setValue(str(self.value))

    def focus(self, msg):
        if msg == 0:
            self.dimLable.hidden = True
            self.inver_flag = True
            self.rotary.setEnable(True)
            self.old_dim = self.value
        else:
            self.parant.switch_siganl.emit()

    def buttonCallback(self, pin, msg):
        if msg == 0:
            print('wisget bt pushed', pin, self)
            self.rotary.setEnable(False)
            self.dimLable.hidden = False
            self.inver_flag = False
            self.old_dim = self.value
            self.parant.switch_siganl.emit()
            self.parant.back_home()
        elif msg == 1:
            self.rotary.setValue(self.old_dim)
            self.parant.switch_siganl.emit()

    def valueToLum(self, value):
        return round((value / 100) * 240)

    def update(self):
        value = self.rotary.value()
        if self.value != value:
            self.value = value
            self.numberGroup.setValue(str(self.value))
            self.display.set_display_dimming(self.valueToLum(self.value))

    def gui_show(self):
        self.buffer.fill(0)
        widgets = self.widgets
        if len(widgets) > 0:
            for widget in widgets:
                if not widget.hidden:
                    res = widget.gui_show()
                    self.buffer.blit(res[0], res[1], res[2], res[3])
        if self.inver_flag:
            # framebuf_inversion(self.buffer, 0, 0, round(self.value / 100 * 25), self.h)
            self.buffer.fill_rect(0, 0, round(self.value / 100 * 25), self.h, 1)
        return (self.buffer, self.x, self.y, self.brackGround)


class NtpWindow(Window):

    def __init__(self, parant, window_info, insert=None, loc="Top"):
        super().__init__(parant, window_info, insert, loc)
        self.isCheckable = True
        self.wlan = self.parant.getWlan()
        self.connect_flag = False
        self.ntp_flag = False
        self.lable = Lable(self, (10, 0, 30, 7), 0.15)
        self.wifi_icon = Animation(self, (0, 0, 7, 7), 200)
        self.wifi_icon.dir = '/ntp'
        self.down_count = -1
        self.ntp_res = None
        self.wifi_icon.setRange([0, 3])

    def setPbmManager(self, pbmManager):
        self.pbmManager = pbmManager
        pbmManager.add_pbm(Pbm('/ntp/main.pbm'))
        pbmManager.add_pbm(Pbm('/ntp/ntp.pbm'))
        pbmManager.add_pbm(Pbm('/ntp/error.pbm'))
        pbmManager.add_pbm(Pbm('/ntp/ok.pbm'))
        pbmManager.add_pbm(Pbm('/ntp/wait.pbm'))
        self.wifi_icon.setPbmManager(pbmManager)
        for i in range(0, 4):
            pbmManager.add_pbm(Pbm('/ntp/%s.pbm' % i))
        self.lable.setPbm(self.pbmManager.get_Pbm('/ntp/main.pbm'))

    def focus(self, msg):
        if msg == 1:
            if self.wlan.isconnected():
                self.isCheckable = False
                self.lable.setPbm(self.pbmManager.get_Pbm('/ntp/ntp.pbm'))
                self._ntptime()
            else:
                print('wifi is not connected')
                self.parant.switch_siganl.emit()
                self.parant.to_set_wifi()
        else:
            self.parant.switch_siganl.emit()

    def buttonCallback(self, pin, msg):
        if msg == 0:
            print('wisget bt pushed', pin, self)
            self.parant.switch_siganl.emit()
        else:
            pass

    def _ntptime(self):
        try:
            ntptime.NTP_DELTA = 3155644800
            ntptime.settime()
            self.ntp_res = True
        except:
            print('ntp error')
            self.ntp_res = False
        self.ntp_flag = 2

    def update(self):
        if self.down_count > 0:
            self.down_count -= 1
        elif self.down_count == 0:
            self.down_count = -1
            self.lable.setPbm(self.pbmManager.get_Pbm('/ntp/main.pbm'))
            self.parant.switch_siganl.emit()
            self.parant.back_home()
        if self.ntp_flag == 2:
            self.ntp_flag = 0
            self.isCheckable = True
            self.down_count = 250
            if self.ntp_res:
                self.lable.setPbm(self.pbmManager.get_Pbm('/ntp/ok.pbm'))
            else:
                self.lable.setPbm(self.pbmManager.get_Pbm('/ntp/error.pbm'))

    def gui_show(self):
        self.buffer.fill(0)
        widgets = self.widgets
        if len(widgets) > 0:
            for widget in widgets:
                if not widget.hidden:
                    res = widget.gui_show()
                    self.buffer.blit(res[0], res[1], res[2], res[3])
        return (self.buffer, self.x, self.y, self.brackGround)


class WifiWindow(Window):
    i = 0

    def __init__(self, parant, window_info, insert=None, loc="Top"):
        super().__init__(parant, window_info, insert, loc)
        self.isCheckable = True
        self.wlan = self.parant.getWlan()
        self.connect_flag = False
        self.lable = Lable(self, (0, 0, 25, 7), 0.15)
        self.wifi_button = ScreenButton(self, (25, 0, 15, 7), 30)
        self.wifi_button.dir = '/wifi'
        self.down_count = -1
        self.wifi_button.setRange([0, 6])

    def setPbmManager(self, pbmManager):
        self.pbmManager = pbmManager
        pbmManager.add_pbm(Pbm('/wifi/main.pbm'))
        pbmManager.add_pbm(Pbm('/wifi/error.pbm'))
        pbmManager.add_pbm(Pbm('/wifi/ok.pbm'))
        pbmManager.add_pbm(Pbm('/wifi/wait.pbm'))
        self.wifi_button.setPbmManager(pbmManager)
        for i in range(0, 7):
            pbmManager.add_pbm(Pbm('/wifi/on/%s.pbm' % i))
            pbmManager.add_pbm(Pbm('/wifi/off/%s.pbm' % i))
        self.lable.setPbm(self.pbmManager.get_Pbm('/wifi/main.pbm'))

    def focus(self, msg):
        if msg == 0:
            if not self.wlan.isconnected() and not self.connect_flag:
                self.i = 0
                self.lable.setPbm(self.pbmManager.get_Pbm('/wifi/wait.pbm'))
                self.wifi_button.setState(True)
                self.connect_flag = True
                self.do_connect('Reboot93--2.4G', 'LOVELIVEsaiko93')
            elif self.wlan.isconnected() and self.connect_flag:
                self.wifi_button.setState(False)
                self.dis_connect()
                self.i = 0
            self.parant.switch_siganl.emit()
        else:
            self.parant.switch_siganl.emit()

    def buttonCallback(self, pin, msg):
        if msg == 0:
            print('wisget bt pushed', pin, self)
            self.parant.switch_siganl.emit()
        else:
            pass

    def do_connect(self, ssid, passwd):
        self.connect_flag = True
        print(self.wlan.active())
        self.wlan.active(True)
        self.wlan.connect(ssid, passwd)
        print('connecting to network...')

    def dis_connect(self):
        self.connect_flag = False
        self.wlan.disconnect()

    def update(self):
        if self.wlan.isconnected() and self.i == 0:
            print('network config:', self.wlan.ifconfig())
            self.i += 1
            self.lable.setPbm(self.pbmManager.get_Pbm('/wifi/main.pbm'))
        if not self.i == 0:
            self.wifi_button.setState(self.wlan.isconnected())

    def gui_show(self):
        self.buffer.fill(0)
        widgets = self.widgets
        if len(widgets) > 0:
            for widget in widgets:
                if not widget.hidden:
                    res = widget.gui_show()
                    self.buffer.blit(res[0], res[1], res[2], res[3])
        return (self.buffer, self.x, self.y, self.brackGround)


class YeelightSetBrightness(Window):

    def __init__(self, parant, window_info, insert=None, loc="Top"):
        super().__init__(parant, window_info, insert, loc)
        self.infoSignal = Signal()
        self.infoSignal.connect(self.init)
        self.pbmManager = None
        self.isCheckable = True
        self.rotary = Rotary(21, 22)
        self.rotary.setEnable(False)
        self.rotary.setRangeMode('MODE_BOUNDED')
        self.rotary.setValueMin(1)
        self.rotary.setValueMax(100)
        self.rotary.setValue(50)
        self.value = 50
        self.numberGroup = NumberGroup(self, (25, 0, 15, 7), 0.7)
        self.lable = Lable(self, (0, 0, 25, 7), 0.2)
        self.lable.setPbm(Pbm('/lum/dim_label.pbm'))
        self.old_brightness = 1

    def setPbmManager(self, pbmManager):
        self.pbmManager = pbmManager
        self.numberGroup.setPbmManager(pbmManager)
        self.numberGroup.setDigit(3)
        self.numberGroup.setValue(str(self.value))

    def init(self):
        info = self.parant.blub.get_properties()
        print(info)
        if type(info) == dict:
            self.value = int(info['bright'])
            self.old_brightness = self.value
            self.rotary.setValue(self.value)
            self.numberGroup.setValue(str(self.value))

    def focus(self, msg):
        if msg == 0:
            self.rotary.setEnable(True)
        else:
            self.parant.switch_siganl.emit()

    def buttonCallback(self, pin, msg):
        if msg == 0:
            print('wisget bt pushed', pin, self)
            self.parant.blub.set_brightness(self.value)
            self.rotary.setEnable(False)
            self.parant.switch_siganl.emit()
            self.parant.back_home()
        elif msg == 1:
            self.rotary.setValue(self.old_brightness)
            self.numberGroup.setValue(str(self.old_brightness))
            self.parant.blub.set_brightness(self.old_brightness)
            self.rotary.setEnable(False)
            self.parant.switch_siganl.emit()
            self.parant.back_home()

    def update(self):
        value = self.rotary.value()
        if self.value != value:
            self.value = value
            self.numberGroup.setValue(str(self.value))
            # self.parant.blub.set_brightness(self.value)

    def gui_show(self):
        self.buffer.fill(0)
        widgets = self.widgets
        if len(widgets) > 0:
            for widget in widgets:
                if not widget.hidden:
                    res = widget.gui_show()
                    self.buffer.blit(res[0], res[1], res[2], res[3])
        return (self.buffer, self.x, self.y, self.brackGround)


class YeelightSetColorTemperature(Window):

    def __init__(self, parant, window_info, insert=None, loc="Top"):
        super().__init__(parant, window_info, insert, loc)
        self.infoSignal = Signal()
        self.infoSignal.connect(self.init)
        self.pbmManager = None
        self.isCheckable = True
        self.rotary = Rotary(21, 22)
        self.rotary.setEnable(False)
        self.rotary.setIncr(100)
        self.rotary.setRangeMode('MODE_BOUNDED')
        self.rotary.setValueMin(2700)
        self.rotary.setValueMax(6500)
        self.rotary.setValue(6500)
        self.value = 6500
        self.numberGroup = NumberGroup(self, (20, 0, 20, 7), 0.7)
        self.lable = Lable(self, (0, 0, 20, 7), 0.2)
        self.lable.setPbm(Pbm('/yee/k.pbm'))
        self.old_ct = 6500

    def setPbmManager(self, pbmManager):
        self.pbmManager = pbmManager
        self.numberGroup.setPbmManager(pbmManager)
        self.numberGroup.setDigit(4)
        self.numberGroup.setValue(str(self.value))

    def init(self):
        info = self.parant.blub.get_properties()
        print(info)
        if type(info) == dict:
            self.value = int(info['ct'])
            self.old_ct = self.value
            self.rotary.setValue(self.value)
            self.numberGroup.setValue(str(self.value))

    def focus(self, msg):
        if msg == 0:
            self.rotary.setEnable(True)
        else:
            self.parant.switch_siganl.emit()

    def buttonCallback(self, pin, msg):
        if msg == 0:
            print('wisget bt pushed', pin, self)
            self.parant.blub.change_color_temperature(self.value)
            self.rotary.setEnable(False)
            self.parant.switch_siganl.emit()
            self.parant.back_home()
        elif msg == 1:
            self.rotary.setValue(self.old_ct)
            self.numberGroup.setValue(str(self.old_ct))
            self.parant.blub.change_color_temperature(self.old_ct)
            self.rotary.setEnable(False)
            self.parant.switch_siganl.emit()
            self.parant.back_home()

    def update(self):
        value = self.rotary.value()
        if self.value != value:
            self.value = value
            self.numberGroup.setValue(str(self.value))

    def gui_show(self):
        self.buffer.fill(0)
        widgets = self.widgets
        if len(widgets) > 0:
            for widget in widgets:
                if not widget.hidden:
                    res = widget.gui_show()
                    self.buffer.blit(res[0], res[1], res[2], res[3])
        return (self.buffer, self.x, self.y, self.brackGround)


class YeelightView(RotaryViewPager):

    def __init__(self, parant, window_info, scrollSpeed=0.1, back=2, back_count=100, insert=None, loc="Top"):
        super().__init__(parant, window_info, scrollSpeed, back, back_count, insert, loc)
        self.wlan = self.parant.getWlan()

        self.window_1 = Lable(self, (0, 0, 40, 7), 0.2)
        self.window_2 = YeelightSetBrightness(self, (0, 0, 40, 7))
        self.window_3 = YeelightSetColorTemperature(self, (0, 0, 40, 7))

        self.window_1.setPbm(Pbm('/yee/main.pbm'))

    def focus(self, msg):
        if msg == 0:
            if self.wlan.isconnected():
                self.rotary.setEnable(True)
                self.blub = yeelight.Bulb('192.168.6.246')
                self.setWidget(1)
                self.window_2.infoSignal.emit()
                self.window_3.infoSignal.emit()
            else:
                print(self, 'wlan not connected')
                self.parant.switch_siganl.emit()
                self.parant.to_set_wifi()
        else:
            self.parant.switch_siganl.emit()

    def setPbmManager(self, pbmManager):
        self.pbmManager = pbmManager
        self.window_2.setPbmManager(self.pbmManager)
        self.window_3.setPbmManager(self.pbmManager)

    def buttonCallback(self, pin, msg):
        if msg == 0:
            print('viewpager button', self.widgetsChecked, self.widgets)
            if self.buttonPassthrough:
                print('Passthrough button to', self.widgets[self.widgetsChecked])
                self.widgets[self.widgetsChecked].buttonCallback(pin, msg)
            else:
                if self.widgets[self.widgetsChecked].isCheckable:
                    self.buttonPassthrough = True
                    self.rotary.setEnable(False)
                    self.widgets[self.widgetsChecked].focus(msg)
                else:
                    print('window: %s is not Checkable' % self.widgets[self.widgetsChecked])
        elif msg == 1:
            print('viewpager button long pressed', self.widgetsChecked, self.widgets)
            self.back_home()
            self.buttonPassthrough = False
            self.rotary.setEnable(False)
            self.parant.switch_siganl.emit()
            self.parant.back_home()