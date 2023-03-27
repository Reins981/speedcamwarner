__version__ = '0.1'
# qpy:kivy
# -*-coding:utf8;-*-
# qpy:2
# ts=4:sw=4:expandtab
import os
from kivy.app import App
from kivy_garden.mapview import MapView
from kivy.uix.popup import Popup
from kivy.properties import ObjectProperty
from kivy.uix.button import Button
from kivy.graphics import Color, Rectangle, Line
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.relativelayout import RelativeLayout
from kivy.uix.image import Image
from kivy.uix.label import Label
from kivy.uix.screenmanager import ScreenManager, Screen, WipeTransition
from kivy.uix.modalview import ModalView
from kivy.uix.gridlayout import GridLayout
from kivy.clock import Clock, mainthread, _default_time as time
from oscpy.server import OSCThreadServer
from oscpy.client import OSCClient
import time, sys
from threading import Condition
from GPSThreads import GPSConsumerThread, GPSThread
from AccusticWarnerThread import VoicePromptThread
from CalculatorThreads import RectangleCalculatorThread
from DeviationCheckerThread import DeviationCheckerThread
from SpeedCamWarnerThread import SpeedCamWarnerThread
from OverspeedThread import OverspeedCheckerThread
from SQL import POIReader
from ThreadBase import ThreadCondition, InterruptQueue, VectorDataPoolQueue, \
    GPSQueue, VoicePromptQueue, AverageAngleQueue, MapQueue, SpeedCamQueue, \
    OverspeedQueue, CurrentSpeedQueue, BorderQueue, BorderQueueReverse, PoiQueue, GpsDataQueue
from OSMWrapper import maps, OSMThread
from Logger import Logger
from kivy.uix.checkbox import CheckBox
from kivy.utils import platform
from plyer import gps
from functools import partial

URL = os.path.join(os.path.abspath(os.path.dirname(__file__)), "assets", "leaf.html")

if platform == "android":
    from android.permissions import request_permissions, Permission

    request_permissions([Permission.ACCESS_COARSE_LOCATION,
                         Permission.ACCESS_FINE_LOCATION,
                         Permission.ACCESS_BACKGROUND_LOCATION,
                         Permission.WRITE_EXTERNAL_STORAGE,
                         Permission.READ_EXTERNAL_STORAGE,
                         Permission.WAKE_LOCK])

logger = Logger("Main")

activityport = 3001
serviceport = 3000
secondApp = None


def some_api_callback(message, *args):
    logger.print_log_line(" Got a message! %s" % message)


class OSM_INIT(Logger):
    def __init__(self, *args, **kwargs):
        super().__init__(self.__class__.__name__)
        self.gps_thread = args[0]
        self.calculator_thread = args[1]
        self.osm_wrapper = args[2]
        self.cv_map = args[3]
        self.map_queue = args[4]

        self.status, self.error_code = self.check_thread_state()

    def is_online(self):
        return self.status is True

    def check_thread_state(self):
        if self.gps_thread is None or self.calculator_thread is None:
            return False, 1
        if self.gps_thread.get_current_gps_state() and self.gps_thread.get_osm_data_state():
            self.draw_map()
            return True, 0
        else:
            return False, 2

    def draw_map(self):
        status = self.osm_wrapper.draw_map(
            geo_rectangle_available=self.calculator_thread.get_osm_data_state())
        if status:
            self.print_log_line("Initial draw map was successful!")
            self.gps_thread.update_map_state(map_thread_started=True)
        else:
            self.print_log_line("Initial draw map was failed!")


class CurveLayout(RelativeLayout):

    def __init__(self):
        super(CurveLayout, self).__init__()
        self.low_deviation = 0
        self.high_deviation = 0
        self.x_coord = 0
        self.y_coord = 0
        self.already_offline = False
        self.points = []
        self.sorted_speed_list = []
        self.trigger_counter = 0
        self.startup = True

        with self.canvas:
            Color(1, 0, 0, 2)
            self.line = Line(points=self.points, width=5, joint='round')
            Color(.80, .80, .80, .80)
            self.axis_y = Line(points=[40, 0, 40, 280], width=3, joint='round')
            Color(.80, .80, .80, .80)
            self.axis_x = Line(points=[40, 0, 970, 0], width=3, joint='round')
            self.sd_y = Label(text='Speed', bold=True, color=(1, 1, 1, 1), font_size=50,
                              pos_hint={"top": 1}, size_hint=(0.15, .2))
            self.add_widget(self.sd_y)
            self.eco = Label(text='', bold=True, color=(0, 1, .3, .8), font_size=50,
                             pos_hint={"top": 1}, size_hint=(1.65, 1.50))
            self.add_widget(self.eco)
            self.sd_x = Label(text='Time', bold=True, color=(1, 1, 1, 1), font_size=50,
                              pos_hint={"top": 1}, size_hint=(1.65, 1.90))
            self.add_widget(self.sd_x)

    def set_offline_points(self):
        points = []
        for i in range(50, 1025, 25):
            points.append(i)
            points.append(0)
        return points

    def set_eco_mode(self):
        self.eco.text = 'ECO'
        Clock.schedule_once(self.eco.texture_update)

    def reset_eco_mode(self):
        self.eco.text = ''
        Clock.schedule_once(self.eco.texture_update)

    def updates(self, new_points):
        self.line.points = new_points
        self.axis_y.points = [40, 0, 40, 280]
        self.axis_x.points = [40, 0, 970, 0]

    def deviation_state_ok(self, *args, **kwargs):
        new_points = args[0]
        self.canvas.clear()
        with self.canvas:
            Color(0, 1, .5, 1)
            self.line = Line(points=[], width=5, joint='round')
            Color(.80, .80, .80, .80)
            self.axis_y = Line(points=[40, 0, 40, 280], width=3, joint='round')
            Color(.80, .80, .80, .80)
            self.axis_x = Line(points=[40, 0, 970, 0], width=3, joint='round')
            self.updates(new_points)

    def deviation_state_within_limit(self, *args, **kwargs):
        new_points = args[0]
        self.canvas.clear()
        with self.canvas:
            Color(1, 1, 0, 2)
            self.line = Line(points=[], width=5, joint='round')
            Color(.80, .80, .80, .80)
            self.axis_y = Line(points=[40, 0, 40, 280], width=3, joint='round')
            Color(.80, .80, .80, .80)
            self.axis_x = Line(points=[40, 0, 970, 0], width=3, joint='round')
            self.updates(new_points)

    def deviation_state_critical(self, *args, **kwargs):
        new_points = args[0]
        self.canvas.clear()
        with self.canvas:
            Color(1, 0, 0, 2)
            self.line = Line(points=[], width=5, joint='round')
            Color(.80, .80, .80, .80)
            self.axis_y = Line(points=[40, 0, 40, 280], width=3, joint='round')
            Color(.80, .80, .80, .80)
            self.axis_x = Line(points=[40, 0, 970, 0], width=3, joint='round')
            self.updates(new_points)

    def deviation_state_offline(self, *args, **kwargs):
        new_points = self.set_offline_points()
        self.canvas.clear()
        with self.canvas:
            Color(1, 0, 0, .2)
            self.line = Line(points=[], width=5, joint='round')
            Color(.80, .80, .80, .80)
            self.axis_y = Line(points=[40, 0, 40, 280], width=3, joint='round')
            Color(.80, .80, .80, .80)
            self.axis_x = Line(points=[40, 0, 970, 0], width=3, joint='round')
            self.updates(new_points)

    def reset_points(self):
        self.points = []
        self.x_coord = 0
        self.low_deviation = 0
        self.high_deviation = 0
        self.trigger_counter = 0
        self.sorted_speed_list = []

    def check_speed_deviation(self, curr_speed=None, trigger=False):
        if trigger:
            self.startup = True
            self.reset_points()
        self.trigger_counter += 1

        if isinstance(curr_speed, str):
            if self.already_offline:
                self.trigger_counter = 0
            else:
                Clock.schedule_once(self.deviation_state_offline)
                self.already_offline = True
                self.trigger_counter = 0
                self.reset_eco_mode()
        else:
            if self.already_offline:
                self.already_offline = False
            if len(self.points) == 78:
                deviation_state = self.calculate_average_deviation()
                if deviation_state == 'HIGH':
                    Clock.schedule_once(partial(self.deviation_state_critical, self.points))
                    self.reset_eco_mode()
                elif deviation_state == 'LOW':
                    Clock.schedule_once(partial(self.deviation_state_within_limit, self.points))
                    self.reset_eco_mode()
                else:
                    Clock.schedule_once(partial(self.deviation_state_ok, self.points))
                    self.set_eco_mode()
                self.reset_points()
                self.startup = True
                return

            if ((self.trigger_counter == 3) or (self.startup)):
                self.trigger_counter = 0
                if self.startup:
                    self.x_coord += 50
                    self.startup = False
                else:
                    self.x_coord += 25
                self.points.append(self.x_coord)

                if curr_speed == 0.1 or curr_speed < 0.5:
                    # avoid zero division
                    self.points.append(curr_speed)
                    self.sorted_speed_list.append(curr_speed)
                else:
                    self.points.append(round(curr_speed))
                    self.sorted_speed_list.append(round(curr_speed))

    def calculate_average_deviation(self):
        self.sorted_speed_list.sort()
        lowest_speeds = self.sorted_speed_list[:3]
        highest_speeds = self.sorted_speed_list[-3:]

        for lindex in range(0, len(lowest_speeds)):
            for hindex in range(0, len(highest_speeds)):
                if self.low_deviation >= 5:
                    return 'LOW'
                elif self.high_deviation >= 5:
                    return 'HIGH'
                state = self.calculate_speed_deviation(lowest_speeds[lindex],
                                                       highest_speeds[hindex])
                if state == 'LOW':
                    self.low_deviation += 1
                elif state == 'HIGH':
                    self.high_deviation += 1
                else:
                    pass
        return 'LOW_LOW'

    def calculate_speed_deviation(self, for_compare, to_compare):
        middle_low = 0
        middle_high = 0
        if ((0 <= for_compare <= 10) and (0 <= to_compare <= 10)):
            middle_low = 100000
            middle_high = 100000
        elif ((10 < for_compare < 50) and (10 < to_compare < 50)):
            middle_low = 70
            middle_high = 100
        elif ((50 <= for_compare < 100) and (50 <= to_compare < 100)):
            middle_low = 20
            middle_high = 40
        elif ((100 <= for_compare < 160) and (100 <= to_compare < 160)):
            middle_low = 10
            middle_high = 20
        elif ((160 <= for_compare < 200) and (160 <= to_compare < 200)):
            middle_low = 5
            middle_high = 10
        elif (for_compare > 200 and to_compare > 200):
            middle_low = 5
            middle_high = 10
        elif ((0 <= for_compare <= 10) and (10 < to_compare <= 25)):
            middle_low = 1900
            middle_high = 100000
        elif ((5 < for_compare <= 10) and (25 < to_compare <= 50)):
            middle_low = 230
            middle_high = 300
        else:
            middle_low = 10
            middle_high = 50

        for_compare /= 100
        if for_compare == 0:
            return None
        deviation_percentage = abs(round((to_compare / for_compare) - 100))
        if (middle_low <= deviation_percentage <= middle_high):
            return 'LOW'
        elif deviation_percentage > middle_high:
            return 'HIGH'
        else:
            return 'LOW_LOW'


class MaxSpeedlayout(FloatLayout):

    def __init__(self, gps_layout):
        super(MaxSpeedlayout, self).__init__()
        self.gps_layout = gps_layout

        with self.canvas.before:
            Color(0, 0, 0, 0)
            self.rect = Rectangle(size=self.size, pos=self.pos)

        self.bind(size=self.updates, pos=self.updates)

        self.camtext = Label(text='', bold=True, font_size=50, pos_hint={"top": 1},
                             size_hint=(1., 0.2), color=(1, 0, 0, 3))
        self.camroad = Label(text='', bold=True, font_size=50, pos_hint={"top": 1},
                             size_hint=(1., 0.6), color=(1, 0, 0, 3))
        self.maxspeed = Label(text='IDLE', bold=True, font_size=180, pos_hint={"top": 1},
                              size_hint=(1., 0.9), color=(1, .9, 0, 2))
        self.roadname = Label(text='', bold=True, font_size=100, pos_hint={"top": 1},
                              size_hint=(1., 1.7))
        self.imwarner = Label(text='MAX', bold=True, font_size=50, pos_hint={"top": 1},
                              size_hint=(.12, 1))
        self.gui_update = Label(text='', bold=True, font_size=50, pos_hint={"top": 1},
                                size_hint=(.12, 1.9))
        # self.imonlinestatus = Image(source='', nochache=True, pos_hint={"top":3}, size_hint=(0,0))
        self.imonlinestatus = Image(source='')
        self.imtrafficcam = Image(source='', nocache=True, pos_hint={"top": 3}, size_hint=(0, 0))

        self.bar_100m = Label(text='-', bold=True, font_size=500, pos_hint={"top": 2},
                              size_hint=(1.9, 2), color=(.5, .5, .5, .5))
        self.bar_300m = Label(text='-', bold=True, font_size=500, pos_hint={"top": 2},
                              size_hint=(1.9, 2.3), color=(.5, .5, .5, .5))
        self.bar_500m = Label(text='-', bold=True, font_size=500, pos_hint={"top": 2},
                              size_hint=(1.9, 2.6), color=(.5, .5, .5, .5))
        self.bar_1000m = Label(text='-', bold=True, font_size=500, pos_hint={"top": 2},
                               size_hint=(1.9, 2.9), color=(.5, .5, .5, .5))
        self.bar_2_100m = Label(text='-', bold=True, font_size=500, pos_hint={"top": 2},
                                size_hint=(1.718, 2), color=(.5, .5, .5, .5))
        self.bar_2_300m = Label(text='-', bold=True, font_size=500, pos_hint={"top": 2},
                                size_hint=(1.718, 2.3), color=(.5, .5, .5, .5))
        self.bar_2_500m = Label(text='-', bold=True, font_size=500, pos_hint={"top": 2},
                                size_hint=(1.718, 2.6), color=(.5, .5, .5, .5))
        self.bar_2_1000m = Label(text='-', bold=True, font_size=500, pos_hint={"top": 2},
                                 size_hint=(1.718, 2.9), color=(.5, .5, .5, .5))
        self.bar_meters = Label(text='', bold=True, font_size=100, pos_hint={"top": 2},
                                size_hint=(1.8, 3.4), color=(.5, .5, .5, .5))

        self.add_widget(self.camtext)
        self.add_widget(self.camroad)
        self.add_widget(self.maxspeed)
        self.add_widget(self.roadname)
        self.add_widget(self.imwarner)
        self.add_widget(self.gui_update)
        self.add_widget(self.imonlinestatus)
        self.add_widget(self.imtrafficcam)
        self.add_widget(self.bar_2_1000m)
        self.add_widget(self.bar_2_500m)
        self.add_widget(self.bar_2_300m)
        self.add_widget(self.bar_2_100m)
        self.add_widget(self.bar_1000m)
        self.add_widget(self.bar_500m)
        self.add_widget(self.bar_300m)
        self.add_widget(self.bar_100m)
        self.add_widget(self.bar_meters)
        self.callback_undefined(self)

    def update_gui(self):
        self.gui_update.text = ""
        Clock.schedule_once(self.gui_update.texture_update)

    def update_online_image_layout(self, no_cache):
        # make sure "UNDEFINED" is the first condition, otherwise it will be treated as True
        if no_cache == "UNDEFINED":
            Clock.schedule_once(self.callback_undefined)
        elif no_cache == "INETFAILED":
            Clock.schedule_once(self.callback_internet)
        elif no_cache is True:
            Clock.schedule_once(self.callback_online)
        elif no_cache is False:
            Clock.schedule_once(self.callback_offline)
        else:
            pass

    def update_bar_widget_1000m(self, color=1):
        if color == 1:
            self.bar_1000m.color = (1, 0, 0, 3)
            self.bar_2_1000m.color = (1, 0, 0, 3)
        else:
            self.bar_1000m.color = (.5, .5, .5, .5)
            self.bar_2_1000m.color = (.5, .5, .5, .5)
        Clock.schedule_once(self.bar_1000m.texture_update)
        Clock.schedule_once(self.bar_2_1000m.texture_update)

    def update_bar_widget_500m(self, color=1):
        if color == 1:
            self.bar_500m.color = (1, 0, 0, 3)
            self.bar_2_500m.color = (1, 0, 0, 3)
        else:
            self.bar_500m.color = (.5, .5, .5, .5)
            self.bar_2_500m.color = (.5, .5, .5, .5)
        Clock.schedule_once(self.bar_500m.texture_update)
        Clock.schedule_once(self.bar_2_500m.texture_update)

    def update_bar_widget_300m(self, color=1):
        if color == 1:
            self.bar_300m.color = (1, 0, 0, 3)
            self.bar_2_300m.color = (1, 0, 0, 3)
        else:
            self.bar_300m.color = (.5, .5, .5, .5)
            self.bar_2_300m.color = (.5, .5, .5, .5)
        Clock.schedule_once(self.bar_300m.texture_update)
        Clock.schedule_once(self.bar_2_300m.texture_update)

    def update_bar_widget_100m(self, color=1):
        if color == 1:
            self.bar_100m.color = (1, 0, 0, 3)
            self.bar_2_100m.color = (1, 0, 0, 3)
        else:
            self.bar_100m.color = (.5, .5, .5, .5)
            self.bar_2_100m.color = (.5, .5, .5, .5)
        Clock.schedule_once(self.bar_100m.texture_update)
        Clock.schedule_once(self.bar_2_100m.texture_update)

    def update_bar_widget_meters(self, meter=0):
        if not isinstance(meter, str):
            meter = str(meter)
        if self.bar_meters.text != meter:
            self.bar_meters.text = meter
            Clock.schedule_once(self.bar_meters.texture_update)

    def update_cam_text(self, distance=0, reset=False):
        if reset:
            self.camtext.text = ""
            self.camtext.color = (1, 0, 0, 3)
            Clock.schedule_once(self.camtext.texture_update)
        else:
            self.camtext.text = "Camera in " + str(distance) + " m"
            self.camtext.color = (1, 0, 0, 3)
            Clock.schedule_once(self.camtext.texture_update)

    def update_cam_road(self, road="", reset=False, m_type="CAMERA", color=None):
        if reset:
            if self.camroad.text != "":
                self.camroad.text = ""
                self.camroad.color = (1, 0, 0, 3) if color is None else color
                Clock.schedule_once(self.camroad.texture_update)
                Clock.schedule_once(self.callback_freeflow)
        else:
            if m_type == "WATER":
                color = (0, 1, 1, 1) if color is None else color
            elif m_type == "ACCESS_CONTROL":
                color = (1, 1, 0, 2) if color is None else color
            else:
                color = (1, 0, 0, 3) if color is None else color

            if road is None:
                road = ""
            if self.camroad.text != str(road):
                self.camroad.text = str(road)
                self.camroad.color = color
                self.camroad.size_hint = (1., 0.2)
                Clock.schedule_once(self.camroad.texture_update)
                if m_type == "HAZARD":
                    Clock.schedule_once(self.callback_hazard)
                elif m_type == "WATER":
                    Clock.schedule_once(self.callback_water)
                elif m_type == "ACCESS_CONTROL":
                    Clock.schedule_once(self.callback_access_control)

    def callback_offline(self, instance):
        self.imonlinestatus.source = 'images/cache.png'
        self.imonlinestatus.pos_hint = {"top": 1}
        self.imonlinestatus.size_hint = (.12, 0.42)
        self.imonlinestatus.texture_update()

    def callback_online(self, instance):
        self.imonlinestatus.source = 'images/ok.png'
        self.imonlinestatus.pos_hint = {"top": 1}
        self.imonlinestatus.size_hint = (.12, 0.42)
        self.imonlinestatus.texture_update()

    def callback_undefined(self, instance):
        self.imonlinestatus.source = 'images/black.png'
        self.imonlinestatus.pos_hint = {"top": 1}
        self.imonlinestatus.size_hint = (.12, 0.42)
        self.imonlinestatus.texture_update()

    def callback_internet(self, instance):
        self.imonlinestatus.source = 'images/noinet.png'
        self.imonlinestatus.pos_hint = {"top": 1}
        self.imonlinestatus.size_hint = (.12, 0.42)
        self.imonlinestatus.texture_update()

    def callback_hazard(self, instance):
        self.gps_layout.camera.source = 'images/hazard.png'
        self.gps_layout.camera.color = (1, .9, 0, 2)
        self.gps_layout.camera.texture_update()

    def callback_freeflow(self, instance):
        self.gps_layout.camera.source = 'images/freeflow.png'
        self.gps_layout.camera.color = (1, .9, 0, 2)
        self.gps_layout.camera.texture_update()

    def callback_water(self, instance):
        self.gps_layout.camera.source = 'images/water.png'
        self.gps_layout.camera.color = (1, 1, 1, 1)
        self.gps_layout.camera.texture_update()

    def callback_access_control(self, instance):
        self.gps_layout.camera.source = 'images/access_control.png'
        self.gps_layout.camera.color = (1, .9, 0, 2)
        self.gps_layout.camera.texture_update()

    def get_maxspeed_label(self):
        return self.maxspeed

    def updates(self, instance, value):
        self.rect.size = instance.size
        self.rect.pos = instance.pos


class Poilayout(GridLayout):

    def __init__(self, *args, **kwargs):
        super(Poilayout, self).__init__(**kwargs)
        self.logger = Logger(self.__class__.__name__)
        self.sm = args[0]
        self.ml = args[1]
        self.main_app = args[2]
        self.voice_prompt_queue = args[3]
        self.cv_voice = args[4]
        self.cols = 3
        self.rows = 3
        self.poi_lookup = "hospital"
        self.route_providers = []
        self.stop_thread = False

        self.poibutton = Button(text='SEARCH', bold=True, font_size=60,
                                background_color=(.35, .35, .35, .35))
        '''self.stopbutton = Button(text='STOP ROUTE', bold=True, font_size=60,
                                 background_color=(.35, .35, .35, .35))'''
        self.add_widget(self.poibutton)
        self.hospital = CheckBox(active=True, color=[3, 3, 3, 3], size_hint_x=0.4)
        self.hospital.bind(active=self.on_checkbox_active)
        self.label_h = Label(text="Hospitals", font_size=60)
        self.add_widget(self.label_h)
        self.add_widget(self.hospital)
        self.returnbutton_main = Button(text='<<<', bold=True, font_size=60,
                                        background_color=(.5, .5, .5, .5))
        # self.add_widget(self.stopbutton)
        self.add_widget(self.returnbutton_main)
        self.label_g = Label(text="Gasstations", font_size=60)
        self.add_widget(self.label_g)
        self.gas = CheckBox(color=[4, 4, 4, 4], size_hint_x=0.4)
        self.gas.bind(active=self.on_checkbox_active)
        self.add_widget(self.gas)
        self.returnbutton_main.bind(on_press=self.callback_return)
        self.poibutton.bind(on_press=self.callback_poi)
        # self.stopbutton.bind(on_press=self.callback_stop)

    def on_checkbox_active(self, checkbox, value):
        if value:
            if checkbox.color == [3, 3, 3, 3]:
                self.poi_lookup = "hospital"
            else:
                self.poi_lookup = "fuel"

    def callback_return(self, instance):
        if not RectangleCalculatorThread.thread_lock:
            self.sm.current = 'Operative'

    '''def callback_stop(self, instance):
        if self.main_app.osm_thread is None:
            self.sm.current = 'Operative'
            return

        OSMThread.route_calc = True
        if self.route_providers:
            self.stop_thread = True
            for route_provider in self.route_providers:
                self.route_providers.remove(route_provider)
                route_provider.join()
            self.logger.print_log_line("Route calculation stopped!")
            self.voice_prompt_queue.produce_poi_status(self.cv_voice, "ROUTE_STOPPED")
        else:
            self.voice_prompt_queue.produce_poi_status(self.cv_voice, "NO_ROUTE")
        self.sm.current = 'Operative'
    '''

    def callback_poi(self, instance):
        if RectangleCalculatorThread.thread_lock:
            self.logger.print_log_line("POI lookup dismissed!! -> Calculator Thread is still busy")
            self.voice_prompt_queue.produce_poi_status(self.cv_voice, "POI_FAILED")
            return

        self.logger.print_log_line("POI lookup started!!")

        # First stop any open route providers
        '''if self.route_providers:
            self.stop_thread = True
            OSMThread.route_calc = True
            for route_provider in self.route_providers:
                self.route_providers.remove(route_provider)
                route_provider.join()'''
        # OSMThread.route_calc = True
        self.stop_thread = False
        self.main_app.map_layout.map_view.re_center = False

        gps_producer, calculator, speedwarner = self.main_app.pass_bot_objects()

        if isinstance(gps_producer, GPSThread) and isinstance(calculator,
                                                              RectangleCalculatorThread) and \
                isinstance(speedwarner, SpeedCamWarnerThread):
            lon, lat = gps_producer.get_lon_lat_bot()
            if (lon is None and lat is None) or (lon == 0 and lat == 0):
                self.voice_prompt_queue.produce_poi_status(self.cv_voice, "POI_FAILED")
                popup = Popup(title='Attention',
                              content=Label(text='No valid GPS position!'),
                              size_hint=(None, None), size=(600, 600))
                popup.open()
                self.sm.current = 'Operative'
                return

            # convert CCP longitude,latitude to (x,y).
            xtile, ytile = calculator.longlat2tile(lat, lon, calculator.zoom)
            h = calculator.tile2hypotenuse(xtile, ytile)
            angle = calculator.tile2polar(xtile, ytile)

            # self.print_log_line(' Polar coordinates = %f %f degrees' %(h,angle))

            xtile_min, xtile_max, ytile_min, ytile_max = calculator.calculatepoints2angle(
                xtile,
                ytile,
                self.main_app.poi_distance,
                calculator.current_rect_angle)
            LON_MIN, LAT_MIN, LON_MAX, LAT_MAX = calculator.createGeoJsonTilePolygonAngle(
                calculator.zoom,
                xtile_min,
                ytile_min,
                xtile_max,
                ytile_max)

            # convert each of the 2 points to (x,y).
            pt1_xtile, pt1_ytile = calculator.longlat2tile(LAT_MIN, LON_MIN,
                                                           calculator.zoom)
            pt2_xtile, pt2_ytile = calculator.longlat2tile(LAT_MAX, LON_MAX,
                                                           calculator.zoom)
            # calculate a rectangle from these 2 points
            CURRENT_RECT = calculator.calculate_rectangle_border(
                [pt1_xtile, pt1_ytile], [pt2_xtile, pt2_ytile])
            CURRENT_RECT.set_rectangle_ident(calculator.direction)
            CURRENT_RECT.set_rectangle_string('CURRENT')
            # calculate the radius of the rectangle in km
            rectangle_radius = calculator.calculate_rectangle_radius(
                CURRENT_RECT.rect_height(),
                CURRENT_RECT.rect_width())

            osm_lookup_properties = [(LON_MIN,
                                      LAT_MIN,
                                      LON_MAX,
                                      LAT_MAX,
                                      calculator.direction,
                                      self.poi_lookup,
                                      'CURRENT')]
            server_responses = calculator.start_thread_pool_lookup(
                calculator.trigger_osm_lookup, 1, osm_lookup_properties, " ", " ", " ", " ",
                'CURRENT')

            status = server_responses[1][1]
            data = server_responses[1][2]
            RectangleCalculatorThread.thread_lock = False

            if status == 'OK' and len(data) > 0:
                self.logger.print_log_line("POI lookup finished!! Found %d %s"
                                           % (len(data), self.poi_lookup))
                self.voice_prompt_queue.produce_poi_status(self.cv_voice, "POI_SUCCESS")
                self.ml.update_pois(len(data))
                self.main_app.poi_queue.produce(self.main_app.cv_poi, data)

                if self.main_app.osm_init is None:
                    self.main_app.init_osm(self.main_app.gps_producer,
                                           self.main_app.calculator,
                                           self.main_app.osm_wrapper,
                                           self.main_app.cv_map,
                                           self.main_app.map_queue)
                # Calculate smallest distance to POIS
                self.sm.current = 'Map'
                '''self.logger.print_log_line("Calculate smallest distance to POIS..")

                pois = []
                # update ccp
                lon, lat = gps_producer.get_lon_lat_bot()
                for element in data:
                    try:
                        poi = (element['lat'], element['lon'])
                    except KeyError:
                        continue
                    distance = speedwarner.check_distance_between_two_points((poi[1], poi[0]),
                                                                             (lon, lat))
                    pois.append((poi, distance))
                poi = speedwarner.sort_pois(pois)
                if poi is not None:
                    poi_tuple = (poi, (lat, lon))
                    self.logger.print_log_line("Nearest POI is %s" % str(poi))
                    self.main_app.poi_queue.produce(self.main_app.cv_poi, poi_tuple)
                    self.main_app.poi_queue.produce(self.main_app.cv_poi, data)
                    self.voice_prompt_queue.produce_poi_status(self.cv_voice, "POI_SUCCESS")
                    route_provider = threading.Thread(target=self.prepare_route, args=(poi,))
                    self.route_providers.append(route_provider)
                    route_provider.start()
                else:
                    self.ml.update_pois(0)
                    self.voice_prompt_queue.produce_poi_status(self.cv_voice, "POI_FAILED")'''
            else:
                self.logger.print_log_line("POI lookup finished without results!")
                self.ml.update_pois(0)
                self.voice_prompt_queue.produce_poi_status(self.cv_voice, "POI_FAILED")
        else:
            self.voice_prompt_queue.produce_poi_status(self.cv_voice, "POI_FAILED")

    def prepare_route(self, poi):
        gps_producer, _, speedwarner = self.main_app.pass_bot_objects()

        while not self.stop_thread:
            time.sleep(2)
            try:
                lon, lat = gps_producer.get_lon_lat_bot()
                poi_tuple = (poi, (lat, lon))
                self.main_app.poi_queue.produce(self.main_app.cv_poi, poi_tuple)
                distance = speedwarner.check_distance_between_two_points((poi[1], poi[0]),
                                                                         (lon, lat))
                if distance <= 50:
                    self.voice_prompt_queue.produce_poi_status(self.cv_voice, "POI_REACHED")
                    break
            except:
                pass


class Cameralayout(BoxLayout):

    def __init__(self, *args, **kwargs):
        super(Cameralayout, self).__init__(**kwargs)
        self.sm = args[0]
        self.main_app = args[1]
        self.voice_prompt_queue = args[2]
        self.cv_voice = args[3]

        self.policebutton = Button(text='POLICE', font_size=300, bold=True,
                                   background_color=(.35, .35, .35, .35))
        self.add_widget(self.policebutton)
        self.returnbutton_main = Button(text='<<<', font_size=600, bold=True,
                                        background_color=(.5, .5, .5, .5))
        self.add_widget(self.returnbutton_main)

        self.returnbutton_main.bind(on_press=self.callback_return)
        self.policebutton.bind(on_press=self.callback_police)

    def callback_return(self, instance):
        self.sm.current = 'Operative'

    def callback_police(self, instance):
        gps_producer, calculator, _ = self.main_app.pass_bot_objects()

        if isinstance(gps_producer, GPSThread) and isinstance(calculator,
                                                              RectangleCalculatorThread):
            lon, lat = gps_producer.get_lon_lat_bot()
            if lon is None and lat is None:
                popup = Popup(title='Attention',
                              content=Label(text='No valid GPS position!'),
                              size_hint=(None, None), size=(600, 600))
                popup.open()
                return
            road_name = calculator.get_road_name_via_nominatim(lat, lon)
            if "ERROR:" in road_name:
                self.voice_prompt_queue.produce_info(self.cv_voice, "ADDING_POLICE_FAILED")
                return
            road_name = "" if road_name is None else road_name

            calculator.start_thread_pool_upload_speed_camera_to_drive(
                calculator.upload_camera_to_drive, 1, road_name, lat, lon)
            self.voice_prompt_queue.produce_info(self.cv_voice, "ADDED_POLICE")


class Gpslayout(BoxLayout):

    def __init__(self, *args, **kwargs):
        super(Gpslayout, self).__init__(**kwargs)
        self.sm = args[0]
        self.main_app = args[1]
        self.imgps = Image(source='images/gps.png', color=(1, .9, 0, 2))
        self.camera = Image(source='images/freeflow.png', color=(1, .9, 0, 2))
        self.plusbutton = Button(text='+', bold=True, font_size=600,
                                 background_color=(.5, .5, .5, .5))
        self.add_widget(self.imgps)
        self.add_widget(self.camera)
        self.add_widget(self.plusbutton)
        self.plusbutton.bind(on_press=self.callback_plus)

    def callback_plus(self, instance):
        if isinstance(self.main_app.gps_producer, GPSThread):
            if not self.main_app.gps_producer.get_current_gps_state():
                popup = Popup(title='Attention',
                              content=Label(text='No valid GPS position!'),
                              size_hint=(None, None), size=(600, 600))
                popup.open()
                return
        else:
            popup = Popup(title='Attention',
                          content=Label(text='Please start App first!'),
                          size_hint=(None, None), size=(600, 600))
            popup.open()
            return
        self.sm.current = 'Add'

    def on_state(self):
        Clock.schedule_once(self.callback_online)

    def off_state(self):
        Clock.schedule_once(self.callback_offline)

    def callback_online(self, instance):
        self.imgps.source = 'images/gps.png'
        self.imgps.color = (0, 1, .3, .8)
        self.imgps.texture_update()

    def callback_offline(self, instance):
        self.imgps.source = 'images/gps.png'
        self.imgps.color = (1, 0, 0, 3)
        self.imgps.texture_update()

    def callback_fix_camera(self, instance):
        self.camera.source = 'images/fixcamera.png'
        self.camera.color = (1, .9, 0, 2)
        self.camera.texture_update()

    def callback_mobile_camera(self, instance):
        self.camera.source = 'images/mobilcamera.png'
        self.camera.color = (1, .9, 0, 2)
        self.camera.texture_update()

    def callback_traffic_camera(self, instance):
        self.camera.source = 'images/trafficlightcamera.png'
        self.camera.color = (1, .9, 0, 2)
        self.camera.texture_update()

    def callback_distance_camera(self, instance):
        self.camera.source = 'images/distancecamera.png'
        self.camera.color = (1, .9, 0, 2)
        self.camera.texture_update()

    def callback_freeflow_camera(self, instance):
        self.camera.source = 'images/freeflow.png'
        self.camera.color = (1, .9, 0, 2)
        self.camera.texture_update()

    def callback_camera_ahead(self, instance):
        self.camera.source = 'images/camera_ahead.png'
        self.camera.color = (1, .9, 0, 2)
        self.camera.texture_update()

    def update_speed_camera(self, camera='fix'):
        if camera == 'fix':
            Clock.schedule_once(self.callback_fix_camera)
        elif camera == 'mobile':
            Clock.schedule_once(self.callback_mobile_camera)
        elif camera == 'traffic':
            Clock.schedule_once(self.callback_traffic_camera)
        elif camera == 'distance':
            Clock.schedule_once(self.callback_distance_camera)
        elif camera == "FREEFLOW":
            Clock.schedule_once(self.callback_freeflow_camera)
        else:
            Clock.schedule_once(self.callback_camera_ahead)


class Speedlayout(FloatLayout):

    def __init__(self):
        super(Speedlayout, self).__init__()

        ## global variables ##
        self.already_offline = False
        self.already_online = False
        self.cur_speed = 0
        self.accel = True
        self.accel_kivi = {}

        with self.canvas:
            Color(0, 0, 0, 0)
            self.rect = Rectangle(size=self.size, pos=self.pos)

            self.bind(size=self.updates, pos=self.updates)

            self.curspeed = Label(text='---.-', bold=True, font_size=250, pos_hint={"top": 1},
                                  size_hint=(1., 1.))
            self.service_unit = Label(text='', bold=False, font_size=50, pos_hint={"top": 1},
                                      size_hint=(1.8, 1.5))
            self.bearing = Label(text='---.-', bold=True, font_size=100, pos_hint={"bottom": 1},
                                 size_hint=(.64, 1.2))
            self.av_bearing = Label(text='AB ', bold=True, font_size=80, pos_hint={"bottom": 1},
                                    size_hint=(1.4, 1.2))
            self.av_bearing_value = Label(text='---.-', bold=True, font_size=80,
                                          pos_hint={"bottom": 1}, size_hint=(1.7, 1.2))

            self.gps_accuracy = Label(text='GPS: -', bold=True, font_size=50, pos_hint={"top": 1},
                                      size_hint=(.30, 0.3), color=(1, 1, 1, 1))
            self.overspeed = Label(text='', bold=True, font_size=120, pos_hint={"top": 1},
                                   size_hint=(.25, 1.), color=(1, 0, 0, 3))

            self.accel5 = Label(text='-', bold=True, font_size=100, pos_hint={"top": 1},
                                size_hint=(0.05, 1.8), color=(0, 0, .3, 0))
            self.accel10 = Label(text='-', bold=True, font_size=100, pos_hint={"top": 1},
                                 size_hint=(0.08, 1.8), color=(0, 0, .3, 0))
            self.accel15 = Label(text='-', bold=True, font_size=100, pos_hint={"top": 1},
                                 size_hint=(0.11, 1.8), color=(0, 0, .3, 0))
            self.accel20 = Label(text='-', bold=True, font_size=100, pos_hint={"top": 1},
                                 size_hint=(0.14, 1.8), color=(0, 0, .3, 0))
            self.accel25 = Label(text='-', bold=True, font_size=100, pos_hint={"top": 1},
                                 size_hint=(0.17, 1.8), color=(0, 0, .3, 0))
            self.accel30 = Label(text='-', bold=True, font_size=100, pos_hint={"top": 1},
                                 size_hint=(0.20, 1.8), color=(0, 0, .3, 0))
            self.accel35 = Label(text='-', bold=True, font_size=100, pos_hint={"top": 1},
                                 size_hint=(0.23, 1.8), color=(0, 0, .3, 0))
            self.accel40 = Label(text='-', bold=True, font_size=100, pos_hint={"top": 1},
                                 size_hint=(0.26, 1.8), color=(0, 0, .3, 0))
            self.accel45 = Label(text='-', bold=True, font_size=100, pos_hint={"top": 1},
                                 size_hint=(0.29, 1.8), color=(0, 0, .3, 0))
            self.accel50 = Label(text='-', bold=True, font_size=100, pos_hint={"top": 1},
                                 size_hint=(0.32, 1.8), color=(0, 0, .3, 0))
            self.accel55 = Label(text='-', bold=True, font_size=100, pos_hint={"top": 1},
                                 size_hint=(0.35, 1.8), color=(0, 0, .3, 0))
            self.accel60 = Label(text='-', bold=True, font_size=100, pos_hint={"top": 1},
                                 size_hint=(0.38, 1.8), color=(0, 0, .3, 0))
            self.accel65 = Label(text='-', bold=True, font_size=100, pos_hint={"top": 1},
                                 size_hint=(0.41, 1.8), color=(0, 0, .3, 0))
            self.accel70 = Label(text='-', bold=True, font_size=100, pos_hint={"top": 1},
                                 size_hint=(0.44, 1.8), color=(0, 0, .3, 0))

            self.accel75 = Label(text='-', bold=True, font_size=100, pos_hint={"top": 1},
                                 size_hint=(0.47, 1.8), color=(0, 0, .3, 0))
            self.accel80 = Label(text='-', bold=True, font_size=100, pos_hint={"top": 1},
                                 size_hint=(0.50, 1.8), color=(0, 0, .3, 0))
            self.accel85 = Label(text='-', bold=True, font_size=100, pos_hint={"top": 1},
                                 size_hint=(0.53, 1.8), color=(0, 0, .3, 0))
            self.accel90 = Label(text='-', bold=True, font_size=100, pos_hint={"top": 1},
                                 size_hint=(0.56, 1.8), color=(0, 0, .3, 0))
            self.accel95 = Label(text='-', bold=True, font_size=100, pos_hint={"top": 1},
                                 size_hint=(0.59, 1.8), color=(0, 0, .3, 0))
            self.accel100 = Label(text='-', bold=True, font_size=100, pos_hint={"top": 1},
                                  size_hint=(0.62, 1.8), color=(0, 0, .3, 0))
            self.accel105 = Label(text='-', bold=True, font_size=100, pos_hint={"top": 1},
                                  size_hint=(0.65, 1.8), color=(0, 0, .3, 0))
            self.accel110 = Label(text='-', bold=True, font_size=100, pos_hint={"top": 1},
                                  size_hint=(0.68, 1.8), color=(0, 0, .3, 0))
            self.accel115 = Label(text='-', bold=True, font_size=100, pos_hint={"top": 1},
                                  size_hint=(0.71, 1.8), color=(0, 0, .3, 0))
            self.accel120 = Label(text='-', bold=True, font_size=100, pos_hint={"top": 1},
                                  size_hint=(0.74, 1.8), color=(0, 0, .3, 0))
            self.accel125 = Label(text='-', bold=True, font_size=100, pos_hint={"top": 1},
                                  size_hint=(0.77, 1.8), color=(0, 0, .3, 0))
            self.accel130 = Label(text='-', bold=True, font_size=100, pos_hint={"top": 1},
                                  size_hint=(0.80, 1.8), color=(0, 0, .3, 0))
            self.accel135 = Label(text='-', bold=True, font_size=100, pos_hint={"top": 1},
                                  size_hint=(0.83, 1.8), color=(0, 0, .3, 0))
            self.accel140 = Label(text='-', bold=True, font_size=100, pos_hint={"top": 1},
                                  size_hint=(0.86, 1.8), color=(0, 0, .3, 0))

            self.accel145 = Label(text='-', bold=True, font_size=100, pos_hint={"top": 1},
                                  size_hint=(0.89, 1.8), color=(0, 0, .3, 0))
            self.accel150 = Label(text='-', bold=True, font_size=100, pos_hint={"top": 1},
                                  size_hint=(0.92, 1.8), color=(0, 0, .3, 0))
            self.accel155 = Label(text='-', bold=True, font_size=100, pos_hint={"top": 1},
                                  size_hint=(0.95, 1.8), color=(0, 0, .3, 0))
            self.accel160 = Label(text='-', bold=True, font_size=100, pos_hint={"top": 1},
                                  size_hint=(0.98, 1.8), color=(0, 0, .3, 0))
            self.accel165 = Label(text='-', bold=True, font_size=100, pos_hint={"top": 1},
                                  size_hint=(1.01, 1.8), color=(0, 0, .3, 0))
            self.accel170 = Label(text='-', bold=True, font_size=100, pos_hint={"top": 1},
                                  size_hint=(1.04, 1.8), color=(0, 0, .3, 0))
            self.accel175 = Label(text='-', bold=True, font_size=100, pos_hint={"top": 1},
                                  size_hint=(1.07, 1.8), color=(0, 0, .3, 0))
            self.accel180 = Label(text='-', bold=True, font_size=100, pos_hint={"top": 1},
                                  size_hint=(1.10, 1.8), color=(0, 0, .3, 0))
            self.accel185 = Label(text='-', bold=True, font_size=100, pos_hint={"top": 1},
                                  size_hint=(1.13, 1.8), color=(0, 0, .3, 0))
            self.accel190 = Label(text='-', bold=True, font_size=100, pos_hint={"top": 1},
                                  size_hint=(1.16, 1.8), color=(0, 0, .3, 0))
            self.accel195 = Label(text='-', bold=True, font_size=100, pos_hint={"top": 1},
                                  size_hint=(1.19, 1.8), color=(0, 0, .3, 0))
            self.accel200 = Label(text='-', bold=True, font_size=100, pos_hint={"top": 1},
                                  size_hint=(1.22, 1.8), color=(0, 0, .3, 0))
            self.accel205 = Label(text='-', bold=True, font_size=100, pos_hint={"top": 1},
                                  size_hint=(1.25, 1.8), color=(0, 0, .3, 0))
            self.accel210 = Label(text='-', bold=True, font_size=100, pos_hint={"top": 1},
                                  size_hint=(1.28, 1.8), color=(0, 0, .3, 0))

            self.accel215 = Label(text='-', bold=True, font_size=100, pos_hint={"top": 1},
                                  size_hint=(1.31, 1.8), color=(0, 0, .3, 0))
            self.accel220 = Label(text='-', bold=True, font_size=100, pos_hint={"top": 1},
                                  size_hint=(1.34, 1.8), color=(0, 0, .3, 0))
            self.accel225 = Label(text='-', bold=True, font_size=100, pos_hint={"top": 1},
                                  size_hint=(1.37, 1.8), color=(0, 0, .3, 0))
            self.accel230 = Label(text='-', bold=True, font_size=100, pos_hint={"top": 1},
                                  size_hint=(1.40, 1.8), color=(0, 0, .3, 0))
            self.accel235 = Label(text='-', bold=True, font_size=100, pos_hint={"top": 1},
                                  size_hint=(1.43, 1.8), color=(0, 0, .3, 0))
            self.accel240 = Label(text='-', bold=True, font_size=100, pos_hint={"top": 1},
                                  size_hint=(1.46, 1.8), color=(0, 0, .3, 0))
            self.accel245 = Label(text='-', bold=True, font_size=100, pos_hint={"top": 1},
                                  size_hint=(1.49, 1.8), color=(0, 0, .3, 0))
            self.accel250 = Label(text='-', bold=True, font_size=100, pos_hint={"top": 1},
                                  size_hint=(1.52, 1.8), color=(0, 0, .3, 0))
            self.accel255 = Label(text='-', bold=True, font_size=100, pos_hint={"top": 1},
                                  size_hint=(1.55, 1.8), color=(0, 0, .3, 0))
            self.accel260 = Label(text='-', bold=True, font_size=100, pos_hint={"top": 1},
                                  size_hint=(1.58, 1.8), color=(0, 0, .3, 0))
            self.accel265 = Label(text='-', bold=True, font_size=100, pos_hint={"top": 1},
                                  size_hint=(1.61, 1.8), color=(0, 0, .3, 0))
            self.accel270 = Label(text='-', bold=True, font_size=100, pos_hint={"top": 1},
                                  size_hint=(1.64, 1.8), color=(0, 0, .3, 0))

            self.add_widget(self.curspeed)
            self.add_widget(self.gps_accuracy)
            self.add_widget(self.overspeed)
            self.add_widget(self.service_unit)
            self.add_widget(self.bearing)
            self.add_widget(self.av_bearing)
            self.add_widget(self.av_bearing_value)
            self.add_widget(self.accel5)
            self.add_widget(self.accel10)
            self.add_widget(self.accel15)
            self.add_widget(self.accel20)
            self.add_widget(self.accel25)
            self.add_widget(self.accel30)
            self.add_widget(self.accel35)
            self.add_widget(self.accel40)
            self.add_widget(self.accel45)
            self.add_widget(self.accel50)
            self.add_widget(self.accel55)
            self.add_widget(self.accel60)
            self.add_widget(self.accel65)
            self.add_widget(self.accel70)

            self.add_widget(self.accel75)
            self.add_widget(self.accel80)
            self.add_widget(self.accel85)
            self.add_widget(self.accel90)
            self.add_widget(self.accel95)
            self.add_widget(self.accel100)
            self.add_widget(self.accel105)
            self.add_widget(self.accel110)
            self.add_widget(self.accel115)
            self.add_widget(self.accel120)
            self.add_widget(self.accel125)
            self.add_widget(self.accel130)
            self.add_widget(self.accel135)
            self.add_widget(self.accel140)
            self.add_widget(self.accel145)

            self.add_widget(self.accel150)
            self.add_widget(self.accel155)
            self.add_widget(self.accel160)
            self.add_widget(self.accel165)
            self.add_widget(self.accel170)
            self.add_widget(self.accel175)
            self.add_widget(self.accel180)
            self.add_widget(self.accel185)
            self.add_widget(self.accel190)
            self.add_widget(self.accel195)
            self.add_widget(self.accel200)
            self.add_widget(self.accel205)
            self.add_widget(self.accel210)
            self.add_widget(self.accel215)
            self.add_widget(self.accel220)

            self.add_widget(self.accel225)
            self.add_widget(self.accel230)
            self.add_widget(self.accel235)
            self.add_widget(self.accel240)
            self.add_widget(self.accel245)
            self.add_widget(self.accel250)
            self.add_widget(self.accel255)
            self.add_widget(self.accel260)
            self.add_widget(self.accel265)
            self.add_widget(self.accel270)
            self.add_kivi_elements()

    def add_kivi_elements(self):
        self.accel_kivi[5] = self.accel5
        self.accel_kivi[10] = self.accel10
        self.accel_kivi[15] = self.accel15
        self.accel_kivi[20] = self.accel20
        self.accel_kivi[25] = self.accel25
        self.accel_kivi[30] = self.accel30
        self.accel_kivi[35] = self.accel35
        self.accel_kivi[40] = self.accel40
        self.accel_kivi[45] = self.accel45
        self.accel_kivi[50] = self.accel50
        self.accel_kivi[55] = self.accel55
        self.accel_kivi[60] = self.accel60
        self.accel_kivi[65] = self.accel65
        self.accel_kivi[70] = self.accel70

        self.accel_kivi[75] = self.accel75
        self.accel_kivi[80] = self.accel80
        self.accel_kivi[85] = self.accel85
        self.accel_kivi[90] = self.accel90
        self.accel_kivi[95] = self.accel95
        self.accel_kivi[100] = self.accel100
        self.accel_kivi[105] = self.accel105
        self.accel_kivi[110] = self.accel110
        self.accel_kivi[115] = self.accel115
        self.accel_kivi[120] = self.accel120
        self.accel_kivi[125] = self.accel125
        self.accel_kivi[130] = self.accel130
        self.accel_kivi[135] = self.accel135
        self.accel_kivi[140] = self.accel140

        self.accel_kivi[145] = self.accel145
        self.accel_kivi[150] = self.accel150
        self.accel_kivi[155] = self.accel155
        self.accel_kivi[160] = self.accel160
        self.accel_kivi[165] = self.accel165
        self.accel_kivi[170] = self.accel170
        self.accel_kivi[175] = self.accel175
        self.accel_kivi[180] = self.accel180
        self.accel_kivi[185] = self.accel185
        self.accel_kivi[190] = self.accel190
        self.accel_kivi[195] = self.accel195
        self.accel_kivi[200] = self.accel200
        self.accel_kivi[205] = self.accel205
        self.accel_kivi[210] = self.accel210
        self.accel_kivi[215] = self.accel215

        self.accel_kivi[220] = self.accel220
        self.accel_kivi[225] = self.accel225
        self.accel_kivi[230] = self.accel230
        self.accel_kivi[235] = self.accel235
        self.accel_kivi[240] = self.accel240
        self.accel_kivi[245] = self.accel245
        self.accel_kivi[250] = self.accel250
        self.accel_kivi[255] = self.accel255
        self.accel_kivi[260] = self.accel260
        self.accel_kivi[265] = self.accel265
        self.accel_kivi[270] = self.accel270

    def updates(self, instance, value):
        self.rect.size = instance.size
        self.rect.pos = instance.pos

    def update_gps_accuracy(self, accuracy=""):
        self.gps_accuracy.text = "GPS: " + accuracy
        Clock.schedule_once(self.gps_accuracy.texture_update)

    def update_overspeed(self, speed=0):
        if self.overspeed.text != "+" + str(speed):
            self.overspeed.text = "+" + str(speed)
            self.overspeed.font_size = 120
            self.overspeed.color = (1, 0, 0, 3)
            Clock.schedule_once(self.overspeed.texture_update)

    def reset_overspeed(self):
        if self.overspeed.text != "":
            self.overspeed.text = ""
            Clock.schedule_once(self.overspeed.texture_update)

    def reset_bearing(self):
        if self.bearing.text != "---.-":
            self.bearing.text = "---.-"
            Clock.schedule_once(self.bearing.texture_update)
        if self.av_bearing_value.text != "---.-":
            self.av_bearing_value.text = "---.-"
            Clock.schedule_once(self.av_bearing_value.texture_update)

    def update_accel_layout(self, cur_speed=0, accel=True, gps_status='OFFLINE'):
        if gps_status == 'ONLINE':
            self.cur_speed = cur_speed
            self.accel = accel

            if self.already_online:
                Clock.schedule_once(self.callback_online)
            else:
                Clock.schedule_once(self.callback_online)
                self.already_online = True
                self.already_offline = False
        else:
            if self.already_offline:
                pass
            else:
                Clock.schedule_once(self.callback_offline)
                self.already_offline = True
                self.already_online = False

    def reset_acceleration(self, accel_index=5):
        for index in range(270, accel_index, -5):
            self.accel_kivi[index].color = (0, 0, .3, 0)
            self.accel_kivi[index].texture_update()

    def accelerate(self, start_index=5, accel_index=270, color=1):
        for index in range(start_index, accel_index, 5):
            if color == 1:
                self.accel_kivi[index].color = (0, 1, .5, 1)
            elif color == 2:
                self.accel_kivi[index].color = (0, 1, .4, 1)
            elif color == 3:
                self.accel_kivi[index].color = (0, 1, .3, 1)
            elif color == 4:
                self.accel_kivi[index].color = (0, 1, .2, 1)
            elif color == 5:
                self.accel_kivi[index].color = (0, 1, .1, 1)
            elif color == 6:
                self.accel_kivi[index].color = (1, 1, 0, 2)
            elif color == 7:
                self.accel_kivi[index].color = (1, .9, 0, 2)
            elif color == 8:
                self.accel_kivi[index].color = (1, .8, 0, 3)
            elif color == 9:
                self.accel_kivi[index].color = (1, .7, 0, 3)
            elif color == 10:
                self.accel_kivi[index].color = (1, .6, 0, 3)
            elif color == 11:
                self.accel_kivi[index].color = (1, .5, 0, 3)
            elif color == 12:
                self.accel_kivi[index].color = (1, .4, 0, 3)
            elif color == 13:
                self.accel_kivi[index].color = (1, .3, 0, 3)
            elif color == 14:
                self.accel_kivi[index].color = (1, .2, 0, 3)
            elif color == 15:
                self.accel_kivi[index].color = (1, .1, 0, 3)
            else:
                self.accel_kivi[index].color = (0, 0, .3, 0)
            self.accel_kivi[index].texture_update()

    def callback_offline(self, instance):
        self.reset_acceleration()
        self.accel_kivi[5].color = (0, 0, .3, 0)
        self.accel_kivi[5].texture_update()

    def callback_online(self, instance):
        if (5 <= self.cur_speed < 10):
            if self.accel:
                self.accelerate(accel_index=10, color=1)
            else:
                self.reset_acceleration(5)
        elif (10 <= self.cur_speed < 15):
            if self.accel:
                self.accelerate(start_index=5, accel_index=15, color=1)
            else:
                self.reset_acceleration(10)
        elif (15 <= self.cur_speed < 20):
            if self.accel:
                self.accelerate(start_index=5, accel_index=20, color=1)
            else:
                self.reset_acceleration(15)
        elif (20 <= self.cur_speed < 25):
            if self.accel:
                self.accelerate(start_index=5, accel_index=25, color=1)
            else:
                self.reset_acceleration(20)
        elif (25 <= self.cur_speed < 30):
            if self.accel:
                self.accelerate(start_index=5, accel_index=30, color=1)
            else:
                self.reset_acceleration(25)
        elif (30 <= self.cur_speed < 35):
            if self.accel:
                self.accelerate(start_index=5, accel_index=35, color=1)
            else:
                self.reset_acceleration(30)
        elif (35 <= self.cur_speed < 40):
            if self.accel:
                self.accelerate(start_index=5, accel_index=40, color=1)
            else:
                self.reset_acceleration(35)
        elif (40 <= self.cur_speed < 45):
            if self.accel:
                self.accelerate(start_index=5, accel_index=45, color=1)
            else:
                self.reset_acceleration(40)
        elif (45 <= self.cur_speed < 50):
            if self.accel:
                self.accelerate(start_index=5, accel_index=50, color=1)
            else:
                self.reset_acceleration(45)
        elif (50 <= self.cur_speed < 55):
            if self.accel:
                self.accelerate(start_index=5, accel_index=55, color=2)
            else:
                self.reset_acceleration(50)
        elif (55 <= self.cur_speed < 60):
            if self.accel:
                self.accelerate(start_index=5, accel_index=60, color=2)
            else:
                self.reset_acceleration(55)
        elif (60 <= self.cur_speed < 65):
            if self.accel:
                self.accelerate(start_index=5, accel_index=65, color=2)
            else:
                self.reset_acceleration(60)
        elif (65 <= self.cur_speed < 70):
            if self.accel:
                self.accelerate(start_index=5, accel_index=70, color=2)
            else:
                self.reset_acceleration(65)
        elif (70 <= self.cur_speed < 75):
            if self.accel:
                self.accelerate(start_index=5, accel_index=75, color=3)
            else:
                self.reset_acceleration(70)
        elif (75 <= self.cur_speed < 80):
            if self.accel:
                self.accelerate(start_index=5, accel_index=80, color=3)
            else:
                self.reset_acceleration(75)
        elif (80 <= self.cur_speed < 85):
            if self.accel:
                self.accelerate(start_index=5, accel_index=85, color=3)
            else:
                self.reset_acceleration(80)
        elif (85 <= self.cur_speed < 90):
            if self.accel:
                self.accelerate(start_index=5, accel_index=90, color=3)
            else:
                self.reset_acceleration(85)
        elif (90 <= self.cur_speed < 95):
            if self.accel:
                self.accelerate(start_index=5, accel_index=95, color=4)
            else:
                self.reset_acceleration(90)
        elif (95 <= self.cur_speed < 100):
            if self.accel:
                self.accelerate(start_index=5, accel_index=100, color=4)
            else:
                self.reset_acceleration(95)
        elif (100 <= self.cur_speed < 105):
            if self.accel:
                self.accelerate(start_index=5, accel_index=100, color=4)
                self.accelerate(start_index=100, accel_index=105, color=5)
            else:
                self.reset_acceleration(100)
        elif (105 <= self.cur_speed < 110):
            if self.accel:
                self.accelerate(start_index=5, accel_index=100, color=4)
                self.accelerate(start_index=100, accel_index=110, color=5)
            else:
                self.reset_acceleration(105)
        elif (110 <= self.cur_speed < 115):
            if self.accel:
                self.accelerate(start_index=5, accel_index=100, color=4)
                self.accelerate(start_index=100, accel_index=115, color=5)
            else:
                self.reset_acceleration(110)
        elif (115 <= self.cur_speed < 120):
            if self.accel:
                self.accelerate(start_index=5, accel_index=100, color=4)
                self.accelerate(start_index=100, accel_index=120, color=5)
            else:
                self.reset_acceleration(115)
        elif (120 <= self.cur_speed < 125):
            if self.accel:
                self.accelerate(start_index=5, accel_index=100, color=4)
                self.accelerate(start_index=100, accel_index=125, color=5)
            else:
                self.reset_acceleration(120)
        elif (125 <= self.cur_speed < 130):
            if self.accel:
                self.accelerate(start_index=5, accel_index=100, color=4)
                self.accelerate(start_index=100, accel_index=125, color=5)
                self.accelerate(start_index=125, accel_index=130, color=6)
            else:
                self.reset_acceleration(125)
        elif (130 <= self.cur_speed < 135):
            if self.accel:
                self.accelerate(start_index=5, accel_index=100, color=4)
                self.accelerate(start_index=100, accel_index=125, color=5)
                self.accelerate(start_index=125, accel_index=135, color=6)
            else:
                self.reset_acceleration(130)
        elif (135 <= self.cur_speed < 140):
            if self.accel:
                self.accelerate(start_index=5, accel_index=100, color=4)
                self.accelerate(start_index=100, accel_index=125, color=5)
                self.accelerate(start_index=125, accel_index=135, color=6)
                self.accelerate(start_index=135, accel_index=140, color=7)
            else:
                self.reset_acceleration(135)
        elif (140 <= self.cur_speed < 145):
            if self.accel:
                self.accelerate(start_index=5, accel_index=100, color=4)
                self.accelerate(start_index=100, accel_index=125, color=5)
                self.accelerate(start_index=125, accel_index=135, color=6)
                self.accelerate(start_index=135, accel_index=145, color=7)
            else:
                self.reset_acceleration(140)
        elif (145 <= self.cur_speed < 150):
            if self.accel:
                self.accelerate(start_index=5, accel_index=100, color=4)
                self.accelerate(start_index=100, accel_index=125, color=5)
                self.accelerate(start_index=125, accel_index=135, color=6)
                self.accelerate(start_index=135, accel_index=150, color=7)
            else:
                self.reset_acceleration(145)
        elif (150 <= self.cur_speed < 155):
            if self.accel:
                self.accelerate(start_index=5, accel_index=100, color=4)
                self.accelerate(start_index=100, accel_index=125, color=5)
                self.accelerate(start_index=125, accel_index=135, color=6)
                self.accelerate(start_index=135, accel_index=150, color=7)
                self.accelerate(start_index=150, accel_index=155, color=8)
            else:
                self.reset_acceleration(150)
        elif (155 <= self.cur_speed < 160):
            if self.accel:
                self.accelerate(start_index=5, accel_index=100, color=4)
                self.accelerate(start_index=100, accel_index=125, color=5)
                self.accelerate(start_index=125, accel_index=135, color=6)
                self.accelerate(start_index=135, accel_index=150, color=7)
                self.accelerate(start_index=150, accel_index=160, color=8)
            else:
                self.reset_acceleration(155)
        elif (160 <= self.cur_speed < 165):
            if self.accel:
                self.accelerate(start_index=5, accel_index=100, color=4)
                self.accelerate(start_index=100, accel_index=125, color=5)
                self.accelerate(start_index=125, accel_index=135, color=6)
                self.accelerate(start_index=135, accel_index=150, color=7)
                self.accelerate(start_index=150, accel_index=160, color=8)
                self.accelerate(start_index=160, accel_index=165, color=9)
            else:
                self.reset_acceleration(160)
        elif (165 <= self.cur_speed < 170):
            if self.accel:
                self.accelerate(start_index=5, accel_index=100, color=4)
                self.accelerate(start_index=100, accel_index=125, color=5)
                self.accelerate(start_index=125, accel_index=135, color=6)
                self.accelerate(start_index=135, accel_index=150, color=7)
                self.accelerate(start_index=150, accel_index=160, color=8)
                self.accelerate(start_index=160, accel_index=170, color=9)
            else:
                self.reset_acceleration(165)
        elif (170 <= self.cur_speed < 175):
            if self.accel:
                self.accelerate(start_index=5, accel_index=100, color=4)
                self.accelerate(start_index=100, accel_index=125, color=5)
                self.accelerate(start_index=125, accel_index=135, color=6)
                self.accelerate(start_index=135, accel_index=150, color=7)
                self.accelerate(start_index=150, accel_index=160, color=8)
                self.accelerate(start_index=160, accel_index=175, color=9)
            else:
                self.reset_acceleration(170)
        elif (175 <= self.cur_speed < 180):
            if self.accel:
                self.accelerate(start_index=5, accel_index=100, color=4)
                self.accelerate(start_index=100, accel_index=125, color=5)
                self.accelerate(start_index=125, accel_index=135, color=6)
                self.accelerate(start_index=135, accel_index=150, color=7)
                self.accelerate(start_index=150, accel_index=160, color=8)
                self.accelerate(start_index=160, accel_index=180, color=9)
            else:
                self.reset_acceleration(175)
        elif (180 <= self.cur_speed < 185):
            if self.accel:
                self.accelerate(start_index=5, accel_index=100, color=4)
                self.accelerate(start_index=100, accel_index=125, color=5)
                self.accelerate(start_index=125, accel_index=135, color=6)
                self.accelerate(start_index=135, accel_index=150, color=7)
                self.accelerate(start_index=150, accel_index=160, color=8)
                self.accelerate(start_index=160, accel_index=180, color=9)
                self.accelerate(start_index=180, accel_index=185, color=10)
            else:
                self.reset_acceleration(180)
        elif (185 <= self.cur_speed < 190):
            if self.accel:
                self.accelerate(start_index=5, accel_index=100, color=4)
                self.accelerate(start_index=100, accel_index=125, color=5)
                self.accelerate(start_index=125, accel_index=135, color=6)
                self.accelerate(start_index=135, accel_index=150, color=7)
                self.accelerate(start_index=150, accel_index=160, color=8)
                self.accelerate(start_index=160, accel_index=180, color=9)
                self.accelerate(start_index=180, accel_index=190, color=10)
            else:
                self.reset_acceleration(185)
        elif (190 <= self.cur_speed < 195):
            if self.accel:
                self.accelerate(start_index=5, accel_index=100, color=4)
                self.accelerate(start_index=100, accel_index=125, color=5)
                self.accelerate(start_index=125, accel_index=135, color=6)
                self.accelerate(start_index=135, accel_index=150, color=7)
                self.accelerate(start_index=150, accel_index=160, color=8)
                self.accelerate(start_index=160, accel_index=180, color=9)
                self.accelerate(start_index=180, accel_index=195, color=10)
            else:
                self.reset_acceleration(190)
        elif (195 <= self.cur_speed < 200):
            if self.accel:
                self.accelerate(start_index=5, accel_index=100, color=4)
                self.accelerate(start_index=100, accel_index=125, color=5)
                self.accelerate(start_index=125, accel_index=135, color=6)
                self.accelerate(start_index=135, accel_index=150, color=7)
                self.accelerate(start_index=150, accel_index=160, color=8)
                self.accelerate(start_index=160, accel_index=180, color=9)
                self.accelerate(start_index=180, accel_index=200, color=10)
            else:
                self.reset_acceleration(195)
        elif (200 <= self.cur_speed < 210):
            if self.accel:
                self.accelerate(start_index=5, accel_index=100, color=4)
                self.accelerate(start_index=100, accel_index=125, color=5)
                self.accelerate(start_index=125, accel_index=135, color=6)
                self.accelerate(start_index=135, accel_index=150, color=7)
                self.accelerate(start_index=150, accel_index=160, color=8)
                self.accelerate(start_index=160, accel_index=180, color=9)
                self.accelerate(start_index=180, accel_index=200, color=10)
                self.accelerate(start_index=200, accel_index=210, color=11)
            else:
                self.reset_acceleration(200)
        elif (210 <= self.cur_speed < 215):
            if self.accel:
                self.accelerate(start_index=5, accel_index=100, color=4)
                self.accelerate(start_index=100, accel_index=125, color=5)
                self.accelerate(start_index=125, accel_index=135, color=6)
                self.accelerate(start_index=135, accel_index=150, color=7)
                self.accelerate(start_index=150, accel_index=160, color=8)
                self.accelerate(start_index=160, accel_index=180, color=9)
                self.accelerate(start_index=180, accel_index=200, color=10)
                self.accelerate(start_index=200, accel_index=210, color=11)
                self.accelerate(start_index=210, accel_index=215, color=12)
            else:
                self.reset_acceleration(210)
        elif (215 <= self.cur_speed < 220):
            if self.accel:
                self.accelerate(start_index=5, accel_index=100, color=4)
                self.accelerate(start_index=100, accel_index=125, color=5)
                self.accelerate(start_index=125, accel_index=135, color=6)
                self.accelerate(start_index=135, accel_index=150, color=7)
                self.accelerate(start_index=150, accel_index=160, color=8)
                self.accelerate(start_index=160, accel_index=180, color=9)
                self.accelerate(start_index=180, accel_index=200, color=10)
                self.accelerate(start_index=200, accel_index=210, color=11)
                self.accelerate(start_index=210, accel_index=220, color=12)
            else:
                self.reset_acceleration(215)
        elif (220 <= self.cur_speed < 225):
            if self.accel:
                self.accelerate(start_index=5, accel_index=100, color=4)
                self.accelerate(start_index=100, accel_index=125, color=5)
                self.accelerate(start_index=125, accel_index=135, color=6)
                self.accelerate(start_index=135, accel_index=150, color=7)
                self.accelerate(start_index=150, accel_index=160, color=8)
                self.accelerate(start_index=160, accel_index=180, color=9)
                self.accelerate(start_index=180, accel_index=200, color=10)
                self.accelerate(start_index=200, accel_index=210, color=11)
                self.accelerate(start_index=210, accel_index=225, color=12)
            else:
                self.reset_acceleration(220)
        elif (225 <= self.cur_speed < 230):
            if self.accel:
                self.accelerate(start_index=5, accel_index=100, color=4)
                self.accelerate(start_index=100, accel_index=125, color=5)
                self.accelerate(start_index=125, accel_index=135, color=6)
                self.accelerate(start_index=135, accel_index=150, color=7)
                self.accelerate(start_index=150, accel_index=160, color=8)
                self.accelerate(start_index=160, accel_index=180, color=9)
                self.accelerate(start_index=180, accel_index=200, color=10)
                self.accelerate(start_index=200, accel_index=210, color=11)
                self.accelerate(start_index=210, accel_index=225, color=12)
                self.accelerate(start_index=225, accel_index=230, color=13)
            else:
                self.reset_acceleration(225)
        elif (230 <= self.cur_speed < 235):
            if self.accel:
                self.accelerate(start_index=5, accel_index=100, color=4)
                self.accelerate(start_index=100, accel_index=125, color=5)
                self.accelerate(start_index=125, accel_index=135, color=6)
                self.accelerate(start_index=135, accel_index=150, color=7)
                self.accelerate(start_index=150, accel_index=160, color=8)
                self.accelerate(start_index=160, accel_index=180, color=9)
                self.accelerate(start_index=180, accel_index=200, color=10)
                self.accelerate(start_index=200, accel_index=210, color=11)
                self.accelerate(start_index=210, accel_index=225, color=12)
                self.accelerate(start_index=225, accel_index=235, color=13)
            else:
                self.reset_acceleration(230)
        elif (235 <= self.cur_speed < 240):
            if self.accel:
                self.accelerate(start_index=5, accel_index=100, color=4)
                self.accelerate(start_index=100, accel_index=125, color=5)
                self.accelerate(start_index=125, accel_index=135, color=6)
                self.accelerate(start_index=135, accel_index=150, color=7)
                self.accelerate(start_index=150, accel_index=160, color=8)
                self.accelerate(start_index=160, accel_index=180, color=9)
                self.accelerate(start_index=180, accel_index=200, color=10)
                self.accelerate(start_index=200, accel_index=210, color=11)
                self.accelerate(start_index=210, accel_index=225, color=12)
                self.accelerate(start_index=225, accel_index=240, color=13)
            else:
                self.reset_acceleration(235)
        elif (240 <= self.cur_speed < 245):
            if self.accel:
                self.accelerate(start_index=5, accel_index=100, color=4)
                self.accelerate(start_index=100, accel_index=125, color=5)
                self.accelerate(start_index=125, accel_index=135, color=6)
                self.accelerate(start_index=135, accel_index=150, color=7)
                self.accelerate(start_index=150, accel_index=160, color=8)
                self.accelerate(start_index=160, accel_index=180, color=9)
                self.accelerate(start_index=180, accel_index=200, color=10)
                self.accelerate(start_index=200, accel_index=210, color=11)
                self.accelerate(start_index=210, accel_index=225, color=12)
                self.accelerate(start_index=225, accel_index=240, color=13)
                self.accelerate(start_index=240, accel_index=245, color=14)
            else:
                self.reset_acceleration(240)
        elif (245 <= self.cur_speed < 250):
            if self.accel:
                self.accelerate(start_index=5, accel_index=100, color=4)
                self.accelerate(start_index=100, accel_index=125, color=5)
                self.accelerate(start_index=125, accel_index=135, color=6)
                self.accelerate(start_index=135, accel_index=150, color=7)
                self.accelerate(start_index=150, accel_index=160, color=8)
                self.accelerate(start_index=160, accel_index=180, color=9)
                self.accelerate(start_index=180, accel_index=200, color=10)
                self.accelerate(start_index=200, accel_index=210, color=11)
                self.accelerate(start_index=210, accel_index=225, color=12)
                self.accelerate(start_index=225, accel_index=240, color=13)
                self.accelerate(start_index=240, accel_index=245, color=14)
                self.accelerate(start_index=245, accel_index=250, color=15)
            else:
                self.reset_acceleration(245)
        elif (250 <= self.cur_speed < 255):
            if self.accel:
                self.accelerate(start_index=5, accel_index=100, color=4)
                self.accelerate(start_index=100, accel_index=125, color=5)
                self.accelerate(start_index=125, accel_index=135, color=6)
                self.accelerate(start_index=135, accel_index=150, color=7)
                self.accelerate(start_index=150, accel_index=160, color=8)
                self.accelerate(start_index=160, accel_index=180, color=9)
                self.accelerate(start_index=180, accel_index=200, color=10)
                self.accelerate(start_index=200, accel_index=210, color=11)
                self.accelerate(start_index=210, accel_index=225, color=12)
                self.accelerate(start_index=225, accel_index=240, color=13)
                self.accelerate(start_index=240, accel_index=245, color=14)
                self.accelerate(start_index=245, accel_index=255, color=15)
            else:
                self.reset_acceleration(250)
        elif (255 <= self.cur_speed < 260):
            if self.accel:
                self.accelerate(start_index=5, accel_index=100, color=4)
                self.accelerate(start_index=100, accel_index=125, color=5)
                self.accelerate(start_index=125, accel_index=135, color=6)
                self.accelerate(start_index=135, accel_index=150, color=7)
                self.accelerate(start_index=150, accel_index=160, color=8)
                self.accelerate(start_index=160, accel_index=180, color=9)
                self.accelerate(start_index=180, accel_index=200, color=10)
                self.accelerate(start_index=200, accel_index=210, color=11)
                self.accelerate(start_index=210, accel_index=225, color=12)
                self.accelerate(start_index=225, accel_index=240, color=13)
                self.accelerate(start_index=240, accel_index=245, color=14)
                self.accelerate(start_index=245, accel_index=260, color=15)
            else:
                self.reset_acceleration(255)
        elif (260 <= self.cur_speed < 265):
            if self.accel:
                self.accelerate(start_index=5, accel_index=100, color=4)
                self.accelerate(start_index=100, accel_index=125, color=5)
                self.accelerate(start_index=125, accel_index=135, color=6)
                self.accelerate(start_index=135, accel_index=150, color=7)
                self.accelerate(start_index=150, accel_index=160, color=8)
                self.accelerate(start_index=160, accel_index=180, color=9)
                self.accelerate(start_index=180, accel_index=200, color=10)
                self.accelerate(start_index=200, accel_index=210, color=11)
                self.accelerate(start_index=210, accel_index=225, color=12)
                self.accelerate(start_index=225, accel_index=240, color=13)
                self.accelerate(start_index=240, accel_index=245, color=14)
                self.accelerate(start_index=245, accel_index=265, color=15)
            else:
                self.reset_acceleration(260)
        elif (265 <= self.cur_speed < 270):
            if self.accel:
                self.accelerate(start_index=5, accel_index=100, color=4)
                self.accelerate(start_index=100, accel_index=125, color=5)
                self.accelerate(start_index=125, accel_index=135, color=6)
                self.accelerate(start_index=135, accel_index=150, color=7)
                self.accelerate(start_index=150, accel_index=160, color=8)
                self.accelerate(start_index=160, accel_index=180, color=9)
                self.accelerate(start_index=180, accel_index=200, color=10)
                self.accelerate(start_index=200, accel_index=210, color=11)
                self.accelerate(start_index=210, accel_index=225, color=12)
                self.accelerate(start_index=225, accel_index=240, color=13)
                self.accelerate(start_index=240, accel_index=245, color=14)
                self.accelerate(start_index=245, accel_index=270, color=15)
            else:
                self.reset_acceleration(265)
        elif (self.cur_speed >= 270):
            if self.accel:
                self.accelerate(start_index=5, accel_index=100, color=4)
                self.accelerate(start_index=100, accel_index=125, color=5)
                self.accelerate(start_index=125, accel_index=135, color=6)
                self.accelerate(start_index=135, accel_index=150, color=7)
                self.accelerate(start_index=150, accel_index=160, color=8)
                self.accelerate(start_index=160, accel_index=180, color=9)
                self.accelerate(start_index=180, accel_index=200, color=10)
                self.accelerate(start_index=200, accel_index=210, color=11)
                self.accelerate(start_index=210, accel_index=225, color=12)
                self.accelerate(start_index=225, accel_index=240, color=13)
                self.accelerate(start_index=240, accel_index=245, color=14)
                self.accelerate(start_index=245, accel_index=270, color=15)
                self.accel_kivi[270].color = (1, .1, 0, 3)
                self.accel_kivi[270].texture_update()
            else:
                # nothing to reset, too fast
                pass
        else:
            self.reset_acceleration()
            self.accel_kivi[5].color = (0, 0, .3, 0)
            self.accel_kivi[5].texture_update()


class Buttonlayout(BoxLayout):

    def __init__(self):
        super(Buttonlayout, self).__init__()

        with self.canvas.before:
            Color(0, 0, 0, 0)
            self.rect = Rectangle(size=self.size, pos=self.pos)

        self.bind(size=self.updates, pos=self.updates)

    def updates(self, instance, value):
        self.rect.size = instance.size
        self.rect.pos = instance.pos


class ListViewModal(ModalView):
    def __init__(self, **kwargs):
        super(ListViewModal, self).__init__(**kwargs)


class Toolbar(BoxLayout):
    def __init__(self, *args, **kwargs):
        super(Toolbar, self).__init__(**kwargs)

        self.size_hint_y = None
        self.height = '48dp'
        self.padding = '4dp'
        self.spacing = '4dp'

        with self.canvas:
            Color(.35, .35, .35, .35)
            self.rect = Rectangle(pos=self.pos, size=self.size)

        def update_rect(*args):
            self.rect.pos = (self.x, self.y)
            self.rect.size = (self.width, self.height)

        self.bind(pos=update_rect)
        self.bind(size=update_rect)


class MyMapView(MapView):
    grp = ObjectProperty(None)
    re_center = False

    def __init__(self, **kwargs):
        self.cache_path = App.get_running_app().user_data_dir
        zoom = kwargs['zoom']
        lat = kwargs['lat']
        lon = kwargs['lon']
        super().__init__(zoom=zoom, lat=lat, lon=lon, cache_dir=self.cache_path)


class Maplayout(RelativeLayout):

    def __init__(self, *args, **kwargs):
        super(Maplayout, self).__init__(**kwargs)
        self.sm = args[0]

        with self.canvas:
            Color(0, 0, 0, 0)
            self.rect = Rectangle(size=self.size, pos=self.pos)

        self.bind(size=self.updates, pos=self.updates)
        self.returnbutton_main = Button(pos_hint={'x': 0, 'y': 0}, text='<<<', font_size=100,
                                        bold=True, background_color=(.5, .5, .5, .5))
        self.returnbutton_main.bind(on_press=self.callback_return)
        self.center_button = Button(pos_hint ={'right': 1, 'top': 1}, text='Center', font_size=100,
                                        bold=True, background_color=(.5, .5, .5, .5))
        self.center_button.bind(on_press=self.callback_center)
        top_bar = Toolbar(pos_hint ={'right': 1, 'top': 1})
        top_bar.add_widget(self.center_button)
        bottom_bar = Toolbar()
        bottom_bar.add_widget(self.returnbutton_main)
        self.map_view = MyMapView(zoom=15, lat=0, lon=0)
        self.map_view.double_tap_zoom = True
        self.map_view.pause_on_action = True
        self.map_view.bind(on_zoom=self.callback_zoom)

        self.add_widget(self.map_view)
        self.add_widget(top_bar)
        self.add_widget(bottom_bar)

    def callback_return(self, instance):
        self.sm.current = 'Operative'

    def callback_center(self, instance):
        self.map_view.re_center = True

    def callback_zoom(self, instance, zoom):
        self.map_view.re_center = False

    def updates(self, instance, value):
        self.rect.size = instance.size
        self.rect.pos = instance.pos


class MainView(FloatLayout):

    def __init__(self, *args, **kwargs):
        super(MainView, self).__init__()
        self.sm = args[0]
        self.speed_cam_txt1 = 'Corridor Range '
        self.speed_cam_txt_range = '--.-'
        self.speed_cam_txt2 = ' km'

        with self.canvas.before:
            Color(0, 0, 0, 0)
            self.rect = Rectangle(size=self.size, pos=self.pos)

        self.bind(size=self.updates, pos=self.updates)

        '''self.speed_camera = Label(
            text=self.speed_cam_txt1 + self.speed_cam_txt_range + self.speed_cam_txt2,
            font_size=100, bold=True, pos=(0, 1000), size_hint=(1, 1))'''
        self.list_view_modal12 = ListViewModal(pos=(0, 420), size_hint=(1, .10))
        self.speedcam_fix_number = Label(text='0', pos=(0, 423), size_hint=(1.8, .10),
                                         font_size=50, bold=True)
        self.img_speedcam_fix = Image(source='images/fixcamera.png', pos=(0, 420),
                                      size_hint=(.4, .10))
        self.list_view_modal13 = ListViewModal(pos=(0, 750), size_hint=(1, .10))
        self.speedcam_trafficlight_number = Label(text='0', pos=(0, 753), size_hint=(1.8, .10),
                                                  font_size=50, bold=True)
        self.img_speedcam_trafficlight = Image(source='images/trafficlightcamera.png',
                                               pos=(0, 750), size_hint=(.4, .10))
        self.list_view_modal14 = ListViewModal(pos=(0, 1050), size_hint=(1, .10))
        self.speedcam_distance_number = Label(text='0', pos=(0, 1053), size_hint=(1.8, .10),
                                              font_size=50, bold=True)
        self.img_speedcam_distance = Image(source='images/distancecamera.png', pos=(0, 1050),
                                           size_hint=(.4, .10))
        self.list_view_modal15 = ListViewModal(pos=(0, 1350), size_hint=(1, .10))
        self.speedcam_mobil_number = Label(text='0', pos=(0, 1353), size_hint=(1.8, .10),
                                           font_size=50, bold=True)
        self.img_speedcam_mobil = Image(source='images/mobilcamera.png', pos=(0, 1350),
                                        size_hint=(.4, .10))
        self.list_view_modal16 = ListViewModal(pos=(0, 1650), size_hint=(1, .10))
        self.poi_number = Label(text='0', pos=(0, 1653), size_hint=(1.8, .10),
                                font_size=50, bold=True)
        self.img_poi = Image(source='images/poi.png', pos=(0, 1650),
                             size_hint=(.4, .10))
        self.returnbutton_main = Button(pos=(0, 0), size_hint=(1, .20), text='<<<', font_size=500,
                                        bold=True, background_color=(.5, .5, .5, .5))
        self.returnbutton_main.bind(on_press=self.callback_return)

        # self.add_widget(self.speed_camera)
        self.add_widget(self.list_view_modal12)
        self.add_widget(self.img_speedcam_fix)
        self.add_widget(self.speedcam_fix_number)
        self.add_widget(self.list_view_modal13)
        self.add_widget(self.img_speedcam_trafficlight)
        self.add_widget(self.speedcam_trafficlight_number)
        self.add_widget(self.list_view_modal14)
        self.add_widget(self.img_speedcam_distance)
        self.add_widget(self.speedcam_distance_number)
        self.add_widget(self.list_view_modal15)
        self.add_widget(self.img_speedcam_mobil)
        self.add_widget(self.speedcam_mobil_number)
        self.add_widget(self.list_view_modal16)
        self.add_widget(self.img_poi)
        self.add_widget(self.poi_number)
        self.add_widget(self.returnbutton_main)

    def callback_return(self, instance):
        self.sm.current = 'Operative'

    def updates(self, instance, value):
        self.rect.size = instance.size
        self.rect.pos = instance.pos

    # provide None in case any of the speed cams should not get updated
    def update_speed_cams(self, fix_cams, mobile_cams, traffic_cams, distance_cams):

        if mobile_cams is not None:
            self.speedcam_mobil_number.text = str(mobile_cams)
            Clock.schedule_once(self.speedcam_mobil_number.texture_update)
        if traffic_cams is not None:
            self.speedcam_trafficlight_number.text = str(traffic_cams)
            Clock.schedule_once(self.speedcam_trafficlight_number.texture_update)
        if fix_cams is not None:
            self.speedcam_fix_number.text = str(fix_cams)
            Clock.schedule_once(self.speedcam_fix_number.texture_update)
        if distance_cams is not None:
            self.speedcam_distance_number.text = str(distance_cams)
            Clock.schedule_once(self.speedcam_distance_number.texture_update)

    def update_pois(self, number):
        self.poi_number.text = str(number)
        Clock.schedule_once(self.poi_number.texture_update)

    def update_speed_cam_txt(self, l_range):
        '''self.speed_cam_txt_range = str(l_range)
        self.speed_camera.text = self.speed_cam_txt1 + self.speed_cam_txt_range + self.speed_cam_txt2
        Clock.schedule_once(self.speed_camera.texture_update)'''
        pass


class ResumeState():
    def __init__(self):
        self.resumed = True

    def set_resume_state(self, state):
        self.resumed = state

    def isResumed(self):
        return self.resumed


class MainTApp(App):

    def request_android_permissions(self):
        """
        Since API 23, Android requires permission to be requested at runtime.
        This function requests permission and handles the response via a
        callback.
        The request will produce a popup if permissions have not already been
        been granted, otherwise it will do nothing.
        """
        from android.permissions import request_permissions, Permission

        def callback(permissions, results):
            """
            Defines the callback to be fired when runtime permission
            has been granted or denied. This is not strictly required,
            but added for the sake of completeness.
            """
            if all([res for res in results]):
                print("callback. All permissions granted.")
            else:
                print("callback. Some permissions refused.")

        request_permissions([Permission.ACCESS_COARSE_LOCATION,
                             Permission.ACCESS_FINE_LOCATION, Permission.WRITE_EXTERNAL_STORAGE,
                             Permission.READ_EXTERNAL_STORAGE], callback)

    def build(self):
        self.gps_status = None
        self.gps_status_type = None
        self.event = {}

        try:
            gps.configure(on_location=self.on_location,
                          on_status=self.on_status)
        except NotImplementedError:
            import traceback
            traceback.print_exc()
            self.gps_status = None

        if platform == "android":
            self.request_android_permissions()

        return self.init()

    def set_configs(self):
        # Distance for POI lookup in km
        self.poi_distance = 30

    @mainthread
    def on_location(self, **kwargs):
        self.event['data'] = {}
        self.event['data']['gps'] = {}
        self.event['data']['gps'].update(
            {'latitude': kwargs['lat'],
             'longitude': kwargs['lon'],
             'speed': kwargs['speed'],
             'bearing': kwargs['bearing'],
             'accuracy': kwargs['accuracy']})
        self.gps_data_queue.produce(self.cv_gps_data, {'event': self.event})

    @mainthread
    def on_status(self, stype, status):
        self.gps_status = str(status)
        self.gps_status_type = str(stype)
        self.gps_data_queue.produce(self.cv_gps_data, {'status': self.gps_status})

    def init(self):

        # set config items
        self.set_configs()

        self.day_update_done = False
        self.night_update_done = False
        self.key_pressed = False
        self.connection = None
        self.battery_checked = False
        ## Start our service
        self.start_service()

        ## Our Screenmanager ##
        self.sm = ScreenManager(transition=WipeTransition())

        # the poi reader instance, which is going to be initiated
        self.poireader = None

        ## Resume State instance ##
        self.resume = ResumeState()

        ## Global GUI attributes ##
        self.threads = []
        self.stopped = False
        self.started = False
        self.gps_producer = None
        self.calculator = None
        self.osm_init = None
        self.speedwarner = None
        self.worker = None
        self.osm_thread = None
        self.worker_list = []

        ## Stuff used by more than one Thread
        self.q = ThreadCondition(False)
        self.cv = Condition()
        self.cv_voice = Condition()
        self.cv_vector = Condition()
        self.cv_average_angle = Condition()
        self.cv_interrupt = Condition()
        self.cv_speedcam = Condition()
        self.cv_overspeed = Condition()
        self.cv_currentspeed = Condition()
        self.cv_osm = Condition()
        self.cv_map = Condition()
        self.cv_border = Condition()
        self.cv_border_reverse = Condition()
        self.cv_poi = Condition()
        self.cv_gps_data = Condition()
        self.poi_queue = PoiQueue()
        self.vdata = VectorDataPoolQueue()
        self.gpsqueue = GPSQueue()
        self.voice_prompt_queue = VoicePromptQueue()
        self.average_angle_queue = AverageAngleQueue()
        self.interruptqueue = InterruptQueue()
        self.map_queue = MapQueue()
        self.speed_cam_queue = SpeedCamQueue()
        self.overspeed_queue = OverspeedQueue()
        self.currentspeed_queue = CurrentSpeedQueue()
        self.gps_data_queue = GpsDataQueue()
        self.gps = None

        ## The Operative Gui##
        self.menubutton = Button(text='>>>', font_size=150, background_color=(.6, .6, .6, .6),
                                 bold=True, pos_hint={"left": 1}, size_hint=(.5, .5))
        self.nightbutton = Button(text='Night', bold=True, font_size=80, pos_hint={"right": 1},
                                  size_hint=(.5, .5), background_color=(.7, .7, .7, .7))
        self.infobutton = Button(text='Info', bold=True, font_size=80, pos_hint={"middle": 1},
                                 size_hint=(.5, .5), background_color=(.68, .68, .68, .68))
        self.mapbutton = Button(text='Map', bold=True, font_size=80, pos_hint={"right": 1},
                                size_hint=(.5, .5), background_color=(.65, .65, .65, .65))
        self.poibutton = Button(text='POIS', bold=True, font_size=80, pos_hint={"right": 1},
                                size_hint=(.5, .5), background_color=(.62, .62, .62, .62))
        self.startbutton = Button(text='Start', bold=True, font_size=200,
                                  background_color=(.7, .7, .7, .7))
        self.stopbutton = Button(text='Stop', bold=True, font_size=200,
                                 background_color=(.6, .6, .6, .6))
        self.exitbutton = Button(text='Exit', bold=True, font_size=200,
                                 background_color=(.5, .5, .5, .5))
        self.returnbutton = Button(background_color=(0, 0, 0, 0), bold=True, font_size=600,
                                   text='<<<')

        self.menubutton.bind(on_press=self.callback_menu)
        self.infobutton.bind(on_press=self.callback_info)
        self.mapbutton.bind(on_press=self.callback_map)
        self.poibutton.bind(on_press=self.callback_poi)
        self.returnbutton.bind(on_press=self.callback_return)

        self.startbutton.bind(on_press=self.callback_start)
        self.stopbutton.bind(on_press=self.callback_stop)
        self.exitbutton.bind(on_press=self.callback_exit)
        self.nightbutton.bind(on_press=self.callback_day_night)

        ## The Boxlayout of the Operative Gui##
        self.root = BoxLayout(orientation='vertical')

        root_action = BoxLayout(orientation='vertical')
        root_action.add_widget(self.startbutton)
        root_action.add_widget(self.stopbutton)
        root_action.add_widget(self.exitbutton)
        root_action.add_widget(self.returnbutton)
        root_main = BoxLayout(orientation='vertical')
        self.root_add = Cameralayout(self.sm, self, self.voice_prompt_queue, self.cv_voice,
                                     orientation='vertical')

        self.g = Gpslayout(self.sm, self)
        self.ms = MaxSpeedlayout(self.g)
        self.maxspeed = self.ms.get_maxspeed_label()
        self.s = Speedlayout()
        self.cl = CurveLayout()
        self.b = Buttonlayout()
        self.ml = MainView(self.sm)
        self.root_table = Poilayout(self.sm, self.ml, self, self.voice_prompt_queue, self.cv_voice)
        self.map_layout = Maplayout(self.sm)
        self.osm_wrapper = maps(self.map_layout)

        self.b.add_widget(self.menubutton)
        self.b.add_widget(self.infobutton)
        self.b.add_widget(self.mapbutton)
        self.b.add_widget(self.poibutton)
        self.b.add_widget(self.nightbutton)

        self.root.add_widget(self.g)
        self.root.add_widget(self.ms)
        self.root.add_widget(self.s)
        self.root.add_widget(self.cl)
        self.root.add_widget(self.b)
        root_main.add_widget(self.ml)

        s1 = Screen(name='Operative')
        s2 = Screen(name='Actions')
        s3 = Screen(name='Info')
        s4 = Screen(name='Add')
        s5 = Screen(name='Poi')
        s6 = Screen(name='Map')
        s1.add_widget(self.root)
        s2.add_widget(root_action)
        s3.add_widget(root_main)
        s4.add_widget(self.root_add)
        s5.add_widget(self.root_table)
        s6.add_widget(self.map_layout)

        self.sm.add_widget(s1)
        self.sm.add_widget(s2)
        self.sm.add_widget(s3)
        self.sm.add_widget(s4)
        self.sm.add_widget(s5)
        self.sm.add_widget(s6)

        self.callback_menu(self)
        return self.sm

    def pass_bot_objects(self):
        return self.gps_producer, self.calculator, self.speedwarner

    def init_osm(self, gps_thread, calculator_thread, osm_wrapper, cv_map, map_queue):
        self.osm_init = OSM_INIT(gps_thread, calculator_thread, osm_wrapper, cv_map, map_queue)

    def init_osm_thread(self, resume, osm_wrapper, calculator_thread, cv_map, cv_poi, map_queue,
                        poi_queue, gps_producer, cond):
        self.osm_thread = OSMThread(resume, osm_wrapper, calculator_thread, cv_map, cv_poi,
                                    map_queue, poi_queue, gps_producer, cond)
        self.threads.append(self.osm_thread)
        logger.print_log_line(" Start osm thread")
        self.osm_thread.setDaemon(True)
        self.osm_thread.start()

    def init_gps_producer(self,
                          g,
                          cv,
                          cv_vector,
                          cv_voice,
                          cv_average_angle,
                          voice_prompt_queue,
                          ms,
                          vdata,
                          gpsqueue,
                          average_angle_queue,
                          cv_map,
                          map_queue,
                          osm_wrapper,
                          cv_currentspeed,
                          currentspeed_queue,
                          cv_gps_data,
                          cv_gps_data_queue,
                          cv_speedcam,
                          speed_cam_queue,
                          calculator,
                          cond):
        self.gps_producer = GPSThread(g,
                                      cv,
                                      cv_vector,
                                      cv_voice,
                                      cv_average_angle,
                                      voice_prompt_queue,
                                      ms,
                                      vdata,
                                      gpsqueue,
                                      average_angle_queue,
                                      cv_map,
                                      map_queue,
                                      osm_wrapper,
                                      cv_currentspeed,
                                      currentspeed_queue,
                                      cv_gps_data,
                                      cv_gps_data_queue,
                                      cv_speedcam,
                                      speed_cam_queue,
                                      calculator,
                                      cond)
        self.threads.append(self.gps_producer)
        logger.print_log_line(" Start gps producer thread")
        self.gps_producer.setDaemon(True)
        self.gps_producer.start()

    def init_gps_consumer(self, resume, cv, curspeed, bearing, gpsqueue, s, cl, cond):
        self.gps_consumer = GPSConsumerThread(resume, cv, curspeed, bearing, gpsqueue, s,
                                              cl, cond)
        self.threads.append(self.gps_consumer)
        logger.print_log_line(" Start gps consumer thread")
        self.gps_consumer.setDaemon(True)
        self.gps_consumer.start()

    def init_voice_consumer(self, resume, cv_voice, voice_prompt_queue, cond):
        self.voice_consumer = VoicePromptThread(resume, cv_voice, voice_prompt_queue, cond)
        self.threads.append(self.voice_consumer)
        logger.print_log_line(" Start accustic voice thread")
        self.voice_consumer.setDaemon(True)
        self.voice_consumer.start()

    def init_deviation_checker(self, resume, cv_average_angle, cv_interrupt, average_angle_queue,
                               interruptqueue, av_bearing_value, cond):
        self.deviation_checker = DeviationCheckerThread(resume,
                                                        cv_average_angle,
                                                        cv_interrupt,
                                                        average_angle_queue,
                                                        interruptqueue,
                                                        av_bearing_value,
                                                        cond)
        self.threads.append(self.deviation_checker)
        logger.print_log_line(" Start deviation thread")
        self.deviation_checker.setDaemon(True)
        self.deviation_checker.start()

    def init_calculator(self,
                        cv_vector,
                        cv_voice,
                        cv_interrupt,
                        cv_speedcam,
                        cv_overspeed,
                        cv_border,
                        cv_border_reverse,
                        gpssignalqueue,
                        interruptqueue,
                        speedcamqueue,
                        overspeed_queue,
                        cv_currentspeed,
                        currentspeed_queue,
                        cv_poi,
                        poi_queue,
                        cv_map,
                        map_queue,
                        ms,
                        s,
                        ml,
                        vdata,
                        osm_wrapper,
                        cond):
        self.calculator = RectangleCalculatorThread(cv_vector,
                                                    cv_voice,
                                                    cv_interrupt,
                                                    cv_speedcam,
                                                    cv_overspeed,
                                                    cv_border,
                                                    cv_border_reverse,
                                                    gpssignalqueue,
                                                    interruptqueue,
                                                    speedcamqueue,
                                                    overspeed_queue,
                                                    cv_currentspeed,
                                                    currentspeed_queue,
                                                    cv_poi,
                                                    poi_queue,
                                                    cv_map,
                                                    map_queue,
                                                    ms,
                                                    s,
                                                    ml,
                                                    vdata,
                                                    osm_wrapper,
                                                    cond)
        self.threads.append(self.calculator)
        logger.print_log_line(" Start calculator thread")
        self.calculator.setDaemon(True)
        self.calculator.start()

        return self.calculator

    def init_speed_cam_warner(self, cv_voice, cv_speedcam, gpssignalqueue, speedcamqueue,
                              cv_overspeed, overspeed_queue, osm_wrapper, calculator, ms, g,
                              cond):
        self.speedwarner = SpeedCamWarnerThread(cv_voice, cv_speedcam, gpssignalqueue,
                                                speedcamqueue, cv_overspeed, overspeed_queue,
                                                osm_wrapper, calculator, ms, g, cond)
        self.threads.append(self.speedwarner)
        logger.print_log_line(" Start speed warner thread")
        self.speedwarner.setDaemon(True)
        self.speedwarner.start()

    def init_overspeed_checker(self, resume, cv_overspeed, overspeed_queue, cv_currentspeed,
                               currentspeed_queue, s, cond):
        self.overspeed_checker = OverspeedCheckerThread(resume, cv_overspeed, overspeed_queue,
                                                        cv_currentspeed, currentspeed_queue, s,
                                                        cond)
        self.threads.append(self.overspeed_checker)
        logger.print_log_line(" Start overspeed checker thread")
        self.overspeed_checker.setDaemon(True)
        self.overspeed_checker.start()

    def callback_info(self, instance):
        self.sm.current = 'Info'

    def callback_poi(self, instance):
        if isinstance(self.gps_producer, GPSThread) and isinstance(self.calculator,
                                                                   RectangleCalculatorThread) and \
                isinstance(self.speedwarner, SpeedCamWarnerThread):
            if not self.gps_producer.get_current_gps_state():
                popup = Popup(title='Attention',
                              content=Label(text='No valid GPS position!'),
                              size_hint=(None, None), size=(600, 600))
                popup.open()
                return
        else:
            self.ml.update_pois(0)
            popup = Popup(title='Attention',
                          content=Label(text='Please start App first!'),
                          size_hint=(None, None), size=(600, 600))
            popup.open()
            return
        self.sm.current = 'Poi'

    def callback_map(self, instance):
        if not isinstance(self.gps_producer, GPSThread):
            popup = Popup(title='Attention',
                          content=Label(text='Please start App first!'),
                          size_hint=(None, None), size=(600, 600))
            popup.open()
        elif not self.calculator.internet_available():
            popup = Popup(title='Attention',
                          content=Label(text='No Internet Connection!'),
                          size_hint=(None, None), size=(600, 600))
            popup.open()
        else:
            self.init_osm(self.gps_producer, self.calculator, self.osm_wrapper, self.cv_map,
                          self.map_queue)
            if self.osm_init.is_online():
                self.sm.current = 'Map'
            else:
                if self.osm_init.error_code == 1:
                    popup = Popup(title='Attention',
                                  content=Label(text='Please start App First!'),
                                  size_hint=(None, None), size=(500, 500))
                    popup.open()
                elif self.osm_init.error_code == 2:
                    popup = Popup(title='Attention',
                                  content=Label(text='No valid GPS position'),
                                  size_hint=(None, None), size=(500, 500))
                    popup.open()

    def callback_menu(self, instance):
        self.sm.current = 'Actions'

    def callback_return(self, instance):
        self.sm.current = 'Operative'

    def callback_exit(self, instance):
        gps.stop()
        self.q.set_terminate_state(True)
        self.root_table.stop_thread = True

        self.osc_server.stop()  # Stop the default socket
        self.osc_server.stop_all()  # Stop all sockets
        self.osc_server.close()  # Close the default socket
        self.osc_server.terminate_server()  # Request the handler thread to stop looping
        self.osc_server.join_server()  # Wait for the handler thread to finish pending tasks and exit
        self.voice_prompt_queue.clear_gpssignalqueue(self.cv_voice)
        self.gpsqueue.clear_gpsqueue(self.cv)
        self.average_angle_queue.clear_average_angle_data(self.cv_average_angle)
        self.vdata.clear_vector_data(self.cv_vector)
        self.overspeed_queue.clear_overspeedqueue(self.cv_overspeed)
        self.interruptqueue.clear_interruptqueue(self.cv_interrupt)
        self.speed_cam_queue.clear_camqueue(self.cv_speedcam)

        for thread in self.root_table.route_providers:
            self.root_table.route_providers.remove(thread)
            thread.join()

        # terminate poi reader timer
        if self.poireader is not None:
            self.poireader.stop_timer()

        for thread in self.threads:
            if thread.is_alive():
                logger.print_log_line(' %s still alive!' % thread)

                self.voice_prompt_queue.produce_gpssignal(self.cv_voice, 'EXIT_APPLICATION')
                self.gps_data_queue.produce(self.cv_gps_data, {'EXIT': True})
                self.gpsqueue.produce(self.cv, {'EXIT': 1})
                self.average_angle_queue.produce(self.cv_average_angle, 'TERMINATE')
                self.vdata.set_vector_data(self.cv_vector, 'vector_data', float(0.0),
                                           float(0.0), float(0.0), float(0.0), '-', 'EXIT', 0)
                self.currentspeed_queue.produce(self.cv_currentspeed, 'EXIT')
                self.interruptqueue.produce(self.cv_interrupt, 'TERMINATE')
                self.speed_cam_queue.produce(self.cv_speedcam,
                                             {'ccp': '(EXIT, EXIT)', 'fix_cam': (False, 0, 0),
                                              'traffic_cam': (False, 0, 0),
                                              'distance_cam': (False, 0, 0),
                                              'mobile_cam': (False, 0, 0),
                                              'ccp_node': (None, None),
                                              'list_tree': (None, None)})
                self.map_queue.produce(self.cv_map, "EXIT")

        logger.print_log_line(' DONE!')
        self.stop()
        sys.exit(0)

    def callback_stop(self, instance):
        self.sm.current = 'Operative'
        if self.stopped:
            pass
        else:
            gps.stop()
            RectangleCalculatorThread.thread_lock = False
            self.stopped = True
            self.started = False
            self.root_table.stop_thread = True
            self.q.set_terminate_state(True)
            self.g.off_state()
            self.gps_producer = None
            self.calculator = None

            # terminate poi reader timer
            if self.poireader is not None:
                self.poireader.stop_timer()

            # make sure threads are terminating
            self.voice_prompt_queue.clear_gpssignalqueue(self.cv_voice)
            self.gpsqueue.clear_gpsqueue(self.cv)
            self.average_angle_queue.clear_average_angle_data(self.cv_average_angle)
            self.vdata.clear_vector_data(self.cv_vector)
            self.overspeed_queue.clear_overspeedqueue(self.cv_overspeed)
            self.interruptqueue.clear_interruptqueue(self.cv_interrupt)
            self.speed_cam_queue.clear_camqueue(self.cv_speedcam)
            self.map_queue.clear_map_update(self.cv_map)
            self.currentspeed_queue.clear(self.cv_currentspeed)

            for thread in self.root_table.route_providers:
                self.root_table.route_providers.remove(thread)
                thread.join()

            for thread in self.threads:
                while thread.is_alive():
                    logger.print_log_line(' %s still alive!' % thread)

                    self.voice_prompt_queue.produce_gpssignal(self.cv_voice,
                                                              'STOP_APPLICATION')
                    self.gpsqueue.produce(self.cv, {'EXIT': 1})
                    self.gps_data_queue.produce(self.cv_gps_data, {'EXIT': True})
                    self.average_angle_queue.produce(self.cv_average_angle, 'TERMINATE')
                    self.interruptqueue.produce(self.cv_interrupt, 'TERMINATE')
                    self.vdata.set_vector_data(self.cv_vector, 'vector_data', float(0.0),
                                               float(0.0), float(0.0), float(0.0), '-', 'EXIT', 0)
                    self.currentspeed_queue.produce(self.cv_currentspeed, 'EXIT')
                    self.speed_cam_queue.produce(self.cv_speedcam, {'ccp': '(EXIT, EXIT)',
                                                                    'fix_cam': (False, 0, 0),
                                                                    'traffic_cam': (
                                                                        False, 0, 0),
                                                                    'distance_cam': (
                                                                        False, 0, 0),
                                                                    'mobile_cam': (
                                                                        False, 0, 0),
                                                                    'ccp_node': (None, None),
                                                                    'list_tree': (None, None)})
                    self.map_queue.produce(self.cv_map, "EXIT")
                    thread.join(float(3))
                    # try it once again
                    self.interruptqueue.produce(self.cv_interrupt, 'TERMINATE')
                    self.vdata.set_vector_data(self.cv_vector, 'vector_data', float(0.0),
                                               float(0.0), float(0.0), float(0.0), '-', 'EXIT', 0)

            self.threads = []
            self.gps_data_queue.clear(self.cv_gps_data)
            self.voice_prompt_queue.clear_gpssignalqueue(self.cv_voice)
            self.gpsqueue.clear_gpsqueue(self.cv)
            self.average_angle_queue.clear_average_angle_data(self.cv_average_angle)
            self.vdata.clear_vector_data(self.cv_vector)
            self.overspeed_queue.clear_overspeedqueue(self.cv_overspeed)
            self.interruptqueue.clear_interruptqueue(self.cv_interrupt)
            self.speed_cam_queue.clear_camqueue(self.cv_speedcam)
            self.map_queue.clear_map_update(self.cv_map)
            self.currentspeed_queue.clear(self.cv_currentspeed)
            self.maxspeed.text = 'STOPPED'
            self.maxspeed.color = (1, .9, 0, 2)
            self.maxspeed.font_size = 130
            Clock.schedule_once(self.maxspeed.texture_update)

    def callback_start(self, instance):
        self.sm.current = 'Operative'
        if self.started:
            pass
        else:
            gps.start(1000, 0)
            # send a message to our service
            self.send_ping()
            self.q.set_terminate_state(False)

            self.maxspeed.text = ''
            self.maxspeed.color = (1, 1, 1, 1)
            self.maxspeed.font_size = 180
            Clock.schedule_once(self.maxspeed.texture_update)

            calculator = self.init_calculator(self.cv_vector,
                                              self.cv_voice,
                                              self.cv_interrupt,
                                              self.cv_speedcam,
                                              self.cv_overspeed,
                                              self.cv_border,
                                              self.cv_border_reverse,
                                              self.voice_prompt_queue,
                                              self.interruptqueue,
                                              self.speed_cam_queue,
                                              self.overspeed_queue,
                                              self.cv_currentspeed,
                                              self.currentspeed_queue,
                                              self.cv_poi,
                                              self.poi_queue,
                                              self.cv_map,
                                              self.map_queue,
                                              self.ms,
                                              self.s,
                                              self.ml,
                                              self.vdata,
                                              self.osm_wrapper,
                                              self.q)

            self.init_deviation_checker(self.resume,
                                        self.cv_average_angle,
                                        self.cv_interrupt,
                                        self.average_angle_queue,
                                        self.interruptqueue,
                                        self.s.av_bearing_value,
                                        self.q)
            self.init_gps_producer(self.g,
                                   self.cv,
                                   self.cv_vector,
                                   self.cv_voice,
                                   self.cv_average_angle,
                                   self.voice_prompt_queue,
                                   self.ms,
                                   self.vdata,
                                   self.gpsqueue,
                                   self.average_angle_queue,
                                   self.cv_map,
                                   self.map_queue,
                                   self.osm_wrapper,
                                   self.cv_currentspeed,
                                   self.currentspeed_queue,
                                   self.cv_gps_data,
                                   self.gps_data_queue,
                                   self.cv_speedcam,
                                   self.speed_cam_queue,
                                   calculator,
                                   self.q)
            self.init_gps_consumer(self.resume,
                                   self.cv,
                                   self.s.curspeed,
                                   self.s.bearing,
                                   self.gpsqueue,
                                   self.s,
                                   self.cl,
                                   self.q)
            self.init_voice_consumer(self.resume, self.cv_voice, self.voice_prompt_queue, self.q)
            self.init_osm_thread(self.resume,
                                 self.osm_wrapper,
                                 self.calculator,
                                 self.cv_map,
                                 self.cv_poi,
                                 self.map_queue,
                                 self.poi_queue,
                                 self.gps_producer,
                                 self.q)
            self.init_speed_cam_warner(self.cv_voice,
                                       self.cv_speedcam,
                                       self.voice_prompt_queue,
                                       self.speed_cam_queue,
                                       self.cv_overspeed,
                                       self.overspeed_queue,
                                       self.osm_wrapper,
                                       calculator,
                                       self.ms,
                                       self.g,
                                       self.q)
            self.init_overspeed_checker(self.resume,
                                        self.cv_overspeed,
                                        self.overspeed_queue,
                                        self.cv_currentspeed,
                                        self.currentspeed_queue,
                                        self.s,
                                        self.q)

            self.poireader = POIReader(self.cv_speedcam,
                                       self.speed_cam_queue,
                                       self.gps_producer,
                                       self.calculator,
                                       self.osm_wrapper,
                                       self.map_queue,
                                       self.cv_map)
            self.started = True
            self.stopped = False

    def callback_day_night(self, instance):
        if self.nightbutton.text == 'Night':
            self.nightbutton.text = 'Day'
            self.nightbutton.texture_update()
            self.ms.imwarner.color = (0, 1, .3, .8)
            self.ms.imwarner.texture_update()
            self.s.gps_accuracy.color = (0, 1, .3, .8)
            self.s.gps_accuracy.texture_update()
            self.ms.roadname.color = (0, 1, .3, .8)
            self.ms.roadname.texture_update()
            self.ms.bar_meters.color = (1, 0, 0, 3)
            self.ms.bar_meters.texture_update()
            self.s.curspeed.color = (0, 1, .3, .8)
            self.s.curspeed.texture_update()
            self.cl.sd_y.color = (0, 1, .3, .8)
            self.cl.sd_y.texture_update()
            self.cl.sd_x.color = (0, 1, .3, .8)
            self.cl.sd_x.texture_update()
            self.s.bearing.color = (0, 1, .3, .8)
            self.s.bearing.texture_update()
            self.s.av_bearing.color = (0, 1, .3, .8)
            self.s.av_bearing.texture_update()
            self.s.av_bearing_value.color = (0, 1, .3, .8)
            self.s.av_bearing_value.texture_update()
            self.startbutton.color = (0, 1, .3, .8)
            self.startbutton.texture_update()
            self.stopbutton.color = (1, 0, 0, 3)
            self.stopbutton.texture_update()
            self.exitbutton.color = (1, 0, 0, 3)
            self.exitbutton.texture_update()
            self.root_add.policebutton.color = (1, 0, 0, 3)
            self.root_add.policebutton.texture_update()
            # self.ml.speed_camera.color = (0, 1, .3, .8)
            # self.ml.speed_camera.texture_update()
            self.ml.speedcam_fix_number.color = (0, 1, .3, .8)
            self.ml.speedcam_fix_number.texture_update()
            self.ml.speedcam_mobil_number.color = (0, 1, .3, .8)
            self.ml.speedcam_mobil_number.texture_update()
            self.ml.speedcam_trafficlight_number.color = (0, 1, .3, .8)
            self.ml.speedcam_trafficlight_number.texture_update()
            self.ml.speedcam_distance_number.color = (0, 1, .3, .8)
            self.ml.speedcam_distance_number.texture_update()
            self.ml.poi_number.color = (0, 1, .3, .8)
            self.ml.poi_number.texture_update()
            self.s.service_unit.color = (0, 1, .3, .8)
            self.s.service_unit.texture_update()
            self.root_table.poibutton.color = (0, 1, .3, .8)
            self.root_table.poibutton.texture_update()
            self.root_table.label_h.color = (0, 1, .3, .8)
            self.root_table.label_h.texture_update()
            self.root_table.label_g.color = (0, 1, .3, .8)
            self.root_table.label_g.texture_update()
        else:
            self.nightbutton.text = 'Night'
            self.nightbutton.texture_update()
            self.ms.imwarner.color = (1, 1, 1, 1)
            self.ms.imwarner.texture_update()
            self.s.gps_accuracy.color = (1, 1, 1, 1)
            self.s.gps_accuracy.texture_update()
            self.ms.roadname.color = (1, 1, 1, 1)
            self.ms.roadname.texture_update()
            self.ms.bar_meters.color = (1, 1, 1, 1)
            self.ms.bar_meters.texture_update()
            self.s.curspeed.color = (1, 1, 1, 1)
            self.s.curspeed.texture_update()
            self.cl.sd_y.color = (1, 1, 1, 1)
            self.cl.sd_y.texture_update()
            self.cl.sd_x.color = (1, 1, 1, 1)
            self.cl.sd_x.texture_update()
            self.s.bearing.color = (1, 1, 1, 1)
            self.s.bearing.texture_update()
            self.s.av_bearing.color = (1, 1, 1, 1)
            self.s.av_bearing.texture_update()
            self.s.av_bearing_value.color = (1, 1, 1, 1)
            self.s.av_bearing_value.texture_update()
            self.startbutton.color = (1, 1, 1, 1)
            self.startbutton.texture_update()
            self.stopbutton.color = (1, 1, 1, 1)
            self.stopbutton.texture_update()
            self.exitbutton.color = (1, 1, 1, 1)
            self.exitbutton.texture_update()
            self.root_add.policebutton.color = (1, 1, 1, 1)
            self.root_add.policebutton.texture_update()
            # self.ml.speed_camera.color = (1, 1, 1, 1)
            # self.ml.speed_camera.texture_update()
            self.ml.speedcam_fix_number.color = (1, 1, 1, 1)
            self.ml.speedcam_fix_number.texture_update()
            self.ml.speedcam_mobil_number.color = (1, 1, 1, 1)
            self.ml.speedcam_mobil_number.texture_update()
            self.ml.speedcam_trafficlight_number.color = (1, 1, 1, 1)
            self.ml.speedcam_trafficlight_number.texture_update()
            self.ml.speedcam_distance_number.color = (1, 1, 1, 1)
            self.ml.speedcam_distance_number.texture_update()
            self.ml.poi_number.color = (1, 1, 1, 1)
            self.ml.poi_number.texture_update()
            self.s.service_unit.color = (1, 1, 1, 1)
            self.s.service_unit.texture_update()
            self.root_table.poibutton.color = (1, 1, 1, 1)
            self.root_table.poibutton.texture_update()
            self.root_table.label_h.color = (1, 1, 1, 1)
            self.root_table.label_h.texture_update()
            self.root_table.label_g.color = (1, 1, 1, 1)
            self.root_table.label_g.texture_update()
        self.day_update_done = True
        self.night_update_done = True

    def callback_night_auto(self, instance):
        self.nightbutton.text = 'Day'
        self.nightbutton.texture_update()
        self.ms.imwarner.color = (0, 1, .3, .8)
        self.ms.imwarner.texture_update()
        self.s.gps_accuracy.color = (0, 1, .3, .8)
        self.s.gps_accuracy.texture_update()
        self.ms.roadname.color = (0, 1, .3, .8)
        self.ms.roadname.texture_update()
        self.ms.bar_meters.color = (1, 0, 0, 3)
        self.ms.bar_meters.texture_update()
        self.s.curspeed.color = (0, 1, .3, .8)
        self.s.curspeed.texture_update()
        self.cl.sd_y.color = (0, 1, .3, .8)
        self.cl.sd_y.texture_update()
        self.cl.sd_x.color = (0, 1, .3, .8)
        self.cl.sd_x.texture_update()
        self.s.bearing.color = (0, 1, .3, .8)
        self.s.bearing.texture_update()
        self.s.av_bearing.color = (0, 1, .3, .8)
        self.s.av_bearing.texture_update()
        self.s.av_bearing_value.color = (0, 1, .3, .8)
        self.s.av_bearing_value.texture_update()
        self.startbutton.color = (0, 1, .3, .8)
        self.startbutton.texture_update()
        self.stopbutton.color = (1, 0, 0, 3)
        self.stopbutton.texture_update()
        self.exitbutton.color = (1, 0, 0, 3)
        self.exitbutton.texture_update()
        self.root_add.policebutton.color = (1, 0, 0, 3)
        self.root_add.policebutton.texture_update()
        # self.ml.speed_camera.color = (0, 1, .3, .8)
        # self.ml.speed_camera.texture_update()
        self.ml.speedcam_fix_number.color = (0, 1, .3, .8)
        self.ml.speedcam_fix_number.texture_update()
        self.ml.speedcam_mobil_number.color = (0, 1, .3, .8)
        self.ml.speedcam_mobil_number.texture_update()
        self.ml.speedcam_trafficlight_number.color = (0, 1, .3, .8)
        self.ml.speedcam_trafficlight_number.texture_update()
        self.ml.speedcam_distance_number.color = (0, 1, .3, .8)
        self.ml.speedcam_distance_number.texture_update()
        self.ml.poi_number.color = (0, 1, .3, .8)
        self.ml.poi_number.texture_update()
        self.s.service_unit.color = (0, 1, .3, .8)
        self.s.service_unit.texture_update()
        self.root_table.poibutton.color = (0, 1, .3, .8)
        self.root_table.poibutton.texture_update()
        self.root_table.label_h.color = (0, 1, .3, .8)
        self.root_table.label_h.texture_update()
        self.root_table.label_g.color = (0, 1, .3, .8)
        self.root_table.label_g.texture_update()

    def callback_day_auto(self, instance):
        self.nightbutton.text = 'Night'
        self.nightbutton.texture_update()
        self.ms.imwarner.color = (1, 1, 1, 1)
        self.ms.imwarner.texture_update()
        self.s.gps_accuracy.color = (1, 1, 1, 1)
        self.s.gps_accuracy.texture_update()
        self.ms.roadname.color = (1, 1, 1, 1)
        self.ms.roadname.texture_update()
        self.ms.bar_meters.color = (1, 1, 1, 1)
        self.ms.bar_meters.texture_update()
        self.s.curspeed.color = (1, 1, 1, 1)
        self.s.curspeed.texture_update()
        self.cl.sd_y.color = (1, 1, 1, 1)
        self.cl.sd_y.texture_update()
        self.cl.sd_x.color = (1, 1, 1, 1)
        self.cl.sd_x.texture_update()
        self.s.bearing.color = (1, 1, 1, 1)
        self.s.bearing.texture_update()
        self.s.av_bearing.color = (1, 1, 1, 1)
        self.s.av_bearing.texture_update()
        self.s.av_bearing_value.color = (1, 1, 1, 1)
        self.s.av_bearing_value.texture_update()
        self.startbutton.color = (1, 1, 1, 1)
        self.startbutton.texture_update()
        self.stopbutton.color = (1, 1, 1, 1)
        self.stopbutton.texture_update()
        self.exitbutton.color = (1, 1, 1, 1)
        self.exitbutton.texture_update()
        self.root_add.policebutton.color = (1, 1, 1, 1)
        self.root_add.policebutton.texture_update()
        # self.ml.speed_camera.color = (1, 1, 1, 1)
        # self.ml.speed_camera.texture_update()
        self.ml.speedcam_fix_number.color = (1, 1, 1, 1)
        self.ml.speedcam_fix_number.texture_update()
        self.ml.speedcam_mobil_number.color = (1, 1, 1, 1)
        self.ml.speedcam_mobil_number.texture_update()
        self.ml.speedcam_trafficlight_number.color = (1, 1, 1, 1)
        self.ml.speedcam_trafficlight_number.texture_update()
        self.ml.speedcam_distance_number.color = (1, 1, 1, 1)
        self.ml.speedcam_distance_number.texture_update()
        self.ml.poi_number.color = (1, 1, 1, .1)
        self.ml.poi_number.texture_update()
        self.s.service_unit.color = (1, 1, 1, 1)
        self.s.service_unit.texture_update()
        self.root_table.poibutton.color = (1, 1, 1, 1)
        self.root_table.poibutton.texture_update()
        self.root_table.label_h.color = (1, 1, 1, 1)
        self.root_table.label_h.texture_update()
        self.root_table.label_g.color = (1, 1, 1, 1)
        self.root_table.label_g.texture_update()

    def check_night_mode(self):
        time_array = time.ctime().split()
        if ((8 <= int(time_array[3].split(':')[0]) < 19) and not self.day_update_done):
            logger.print_log_line(' Daymode active')
            Clock.schedule_once(self.callback_day_auto)
            self.day_update_done = True
            self.night_update_done = False

        elif ((int(time_array[3].split(':')[0]) >= 19) and not self.night_update_done):
            logger.print_log_line(' Nightmode active')
            Clock.schedule_once(self.callback_night_auto)
            self.day_update_done = False
            self.night_update_done = True

    def clear_voice_queue(self, cv):
        self.voice_prompt_queue.clear_gpssignalqueue(cv)

    def on_pause(self):
        # self.resume.set_resume_state(False)
        if self.calculator is not None:
            self.calculator.url_timeout = 5
        return True

    def on_resume(self):
        # self.resume.set_resume_state(True)
        if self.calculator is not None:
            self.calculator.url_timeout = self.calculator.osm_timeout
        return True

    def on_start(self):
        from kivy.base import EventLoop
        EventLoop.window.bind(on_keyboard=self.hook_keyboard)

    def hook_keyboard(self, window, key, *largs):
        if key == 27 or key == 4:
            self.sm.current = 'Operative'
            self.key_pressed = True
            # return True for stopping the propagation
            return True

    def start_service(self):
        global activityport
        self.osc_server = OSCThreadServer()
        sock = self.osc_server.listen(address='127.0.0.1', port=activityport, default=True)
        self.osc_server.bind(b'/ping', self.ping)

        # In the service update do day or night mode every 1 min
        Clock.schedule_interval(lambda *x: self.check_night_mode(), 60)

    def send_ping(self):
        global activityport
        logger.print_log_line(' Sending ping message')
        address = "127.0.0.1"
        osc = OSCClient(address, activityport, encoding='utf8')
        # send an update message to our service every 2 seconds
        Clock.schedule_interval(lambda *x: osc.send_message(b'/ping', [b'', ]), 1)

    def ping(self, *values):
        # logger.print_log_line(" Got a message! %s" % values[0].decode('utf-8'))

        self.s.service_unit.text = values[0].decode('utf-8')
        Clock.schedule_once(self.s.service_unit.texture_update)


if __name__ == '__main__':
    try:
        MainTApp().run()
    except:
        pass
