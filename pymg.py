from machine import Pin, Timer
import time, framebuf, network
from math import ceil
from rotary_irp_esp import RotaryIRQ


# 帧缓冲局部反转
def framebuf_inversion(original_buf, x, y, w, h):
    if h < 8:
        h = 8
    buf = bytearray((h // 8) * w)
    fbuf = framebuf.FrameBuffer(buf, w, h, framebuf.MONO_VLSB)
    fbuf.blit(original_buf, 0, 0, -1)
    for i in range(0, len(buf)):
        buf[i] = ~buf[i]
    original_buf.blit(fbuf, int(x), int(y), -1)


class Pbm:
    w = None
    h = None
    pbm = None
    filename = None

    def __init__(self, file):
        self.filename = file
        self.loadPBM(file)

    def loadPBM(self, file):
        with open(file, 'rb') as f:
            f.readline()
            self.w = int(f.readline())
            self.h = int(f.readline())
            self.pbm = bytearray(f.read())
            f.close()

    def pbmPrint(self) -> framebuf:
        return framebuf.FrameBuffer(self.pbm, self.w, self.h, framebuf.MONO_HLSB)

    def zoom(self, w, h):
        Image = self.pbmPrint()
        buffer = bytearray((w * h) // 8)
        newImage = framebuf.FrameBuffer(buffer, w, h, framebuf.MONO_HLSB)
        alpha_w = w / self.w
        alpha_h = h / self.h
        for x in range(0, w):
            for y in range(0, h):
                resX = round(x / alpha_w)
                resY = round(y / alpha_h)
                newImage.pixel(x, y, Image.pixel(resX, resY))
        return newImage, w, h


class PbmManager:

    def __init__(self):
        self.pbms = {}

    def get_Pbm(self, filename):
        if filename in self.pbms:
            return self.pbms[filename]
        else:
            print('PBM: %s not load |get' % filename)
            return None

    def add_pbm(self, pbm: Pbm):
        self.pbms[pbm.filename] = pbm

    def del_pbm(self, filename):
        try:
            del self.pbms[filename]
        except:
            print('PBM: %s not load |del' % filename)


class Pymg:

    def __init__(self, display, display_info, refresh_interval=30, fps=False):
        self.display = display
        self.display_info = display_info
        self.refresh_interval = refresh_interval
        self._fps = fps
        self.fps = 0
        self.wlan = network.WLAN(network.STA_IF)
        self.wlan.active(False)
        self.windows = []
        self.showWindows = []
        self.last_show_time = time.ticks_ms()

    '''
    window : 窗口对象
    insert : 插入位置
    loc : 顶部或底部'''

    def widgetAdd(self, window, insert=None, loc='Top'):
        if insert == None:
            if loc == "Top":
                self.windows.append(window)
            else:
                self.windows.insert(0, window)
        else:
            self.windows.insert(insert, window)

    # 移除窗口
    def widgetDel(self, window):
        self.windows.remove(window)

    # 获取传入窗口下标
    def getWidgetIndex(self, window):
        return self.windows.index(window)

    # 获取需要显示的窗口
    def getShowWindows(self):
        self.showWindows.clear()
        for window in self.windows:
            if not window.hidden:
                self.showWindows.append(window)

    def getDisplay(self):
        return self.display

    def getWlan(self):
        return self.wlan

    # 更新窗口
    def window_update(self):
        # if not self.now_show:
        # self.getShowWindows()
        # 遍历 当前显示的窗口， 刷新
        # for window in self.showWindows:
        #    window.gui_update()
        for window in self.windows:
            if not window.hidden:
                window.gui_update()

    def show(self):
        self.display.fill(0)
        for window in self.showWindows:
            res = window.gui_show()
            self.display.blit(res[0], res[1], res[2], res[3])
        if self._fps:
            self.display.fill_rect(0, 0, 24, 8, 0)
            self.display.text(str(self.fps), 0, 0)
        self.display.show()

    def start(self):
        while True:
            self.window_update()
            now_time = time.ticks_ms()
            interval = time.ticks_diff(now_time, self.last_show_time)
            if interval >= self.refresh_interval:
                self.getShowWindows()
                self.last_show_time = now_time
                if self._fps:
                    self.fps = int(1000 / interval)
                self.show()


class Button:

    def __init__(self, pin, single_click_time=130, long_press_time=210, pull=Pin.PULL_UP, trigger=Pin.IRQ_FALLING):
        self.pin = pin
        self.callback = None
        self.isEnable = False
        self._single_click_time = single_click_time
        self._long_press_time = long_press_time
        self._timer_count = 0
        self.button = Pin(pin, Pin.IN, pull)
        self.trigger = trigger
        self._long_press_timer = Timer(0)

    def setEnable(self, flag: bool):
        if flag:
            self.button.irq(handler=self._irq_callback, trigger=self.trigger)
            self.isEnable = True
        else:
            self.button.irq(handler=None)
            self.isEnable = False

    def connect(self, fun):
        self.callback = fun

    def _irq_callback(self, pin):
        self.setEnable(False)
        self.click_flag = False
        self.long_press_flag = False
        self._long_press_timer.init(period=2, callback=self._timer_irp_callback)

    def _timer_irp_callback(self, msg):
        if self.button.value() != 0 or self._timer_count > self._long_press_time + 10:
            print(self._timer_count)
            if 5 < self._timer_count < self._single_click_time:
                self._long_press_timer.deinit()
                print('Button %s clicked' % str(self.pin))
                self.callback(self.pin, 0)
            elif self._timer_count > self._long_press_time:
                self._long_press_timer.deinit()
                print('Button %s long pressed' % str(self.pin))
                self.callback(self.pin, 1)
            else:
                self._long_press_timer.deinit()
            self._timer_count = 0
            self.setEnable(True)
        else:
            self._timer_count += 1


class Signal:

    def __init__(self, msg=None):
        self._signal_msg = msg
        self._callback = None

    def connect(self, fun):
        self._callback = fun

    def emit(self, msg):
        self._callback(msg)

    def emit(self):
        self._callback()


class Widget:

    def __init__(self, parant, window_info, insert=None, loc="Top", brackGround=-1):
        self.x, self.y, self.w, self.h = window_info
        self.parant = parant
        self.parant.widgetAdd(self, insert, loc)
        self.hidden = False
        self.isCheckable = False
        self.brackGround = brackGround
        self.buffer = framebuf.FrameBuffer(bytearray((self.h * self.w) // 8), self.w, self.h, framebuf.MONO_HMSB)

    # 接受 更新信号 并处理
    def gui_update(self):
        pass

    def focus(self, msg):
        pass

    def getWlan(self):
        return self.parant.wlan

    def getDisplay(self):
        return self.parant.getDisplay()

    def buttonCallback(self, pin, msg):
        if msg == 0:
            print('%s : button callback not set | Pin call : %s' % self, pin)
        elif msg == 1:
            print('%s : button long press not set | Pin call : %s' % self, pin)

    # 接受 画面渲染信号 并处理
    def gui_show(self) -> (framebuf, int, int, int):
        return (self.buffer, self.x, self.y, self.brackGround)


class Window(Widget):

    def __init__(self, parant, window_info, insert=None, loc="Top", brackGround=-1):
        super().__init__(parant, window_info, insert, loc, brackGround)
        self.widgets = []

    def widgetAdd(self, window, insert=None, loc='Top'):
        if insert == None:
            if loc == "Top":
                self.widgets.append(window)
            else:
                self.widgets.insert(0, window)
        else:
            self.widgets.insert(insert, window)

    # 移除窗口
    def widgetDel(self, window):
        self.widgets.remove(window)

    # 获取传入窗口下标
    def getWidgetIndex(self, window):
        return self.widgets.index(window)

    # 接受 更新信号 并处理
    def gui_update(self):
        # 更新自身及子窗口状态
        self.update()
        widgets = self.widgets
        if len(widgets) > 0:
            for widget in widgets:
                if not widget.hidden:
                    widget.gui_update()

    def buttonCallback(self, pin, msg):
        if msg == 0:
            print('%s : button callback not set | Pin call : %s' % self, pin)
        elif msg == 1:
            print('%s : button long press not set | Pin call : %s' % self, pin)

    # 更新自身窗口状态
    def update(self):
        pass
        # 需要重构

    # 接受 画面渲染信号 并处理
    def gui_show(self):
        self.buffer.fill(0)
        self.show()
        widgets = self.widgets
        if len(widgets) > 0:
            for widget in widgets:
                if not widget.hidden:
                    res = widget.gui_show()
                    self.buffer.blit(res[0], res[1], res[2], res[3])
        return (self.buffer, self.x, self.y, self.brackGround)

    def show(self):
        pass


class Rotary:
    MODE_UNBOUNDED = RotaryIRQ.RANGE_UNBOUNDED
    MODE_BOUNDED = RotaryIRQ.RANGE_BOUNDED
    MODE_WRAP = RotaryIRQ.RANGE_WRAP

    def __init__(self, clk, dt, mode=MODE_UNBOUNDED, min=0):
        self.dt = dt
        self.clk = clk
        self.min = min
        self.mode = mode
        self.rotary = RotaryIRQ(pin_num_clk=self.clk,
                                pin_num_dt=self.dt,
                                min_val=self.min,
                                reverse=False,
                                half_step=True,
                                range_mode=self.mode)
        self.setEnable(False)
        self.callback = None

    def init(self):
        self.rotary = RotaryIRQ(pin_num_clk=self.clk,
                                pin_num_dt=self.dt,
                                min_val=self.min,
                                reverse=False,
                                half_step=True,
                                range_mode=self.mode)

    def setEnable(self, flag: bool):
        if flag:
            self.rotary.enable()
        else:
            self.rotary.close()

    def setIncr(self, count: int):
        self.rotary.setIncr(count)

    def setListener(self, fun):
        self.rotary.add_listener(fun)

    def delListener(self, fun):
        self.rotary.remove_listener(fun)

    def setValue(self, value: int):
        self.rotary.setValue(value)

    def setValueMax(self, value: int):
        self.rotary.setValueMax(value)

    def setValueMin(self, value: int):
        self.rotary.setValueMin(value)

    def setRangeMode(self, mode):
        if mode == 'MODE_UNBOUNDED':
            self.rotary.setRangeMode(self.MODE_UNBOUNDED)
        elif mode == 'MODE_BOUNDED':
            self.rotary.setRangeMode(self.MODE_BOUNDED)
        elif mode == 'MODE_WRAP':
            self.rotary.setRangeMode(self.MODE_WRAP)
        else:
            print('mode error')
            raise Exception

    def value(self):
        return self.rotary.value()


class ViewPager(Window):

    def __init__(self, parant, window_info, scrollSpeed=0.1, back=2, back_count=100, insert=None, loc="Top",
                 brackGround=-1, refresh_interval=5):
        super().__init__(parant, window_info, insert, loc, brackGround)
        self.widgetsChecked = 0
        self.switch_siganl = Signal()
        self.scrollCount = 0
        self.gap = 2
        self.scrollSpeed = scrollSpeed
        self.back = back
        self.back_count = back_count
        self.scroll_flag = None  # left right back_left back_right
        self.checkable = True
        self.isCheckable = True
        self.buttonPassthrough = False
        self._back_scroll_count = 0
        self._back_scroll_flag = None
        self._last_time = time.ticks_ms()
        self.refresh_interval = refresh_interval

        self.switch_siganl.connect(self.switch_widget)

    def switch_widget(self):
        self.buttonPassthrough = False

    def back_home(self):
        left = len(self.widgets[self.widgetsChecked:])
        right = self.widgetsChecked
        if left > right:
            self._back_scroll_count = right
            self._back_scroll_flag = 'right'
        else:
            self._back_scroll_count = left
            self._back_scroll_flag = 'left'

    def setWidget(self, flag: int):
        count = flag - self.widgetsChecked
        print('set widget', count)
        if count < 0:
            self._back_scroll_count = count
            self._back_scroll_flag = 'right'
        else:
            self._back_scroll_count = count
            self._back_scroll_flag = 'left'

    def buttonCallback(self, pin, msg):
        if msg == 0:
            print('viewpager button clicked', self.widgetsChecked, self.widgets)
        elif msg == 1:
            print('viewpager button long pressed', self.widgetsChecked, self.widgets)
        if self.buttonPassthrough:
            print('Passthrough button to', self.widgets[self.widgetsChecked])
            self.widgets[self.widgetsChecked].buttonCallback(pin, msg)
        else:
            if self.widgets[self.widgetsChecked].isCheckable:
                self.buttonPassthrough = True
                self.widgets[self.widgetsChecked].focus(msg)
            else:
                print('window: %s is not Checkable' % self.widgets[self.widgetsChecked])

    def gui_update(self):
        now_time = time.ticks_ms()
        if time.ticks_diff(now_time, self._last_time) > self.refresh_interval:
            self.update()
            self._last_time = now_time
        widgets = self.widgets
        if self.scroll_flag != None:
            widgets = [widgets[(self.widgetsChecked - 1) % len(widgets)],
                       widgets[self.widgetsChecked],
                       widgets[(self.widgetsChecked + 1) % len(widgets)]]
            for widget in widgets:
                widget.gui_update()
        else:
            widget = widgets[self.widgetsChecked]
            widget.gui_update()

    def update(self):
        self._scroll()

    def _scroll(self):
        pass

    def _get_show_list(self):
        pass

    def gui_show(self):
        self.buffer.fill(0)
        widgets = self.widgets
        count = -self.w
        if self.scroll_flag != None:
            widgets = [widgets[(self.widgetsChecked - 1) % len(widgets)],
                       widgets[self.widgetsChecked],
                       widgets[(self.widgetsChecked + 1) % len(widgets)]]
            for widget in widgets:
                if not widget.hidden:
                    res = widget.gui_show()
                    self.buffer.blit(res[0], ceil(count + self.scrollCount), 0, res[3])
                    count += self.w
        else:
            widget = widgets[self.widgetsChecked]
            res = widget.gui_show()
            self.buffer.blit(res[0], 0, 0, res[3])
        return (self.buffer, self.x, self.y, self.brackGround)


class Lable(Widget):

    def __init__(self, parant, widget_info, scrollSpeed=1, insert=None, loc="Top", brackGround=-1, refresh_interval=10):
        super().__init__(parant, widget_info, insert, loc, brackGround)
        self.scroll_count = 0
        self.scroll_flag = False
        self.refresh_interval = refresh_interval
        self.last_time = time.ticks_ms()
        self.pbm = None
        self.scrollSpeed = scrollSpeed

    def gui_update(self):
        now_time = time.ticks_ms()
        if time.ticks_diff(now_time, self.last_time) >= self.refresh_interval:
            if self.scroll_flag:
                if self.scroll_count > 0:
                    self.scroll_count -= self.scrollSpeed
                else:
                    self.scroll_count = self.pbm.w
            self.last_time = now_time

    def setPbm(self, pbm: Pbm):
        self.pbm = pbm
        if self.pbm.w > self.w:
            self.scroll_flag = True
            self.scroll_count = self.pbm.w
        else:
            self.buffer.fill(0)
            self.scroll_flag = False
            self.scroll_count = 0
            self.buffer.blit(self.pbm.pbmPrint(), round((self.w - self.pbm.w) / 2), 0, self.brackGround)

    def gui_show(self) -> (framebuf, int, int, int):
        if self.scroll_flag:
            self.buffer.fill(0)
            if self.scroll_count != 0:
                self.buffer.blit(self.pbm.pbmPrint(), round(-self.pbm.w + self.scroll_count), 0, self.brackGround)
                self.buffer.blit(self.pbm.pbmPrint(), round(self.scroll_count), 0, self.brackGround)
            else:
                self.buffer.blit(self.pbm.pbmPrint(), 0, 0, self.brackGround)

        return (self.buffer, self.x, self.y, self.brackGround)


class Animation(Widget):

    def __init__(self, parant, widget_info, duration=30, insert=None, loc="Top", brackGround=-1):
        super().__init__(parant, widget_info, insert, loc, brackGround)
        self._pbmManager = None
        self._duration = duration
        self.dir = ''
        self._last_time = time.ticks_ms()
        self._pbmListRange = [0, 0]
        self._pbmCount = 0

    def setPbmManager(self, pbmManager):
        self._pbmManager = pbmManager

    def setRange(self, msg: list):
        self._pbmListRange = msg

    def gui_update(self):
        now_time = time.ticks_ms()
        if time.ticks_diff(now_time, self._last_time) > self._duration:
            self.buffer.fill(0)
            self._last_time = now_time
            if self._pbmCount == self._pbmListRange[1]:
                self._pbmCount = 0
            else:
                self._pbmCount += 1
            self.buffer.blit(self._pbmManager.get_Pbm('%s/%s.pbm' % (self.dir, str(self._pbmCount))).pbmPrint(),
                             0,
                             0,
                             self.brackGround)
        else:
            pass

    def gui_show(self) -> (framebuf, int, int, int):
        return (self.buffer, self.x, self.y, self.brackGround)


class ScreenButton(Animation):

    def __init__(self, parant, widget_info, duration=30, insert=None, loc="Top", brackGround=-1):
        super().__init__(parant, widget_info, insert, loc, brackGround)
        self._pbmManager = None
        self._duration = duration
        self.dir = ''
        self.state_dir = '/off'
        self._last_time = time.ticks_ms()
        self._pbmListRange = [0, 0]
        self._pbmCount = 0
        self.state = False
        self.play_flag = False

    def setPbmManager(self, pbmManager):
        self._pbmManager = pbmManager

    def setRange(self, msg: list):
        self._pbmListRange = msg

    def setState(self, flag: bool):
        if flag != self.state:
            self.state = flag
            self._change()

    def _change(self):
        self.play_flag = True
        self._pbmCount = 0
        if self.state:
            self.state_dir = '/on'
        else:
            self.state_dir = '/off'

    def gui_update(self):
        if self.play_flag:
            now_time = time.ticks_ms()
            if time.ticks_diff(now_time, self._last_time) > self._duration:
                self.buffer.fill(0)
                self._last_time = now_time
                if self._pbmCount == self._pbmListRange[1]:
                    self.play_flag = False
                else:
                    self._pbmCount += 1
                self.buffer.blit(self._pbmManager.get_Pbm(
                    '%s%s/%s.pbm' % (self.dir, self.state_dir, str(self._pbmCount))).pbmPrint(),
                                 0,
                                 0,
                                 self.brackGround)
            else:
                pass
        else:
            self.buffer.blit(
                self._pbmManager.get_Pbm(
                    '%s%s/%s.pbm' % (self.dir, self.state_dir, str(self._pbmListRange[1]))).pbmPrint(),
                0,
                0,
                self.brackGround)

    def gui_show(self) -> (framebuf, int, int, int):
        return (self.buffer, self.x, self.y, self.brackGround)


class Number(Widget):

    def __init__(self, parant, widget_info, pbmManager, scrollSpeed=1, numberList=False, insert=None, loc="Top",
                 brackGround=-1, refresh_interval=16):
        super().__init__(parant, widget_info, insert, loc, brackGround)
        self.value = 0
        self.value_old = None
        self.scroll_flag = False
        self.scroll_count = 0
        self.refresh_interval = refresh_interval
        self.last_time = time.ticks_ms()
        self.pbmManager = None
        self.switchDirection = 0
        self.pbmManager = pbmManager
        self.numberList = numberList
        self.list = []
        self.scrollSpeed = scrollSpeed
        self.scroll_list_flag = False

    def setValue(self, value) -> int:
        if value != self.value or self.scroll_list_flag:
            if not self.scroll_flag and not self.scroll_list_flag:
                self._scroll(value)
                return 1
            else:
                if self.numberList:
                    if len(self.list) > 5:
                        self.list = self.list[-5:]
                    if len(self.list) > 0:
                        if value != self.list[-1]:
                            self.list.append(value)
                    else:
                        self.scroll_list_flag = True
                        self.list.append(value)
                    print('now scrolling, add %s in list' % value)
                    return 1
                else:
                    print('now scrolling', str(self.value))
                    return 0

    def _scroll(self, value):
        self.scroll_flag = True
        if self.value == 9 and value == 0:
            self.switchDirection = 0
        elif value < self.value:
            self.switchDirection = 1
        elif value == 9 and self.value == 0:
            self.switchDirection = 1
        else:
            self.switchDirection = 0
        if self.switchDirection == 0 or self.switchDirection == 1:
            self.scroll_count = self.h + 1
        else:
            self.scroll_count = self.w + 1
        self.value_old = self.value
        self.value = value

    def getValue(self) -> int:
        return self.value

    def gui_update(self):
        now_time = time.ticks_ms()
        if time.ticks_diff(now_time, self.last_time) > self.refresh_interval:
            if self.scroll_flag:
                if self.scroll_count > 0:
                    if len(self.list) > 0:
                        scrollSpeed = self.scrollSpeed * len(self.list) * 2
                        if scrollSpeed > self.h:
                            scrollSpeed = self.h
                    else:
                        scrollSpeed = self.scrollSpeed
                    self.scroll_count -= scrollSpeed
                    if self.scroll_count - 0 < scrollSpeed:
                        self.scroll_count = 0
                else:
                    self.scroll_flag = False
                    if self.scroll_list_flag:
                        if len(self.list) == 0:
                            self.scroll_list_flag = False
            else:
                if len(self.list) > 0:
                    self._scroll(self.list.pop(0))
            self.last_time = now_time

    def gui_show(self) -> (framebuf, int, int, int):
        self.buffer.fill(0)
        if self.scroll_flag:
            if self.switchDirection == 0:  # down
                self.buffer.blit(self.pbmManager.get_Pbm('%s.pbm' % self.value).pbmPrint(),
                                 0,
                                 round(0 - self.scroll_count),
                                 self.brackGround)
                self.buffer.blit(self.pbmManager.get_Pbm('%s.pbm' % self.value_old).pbmPrint(),
                                 0,
                                 round(0 - self.scroll_count + self.h + 1),
                                 self.brackGround)
            elif self.switchDirection == 1:  # up
                self.buffer.blit(self.pbmManager.get_Pbm('%s.pbm' % self.value).pbmPrint(),
                                 0,
                                 round(self.scroll_count),
                                 self.brackGround)
                self.buffer.blit(self.pbmManager.get_Pbm('%s.pbm' % self.value_old).pbmPrint(),
                                 0,
                                 round(-self.h + self.scroll_count - 1),
                                 self.brackGround)
        else:
            self.buffer.blit(self.pbmManager.get_Pbm('%s.pbm' % self.value).pbmPrint(),
                             0,
                             0,
                             self.brackGround)
        return (self.buffer, self.x, self.y, self.brackGround)


class NumberGroup(Window):

    def __init__(self, parant, window_info, scrollSpeed=1, insert=None, loc="Top", brackGround=-1):
        super().__init__(parant, window_info, insert, loc, brackGround)
        self.show_X = 0
        self.pbmManager = None
        self.scrollSpeed = scrollSpeed
        self.value = '0'
        self.digit = 1
        self.numberList = []

    def init(self):
        self.numberList = []
        for i in range(0, self.digit):
            self._add_num()
        self._update_show_X()

    def setPbmManager(self, pbmManager):
        self.pbmManager = pbmManager

    def setDigit(self, digit: int):
        self.digit = digit
        self.init()

    def getValue(self):
        return int(self.value)

    def _update_show_X(self):
        x = self.show_X
        for num in self.numberList:
            num.x = x
            x += 5
        for i in self.numberList:
            print(self.parant, i, i.x)

    def setValue(self, value: str):
        if self.value != value:
            count_new = len(value)
            count_old = len(self.value)
            self.value = value
            # 匹配位数
            if count_new < self.digit:
                for num in range(0, self.digit - count_new):
                    self.numberList[num].setValue(0)
            for num in value:
                self.numberList[-count_new].setValue(int(num))
                count_new -= 1

    def _del_num(self):
        del self.numberList[0]

    def _add_num(self):
        self.numberList.insert(0, Number(self, (0, 0, 5, 7), self.pbmManager, self.scrollSpeed, True))


class RotaryViewPager(ViewPager):

    def __init__(self, parant, window_info, scrollSpeed=0.1, back=2, back_count=100, insert=None, loc="Top",
                 brackGround=-1, refresh_interval=5):
        super().__init__(parant, window_info, scrollSpeed, back, back_count, insert, loc, brackGround, refresh_interval)
        self.rotary = Rotary(18, 19)
        print(self, self.rotary)
        self.rotary_value_old = 0
        self.rotary_value_count = 0
        self.pbmManager = PbmManager()

    def switch_widget(self):
        self.buttonPassthrough = False
        self.rotary.setEnable(True)

    def buttonCallback(self, pin, msg):
        if msg == 0:
            print('viewpager button', self.widgetsChecked, self.widgets)
        elif msg == 1:
            print('viewpager button long pressed', self.widgetsChecked, self.widgets)
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

    def update(self):
        rotary_value = self.rotary.value()
        rotary_value_old = self.rotary_value_old
        if self._back_scroll_count == 0:
            if self.scroll_flag == None and rotary_value != 0:
                self.scroll_flag = 'mv'
            if self.scroll_flag == 'mv':
                if rotary_value < self.back and rotary_value > -self.back:
                    self.scrollCount = rotary_value * 2
                    if rotary_value == rotary_value_old:
                        self.rotary_value_count += 1
                    elif rotary_value < rotary_value_old:
                        self.rotary_value_count -= 1
                    self.rotary_value_old = rotary_value
                    if self.rotary_value_count > self.back_count:
                        self.checkable = False
                        self.rotary_value_count = 0
                        if rotary_value > 0:
                            self.scroll_flag = 'back_left'
                        else:
                            self.scroll_flag = 'back_right'
                else:
                    if rotary_value > 0:
                        self.scroll_flag = 'right'
                    else:
                        self.scroll_flag = 'left'
            else:
                self._scroll()
        else:
            self.scroll_flag = self._back_scroll_flag
            self._scroll()

    def _scroll(self):
        if self.scroll_flag == 'right':
            self.checkable = False
            if self.scrollCount < self.w:
                count = (self.w - self.scrollCount) * self.scrollSpeed
                if count < 0.7:
                    count = 0.7
                if self.scrollCount + count >= self.w:
                    self.scrollCount = self.w
                else:
                    self.scrollCount += count
            else:
                self.scrollCount = 0
                self.rotary_value_count = 0
                self.scroll_flag = None
                self.widgetsChecked = (self.widgetsChecked - 1) % len(self.widgets)
                if self._back_scroll_count > 0:
                    self._back_scroll_count -= 1
                else:
                    self.checkable = True
                    self.rotary.setValue(0)
        elif self.scroll_flag == 'left':
            self.checkable = False
            if self.scrollCount > -self.w:
                count = abs(self.w + self.scrollCount) * self.scrollSpeed
                if count < 0.7:
                    count = 0.7
                if self.scrollCount - count <= -self.w:
                    self.scrollCount = -self.w
                else:
                    self.scrollCount -= count
            else:
                self.scrollCount = 0
                self.rotary_value_count = 0
                self.scroll_flag = None
                self.widgetsChecked = (self.widgetsChecked + 1) % len(self.widgets)
                if self._back_scroll_count > 0:
                    self._back_scroll_count -= 1
                else:
                    self.checkable = True
                    self.rotary.setValue(0)
        elif self.scroll_flag == 'back_right':
            self.checkable = False
            if self.scrollCount < 0:
                self.scrollCount += ceil((-self.scrollCount + 1) * self.scrollSpeed)
            else:
                self.scrollCount = 0
                self.rotary_value_count = 0
                self.scroll_flag = None
                self.checkable = True
                self.rotary.setValue(0)
        elif self.scroll_flag == 'back_left':
            self.checkable = False
            if self.scrollCount > 0:
                self.scrollCount -= ceil(self.scrollCount * self.scrollSpeed)
            else:
                self.scrollCount = 0
                self.rotary_value_count = 0
                self.scroll_flag = None
                self.checkable = True
                self.rotary.setValue(0)