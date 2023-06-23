# qpy:kivy
# -*-coding:utf8;-*-
# qpy:2
# ts=4:sw=4:expandtab
'''
Created on 01.07.2014

@author: rkoraschnigg
'''

import time
import math
from math import sin, cos, sqrt, atan2, radians
from kivy.clock import Clock
from copy import deepcopy
from functools import partial
from ThreadBase import StoppableThread
from LinkedListGenerator import DoubleLinkedListNodes
from Logger import Logger
from CalculatorThreads import RectangleCalculatorThread


class SpeedCamWarnerThread(StoppableThread, Logger):

    CAM_IN_PROGRESS = False

    def __init__(self, main_app, resume, cv_voice, cv_speedcam, voice_prompt_queue,
                 speedcamqueue, cv_overspeed, overspeed_queue,
                 osm_wrapper, calculator, ms, g, cond):
        StoppableThread.__init__(self)
        Logger.__init__(self, self.__class__.__name__)
        self.main_app = main_app
        self.resume = resume
        self.cv_voice = cv_voice
        self.cv_speedcam = cv_speedcam
        self.voice_prompt_queue = voice_prompt_queue
        self.speedcamqueue = speedcamqueue
        self.cv_overspeed = cv_overspeed
        self.overspeed_queue = overspeed_queue
        self.osm_wrapper = osm_wrapper
        self.calculator = calculator
        self.ms = ms
        self.g = g
        self.cond = cond

        self.cam_coordinates = (None, None)
        self.ccp_node_coordinates = (None, None)
        self.ccp_bearing = None
        self.ITEMQUEUE = {}
        self.ITEMQUEUE_BACKUP = {}
        self.start_times = {}
        self.start_times_backup = {}
        self.INSERTED_SPEEDCAMS = []
        self.longitude = float(0.0)
        self.latitude = float(0.0)
        # Dismiss counter for cameras that are not reported because of an angle mismatch
        self.dismiss_counter = 0
        # Pointer to current cam coordinates
        self.current_cam_pointer = None
        self.camera_deletion_lock = False

        self.set_configs()

        # delete obsolete cameras every 30 seconds
        Clock.schedule_interval(lambda *x: self.delete_passed_cameras(),
                                self.traversed_cameras_interval)

    def set_configs(self):
        # report only cames in driving direction,
        # cams outside the defined angles relative to CCP will be ignored
        self.enable_inside_relevant_angle_feature = True
        # Emergency angle distance. If the camera is outside the defined angle but inside the
        # emergency distance in meters, it will be reported. Set to a low value.
        # This parameter is only evaluated
        # when self.enable_inside_relevant_angle_feature is set to True
        self.emergency_angle_distance = 150
        # If this parameter is set to true, it has a higher priority than the settings
        # max_absolute_distance and max_storage_time. This means if cameras are outside the
        # current lookahead rectangle, they will be deleted and cameras remaining inside the
        # lookahead rectangle will be checked against storage time and absolute distance.
        self.delete_cameras_outside_lookahead_rectangle = True
        # Max absolute distance between the car and the camera.
        # If the calculated absolute distance of traversed cameras is reached,
        # those cameras will be deleted
        self.max_absolute_distance = 300000
        # Initial max storage time. If this time has passed,
        # cameras which have been traversed by the car
        # and which have never been initialized once (last_distance = -1) will be deleted
        # The value increases by 600 units if the ccp is UNSTABLE assuming the driver makes a
        # UTURN and cameras behind are still relevant
        self.max_storage_time = 28800
        # Traversed cameras will be checked every X seconds
        self.traversed_cameras_interval = 3
        # Max dismiss counter for cameras with angle mismatch after which the cam road name text
        # will be resetted
        self.max_dismiss_counter = 5
        # Maximal distance in meters to be displayed to a future speed camera
        self.max_distance_to_future_camera = 5000

        # SpeedLimits Base URL example##
        self.baseurl = 'http://overpass-api.de/api/interpreter?'
        self.querystring1 = 'data=[out:json];'
        self.querystring2 = 'way["highway"~"."](around:5,'
        self.querystring3 = '50.7528080,2.0377858'
        self.querystring4 = ');out geom;'

    def run(self):
        while not self.cond.terminate:
            if self.main_app.run_in_back_ground:
                self.main_app.main_event.wait()
            status = self.process()
            if status == 'EXIT':
                break
        self.print_log_line("Terminated")
        self.stop()

    def process(self):
        item = self.speedcamqueue.consume(self.cv_speedcam)
        self.cv_speedcam.release()

        self.ccp_bearing = item.get('bearing', None)

        if item['ccp'][0] == 'EXIT' or item['ccp'][1] == 'EXIT':
            self.print_log_line(' Speedcamwarner thread got a termination item')
            return 'EXIT'

        if item['ccp'][0] == 'IGNORE' or item['ccp'][1] == 'IGNORE':
            self.print_log_line(' Got a camera from the POI Reader ')
        else:
            # back the updated ccp in case cameras originating from the POI Reader arrive
            self.longitude = item['ccp'][0]
            self.latitude = item['ccp'][1]

        if item['fix_cam'][0]:

            enforcement = item['fix_cam'][3]
            if not enforcement:
                self.print_log_line(' Fix Cam with %f %f is not an enforcement camera. '
                                    'Skipping..' % (item['fix_cam'][1], item['fix_cam'][2]))
                return False

            if self.is_already_added((item['fix_cam'][1], item['fix_cam'][2])):
                self.print_log_line(' Cam with %f %f already added. Skip processing..' % (
                    item['fix_cam'][1], item['fix_cam'][2]))
                return False
            else:
                self.print_log_line(' Add new fix cam (%f, %f)'
                                    % (item['fix_cam'][1], item['fix_cam'][2]))

                self.cam_coordinates = (item['fix_cam'][1], item['fix_cam'][2])
                self.ccp_node_coordinates = (item['ccp_node'][0], item['ccp_node'][1])
                dismiss = False

                linked_list = item['list_tree'][0]
                tree = item['list_tree'][1]
                last_distance = -1
                last_calc_distance = 0
                start_time = time.time()
                roadname = item.get('name', None)
                max_speed = item.get('maxspeed', None)
                new = True
                cam_direction = self.convert_cam_direction(item.get('direction', None))
                self.start_times[self.cam_coordinates] = start_time

                self.ITEMQUEUE[self.cam_coordinates] = ['fix',
                                                        dismiss,
                                                        self.ccp_node_coordinates,
                                                        linked_list,
                                                        tree,
                                                        last_distance,
                                                        start_time,
                                                        roadname,
                                                        last_calc_distance,
                                                        cam_direction,
                                                        max_speed,
                                                        new]
                self.INSERTED_SPEEDCAMS.append((item['fix_cam'][1], item['fix_cam'][2]))

        if item['traffic_cam'][0]:

            enforcement = item['traffic_cam'][3]
            if not enforcement:
                self.print_log_line(' Traffic Cam with %f %f is not an enforcement camera. '
                                    'Skipping..' % (item['traffic_cam'][1], item['traffic_cam'][2]))
                return False

            if self.is_already_added((item['traffic_cam'][1], item['traffic_cam'][2])):
                self.print_log_line(' Cam with %f %f already added. Skip processing..' % (
                    item['traffic_cam'][1], item['traffic_cam'][2]))
                return False
            else:
                self.print_log_line(' Add new traffic cam (%f, %f)'
                                    % (item['traffic_cam'][1], item['traffic_cam'][2]))

                self.cam_coordinates = (item['traffic_cam'][1], item['traffic_cam'][2])
                self.ccp_node_coordinates = (item['ccp_node'][0], item['ccp_node'][1])
                dismiss = False

                linked_list = item['list_tree'][0]
                tree = item['list_tree'][1]
                last_distance = -1
                last_calc_distance = 0
                start_time = time.time()
                roadname = item.get('name', None)
                max_speed = item.get('maxspeed', None)
                new = True
                cam_direction = self.convert_cam_direction(item.get('direction', None))
                self.start_times[self.cam_coordinates] = start_time

                self.ITEMQUEUE[self.cam_coordinates] = ['traffic',
                                                        dismiss,
                                                        self.ccp_node_coordinates,
                                                        linked_list,
                                                        tree,
                                                        last_distance,
                                                        start_time,
                                                        roadname,
                                                        last_calc_distance,
                                                        cam_direction,
                                                        max_speed,
                                                        new]
                self.INSERTED_SPEEDCAMS.append((item['traffic_cam'][1], item['traffic_cam'][2]))

        if item['distance_cam'][0]:

            enforcement = item['distance_cam'][3]
            if not enforcement:
                self.print_log_line(' Distance Cam with %f %f is not an enforcement camera. '
                                    'Skipping..' % (item['distance_cam'][1], item['distance_cam'][2]))
                return False

            if self.is_already_added((item['distance_cam'][1], item['distance_cam'][2])):
                self.print_log_line(' Cam with %f %f already added. Skip processing..' % (
                    item['distance_cam'][1], item['distance_cam'][2]))
                return False
            else:
                self.print_log_line(' Add new distance cam (%f, %f)'
                                    % (item['distance_cam'][1], item['distance_cam'][2]))

                self.cam_coordinates = (item['distance_cam'][1], item['distance_cam'][2])
                self.ccp_node_coordinates = (item['ccp_node'][0], item['ccp_node'][1])
                dismiss = False

                linked_list = item['list_tree'][0]
                tree = item['list_tree'][1]
                last_distance = -1
                last_calc_distance = 0
                start_time = time.time()
                roadname = item.get('name', None)
                max_speed = item.get('maxspeed', None)
                new = True
                cam_direction = self.convert_cam_direction(item.get('direction', None))
                self.start_times[self.cam_coordinates] = start_time

                self.ITEMQUEUE[self.cam_coordinates] = ['distance',
                                                        dismiss,
                                                        self.ccp_node_coordinates,
                                                        linked_list,
                                                        tree,
                                                        last_distance,
                                                        start_time,
                                                        roadname,
                                                        last_calc_distance,
                                                        cam_direction,
                                                        max_speed,
                                                        new]
                self.INSERTED_SPEEDCAMS.append((item['distance_cam'][1], item['distance_cam'][2]))

        if item['mobile_cam'][0]:

            enforcement = item['mobile_cam'][3]
            if not enforcement:
                self.print_log_line(' Mobile Cam with %f %f is not an enforcement camera. '
                                    'Skipping..' % (item['mobile_cam'][1], item['mobile_cam'][2]))
                return False

            if self.is_already_added((item['mobile_cam'][1], item['mobile_cam'][2])):
                self.print_log_line(' Cam with %f %f already added. Skip processing..' % (
                    item['mobile_cam'][1], item['mobile_cam'][2]))
                return False
            else:
                self.print_log_line(' Add new mobile cam (%f, %f)'
                                    % (item['mobile_cam'][1], item['mobile_cam'][2]))

                self.cam_coordinates = (item['mobile_cam'][1], item['mobile_cam'][2])
                self.ccp_node_coordinates = (item['ccp_node'][0], item['ccp_node'][1])
                dismiss = False

                linked_list = item['list_tree'][0]
                tree = item['list_tree'][1]
                last_distance = -1
                last_calc_distance = 0
                start_time = time.time()
                roadname = item.get('name', None)
                max_speed = item.get('maxspeed', None)
                new = True
                cam_direction = self.convert_cam_direction(item.get('direction', None))
                self.start_times[self.cam_coordinates] = start_time

                self.ITEMQUEUE[self.cam_coordinates] = ['mobile',
                                                        dismiss,
                                                        self.ccp_node_coordinates,
                                                        linked_list,
                                                        tree,
                                                        last_distance,
                                                        start_time,
                                                        roadname,
                                                        last_calc_distance,
                                                        cam_direction,
                                                        max_speed,
                                                        new]
                self.INSERTED_SPEEDCAMS.append((item['mobile_cam'][1], item['mobile_cam'][2]))

        # cameras to be deleted
        cams_to_delete = []
        # sort the cams based on distance
        cam_list = []

        for cam, cam_attributes in self.ITEMQUEUE_BACKUP.copy().items():
            current_distance = self.check_distance_between_two_points(cam,
                                                                      (self.longitude,
                                                                       self.latitude))
            # calculate new start time
            # Make sure the camera still exists in the original item queue
            if cam in self.start_times_backup and cam in self.ITEMQUEUE_BACKUP:
                start_time = time.time() - self.start_times_backup[cam]
                self.ITEMQUEUE_BACKUP[cam][6] = start_time

                last_distance = cam_attributes[8]
                if current_distance < last_distance:
                    self.print_log_line(f"Reinserting {cam_attributes[0]} camera {str(cam)} "
                                        f"with new distance "
                                        f"{current_distance} meters")
                    self.ITEMQUEUE[cam] = cam_attributes
                    self.ITEMQUEUE[cam][1] = False
                    self.ITEMQUEUE[cam][6] = start_time
                    self.ITEMQUEUE[cam][8] = current_distance
                    self.ITEMQUEUE[cam][5] = -1
                    # delete backup camera and startup time
                    self.ITEMQUEUE_BACKUP.pop(cam)
                    self.start_times_backup.pop(cam)
                    self.voice_prompt_queue.produce_camera_status(self.cv_voice,
                                                                  'SPEEDCAM_REINSERT')

        for cam, cam_attributes in self.ITEMQUEUE.copy().items():
            distance = self.check_distance_between_two_points(cam,
                                                              (self.longitude,
                                                               self.latitude))
            self.print_log_line(" Initial Distance to speed cam (%f, %f, %s): "
                                "%f meters , last distance: %s, storage_time: %f seconds"
                                % (cam[0], cam[1], cam_attributes[0],
                                   distance, str(cam_attributes[5]), cam_attributes[6]))

            if distance < 0 or cam_attributes[1] is True:
                cams_to_delete.append(cam)
                self.remove_cached_camera(cam)
                self.trigger_free_flow()
                self.update_cam_road(reset=True)
                self.update_max_speed(reset=True)
                self.update_calculator_cams(cam_attributes)
            else:
                # Make sure the camera still exists in the original item queue
                if cam in self.start_times and cam in self.ITEMQUEUE:
                    start_time = time.time() - self.start_times[cam]
                    self.ITEMQUEUE[cam][6] = start_time
                    self.ITEMQUEUE[cam][11] = False

                    # Add the camera to the backup cameras and delete it for this processing cycle
                    if cam_attributes[1] == "to_be_stored":
                        cams_to_delete.append(cam)
                        self.backup_camera(cam, distance)

                    if cam_attributes[1] is False:
                        entry = (cam, distance)
                        cam_list.append(entry)

        # Delete obsolete cameras
        self.delete_cameras(cams_to_delete)
        # Sort cameras based on distance
        cam, cam_entry = self.sort_pois(cam_list)
        # Reset the camera dismiss counter
        if cam != self.current_cam_pointer:
            self.dismiss_counter = 0
        # Point to the current camera
        self.current_cam_pointer = cam
        # Nothing to sort
        if cam is None:
            self.print_log_line("Sorting speed cameras failed -> "
                                "No cameras available. Abort processing..")
            self.update_cam_road(reset=True)
            return False
        # Sort the follow up cameras based on the list of cameras - the actual camera
        cam_list_followup = cam_list.copy()
        cam_list_followup.remove(cam_entry)
        next_cam, next_cam_entry = self.sort_pois(cam_list_followup)
        # Set up the road name and the distance for the next camera
        next_cam_road = ""
        next_cam_distance = ""
        next_cam_distance_as_int = 0
        process_next_cam = False
        if next_cam is not None and next_cam in self.ITEMQUEUE:
            try:
                next_cam_road = self.ITEMQUEUE[next_cam][7]
            except KeyError:
                pass
            next_cam_distance = str(next_cam_entry[1]) + "m"
            next_cam_distance_as_int = next_cam_entry[1]
            process_next_cam = True

        try:
            cam_attributes = self.ITEMQUEUE[cam]
            cam_road_name = cam_attributes[7] if cam_attributes[7] else ""
            current_distance_to_cam = cam_entry[1]
        except KeyError:
            self.print_log_line(" Speed cam with cam coordinates %f %f has been deleted already. "
                                "Abort processing.. " % (cam[0], cam[1]), log_level="WARNING")
            return False

        if self.enable_inside_relevant_angle_feature:
            success = self.match_camera_against_angle(cam, current_distance_to_cam, cam_road_name)
            if not success:
                return False

        # check speed cam distance to updated ccp position
        # if we already found a speed cam previously
        if cam_attributes[1] is False:
            distance = self.check_distance_between_two_points(cam,
                                                              (self.longitude,
                                                               self.latitude))
            self.print_log_line(" Followup Distance to current speed cam "
                                "(%f, %f, %s): %f meters , "
                                "last distance: %s, storage_time: %f seconds"
                                % (cam[0], cam[1], cam_attributes[0],
                                   distance, str(cam_attributes[5]), cam_attributes[6]))
            if process_next_cam:
                self.print_log_line(" -> Future speed cam in queue is: "
                                    "coords: (%f, %f), road name: %s, distance: %s "
                                    % (next_cam[0], next_cam[1], next_cam_road, next_cam_distance))
            else:
                self.print_log_line(" No future speed cam in queue found")

            self.trigger_speed_cam_update(round(distance),
                                          cam,
                                          cam_attributes[0],
                                          cam_attributes[2],
                                          cam_attributes[3],
                                          cam_attributes[4],
                                          cam_attributes[5],
                                          cam_attributes[10],
                                          next_cam_road,
                                          next_cam_distance,
                                          next_cam_distance_as_int,
                                          process_next_cam)
            self.calculator.camera_in_progress(SpeedCamWarnerThread.CAM_IN_PROGRESS)

        else:
            if cam_attributes[1] is True:
                self.print_log_line(" Removed %s speed cam with cam coordinates %f %f" % (
                    cam_attributes[0], cam[0], cam[1]))
                self.voice_prompt_queue.produce_camera_status(self.cv_voice, 'SPEEDCAM_REMOVED')
                cams_to_delete.append(cam)
                self.delete_cameras(cams_to_delete)
                self.remove_cached_camera(cam)

        if len(self.ITEMQUEUE) == 0:
            SpeedCamWarnerThread.CAM_IN_PROGRESS = False
            self.trigger_free_flow()
            self.update_cam_road(reset=True)
            self.update_max_speed(reset=True)
            del self.INSERTED_SPEEDCAMS[:]

        return True

    def match_camera_against_angle(self, cam, current_distance_to_cam, cam_road_name):
        if not self.inside_relevant_angle(cam, current_distance_to_cam):
            SpeedCamWarnerThread.CAM_IN_PROGRESS = False
            self.trigger_free_flow()
            if self.dismiss_counter <= self.max_dismiss_counter:
                self.update_cam_road(road=f"DISMISS -> {cam_road_name}",
                                     color=(0, 1, .3, .8))
                self.dismiss_counter += 1
            else:
                self.update_cam_road(reset=True)
            self.update_max_speed(reset=True)
            self.print_log_line(" Leaving Speed Camera with coordinates: "
                                "(%s %s), road name: %s because of Angle mismatch"
                                % (cam[0], cam[1], cam_road_name), log_level="WARNING")
            # self.voice_prompt_queue.produce_camera_status(self.cv_voice, 'ANGLE_MISMATCH')
            return False

        return True

    def backup_camera(self, cam, distance):
        self.print_log_line(f" Backup camera {str(cam)} with last distance {distance} km")
        while self.camera_deletion_lock:
            self.print_log_line("Waiting for camera deletion lock()..")
        try:
            self.ITEMQUEUE_BACKUP[cam] = deepcopy(self.ITEMQUEUE[cam])
            self.ITEMQUEUE_BACKUP[cam][1] = False
            self.ITEMQUEUE_BACKUP[cam][8] = distance
            self.start_times_backup[cam] = time.time() - deepcopy(self.ITEMQUEUE[cam][6])
        except Exception:
            self.print_log_line(f"Backup of camera {str(cam)} "
                                f"with last distance {distance} km failed!", log_level="ERROR")

    def delete_cameras(self, cams_to_delete):
        # delete cams
        self.camera_deletion_lock = True
        error = False
        for cam in cams_to_delete:
            try:
                self.ITEMQUEUE.pop(cam)
                self.start_times.pop(cam)
            except KeyError:
                error = True
                self.print_log_line(f"Failed to delete camera {str(cam)}, camera already deleted",
                                    log_level="WARNING")

        if len(cams_to_delete) > 0 and not error:
            self.voice_prompt_queue.produce_camera_status(self.cv_voice, 'SPEEDCAM_REMOVED')

        del cams_to_delete[:]
        self.camera_deletion_lock = False

    def remove_cached_camera(self, cam):
        try:
            cam_index = self.INSERTED_SPEEDCAMS.index(cam)
            self.print_log_line(" Removing cached speed camera %s at index %d"
                                % (str(cam), cam_index))
            self.INSERTED_SPEEDCAMS.pop(cam_index)
        except ValueError:
            pass

    def is_already_added(self, cam_coordinates=(0, 0)):
        return cam_coordinates in self.INSERTED_SPEEDCAMS

    def trigger_free_flow(self):
        if self.resume.isResumed():
            self.update_kivi_speedcam('FREEFLOW')
            self.update_bar_widget_1000m(color=2)
            self.update_bar_widget_500m(color=2)
            self.update_bar_widget_300m(color=2)
            self.update_bar_widget_100m(color=2)
            self.update_bar_widget_meters('')

    def trigger_speed_cam_update(self, distance=0, cam_coordinates=(0, 0), speedcam='fix',
                                 ccp_node=(0, 0), linked_list=None, tree=None,
                                 last_distance=-1, max_speed=None,
                                 next_cam_road="", next_cam_distance="",
                                 next_cam_distance_as_int=0, process_next_cam=False):

        if 0 <= distance <= 100:
            SpeedCamWarnerThread.CAM_IN_PROGRESS = True
            if last_distance == -1 or last_distance > 100:
                if distance < 50:
                    if speedcam == 'fix':
                        self.voice_prompt_queue.produce_camera_status(self.cv_voice, 'FIX_NOW')
                    elif speedcam == 'traffic':
                        self.voice_prompt_queue.produce_camera_status(self.cv_voice, 'TRAFFIC_NOW')
                    elif speedcam == 'mobile':
                        self.voice_prompt_queue.produce_camera_status(self.cv_voice, 'MOBILE_NOW')
                    else:
                        self.voice_prompt_queue.produce_camera_status(self.cv_voice, 'DISTANCE_NOW')
                else:
                    if speedcam == 'fix':
                        self.voice_prompt_queue.produce_camera_status(self.cv_voice, 'FIX_100')
                    elif speedcam == 'traffic':
                        self.voice_prompt_queue.produce_camera_status(self.cv_voice, 'TRAFFIC_100')
                    elif speedcam == 'mobile':
                        self.voice_prompt_queue.produce_camera_status(self.cv_voice, 'MOBILE_100')
                    else:
                        self.voice_prompt_queue.produce_camera_status(self.cv_voice, 'DISTANCE_100')

                Clock.schedule_once(
                    partial(self.check_road_name, linked_list, tree, cam_coordinates), 0)
                if self.resume.isResumed():
                    self.update_kivi_speedcam(speedcam)
                    self.update_bar_widget_100m()
                    self.update_bar_widget_300m()
                    self.update_bar_widget_500m()
                    self.update_bar_widget_1000m()
                    self.update_bar_widget_meters(distance)
                if cam_coordinates in self.ITEMQUEUE:
                    try:
                        self.update_cam_road(road=self.ITEMQUEUE[cam_coordinates][7])
                        self.update_max_speed(max_speed=self.ITEMQUEUE[cam_coordinates][10])
                    except KeyError:
                        self.update_cam_road(road="")
                        self.update_max_speed(reset=True)

            if last_distance == 100:
                Clock.schedule_once(
                    partial(self.check_road_name, linked_list, tree, cam_coordinates), 0)
                if self.resume.isResumed():
                    self.update_kivi_speedcam(speedcam)
                    self.update_bar_widget_100m()
                    self.update_bar_widget_300m()
                    self.update_bar_widget_500m()
                    self.update_bar_widget_1000m()
                    self.update_bar_widget_meters(distance)
                if cam_coordinates in self.ITEMQUEUE:
                    try:
                        self.update_cam_road(road=self.ITEMQUEUE[cam_coordinates][7])
                        self.update_max_speed(max_speed=max_speed)
                    except KeyError:
                        self.update_cam_road(road="")
                        self.update_max_speed(reset=True)

            last_distance = 100
            dismiss = False
        elif 100 < distance <= 300:
            SpeedCamWarnerThread.CAM_IN_PROGRESS = True
            dismiss = False
            if last_distance == -1 or last_distance > 300:
                if speedcam == 'fix':
                    self.voice_prompt_queue.produce_camera_status(self.cv_voice, 'FIX_300')
                elif speedcam == 'traffic':
                    self.voice_prompt_queue.produce_camera_status(self.cv_voice, 'TRAFFIC_300')
                elif speedcam == 'mobile':
                    self.voice_prompt_queue.produce_camera_status(self.cv_voice, 'MOBILE_300')
                else:
                    self.voice_prompt_queue.produce_camera_status(self.cv_voice, 'DISTANCE_300')

                Clock.schedule_once(
                    partial(self.check_road_name, linked_list, tree, cam_coordinates), 0)
                if self.resume.isResumed():
                    self.update_kivi_speedcam(speedcam)
                    self.update_bar_widget_100m(color=2)
                    self.update_bar_widget_300m()
                    self.update_bar_widget_500m()
                    self.update_bar_widget_1000m()
                    self.update_bar_widget_meters(distance)
                if cam_coordinates in self.ITEMQUEUE:
                    try:
                        self.update_cam_road(road=self.ITEMQUEUE[cam_coordinates][7])
                        self.update_max_speed(max_speed=max_speed)
                    except KeyError:
                        self.update_cam_road(road="")
                        self.update_max_speed(reset=True)
            else:

                if last_distance == 300:
                    Clock.schedule_once(
                        partial(self.check_road_name, linked_list, tree, cam_coordinates), 0)
                    if self.resume.isResumed():
                        self.update_kivi_speedcam(speedcam)
                        self.update_bar_widget_100m(color=2)
                        self.update_bar_widget_300m()
                        self.update_bar_widget_500m()
                        self.update_bar_widget_1000m()
                        self.update_bar_widget_meters(distance)
                    if cam_coordinates in self.ITEMQUEUE:
                        try:
                            self.update_cam_road(road=self.ITEMQUEUE[cam_coordinates][7])
                            self.update_max_speed(max_speed=max_speed)
                        except KeyError:
                            self.update_cam_road(road="")
                            self.update_max_speed(reset=True)
                else:
                    SpeedCamWarnerThread.CAM_IN_PROGRESS = False
                    self.trigger_free_flow()
                    self.update_cam_road(reset=True) if not process_next_cam \
                        else self.update_cam_road(road=f"{next_cam_road} -> {next_cam_distance}",
                                                  color=(1, .9, 0, 2)) if \
                        next_cam_distance_as_int <= self.max_distance_to_future_camera else \
                        self.update_cam_road(reset=True)
                    self.update_max_speed(reset=True)
                    dismiss = "to_be_stored"

            last_distance = 300
        elif 300 < distance <= 500:
            SpeedCamWarnerThread.CAM_IN_PROGRESS = True
            dismiss = False
            if last_distance == -1 or last_distance > 500:
                if speedcam == 'fix':
                    self.voice_prompt_queue.produce_camera_status(self.cv_voice, 'FIX_500')
                elif speedcam == 'traffic':
                    self.voice_prompt_queue.produce_camera_status(self.cv_voice, 'TRAFFIC_500')
                elif speedcam == 'mobile':
                    self.voice_prompt_queue.produce_camera_status(self.cv_voice, 'MOBILE_500')
                else:
                    self.voice_prompt_queue.produce_camera_status(self.cv_voice, 'DISTANCE_500')

                Clock.schedule_once(
                    partial(self.check_road_name, linked_list, tree, cam_coordinates), 0)
                if self.resume.isResumed():
                    self.update_kivi_speedcam(speedcam)
                    self.update_bar_widget_100m(color=2)
                    self.update_bar_widget_300m(color=2)
                    self.update_bar_widget_500m()
                    self.update_bar_widget_1000m()
                    self.update_bar_widget_meters(distance)
                if cam_coordinates in self.ITEMQUEUE:
                    try:
                        self.update_cam_road(road=self.ITEMQUEUE[cam_coordinates][7])
                        self.update_max_speed(max_speed=max_speed)
                    except KeyError:
                        self.update_cam_road(road="")
                        self.update_max_speed(reset=True)
            else:

                if last_distance == 500:
                    Clock.schedule_once(
                        partial(self.check_road_name, linked_list, tree, cam_coordinates), 0)
                    if self.resume.isResumed():
                        self.update_kivi_speedcam(speedcam)
                        self.update_bar_widget_100m(color=2)
                        self.update_bar_widget_300m(color=2)
                        self.update_bar_widget_500m()
                        self.update_bar_widget_1000m()
                        self.update_bar_widget_meters(distance)
                    if cam_coordinates in self.ITEMQUEUE:
                        try:
                            self.update_cam_road(road=self.ITEMQUEUE[cam_coordinates][7])
                            self.update_max_speed(max_speed=max_speed)
                        except KeyError:
                            self.update_cam_road(road="")
                            self.update_max_speed(reset=True)
                else:
                    SpeedCamWarnerThread.CAM_IN_PROGRESS = False
                    self.trigger_free_flow()
                    self.update_cam_road(reset=True) if not process_next_cam \
                        else self.update_cam_road(road=f"{next_cam_road} -> {next_cam_distance}",
                                                  color=(1, .9, 0, 2)) if \
                        next_cam_distance_as_int <= self.max_distance_to_future_camera else \
                        self.update_cam_road(reset=True)
                    self.update_max_speed(reset=True)
                    dismiss = "to_be_stored"

            last_distance = 500
        elif 500 < distance <= 1000:
            SpeedCamWarnerThread.CAM_IN_PROGRESS = True
            dismiss = False
            if last_distance == -1 or last_distance > 1000:
                if speedcam == 'fix':
                    self.voice_prompt_queue.produce_camera_status(self.cv_voice, 'FIX_1000')
                elif speedcam == 'traffic':
                    self.voice_prompt_queue.produce_camera_status(self.cv_voice, 'TRAFFIC_1000')
                elif speedcam == 'mobile':
                    self.voice_prompt_queue.produce_camera_status(self.cv_voice, 'MOBILE_1000')
                else:
                    self.voice_prompt_queue.produce_camera_status(self.cv_voice, 'DISTANCE_1000')

                Clock.schedule_once(
                    partial(self.check_road_name, linked_list, tree, cam_coordinates), 0)
                if self.resume.isResumed():
                    self.update_kivi_speedcam(speedcam)
                    self.update_bar_widget_100m(color=2)
                    self.update_bar_widget_300m(color=2)
                    self.update_bar_widget_500m(color=2)
                    self.update_bar_widget_1000m()
                    self.update_bar_widget_meters(distance)
                if cam_coordinates in self.ITEMQUEUE:
                    try:
                        self.update_cam_road(road=self.ITEMQUEUE[cam_coordinates][7])
                        self.update_max_speed(max_speed=max_speed)
                    except KeyError:
                        self.update_cam_road(road="")
                        self.update_max_speed(reset=True)
            else:

                if last_distance == 1000:
                    Clock.schedule_once(
                        partial(self.check_road_name, linked_list, tree, cam_coordinates), 0)
                    if self.resume.isResumed():
                        self.update_kivi_speedcam(speedcam)
                        self.update_bar_widget_100m(color=2)
                        self.update_bar_widget_300m(color=2)
                        self.update_bar_widget_500m(color=2)
                        self.update_bar_widget_1000m()
                        self.update_bar_widget_meters(distance)
                    if cam_coordinates in self.ITEMQUEUE:
                        try:
                            self.update_cam_road(self.ITEMQUEUE[cam_coordinates][7])
                            self.update_max_speed(max_speed=max_speed)
                        except KeyError:
                            self.update_cam_road(road="")
                            self.update_max_speed(reset=True)
                else:
                    SpeedCamWarnerThread.CAM_IN_PROGRESS = False
                    self.trigger_free_flow()
                    self.update_cam_road(reset=True) if not process_next_cam \
                        else self.update_cam_road(road=f"{next_cam_road} -> {next_cam_distance}",
                                                  color=(1, .9, 0, 2)) if \
                        next_cam_distance_as_int <= self.max_distance_to_future_camera else \
                        self.update_cam_road(reset=True)
                    self.update_max_speed(reset=True)
                    dismiss = "to_be_stored"

            last_distance = 1000
        elif 1000 < distance <= 1500:
            SpeedCamWarnerThread.CAM_IN_PROGRESS = True
            dismiss = False
            if last_distance == -1 or last_distance > 1001:
                self.print_log_line(" %s speed cam ahead with distance %d m" % (
                    speedcam, int(distance)))
                self.voice_prompt_queue.produce_camera_status(self.cv_voice, 'CAMERA_AHEAD')
                if self.resume.isResumed():
                    self.update_kivi_speedcam('CAMERA_AHEAD')
                    self.update_bar_widget_meters(distance)
            else:
                if last_distance == 1001:
                    SpeedCamWarnerThread.CAM_IN_PROGRESS = False
                    if self.resume.isResumed():
                        self.update_kivi_speedcam('CAMERA_AHEAD')
                        self.update_bar_widget_meters(distance)
                    if cam_coordinates in self.ITEMQUEUE:
                        try:
                            self.update_cam_road(road=self.ITEMQUEUE[cam_coordinates][7])
                        except KeyError:
                            self.update_cam_road(road="")
                else:
                    SpeedCamWarnerThread.CAM_IN_PROGRESS = False
                    self.trigger_free_flow()
                    self.update_cam_road(reset=True) if not process_next_cam \
                        else self.update_cam_road(road=f"{next_cam_road} -> {next_cam_distance}",
                                                  color=(1, .9, 0, 2)) if \
                        next_cam_distance_as_int <= self.max_distance_to_future_camera else \
                        self.update_cam_road(reset=True)
                    self.update_max_speed(reset=True)
                    dismiss = "to_be_stored"

            last_distance = 1001
        else:
            if last_distance == -1 and distance < self.max_absolute_distance:
                self.update_cam_road(reset=True) if not process_next_cam \
                    else self.update_cam_road(road=f"{next_cam_road} -> {next_cam_distance}",
                                              color=(1, .9, 0, 2)) if \
                    next_cam_distance_as_int <= self.max_distance_to_future_camera else \
                    self.update_cam_road(reset=True)
                SpeedCamWarnerThread.CAM_IN_PROGRESS = False
                return
            self.print_log_line(" %s speed cam OUTSIDE relevant radius -> distance %d m" % (
                speedcam, int(distance)))

            SpeedCamWarnerThread.CAM_IN_PROGRESS = False
            self.trigger_free_flow()
            self.update_cam_road(reset=True) if not process_next_cam \
                else self.update_cam_road(road=f"{next_cam_road} -> {next_cam_distance}",
                                          color=(1, .9, 0, 2)) if \
                next_cam_distance_as_int <= self.max_distance_to_future_camera else \
                self.update_cam_road(reset=True)
            self.update_max_speed(reset=True)

            last_distance = self.max_absolute_distance
            # Those cameras will not be dismissed until their storage time has passed or they are
            # above max_absolute_distance
            dismiss = "to_be_stored"

        # Finally update the camera attributes
        self.ITEMQUEUE[cam_coordinates][0] = speedcam
        self.ITEMQUEUE[cam_coordinates][1] = dismiss
        self.ITEMQUEUE[cam_coordinates][2] = ccp_node
        self.ITEMQUEUE[cam_coordinates][3] = linked_list
        self.ITEMQUEUE[cam_coordinates][4] = tree
        self.ITEMQUEUE[cam_coordinates][5] = last_distance
        self.ITEMQUEUE[cam_coordinates][8] = distance

    @staticmethod
    def sort_pois(cam_list):
        if len(cam_list) > 0:
            attributes = min(cam_list, key=lambda c: c[1])
            return attributes[0], attributes
        return None, None

    def check_road_name(self, *args):
        linked_list = args[0]
        tree = args[1]
        cam_coordinates = args[2]

        if linked_list is not None and tree is not None:

            if not isinstance(linked_list, DoubleLinkedListNodes):
                return

            try:
                self.ITEMQUEUE[cam_coordinates][7]
            except KeyError:
                self.print_log_line(f" Check road name for speed cam with coords "
                                    f"{str(cam_coordinates)} failed. "
                                    f"Speed cameras had been deleted already", log_level="WARNING")
                return

            if self.ITEMQUEUE[cam_coordinates][7] is None:
                node_id = linked_list.match_node((cam_coordinates[1], cam_coordinates[0]))
                if node_id:
                    if node_id in tree:
                        self.print_log_line(
                            ' Found node_id %s in list and tree' % (str(node_id)),
                            log_level="DEBUG")
                        way = tree[node_id]
                        # get the way attributes
                        if tree.hasRoadNameAttribute(way):
                            self.print_log_line(' Road name in tree', log_level="DEBUG")
                            road_name = tree.getRoadNameValue(way)
                            try:
                                self.ITEMQUEUE[cam_coordinates][7] = road_name
                            except KeyError:
                                return

    def update_kivi_speedcam(self, speedcam):
        self.g.update_speed_camera(speedcam)

    def update_bar_widget_1000m(self, color=1):
        self.ms.update_bar_widget_1000m(color)

    def update_bar_widget_500m(self, color=1):
        self.ms.update_bar_widget_500m(color)

    def update_bar_widget_300m(self, color=1):
        self.ms.update_bar_widget_300m(color)

    def update_bar_widget_100m(self, color=1):
        self.ms.update_bar_widget_100m(color)

    def update_bar_widget_meters(self, meter):
        self.ms.update_bar_widget_meters(meter)

    def update_cam_text(self, distance=0, reset=False):
        self.ms.update_cam_text(distance, reset)

    def has_current_cam_road(self):
        return self.ms.has_current_cam_road()

    def update_cam_road(self, road=None, reset=False, color=None):
        if self.resume.isResumed():
            self.ms.update_cam_road(road, reset, color=color)

    def update_max_speed(self, max_speed=None, reset=False):
        if self.resume.isResumed():
            if reset:
                if self.ms.maxspeed.text != ">->->" and self.calculator.internet_available():
                    font_size = 230
                    self.ms.maxspeed.text = ">->->"
                    self.ms.maxspeed.color = (0, 1, .3, .8)
                    self.ms.maxspeed.font_size = font_size
                    Clock.schedule_once(self.ms.maxspeed.texture_update)
            else:
                if max_speed:
                    if self.ms.maxspeed.text != str(max_speed):
                        font_size = 250
                        self.ms.maxspeed.text = str(max_speed)
                        self.ms.maxspeed.color = (1, 0, 0, 3)
                        self.ms.maxspeed.font_size = font_size
                        Clock.schedule_once(self.ms.maxspeed.texture_update)
                else:
                    if self.ms.maxspeed.text != ">->->":
                        font_size = 230
                        self.ms.maxspeed.text = ">->->"
                        self.ms.maxspeed.color = (0, 1, .3, .8)
                        self.ms.maxspeed.font_size = font_size
                        Clock.schedule_once(self.ms.maxspeed.texture_update)

            if reset or not max_speed:
                self.overspeed_queue.produce(self.cv_overspeed, {'maxspeed': 10000})
            else:
                try:
                    self.overspeed_queue.produce(self.cv_overspeed, {'maxspeed': int(max_speed)})
                except:
                    self.overspeed_queue.produce(self.cv_overspeed, {'maxspeed': 10000})

    # beeline distance between 2 points (lon,lat) in meters.
    def check_beeline_distance(self, pt1, pt2):
        lon1, lat1 = pt1[0], pt1[1]
        lon2, lat2 = pt2[0], pt2[1]
        radius = 6371  # km

        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        a = math.sin(dlat / 2) * math.sin(dlat / 2) + math.cos(math.radians(lat1)) \
            * math.cos(math.radians(lat2)) * math.sin(dlon / 2) * math.sin(dlon / 2)
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        d = radius * c
        return int(d) * 1000

    # distance between 2 points (lon (x),lat (y)) in meters.
    def check_distance_between_two_points(self, pt1, pt2):
        # approximate radius of earth in km
        R = 6373.0

        try:
            lat1 = radians(float(pt1[1]))
            lon1 = radians(float(pt1[0]))
            lat2 = radians(float(pt2[1]))
            lon2 = radians(float(pt2[0]))
        except ValueError:
            return -1

        dlon = lon2 - lon1
        dlat = lat2 - lat1

        a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
        c = 2 * atan2(sqrt(a), sqrt(1 - a))

        distance = R * c

        return round(distance * 1000, 3)

    @staticmethod
    def convert_cam_direction(cam_dir):
        if cam_dir is None:
            return None

        cam_dirs = list()
        try:
            cam_dir = int(cam_dir)
            cam_dirs.append(cam_dir)
        except ValueError:
            cam_directions = cam_dir.split(";")
            for cam_d in cam_directions:
                try:
                    c_d = int(cam_d)
                    cam_dirs.append(c_d)
                except ValueError:
                    pass

        if not cam_dirs:
            return None

        return cam_dirs

    def inside_relevant_angle(self, cam, distance_to_camera):
        """
        Check if the given camera is  in driving direction.
            If no direction is given or an error occurs, the cam will always be considered for
                lookup
            If the emergency distance is met, the camera will be reported anyways
        :param cam: current camera
        :param distance_to_camera: actual distance to camera
        :return:
        """
        try:
            cam_direction = self.ITEMQUEUE[cam][9]
            cam_type = self.ITEMQUEUE[cam][0]
        except Exception as e:
            return True

        if distance_to_camera < self.emergency_angle_distance:
            self.print_log_line(f" Emergency report triggered for Speed Camera "
                                f"'{cam_type}' ({str(cam)}): "
                                f"Distance: {str(distance_to_camera)} m < "
                                f"{str(self.emergency_angle_distance)} m")
            return True

        if self.ccp_bearing is not None and cam_direction is not None:
            direction_ccp = self.calculate_direction(self.ccp_bearing)
            if direction_ccp is None:
                return True

            directions = list()
            for cam_d in cam_direction:
                directions.append(self.calculate_direction(cam_d))

            if direction_ccp in directions:
                return True
            else:
                self.print_log_line(f" Speed Camera '{cam_type}' ({str(cam)}): "
                                    f"CCP bearing angle: {self.ccp_bearing}, "
                                    f"Expected camera angle: "
                                    f"{str(cam_direction)}")
                return False
        return True

    def calculate_angle(self, pt1, pt2):
        lon1, lat1 = pt1, pt1
        lon2, lat2 = pt2, pt2

        x_diff = lon2 - lon1
        y_diff = lat2 - lat1
        angle = abs(math.atan2(y_diff, x_diff) * (180 / math.pi))
        return angle

    def camera_inside_camera_rectangle(self, cam):
        xtile, ytile = self.calculator.longlat2tile(cam[1],
                                                    cam[0],
                                                    self.calculator.zoom)
        if self.calculator.RECT_SPEED_CAM_LOOKAHAEAD is None:
            return True

        rectangle = self.calculator.RECT_SPEED_CAM_LOOKAHAEAD
        if rectangle is not None:
            return rectangle.point_in_rect(xtile, ytile)
        return False

    def calculate_camera_rectangle_radius(self):
        if self.calculator.RECT_SPEED_CAM_LOOKAHAEAD is None:
            return 0

        rectangle = self.calculator.RECT_SPEED_CAM_LOOKAHAEAD
        return self.calculator.calculate_rectangle_radius(rectangle.rect_height(),
                                                          rectangle.rect_width())

    def delete_passed_cameras(self):

        self.camera_deletion_lock = True
        item_dict = self.ITEMQUEUE.copy()
        item_dict_backup = self.ITEMQUEUE_BACKUP.copy()
        camera_items = [item_dict, item_dict_backup]
        self.camera_deletion_lock = False

        for index, cameras in enumerate(camera_items):
            for cam, cam_attributes in cameras.items():
                if self.delete_cameras_outside_lookahead_rectangle \
                        and not self.camera_inside_camera_rectangle(cam):
                    self.print_log_line(f" Deleting obsolete camera: {str(cam)} "
                                        f"(camera is outside current camera rectangle with "
                                        f"radius {self.calculate_camera_rectangle_radius()} "
                                        f"km)")
                    self.delete_obsolete_camera(index, cam, cam_attributes)
                    self.osm_wrapper.remove_marker_from_map(cam[0], cam[1])
                else:
                    if cam_attributes[2][0] == 'IGNORE' or cam_attributes[2][1] == 'IGNORE':
                        distance = self.check_distance_between_two_points(cam,
                                                                          (self.longitude,
                                                                           self.latitude))
                        if abs(distance) >= self.max_absolute_distance:
                            self.print_log_line(" Deleting obsolete camera: %s "
                                                "(max distance %d m < current distance %d m)"
                                                % (str(cam), self.max_absolute_distance,
                                                   abs(distance)))
                            self.delete_obsolete_camera(index, cam, cam_attributes)
                            self.osm_wrapper.remove_marker_from_map(cam[0], cam[1])
                        else:
                            if cam_attributes[6] > self.max_storage_time:
                                if cam_attributes[11] is False:
                                    self.print_log_line(" Deleting obsolete camera: %s "
                                                        "because of storage time "
                                                        "(max: %d seconds, current: %f seconds)"
                                                        % (str(cam),
                                                           self.max_storage_time,
                                                           cam_attributes[6]))
                                    self.delete_obsolete_camera(index, cam, cam_attributes)
                                    self.osm_wrapper.remove_marker_from_map(cam[0], cam[1])
                                else:
                                    self.print_log_line(f"Camera {cam} is new. Ignore deletion")
                    else:
                        distance = self.check_distance_between_two_points(cam, cam_attributes[2]) \
                                   - self.check_distance_between_two_points((self.longitude,
                                                                             self.latitude),
                                                                            cam_attributes[2])
                        if distance < 0 and abs(distance) >= self.max_absolute_distance:
                            self.print_log_line(" Deleting obsolete camera: %s "
                                                "(max distance %d m < current distance %d m)"
                                                % (str(cam), self.max_absolute_distance,
                                                   abs(distance)))
                            self.delete_obsolete_camera(index, cam, cam_attributes)
                            self.osm_wrapper.remove_marker_from_map(cam[0], cam[1])
                        else:
                            if distance < 0 and cam_attributes[5] == -1 and cam_attributes[6] > \
                                    self.max_storage_time:
                                if cam_attributes[11] is False:
                                    self.print_log_line(" Deleting obsolete camera: %s "
                                                        "because of storage time "
                                                        "(max: %d seconds, current: %f seconds)"
                                                        % (str(cam),
                                                           self.max_storage_time,
                                                           cam_attributes[6]))
                                    self.delete_obsolete_camera(index, cam, cam_attributes)
                                    self.osm_wrapper.remove_marker_from_map(cam[0], cam[1])
                                else:
                                    self.print_log_line(f"Camera {cam} is new. Ignore deletion")

    def delete_obsolete_camera(self, index, cam, cam_attributes):
        self.camera_deletion_lock = True
        try:
            if index == 0:
                self.ITEMQUEUE.pop(cam)
                self.start_times.pop(cam)
                self.remove_cached_camera(cam)
                self.update_calculator_cams(cam_attributes)
            else:
                self.ITEMQUEUE_BACKUP.pop(cam)
                self.start_times_backup.pop(cam)
        except Exception as e:
            self.print_log_line(f" Deleting obsolete camera: {str(cam)} failed! "
                                f"Error: {e}", log_level="ERROR")
        self.camera_deletion_lock = False

    def update_calculator_cams(self, cam_attributes):
        if self.calculator is not None and isinstance(self.calculator, RectangleCalculatorThread):
            if cam_attributes[0] == 'fix' and self.calculator.fix_cams > 0:
                self.calculator.fix_cams -= 1
            elif cam_attributes[0] == 'traffic' and self.calculator.traffic_cams > 0:
                self.calculator.traffic_cams -= 1
            elif cam_attributes[0] == 'distance' and self.calculator.distance_cams > 0:
                self.calculator.distance_cams -= 1
            elif cam_attributes[0] == 'mobile' and self.calculator.mobile_cams > 0:
                self.calculator.mobile_cams -= 1
            # Now update the kivy info page
            self.calculator.update_kivi_info_page()

    @staticmethod
    def calculate_direction(bearing):
        if 0 <= bearing <= 11:
            direction = 'TOP-N'
        elif 11 < bearing < 22:
            direction = 'N'
        elif 22 <= bearing < 45:
            direction = 'NNO'
        elif 45 <= bearing < 67:
            direction = 'NO'
        elif 67 <= bearing < 78:
            direction = 'ONO'
        elif 78 <= bearing <= 101:
            direction = 'TOP-O'
        elif 101 < bearing < 112:
            direction = 'O'
        elif 112 <= bearing < 135:
            direction = 'OSO'
        elif 135 <= bearing < 157:
            direction = 'SO'
        elif 157 <= bearing < 168:
            direction = 'SSO'
        elif 168 <= bearing < 191:
            direction = 'TOP-S'
        elif 191 <= bearing < 202:
            direction = 'S'
        elif 202 <= bearing < 225:
            direction = 'SSW'
        elif 225 <= bearing < 247:
            direction = 'SW'
        elif 247 <= bearing < 258:
            direction = 'WSW'
        elif 258 <= bearing < 281:
            direction = 'TOP-W'
        elif 281 <= bearing < 292:
            direction = 'W'
        elif 292 <= bearing < 315:
            direction = 'WNW'
        elif 315 <= bearing < 337:
            direction = 'NW'
        elif 337 <= bearing < 348:
            direction = 'NNW'
        elif 348 <= bearing < 355:
            direction = 'N'
        elif 355 <= bearing <= 360:
            direction = 'TOP-N'
        else:
            direction = None

        return direction
