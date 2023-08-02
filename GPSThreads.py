# qpy:kivy
# -*-coding:utf8;-*-
# qpy:2
# ts=4:sw=4:expandtab
'''
Created on 01.07.2014

@author: rkoraschnigg
'''

import time
import os
from kivy.clock import Clock
from ThreadBase import StoppableThread
from GpsData import GpsTestDataGenerator
from Logger import Logger


class GPSConsumerThread(StoppableThread, Logger):
    def __init__(self, main_app, resume, cv, curspeed, bearing, gpsqueue, s, cl, cond):
        StoppableThread.__init__(self)
        Logger.__init__(self, self.__class__.__name__)
        self.main_app = main_app
        self.resume = resume
        self.cv = cv
        self.curspeed = curspeed
        self.bearing = bearing
        self.gpsqueue = gpsqueue
        self.speedlayout = s
        self.curvelayout = cl
        self.cond = cond

        # global items
        self.backup_speed = 0
        self.av_speed_queue = []
        self.startup = True
        self.connection = None
        self.set_configs()

    def set_configs(self):
        self.display_miles = False

    def run(self):

        while not self.cond.terminate:
            if self.main_app.run_in_back_ground:
                self.main_app.main_event.wait()
            if not self.resume.isResumed():
                self.gpsqueue.clear_gpsqueue(self.cv)
            else:
                self.process()

        self.print_log_line("Terminating")
        self.gpsqueue.clear_gpsqueue(self.cv)
        self.stop()

    def calculate_av_speed_kivy_update(self, key):
        """
        Calculate the average speed and update the kivy UI
        :param key:
        :return:
        """
        av_speed = self.calculate_average_speed(key)
        if av_speed != -1:
            if self.display_miles:
                av_speed = str(round(av_speed / 1.609344, 1))
            if not isinstance(av_speed, str):
                av_speed = str(av_speed)
            font_size = 250
            self.curspeed.text = av_speed
            self.curspeed.font_size = font_size
            Clock.schedule_once(self.curspeed.texture_update)

    def speed_update_kivy(self, key):
        """
        Update kivy UI without calculating the average speed
        :param key:
        :return:
        """
        speed = round(key, 1)
        if self.display_miles:
            speed = str(round(speed / 1.609344, 1))
        if not isinstance(speed, str):
            speed = str(speed)
        font_size = 250
        self.curspeed.text = speed
        self.curspeed.font_size = font_size
        Clock.schedule_once(self.curspeed.texture_update)

    def process(self):

        item = self.gpsqueue.consume(self.cv)
        for key, value in item.items():
            if value == 3:
                if key == '---.-':
                    self.clear_all(key)
                elif key == "...":
                    self.in_progress(key)
                else:
                    int_key = int(round(float(key)))
                    float_key = float(key)
                    # Update the current speed
                    self.speed_update_kivy(float_key)

                    if self.startup:
                        self.speedlayout.update_accel_layout(int_key, True, 'ONLINE')
                        self.backup_speed = int_key

                        if float_key == 0.0:
                            self.curvelayout.check_speed_deviation(float(0.1), True)

                        else:
                            self.curvelayout.check_speed_deviation(float_key, True)
                        self.startup = False
                    else:
                        if int_key > self.backup_speed:
                            self.speedlayout.update_accel_layout(int_key, True, 'ONLINE')
                        elif int(round(float(key))) < self.backup_speed:
                            self.speedlayout.update_accel_layout(int_key, False, 'ONLINE')
                        else:
                            # nothing to do
                            pass

                        if float_key == 0.0:
                            self.curvelayout.check_speed_deviation(float(0.1), False)
                        else:
                            self.curvelayout.check_speed_deviation(float_key, False)
                        self.backup_speed = float_key
            elif value == 4:
                font_size = 100
                self.bearing.text = key
                self.bearing.font_size = font_size
                Clock.schedule_once(self.bearing.texture_update)
            elif value == 5:
                self.speedlayout.update_gps_accuracy(key)
            elif value == 1:
                self.print_log_line("Exit item received")
            else:
                self.print_log_line(f"Invalid value {value} received!")
        self.cv.release()

    def update_current_speed_ui(self, key):
        if self.curspeed.text != key:
            font_size = 250
            self.curspeed.text = key
            self.curspeed.font_size = font_size
            Clock.schedule_once(self.curspeed.texture_update)

    def in_progress(self, key):
        self.update_current_speed_ui(key)

    def clear_all(self, key):
        self.update_current_speed_ui(key)
        self.speedlayout.update_accel_layout()
        self.speedlayout.reset_overspeed()
        self.speedlayout.reset_bearing()
        self.curvelayout.check_speed_deviation(key, False)

    def calculate_average_speed(self, speed):
        # based on 3 speed values
        if len(self.av_speed_queue) == 3:
            av_speed = round(
                ((self.av_speed_queue[0] + self.av_speed_queue[1] + self.av_speed_queue[2]) / 3),
                1)
            self.av_speed_queue.clear()
            return av_speed

        self.av_speed_queue.append(speed)
        return -1


class GPSThread(StoppableThread, Logger):
    GPS_INACCURACY_COUNTER = 0

    def __init__(self, main_app, g, cv, cv_vector, cv_voice, cv_average_angle, voice_prompt_queue,
                 ms, vdata, gpsqueue, average_angle_queue, cv_map, map_queue,
                 osm_wrapper, cv_currentspeed, currentspeed_queue, cv_gps_data, gps_data_queue,
                 cv_speedcam, speed_cam_queue, calculator, cond):
        StoppableThread.__init__(self)
        Logger.__init__(self, self.__class__.__name__)
        self.main_app = main_app
        self.main_app = main_app
        self.g = g
        self.cv = cv
        self.cv_vector = cv_vector
        self.cv_voice = cv_voice
        self.cv_average_angle = cv_average_angle
        self.voice_prompt_queue = voice_prompt_queue
        self.ms = ms
        self.vdata = vdata
        self.gpsqueue = gpsqueue
        self.average_angle_queue = average_angle_queue
        self.cond = cond
        self.cv_map = cv_map
        self.map_queue = map_queue
        self.osm_wrapper = osm_wrapper
        self.cv_currentspeed = cv_currentspeed
        self.currentspeed_queue = currentspeed_queue
        self.cv_gps_data = cv_gps_data
        self.gps_data_queue = gps_data_queue
        self.cv_speedcam = cv_speedcam
        self.speed_cam_queue = speed_cam_queue
        self.calculator = calculator

        # global items
        self.startup = True
        self.first_offline_call = True
        self.off_state = False
        self.on_state = False
        self.in_progress = False
        self.is_filled = False
        self.day_update_done = False
        self.night_update_done = False
        self.map_thread_started = False
        self.latitude = None
        self.longitude = None
        self.latitude_bot = None
        self.longitude_bot = None
        self.accuracy = None
        self.last_bearing = None
        self.current_bearings = []
        self.curr_driving_direction = None
        self.last_speed = 0
        self.trigger_speed_correction = False

        # set config items
        self.set_configs()
        if self.gps_test_data:
            self.gps_data = iter(GpsTestDataGenerator(self.max_gps_entries, self.gpx_file))
        else:
            pass

    def set_configs(self):
        # use gps test data
        self.gps_test_data = True
        self.max_gps_entries = 50000
        self.gpx_file = os.path.join(os.path.dirname(__file__), "gpx",
                                     "Ronde_van_Nederland_reverse_aug_2021.gpx")
        # GPS treshold which is considered as a Weak GPS Signal
        self.gps_treshold = 40
        # Max GPS inaccuracy treshold after which the App will go into OFF mode.
        # Note: This only applies for Weak GPS signals, not if GPS is disabled
        self.gps_inaccuracy_treshold = 4

    def run(self):

        while not self.cond.terminate:
            if self.main_app.run_in_back_ground:
                self.main_app.main_event.wait()
            status = self.process()
            if status == 'EXIT':
                break

        '''
            add an exit item in case consumer threads
            are in wait condition while producer is ready
            to terminate
        '''
        self.voice_prompt_queue.produce_gpssignal(self.cv_voice, 'EXIT_APPLICATION')
        self.gpsqueue.produce(self.cv, {'EXIT': 1})
        self.vdata.set_vector_data(self.cv_vector, 'vector_data', float(0.0), float(0.0),
                                   float(0.0), float(0.0), '-', 'EXIT', 0)
        self.produce_bearing_set(0.002)
        self.map_queue.produce(self.cv_map, "EXIT")
        self.print_log_line("Terminated")
        self.startup = True
        self.first_offline_call = True
        self.stop()

    def process(self):
        gps_accuracy = 'OFF'

        if self.startup:
            self.vdata.set_vector_data(self.cv_vector, 'vector_data', float(0.0), float(0.0),
                                       float(0.0), float(0.0), '-', 'INIT', 0)
            self.ms.update_gui()
            self.startup = False
            time.sleep(0.3)

        if self.gps_test_data:
            try:
                event = next(self.gps_data)
                time.sleep(1.5)
            except StopIteration:
                event = None
        else:
            item = self.gps_data_queue.consume(self.cv_gps_data)
            self.cv_gps_data.release()

            if item.get('EXIT', None):
                return 'EXIT'

            event = item.get('event', None)
            gps_status = item.get('status', None)

            if gps_status is not None and \
                    (gps_status != 'available' and gps_status != 'provider-enabled'):
                self.process_offroute(gps_accuracy)

        if event:

            self.in_progress = False

            if 'gps' in event['data'] and 'accuracy' in event['data']['gps']:
                # Set accuracy
                accuracy = event['data']['gps']['accuracy']
                if int(accuracy) <= self.gps_treshold:
                    # Set members
                    success_coords = False
                    speed_vector = None
                    speed = None
                    lon, lat = None, None
                    if 'speed' in event['data']['gps']:
                        speed = round((float(event['data']['gps']['speed']) * 3.6), 1)
                        speed_vector = round((float(event['data']['gps']['speed'])), 2)
                    if 'latitude' in event['data']['gps']:
                        lat = float(event['data']['gps']['latitude'])
                        lon = float(event['data']['gps']['longitude'])
                        success_coords = True
                    if speed is None or success_coords is False:
                        self.print_log_line("Could not retrieve speed or coordinates from event!. "
                                            "Skipping..")
                        return None

                    self.callback_gps(lon, lat)
                    speed = self.correct_speed(speed)
                    self.gpsqueue.produce(self.cv, {speed: 3}) if speed != 'DISMISS' else \
                        self.print_log_line(f"Speed dismissed: Ignore GPS Queue Update")
                    self.currentspeed_queue.produce(self.cv_currentspeed, round(speed)) \
                        if speed != 'DISMISS' else \
                        self.print_log_line(f"Speed dismissed: Ignore Current Speed Queue Update ")
                    self.gpsqueue.produce(self.cv, {str(round(float(accuracy), 1)): 5})

                    direction, bearing = self.calculate_direction(event)
                    if direction is None:
                        self.print_log_line("Could not calculate direction from event!. "
                                            "Skipping..")
                        return None

                    # trigger calculation only if speed >= 0 km/h and
                    # initiate deviation checker thread##
                    if speed_vector > 0:
                        self.vdata.set_vector_data(self.cv_vector, 'vector_data',
                                                   lon,
                                                   lat,
                                                   speed_vector,
                                                   bearing,
                                                   direction,
                                                   'CALCULATE',
                                                   int(accuracy))
                        self.speed_cam_queue.produce(self.cv_speedcam, {
                            'ccp': (lon, lat),
                            'fix_cam': (False, 0, 0),
                            'traffic_cam': (False, 0, 0),
                            'distance_cam': (False, 0, 0),
                            'mobile_cam': (False, 0, 0),
                            'ccp_node': (None, None),
                            'list_tree': (None, None),
                            'stable_ccp': None,
                            'bearing': bearing})

                    self.gpsqueue.produce(self.cv, {str(bearing) + ' ' + direction: 4})
                    self.produce_bearing_set(bearing)
                    self.set_accuracy(accuracy)

                    self.osm_wrapper.osm_update_heading(direction)
                    self.osm_wrapper.osm_update_bearing(int(bearing))
                    self.osm_wrapper.osm_update_center(lat, lon)
                    self.osm_wrapper.osm_update_accuracy(self.accuracy)
                    self.osm_data_isFilled()
                    self.update_map_queue()
                else:
                    gps_accuracy = str(round(float(accuracy), 1))
                    self.process_offroute(gps_accuracy)
        return None

    def process_offroute(self, gps_accuracy):

        if self.already_off():
            pass
        else:
            if gps_accuracy != "OFF" and self.first_offline_call is False \
                    and GPSThread.GPS_INACCURACY_COUNTER <= self.gps_inaccuracy_treshold:
                GPSThread.GPS_INACCURACY_COUNTER += 1
                self.print_log_line(f"Processing inaccurate GPS signal number "
                                    f"({GPSThread.GPS_INACCURACY_COUNTER})")
                self.gpsqueue.produce(self.cv, {"...": 5})
                self.gpsqueue.produce(self.cv, {"...": 3})
                self.in_progress = True
                return

            GPSThread.GPS_INACCURACY_COUNTER = 0

            # Clear old gps items
            self.gpsqueue.clear_gpsqueue(self.cv)
            self.print_log_line(f"GPS status is {gps_accuracy}")
            if gps_accuracy != "OFF":
                self.voice_prompt_queue.produce_gpssignal(self.cv_voice, "GPS_LOW")
            else:
                self.voice_prompt_queue.produce_gpssignal(self.cv_voice, "GPS_OFF")
            self.g.off_state()

            self.gpsqueue.produce(self.cv, {'---.-': 3})

            self.off_state = True
            self.on_state = False
            self.in_progress = False
            self.gpsqueue.produce(self.cv, {gps_accuracy: 5})

            self.reset_osm_data_state()

        if self.first_offline_call:
            self.first_offline_call = False
        # Always calculate extrapolated positions
        self.vdata.set_vector_data(self.cv_vector, 'vector_data', float(0.0), float(0.0),
                                   float(0.0), float(0.0), '-', 'OFFLINE', 0)

    def callback_gps(self, lon, lat):
        """
        Set the GPS state to online
        :param lon:
        :param lat:
        :return:
        """
        # Update longitude and latitude
        self.set_lon_lat(lat, lon)
        # Update our bot
        self.set_lon_lat_bot(lat, lon)
        GPSThread.GPS_INACCURACY_COUNTER = 0

        if self.already_on():
            pass
        else:
            self.print_log_line("GPS status is ON")
            self.voice_prompt_queue.produce_gpssignal(self.cv_voice, 'GPS_ON')
            self.calculator.update_kivi_maxspeed(">->->")
            self.g.on_state()
            self.on_state = True
            self.off_state = False

    def correct_speed(self, speed):
        if speed > 0:
            self.last_speed = speed
            self.trigger_speed_correction = True
        if speed == 0 and self.trigger_speed_correction is True:
            speed = self.last_speed if self.last_speed > 0 else 'DISMISS'
            self.print_log_line(f"Speed value corrected to {speed}")
            self.trigger_speed_correction = False
        elif speed == 0 and self.trigger_speed_correction is False:
            self.trigger_speed_correction = True
            self.last_speed = 0
        return speed

    def update_map_queue(self):
        if self.map_thread_started:
            self.map_queue.produce(self.cv_map, "UPDATE")

    def update_map_state(self, map_thread_started=False):
        self.map_thread_started = map_thread_started

    def get_direction(self):
        return self.curr_driving_direction

    def calculate_direction(self, event):
        direction = None
        bearing = None

        if 'bearing' in event['data']['gps']:
            bearing = round(float(event['data']['gps']['bearing']), 2)

            if 0 <= bearing <= 11:
                direction = 'TOP-N'
                self.last_bearing = bearing
            elif 11 < bearing < 22:
                direction = 'N'
                self.last_bearing = bearing
            elif 22 <= bearing < 45:
                direction = 'NNO'
                self.last_bearing = bearing
            elif 45 <= bearing < 67:
                direction = 'NO'
                self.last_bearing = bearing
            elif 67 <= bearing < 78:
                direction = 'ONO'
                self.last_bearing = bearing
            elif 78 <= bearing <= 101:
                direction = 'TOP-O'
                self.last_bearing = bearing
            elif 101 < bearing < 112:
                direction = 'O'
                self.last_bearing = bearing
            elif 112 <= bearing < 135:
                direction = 'OSO'
                self.last_bearing = bearing
            elif 135 <= bearing < 157:
                direction = 'SO'
                self.last_bearing = bearing
            elif 157 <= bearing < 168:
                direction = 'SSO'
            elif 168 <= bearing < 191:
                direction = 'TOP-S'
                self.last_bearing = bearing
            elif 191 <= bearing < 202:
                direction = 'S'
                self.last_bearing = bearing
            elif 202 <= bearing < 225:
                direction = 'SSW'
                self.last_bearing = bearing
            elif 225 <= bearing < 247:
                direction = 'SW'
                self.last_bearing = bearing
            elif 247 <= bearing < 258:
                direction = 'WSW'
                self.last_bearing = bearing
            elif 258 <= bearing < 281:
                direction = 'TOP-W'
            elif 281 <= bearing < 292:
                direction = 'W'
                self.last_bearing = bearing
            elif 292 <= bearing < 315:
                direction = 'WNW'
                self.last_bearing = bearing
            elif 315 <= bearing < 337:
                direction = 'NW'
                self.last_bearing = bearing
            elif 337 <= bearing < 348:
                direction = 'NNW'
                self.last_bearing = bearing
            elif 348 <= bearing < 355:
                direction = 'N'
                self.last_bearing = bearing
            elif 355 <= bearing <= 360:
                direction = 'TOP-N'
                self.last_bearing = bearing
            else:
                self.print_log_line('Something bad happened here, direction = -')
                # this should not happen,
                # but currently it occurs for bearing values in range 45 - 70
                direction = self.calculate_bearing_deviation(bearing, self.last_bearing)

            self.curr_driving_direction = direction

        return direction, bearing

    # this is a hack!
    @staticmethod
    def calculate_bearing_deviation(current_bearing, last_bearing):
        if last_bearing is not None:
            if current_bearing >= last_bearing:
                deviation = int(((current_bearing - last_bearing) / last_bearing) * 100)

                if deviation > 20:
                    direction = 'ONO'
                else:
                    direction = 'NO'
            else:
                deviation = int(abs(((current_bearing - last_bearing) / last_bearing) * 100))

                if deviation > 20:
                    direction = 'NO'
                else:
                    direction = 'ONO'
        else:
            direction = 'NO'

        return direction

    def produce_bearing_set(self, bearing):
        if bearing == 0.002 or bearing == 0.001 or bearing == 0.0:
            self.init_average_bearing_update(bearing)
            return
        if len(self.current_bearings) == 5:
            self.init_average_bearing_update(self.current_bearings)
            return
        self.current_bearings.append(bearing)

    def reset_current_bearings(self):
        self.current_bearings = []

    def init_average_bearing_update(self, current_bearings):
        self.average_angle_queue.produce(self.cv_average_angle, current_bearings)
        self.reset_current_bearings()

    def set_lon_lat(self, lat=0, lon=0):
        self.latitude = lat
        self.longitude = lon

    def set_lon_lat_bot(self, lat=float(0), lon=float(0)):
        self.latitude_bot = lat
        self.longitude_bot = lon

    def get_lon_lat(self):
        return self.longitude, self.latitude

    def get_lon_lat_bot(self):
        return self.longitude_bot, self.latitude_bot

    def set_accuracy(self, accuracy):
        self.accuracy = float(accuracy)

    def get_current_gps_state(self):
        return self.already_on()

    def gps_in_progress(self):
        return self.in_progress

    def already_on(self):
        return self.on_state

    def already_off(self):
        return self.off_state

    def get_osm_data_state(self):
        return self.is_filled

    def osm_data_isFilled(self):
        self.is_filled = True

    def reset_osm_data_state(self):
        self.is_filled = False
