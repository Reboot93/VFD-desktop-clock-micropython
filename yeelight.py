'''
This library is from https://github.com/GianniDPC/Yeelight-micropython
Reboot93 adds some methods according to the yeelight API document
https://github.com/Reboot93/Yeelight-micropython
'''


import usocket as socket
import json


class YeeLightException(Exception):
    pass


class EFFECT:
    SMOOTH = "smooth"
    SUDDEN = "sudden"


class MODE:
    NORMAL = 0
    CT_MODE = 1
    RGB_MODE = 2
    HSV_MODE = 3
    COLOR_FLOW_MODE = 4
    NIGHT_LIGHT_MODE = 5


class ACTION:
    LED_RECOVER_STATE = 0
    LED_STAY = 1
    LED_TURN_OFF = 2


class SCENE_CLASS:
    COLOR = "color"
    HSV = "hsv"
    CT = "ct"
    AUTO_DELAY_OFF = "auto_delay_off"


class SET_ADJUST_ACTION:
    INCREASE = "increase"
    DECREASE = "decrease"
    CIRCLE = "circle"


class SET_ADJUST_PROP:
    BRIGHT = "bright"
    CT = "ct"
    COLOR = "color"


""" API DOCS: https://www.yeelight.com/download/Yeelight_Inter-Operation_Spec.pdf """


class Bulb():
    def __init__(self, ip, port=55443, debug=False):
        self.cmd_id = 0
        self._ip = ip
        self._port = port
        self.debug = debug

    @property
    def get_ip(self):
        return self._ip

    @property
    def get_port(self):
        return self._port

    def turn_on(self, effect=EFFECT.SUDDEN, duration=30, mode=MODE.NORMAL):
        return self._handle_response(self._send_message("set_power",
                                                        ["on", effect, duration, mode]))

    def turn_off(self, effect=EFFECT.SUDDEN, duration=30, mode=MODE.NORMAL):
        return self._handle_response(self._send_message("set_power",
                                                        ["off", effect, duration, mode]))

    def toggle(self):
        return self._handle_response(self._send_message("toggle"))

    @property
    def is_on(self):
        result = self._handle_response(self._send_message("get_prop", ["power"]))
        return result[0] == "on"

    def change_color_temperature(self, color_temp_val, effect=EFFECT.SUDDEN, duration=30):
        """
        :param color_temp_val: between 1700 and 6500K
        """
        return self._handle_response(self._send_message("set_ct_abx",
                                                        [color_temp_val, effect, duration]))

    def set_rgb(self, r, g, b, effect=EFFECT.SUDDEN, duration=30):
        """
        :param r: red
        :param g: green
        :param b: blue
        """
        rgb = (r * 65536) + (g * 256) + b
        return self._handle_response(self._send_message("set_rgb",
                                                        [rgb, effect, duration]))
    
    def bg_set_rgb(self, r, g, b, effect=EFFECT.SUDDEN, duration=30):
        rgb = (r * 65536) + (g * 256) + b
        return self._handle_response(self._send_message("bg_set_rgb",
                                                        [rgb, effect, duration]))

    def set_hsv(self, hue, sat, effect=EFFECT.SUDDEN, duration=30):
        """
        :param hue: ranges from 0 to 359
        :param sat:  ranges from 0 to 100
        """
        return self._handle_response(self._send_message("set_hsv",
                                                        [hue, sat, effect, duration]))

    def set_brightness(self, brightness, effect=EFFECT.SUDDEN, duration=30):
        """
        :param brightness: between 1 and 100
        """
        return self._handle_response(self._send_message("set_bright",
                                                        [brightness, effect, duration]))

    def save_current_state(self):
        return self._handle_response(self._send_message("set_default"))

    def start_color_flow(self, count, flow_expression, action=ACTION.LED_RECOVER_STATE):
        """
        :param count: is the total number of visible state changing before color flow
                         stopped. 0 means infinite loop on the state changing.
        :param flow_expression: is the expression of the state changing series (see API docs)
        :param action: is the action taken after the flow is stopped.
                          0 means smart LED recover to the state before the color flow started.
                          1 means smart LED stay at the state when the flow is stopped.
                          2 means turn off the smart LED after the flow is stopped.
        """
        return self._handle_response(self._send_message("start_cf",
                                                        [count, action, flow_expression]))

    def stop_color_flow(self):
        return self._handle_response(self._send_message("stop_cf"))

    def set_scene(self, val1, val2, val3, opt=SCENE_CLASS.COLOR):
        """
        :param val1: :param val2: :param val3: are class specific. (see API docs)
        :param opt: can be "color", "hsv", "ct", "cf", "auto_delay_off".
                      "color" means change the smart LED to specified color and brightness.
                      "hsv" means change the smart LED to specified color and brightness.
                      "ct" means change the smart LED to specified ct and brightness.
                      "cf" means start a color flow in specified fashion.
                      "auto_delay_off" means turn on the smart LED to specified
                      brightness and start a sleep timer to turn off the light after the specified minutes.
        """
        return self._handle_response(self._send_message("set_scene",
                                                        [opt, val1, val2, val3]))

    def sleep_timer(self, time_minutes, type=0):
        return self._handle_response(self._send_message("cron_add",
                                                        [type, time_minutes]))

    def get_background_job(self, type=0):
        return self._handle_response(self._send_message("cron_get",
                                                        [type]))

    def get_properties(self, requested_properties=['power',
                                                   'bright',
                                                   'ct',
                                                   'rgb',
                                                   'hue',
                                                   'sat',
                                                   'color_mode',
                                                   'flowing',
                                                   'delayoff',
                                                   'music_on',
                                                   'name',
                                                   'bg_power',
                                                   'bg_flowing',
                                                   'bg_ct',
                                                   'bg_bright',
                                                   'bg_hue',
                                                   'bg_sat',
                                                   'bg_rgb',
                                                   'nl_br',
                                                   'active_mode']):
        try:
            res = self._handle_response(self._send_message("get_prop", requested_properties))
            count = 0
            properties = {}
            for i in res:
                properties[requested_properties[count]] = i
                count += 1
            return properties
        except:
            return -1
        
        return res

    def delete_background_job(self, type=0):
        return self._handle_response(self._send_message("cron_del",
                                                        [type]))

    def set_adjust(self, action=SET_ADJUST_ACTION.INCREASE, prop=SET_ADJUST_PROP.BRIGHT):
        """
        :param action: the direction of the adjustment. The valid value can be:
                         "increase": increase the specified property
                         "decrease": decrease the specified property
                         "circle": increase the specified property, after it reaches the max
                         value, go back to minimum value.
        :param prop: the property to adjust. The valid value can be:
                        "bright": adjust brightness.
                        "ct": adjust color temperature.
                        "color": adjust color. (When “prop" is “color", the “action" can only
                        be “circle", otherwise, it will be deemed as invalid request.)
        """
        return self._handle_response(self._send_message("set_adjust",
                                                        [action, prop]))

    def adjust_brightness(self, percentage, duration=30):
        """
        :param percentage: the percentage to be adjusted. The range is: -100 ~ 100
        """
        return self._handle_response(self._send_message("adjust_bright",
                                                        [percentage, duration]))

    def adjust_color_temperature(self, percentage, duration=30):
        """
        :param percentage: the percentage to be adjusted. The range is: -100 ~ 100
        """
        return self._handle_response(self._send_message("adjust_ct",
                                                        [percentage, duration]))

    def adjust_color(self, percentage, duration=30):
        """
         :param percentage: the percentage to be adjusted. The range is: -100 ~ 100
         """
        return self._handle_response(self._send_message("adjust_color",
                                                        [percentage, duration]))

    def set_music(self, enable=True):
        """
        :param host: the IP address of the music server.
        :param port: the TCP port music application is listening on.
        :param enable:  0: turn off music mode.
                           1: turn on music mode.
        """
        return self._handle_response(self._send_message("set_music",
                                                        [1 if enable else 0]))

    def set_name(self, name):
        """
        :param name: the name of the device
        """
        return self._handle_response(self._send_message("set_name",
                                                        [name]))

    def _send_message(self, method, params=None):
        if params is None:
            params = []

        self.cmd_id += 1

        message = '{{"id": {id}, "method": "{method}", "params": {params}}}\r\n'. \
            format(id=self.cmd_id, method=method, params=json.dumps(params))

        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        try:
            sock.connect((self.get_ip, self.get_port))
            sock.send(message.encode())
            recv_data = sock.recv(1024)
        except socket.timeout:
            return ""
        finally:
            sock.close()

        return recv_data

    def _handle_response(self, response):
        response = json.loads(response.decode('utf-8'))

        if self.debug:
            print(response)

        if "params" in response:
            return response["params"]
        elif "id" in response and not "error" in response:
            return response["result"]
        elif "error" in response:
            raise YeeLightException(response["error"])
        else:
            raise YeeLightException("Unknown Exception occurred.")
