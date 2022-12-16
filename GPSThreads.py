# qpy:kivy
# -*-coding:utf8;-*-
# qpy:2
# ts=4:sw=4:expandtab
'''
Created on 01.07.2014

@author: rkoraschnigg
'''

import time
from kivy.clock import Clock
from ThreadBase import StoppableThread
from gps_data import GpsTestDataGenerator
from Logger import Logger


class GPSConsumerThread(StoppableThread, Logger):
    def __init__(self, resume, cv, curspeed, bearing, gpsqueue, s, cl, cond):
        StoppableThread.__init__(self)
        Logger.__init__(self, self.__class__.__name__)
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
            if not self.resume.isResumed():
                self.gpsqueue.clear_gpsqueue(self.cv)
            else:
                self.update_kivi()

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
            self.curspeed.text = av_speed
            Clock.schedule_once(self.curspeed.texture_update)

    def update_kivi(self):

        item = self.gpsqueue.consume(self.cv)
        for key, value in item.items():
            if value == 3:
                if key == '---.-':
                    self.speedlayout.update_accel_layout()
                    self.curvelayout.check_speed_deviation(key, False)
                elif key != '---.-':
                    int_key = int(round(float(key)))
                    float_key = float(key)
                    # Calculate average speed
                    self.calculate_av_speed_kivy_update(float_key)

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
                if key is not None:
                    self.bearing.text = key
                    Clock.schedule_once(self.bearing.texture_update)
            elif value == 5:
                self.speedlayout.update_gps_accuracy(key)
            elif value == 1:
                self.curvelayout.check_speed_deviation('---.-', False)
                self.speedlayout.update_accel_layout()
                self.curspeed.text = '---.-'
                Clock.schedule_once(self.curspeed.texture_update)
            else:
                self.print_log_line(f"Invalid value {value} received!")
        self.cv.release()

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
    def __init__(self, g, cv, cv_vector, cv_voice, cv_average_angle, voice_prompt_queue, ms, vdata,
                 gpsqueue, average_angle_queue, cv_map, map_queue, osm_wrapper, cv_currentspeed,
                 currentspeed_queue, cv_gps_data, gps_data_queue,  cv_speedcam, speed_cam_queue,
                 calculator,cond):
        StoppableThread.__init__(self)
        Logger.__init__(self, self.__class__.__name__)
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
        self.off_state = False
        self.on_state = False
        self.is_filled = False
        self.day_update_done = False
        self.night_update_done = False
        self.map_thread_started = False
        self.startup = True
        self.latitude = None
        self.longitude = None
        self.latitude_bot = None
        self.longitude_bot = None
        self.accuracy = None
        self.last_bearing = None
        self.current_bearings = []
        self.curr_driving_direction = None

        # set config items
        self.set_configs()
        if self.gps_test_data:
            self.gps_data = iter(GpsTestDataGenerator(50000))
        else:
            pass

    def set_configs(self):
        # use gps test data
        self.gps_test_data = True
        # GPS treshold which is considered as a Weak GPS Signal
        self.gps_treshold = 5000

    def run(self):

        while not self.cond.terminate:
            self.process()

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
        self.stop()

    def process(self):
        gps_accuracy = 'GPS_OFF'

        if self.startup:
            self.vdata.set_vector_data(self.cv_vector, 'vector_data', float(0.0), float(0.0),
                                       float(0.0), float(0.0), '-', 'INIT', 0)
            self.startup = False

        if self.gps_test_data:
            try:
                event = next(self.gps_data)
                time.sleep(0.5)
            except StopIteration:
                event = None
        else:
            item = self.gps_data_queue.consume(self.cv_gps_data)
            self.cv_gps_data.release()
            if item is not None:
                event = item.get('event', None)
                gps_status = item.get('status', None)

                if gps_status is not None \
                        and (gps_status == 'network' or gps_status == 'passive') and not event:
                    self.process_offroute(gps_accuracy)
                    return
            else:
                return

        if event:
            if 'gps' in event['data'] and 'accuracy' in event['data']['gps']:
                # Set accuracy
                accuracy = event['data']['gps']['accuracy']
                if int(accuracy) <= self.gps_treshold:

                    # Set members
                    success_speed = False
                    success_coords = False
                    speed = None
                    speed_vector = None
                    lon, lat = None, None
                    if 'speed' in event['data']['gps']:
                        speed = round((float(event['data']['gps']['speed']) * 3.6), 1)
                        speed_vector = round((float(event['data']['gps']['speed'])), 2)
                        success_speed = True
                    if 'latitude' in event['data']['gps']:
                        lat = float(event['data']['gps']['latitude'])
                        lon = float(event['data']['gps']['longitude'])
                        success_coords = True
                    if success_speed is False or success_coords is False:
                        self.print_log_line("Could not retrieve speed or coordinates from event!. "
                                            "Skipping..")
                        return

                    self.callback_gps(lon, lat)
                    # Update our bot
                    self.set_lon_lat_bot(lat, lon)

                    self.gpsqueue.produce(self.cv, {speed: 3})
                    self.currentspeed_queue.produce(self.cv_currentspeed, int(speed))
                    self.gpsqueue.produce(self.cv, {str(accuracy): 5})

                    direction, bearing = self.calculate_direction(event)
                    if direction is None:
                        self.print_log_line("Could not calculate direction from event!. "
                                            "Skipping..")
                        return

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
                        if self.calculator.thread_lock:
                            '''self.print_log_line("Thread lock active, "
                                                "update speedcamwarner position")'''
                            self.speed_cam_queue.produce(self.cv_speedcam, {
                                'ccp': (lon, lat),
                                'fix_cam': (False, 0, 0),
                                'traffic_cam': (False, 0, 0),
                                'distance_cam': (False, 0, 0),
                                'mobile_cam': (False, 0, 0),
                                'ccp_node': (None, None),
                                'list_tree': (None, None),
                                'stable_ccp': None})

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
                    gps_accuracy = str(accuracy)
                    self.process_offroute(gps_accuracy)

    def process_offroute(self, gps_accuracy):

        if self.already_off():
            pass
        else:
            self.voice_prompt_queue.produce_gpssignal(self.cv_voice, gps_accuracy)
            self.g.off_state()

            self.gpsqueue.produce(self.cv, {'---.-': 3})
            self.gpsqueue.produce(self.cv, {'---.-': 4})
            self.produce_bearing_set(0.001)

            self.off_state = True
            self.on_state = False
            self.gpsqueue.produce(self.cv, {gps_accuracy: 5})

        self.vdata.set_vector_data(self.cv_vector, 'vector_data', float(0.0), float(0.0),
                                   float(0.0), float(0.0), '-', 'OFFLINE', 0)
        self.reset_osm_data_state()

    def callback_gps(self, lon, lat):
        """
        Set the GPS state to online
        :param lon:
        :param lat:
        :return:
        """
        if self.already_on():
            pass
        else:
            self.voice_prompt_queue.produce_gpssignal(self.cv_voice, 'GPS_ON')
            self.g.on_state()
            self.on_state = True
            self.off_state = False

            self.set_lon_lat(lat, lon)
            # update the maxspeed widget only once in case we receive a gps position immediately
            if self.startup:
                self.startup = False
                self.ms.maxspeed.text = ""
                Clock.schedule_once(self.ms.maxspeed.texture_update)

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
