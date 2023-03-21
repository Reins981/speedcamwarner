# qpy:kivy
# -*-coding:utf8;-*-
# qpy:2
# ts=4:sw=4:expandtab
'''
Created on 01.07.2014

@author: rkoraschnigg
'''

import time, sys, os
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

    def __init__(self, cv_voice, cv_speedcam, voice_prompt_queue, speedcamqueue, cv_overspeed,
                 overspeed_queue, osm_wrapper, calculator, ms, g, cond):
        StoppableThread.__init__(self)
        Logger.__init__(self, self.__class__.__name__)
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

        self.set_configs()

        # delete obsolete cameras every 30 seconds
        Clock.schedule_interval(lambda *x: self.delete_passed_cameras(),
                                self.traversed_cameras_interval)

    def set_configs(self):
        # report only cames in driving direction,
        # cams outside the defined angles relative to CCP will be ignored
        self.enable_inside_relevant_angle_feature = True
        # Max absolute distance between the car and the camera.
        # If the calculated absolute distance of traversed cameras is reached,
        # those cameras will be deleted
        self.max_absolute_distance = 300000
        # Initial max storage time. If this time has passed,
        # cameras which have been traversed by the car
        # and which have never been initialized once (last_distance = -1) will be deleted
        # The value increases by 600 units if the ccp is UNSTABLE assuming the driver makes a
        # UTURN and cameras behind are still relevant
        self.max_storage_time = 14400
        # Traversed cameras will be checked every X seconds
        self.traversed_cameras_interval = 3

        # SpeedLimits Base URL example##
        self.baseurl = 'http://overpass-api.de/api/interpreter?'
        self.querystring1 = 'data=[out:json];'
        self.querystring2 = 'way["highway"~"."](around:5,'
        self.querystring3 = '50.7528080,2.0377858'
        self.querystring4 = ');out geom;'

    def run(self):

        while not self.cond.terminate:
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
                                                        max_speed ,
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
                                        f"{current_distance} km")
                    self.ITEMQUEUE[cam] = cam_attributes
                    self.ITEMQUEUE[cam][1] = False
                    self.ITEMQUEUE[cam][6] = start_time
                    self.ITEMQUEUE[cam][8] = current_distance
                    self.ITEMQUEUE[cam][5] = -1
                    # delete backup camera and startup time
                    self.ITEMQUEUE_BACKUP.pop(cam)
                    self.start_times_backup.pop(cam)

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
                self.update_kivi_speedcam('FREEFLOW')
                self.update_bar_widget_1000m(color=2)
                self.update_bar_widget_500m(color=2)
                self.update_bar_widget_300m(color=2)
                self.update_bar_widget_100m(color=2)
                self.update_bar_widget_meters('')
                self.update_cam_road(reset=True)
                self.update_max_speed(reset=True)
                self.update_calculator_cams(cam_attributes)
            else:
                # Make sure the camera still exists in the original item queue
                if cam in self.start_times and cam in self.ITEMQUEUE:
                    start_time = time.time() - self.start_times[cam]
                    self.ITEMQUEUE[cam][6] = start_time
                    self.ITEMQUEUE[cam][11] = False

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
        # Nothing to sort
        if cam is None:
            self.update_cam_road(reset=True)
            return False
        # Sort the follow up cameras based on the list of cameras - the actual camera
        cam_list_followup = cam_list.copy()
        cam_list_followup.remove(cam_entry)
        next_cam, next_cam_entry = self.sort_pois(cam_list_followup)
        # Set up the road name and the distance for the next camera
        next_cam_road = ""
        next_cam_distance = ""
        process_next_cam = False
        if next_cam is not None and next_cam in self.ITEMQUEUE:
            tmp = deepcopy(self.ITEMQUEUE)
            next_cam_road = tmp[next_cam][7]
            next_cam_distance = str(next_cam_entry[1]) + "m"
            process_next_cam = True

        try:
            cam_attributes = self.ITEMQUEUE[cam]
        except KeyError:
            return False

        if self.enable_inside_relevant_angle_feature:
            if not self.inside_relevant_angle(cam):
                SpeedCamWarnerThread.CAM_IN_PROGRESS = False
                self.update_kivi_speedcam('FREEFLOW')
                self.update_bar_widget_1000m(color=2)
                self.update_bar_widget_500m(color=2)
                self.update_bar_widget_300m(color=2)
                self.update_bar_widget_100m(color=2)
                self.update_bar_widget_meters('')
                self.update_cam_road(road="Camera dismissed (Angle)", color=(0, 1, .3, .8))
                self.update_max_speed(reset=True)
                self.print_log_line(" Leaving Speed Camera with coordinates: "
                                    "%s %s because of Angle mismatch" % (cam[0], cam[1]))
                # self.voice_prompt_queue.produce_camera_status(self.cv_voice, 'ANGLE_MISMATCH')
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
                self.print_log_line("-> Future speed cam in queue is: "
                                    "coords: (%f, %f), road name: %s, distance: %s "
                                    % (next_cam[0], next_cam[1], next_cam_road, next_cam_distance))
            else:
                self.print_log_line("No future speed cam in queue found")

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
            self.update_kivi_speedcam('FREEFLOW')
            self.update_bar_widget_1000m(color=2)
            self.update_bar_widget_500m(color=2)
            self.update_bar_widget_300m(color=2)
            self.update_bar_widget_100m(color=2)
            self.update_bar_widget_meters('')
            self.update_cam_road(reset=True)
            self.update_max_speed(reset=True)
            del self.INSERTED_SPEEDCAMS[:]

        return True

    def backup_camera(self, cam, distance):
        self.print_log_line(f"Backup camera {str(cam)} with last distance {distance} km")
        self.ITEMQUEUE_BACKUP[cam] = deepcopy(self.ITEMQUEUE[cam])
        self.ITEMQUEUE_BACKUP[cam][1] = False
        self.ITEMQUEUE_BACKUP[cam][8] = distance
        self.start_times_backup[cam] = time.time() - deepcopy(self.ITEMQUEUE[cam][6])

    def delete_cameras(self, cams_to_delete):
        if len(cams_to_delete) > 0:
            self.voice_prompt_queue.produce_camera_status(self.cv_voice, 'SPEEDCAM_REMOVED')
        # delete cams
        for cam in cams_to_delete:
            self.ITEMQUEUE.pop(cam)
            self.start_times.pop(cam)
        del cams_to_delete[:]

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

    def trigger_speed_cam_update(self, distance=0, cam_coordinates=(0, 0), speedcam='fix',
                                 ccp_node=(0, 0), linked_list=None, tree=None,
                                 last_distance=-1, max_speed=None,
                                 next_cam_road="", next_cam_distance="", process_next_cam=False):

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
                self.update_kivi_speedcam(speedcam)
                self.update_bar_widget_100m()
                self.update_bar_widget_300m()
                self.update_bar_widget_500m()
                self.update_bar_widget_1000m()
                self.update_bar_widget_meters(distance)
                if cam_coordinates in self.ITEMQUEUE:
                    tmp = deepcopy(self.ITEMQUEUE)
                    self.update_cam_road(road=tmp[cam_coordinates][7])
                    self.update_max_speed(max_speed=self.ITEMQUEUE[cam_coordinates][10])

            if last_distance == 100:
                Clock.schedule_once(
                    partial(self.check_road_name, linked_list, tree, cam_coordinates), 0)
                self.update_kivi_speedcam(speedcam)
                self.update_bar_widget_100m()
                self.update_bar_widget_300m()
                self.update_bar_widget_500m()
                self.update_bar_widget_1000m()
                self.update_bar_widget_meters(distance)
                if cam_coordinates in self.ITEMQUEUE:
                    tmp = deepcopy(self.ITEMQUEUE)
                    self.update_cam_road(road=tmp[cam_coordinates][7])
                    self.update_max_speed(max_speed=max_speed)

            last_distance = 100
            dismiss = False
            self.ITEMQUEUE[cam_coordinates][0] = speedcam
            self.ITEMQUEUE[cam_coordinates][1] = dismiss
            self.ITEMQUEUE[cam_coordinates][2] = ccp_node
            self.ITEMQUEUE[cam_coordinates][3] = linked_list
            self.ITEMQUEUE[cam_coordinates][4] = tree
            self.ITEMQUEUE[cam_coordinates][5] = last_distance
            self.ITEMQUEUE[cam_coordinates][8] = distance
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
                self.update_kivi_speedcam(speedcam)
                self.update_bar_widget_100m(color=2)
                self.update_bar_widget_300m()
                self.update_bar_widget_500m()
                self.update_bar_widget_1000m()
                self.update_bar_widget_meters(distance)
                if cam_coordinates in self.ITEMQUEUE:
                    self.update_cam_road(road=self.ITEMQUEUE[cam_coordinates][7])
                    self.update_max_speed(max_speed=max_speed)
            else:

                if last_distance == 300:
                    Clock.schedule_once(
                        partial(self.check_road_name, linked_list, tree, cam_coordinates), 0)
                    self.update_kivi_speedcam(speedcam)
                    self.update_bar_widget_100m(color=2)
                    self.update_bar_widget_300m()
                    self.update_bar_widget_500m()
                    self.update_bar_widget_1000m()
                    self.update_bar_widget_meters(distance)
                    if cam_coordinates in self.ITEMQUEUE:
                        tmp = deepcopy(self.ITEMQUEUE)
                        self.update_cam_road(road=tmp[cam_coordinates][7])
                        self.update_max_speed(max_speed=max_speed)
                else:
                    SpeedCamWarnerThread.CAM_IN_PROGRESS = False
                    self.update_kivi_speedcam('FREEFLOW')
                    self.update_bar_widget_1000m(color=2)
                    self.update_bar_widget_500m(color=2)
                    self.update_bar_widget_300m(color=2)
                    self.update_bar_widget_100m(color=2)
                    self.update_bar_widget_meters('')
                    self.update_cam_road(reset=True) if not process_next_cam \
                        else self.update_cam_road(road=f"{next_cam_road} -> {next_cam_distance}",
                                                  color=(0, 1, .3, .8))
                    self.update_max_speed(reset=True)
                    dismiss = "to_be_stored"

            last_distance = 300
            self.ITEMQUEUE[cam_coordinates][0] = speedcam
            self.ITEMQUEUE[cam_coordinates][1] = dismiss
            self.ITEMQUEUE[cam_coordinates][2] = ccp_node
            self.ITEMQUEUE[cam_coordinates][3] = linked_list
            self.ITEMQUEUE[cam_coordinates][4] = tree
            self.ITEMQUEUE[cam_coordinates][5] = last_distance
            self.ITEMQUEUE[cam_coordinates][8] = distance
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
                self.update_kivi_speedcam(speedcam)
                self.update_bar_widget_100m(color=2)
                self.update_bar_widget_300m(color=2)
                self.update_bar_widget_500m()
                self.update_bar_widget_1000m()
                self.update_bar_widget_meters(distance)
                if cam_coordinates in self.ITEMQUEUE:
                    self.update_cam_road(road=self.ITEMQUEUE[cam_coordinates][7])
                    self.update_max_speed(max_speed=max_speed)
            else:

                if last_distance == 500:
                    Clock.schedule_once(
                        partial(self.check_road_name, linked_list, tree, cam_coordinates), 0)
                    self.update_kivi_speedcam(speedcam)
                    self.update_bar_widget_100m(color=2)
                    self.update_bar_widget_300m(color=2)
                    self.update_bar_widget_500m()
                    self.update_bar_widget_1000m()
                    self.update_bar_widget_meters(distance)
                    if cam_coordinates in self.ITEMQUEUE:
                        tmp = deepcopy(self.ITEMQUEUE)
                        self.update_cam_road(road=tmp[cam_coordinates][7])
                        self.update_max_speed(max_speed=max_speed)
                else:
                    SpeedCamWarnerThread.CAM_IN_PROGRESS = False
                    self.update_kivi_speedcam('FREEFLOW')
                    self.update_bar_widget_1000m(color=2)
                    self.update_bar_widget_500m(color=2)
                    self.update_bar_widget_300m(color=2)
                    self.update_bar_widget_100m(color=2)
                    self.update_bar_widget_meters('')
                    self.update_cam_road(reset=True) if not process_next_cam \
                        else self.update_cam_road(road=f"{next_cam_road} -> {next_cam_distance}",
                                                  color=(0, 1, .3, .8))
                    self.update_max_speed(reset=True)
                    dismiss = "to_be_stored"

            last_distance = 500
            self.ITEMQUEUE[cam_coordinates][0] = speedcam
            self.ITEMQUEUE[cam_coordinates][1] = dismiss
            self.ITEMQUEUE[cam_coordinates][2] = ccp_node
            self.ITEMQUEUE[cam_coordinates][3] = linked_list
            self.ITEMQUEUE[cam_coordinates][4] = tree
            self.ITEMQUEUE[cam_coordinates][5] = last_distance
            self.ITEMQUEUE[cam_coordinates][8] = distance
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
                self.update_kivi_speedcam(speedcam)
                self.update_bar_widget_100m(color=2)
                self.update_bar_widget_300m(color=2)
                self.update_bar_widget_500m(color=2)
                self.update_bar_widget_1000m()
                self.update_bar_widget_meters(distance)
                if cam_coordinates in self.ITEMQUEUE:
                    self.update_cam_road(road=self.ITEMQUEUE[cam_coordinates][7])
                    self.update_max_speed(max_speed=max_speed)
            else:

                if last_distance == 1000:
                    Clock.schedule_once(
                        partial(self.check_road_name, linked_list, tree, cam_coordinates), 0)
                    self.update_kivi_speedcam(speedcam)
                    self.update_bar_widget_100m(color=2)
                    self.update_bar_widget_300m(color=2)
                    self.update_bar_widget_500m(color=2)
                    self.update_bar_widget_1000m()
                    self.update_bar_widget_meters(distance)
                    if cam_coordinates in self.ITEMQUEUE:
                        tmp = deepcopy(self.ITEMQUEUE)
                        self.update_cam_road(road=tmp[cam_coordinates][7])
                        self.update_max_speed(max_speed=max_speed)
                else:
                    SpeedCamWarnerThread.CAM_IN_PROGRESS = False
                    self.update_kivi_speedcam('FREEFLOW')
                    self.update_bar_widget_1000m(color=2)
                    self.update_bar_widget_500m(color=2)
                    self.update_bar_widget_300m(color=2)
                    self.update_bar_widget_100m(color=2)
                    self.update_bar_widget_meters('')
                    self.update_cam_road(reset=True) if not process_next_cam \
                        else self.update_cam_road(road=f"{next_cam_road} -> {next_cam_distance}",
                                                  color=(0, 1, .3, .8))
                    self.update_max_speed(reset=True)
                    dismiss = "to_be_stored"

            last_distance = 1000
            self.ITEMQUEUE[cam_coordinates][0] = speedcam
            self.ITEMQUEUE[cam_coordinates][1] = dismiss
            self.ITEMQUEUE[cam_coordinates][2] = ccp_node
            self.ITEMQUEUE[cam_coordinates][3] = linked_list
            self.ITEMQUEUE[cam_coordinates][4] = tree
            self.ITEMQUEUE[cam_coordinates][5] = last_distance
            self.ITEMQUEUE[cam_coordinates][8] = distance
        elif 1000 < distance <= 1500:
            SpeedCamWarnerThread.CAM_IN_PROGRESS = True
            dismiss = False
            if last_distance == -1 or last_distance > 1001:
                self.print_log_line(" %s speed cam ahead with distance %d m" % (
                    speedcam, int(distance)))
                self.voice_prompt_queue.produce_camera_status(self.cv_voice, 'CAMERA_AHEAD')
                self.update_kivi_speedcam('CAMERA_AHEAD')
                self.update_bar_widget_meters(distance)
            else:
                if last_distance == 1001:
                    SpeedCamWarnerThread.CAM_IN_PROGRESS = False
                    self.update_kivi_speedcam('CAMERA_AHEAD')
                    self.update_bar_widget_meters(distance)
                    if cam_coordinates in self.ITEMQUEUE:
                        tmp = deepcopy(self.ITEMQUEUE)
                        self.update_cam_road(road=tmp[cam_coordinates][7])
                else:
                    SpeedCamWarnerThread.CAM_IN_PROGRESS = False
                    self.update_kivi_speedcam('FREEFLOW')
                    self.update_bar_widget_1000m(color=2)
                    self.update_bar_widget_500m(color=2)
                    self.update_bar_widget_300m(color=2)
                    self.update_bar_widget_100m(color=2)
                    self.update_bar_widget_meters('')
                    self.update_cam_road(reset=True) if not process_next_cam \
                        else self.update_cam_road(road=f"{next_cam_road} -> {next_cam_distance}",
                                                  color=(0, 1, .3, .8))
                    self.update_max_speed(reset=True)
                    dismiss = "to_be_stored"

            last_distance = 1001
            self.ITEMQUEUE[cam_coordinates][0] = speedcam
            self.ITEMQUEUE[cam_coordinates][1] = dismiss
            self.ITEMQUEUE[cam_coordinates][2] = ccp_node
            self.ITEMQUEUE[cam_coordinates][3] = linked_list
            self.ITEMQUEUE[cam_coordinates][4] = tree
            self.ITEMQUEUE[cam_coordinates][5] = last_distance
            self.ITEMQUEUE[cam_coordinates][8] = distance
        else:
            if last_distance == -1 and distance < self.max_absolute_distance:
                SpeedCamWarnerThread.CAM_IN_PROGRESS = False
                return
            self.print_log_line(" %s speed cam OUTSIDE relevant radius -> distance %d m" % (
                speedcam, int(distance)))

            SpeedCamWarnerThread.CAM_IN_PROGRESS = False
            self.update_kivi_speedcam('FREEFLOW')
            self.update_bar_widget_1000m(color=2)
            self.update_bar_widget_500m(color=2)
            self.update_bar_widget_300m(color=2)
            self.update_bar_widget_100m(color=2)
            self.update_bar_widget_meters('')
            self.update_cam_road(reset=True) if not process_next_cam \
                else self.update_cam_road(road=f"{next_cam_road} -> {next_cam_distance}",
                                          color=(0, 1, .3, .8))
            self.update_max_speed(reset=True)

            last_distance = self.max_absolute_distance
            # Those cameras will not be dismissed until their storage time has passed or they are
            # above max_absolute_distance
            dismiss = "to_be_stored"
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
                return

            if self.ITEMQUEUE[cam_coordinates][7] is None:
                node_id = linked_list.match_node((cam_coordinates[1], cam_coordinates[0]))
                if node_id:
                    if node_id in tree:
                        self.print_log_line(
                            ' Found node_id %s in list and tree' % (str(node_id)))
                        way = tree[node_id]
                        # get the way attributes
                        if tree.hasRoadNameAttribute(way):
                            self.print_log_line(' road name in tree')
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

    def update_cam_road(self, road=None, reset=False, color=None):
        self.ms.update_cam_road(road, reset, color=color)

    def update_max_speed(self, max_speed=None, reset=False):
        if reset:
            if self.ms.maxspeed.text != "->->->":
                font_size = 230
                self.ms.maxspeed.text = "->->->"
                self.ms.maxspeed.color = (0, 1, .3, .8)
                self.ms.maxspeed.font_size = font_size
                Clock.schedule_once(self.ms.maxspeed.texture_update)
        else:
            if max_speed:
                if self.ms.maxspeed.text != str(max_speed):
                    font_size = 250
                    self.ms.maxspeed.text = str(max_speed)
                    self.ms.maxspeed.color = (0, 1, .3, .8)
                    self.ms.maxspeed.font_size = font_size
                    Clock.schedule_once(self.ms.maxspeed.texture_update)
            else:
                if self.ms.maxspeed.text != "->->->":
                    font_size = 230
                    self.ms.maxspeed.text = "->->->"
                    self.ms.maxspeed.color = (0, 1, .3, .8)
                    self.ms.maxspeed.font_size = font_size
                    Clock.schedule_once(self.ms.maxspeed.texture_update)

        if reset or not max_speed:
            self.overspeed_queue.produce(self.cv_overspeed, {'maxspeed': 10000})
        else:
            try:
                self.overspeed_queue.produce(self.cv_overspeed, {'maxspeed': int(max_speed)})
            except:
                pass

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

    def inside_relevant_angle(self, cam):
        """
        If no direction is given or an error occurs, the cam will always be considered for lookup
        :param cam:
        :return:
        """
        try:
            cam_direction = self.ITEMQUEUE[cam][9]
            cam_type = self.ITEMQUEUE[cam][0]
        except Exception as e:
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

    def delete_passed_cameras(self):

        item_dict = self.ITEMQUEUE.copy()
        item_dict_backup = self.ITEMQUEUE_BACKUP.copy()
        camera_items = [item_dict, item_dict_backup]

        for index, cameras in enumerate(camera_items):
            for cam, cam_attributes in cameras.items():
                if cam_attributes[2][0] == 'IGNORE' or cam_attributes[2][1] == 'IGNORE':
                    distance = self.check_distance_between_two_points(cam,
                                                                      (self.longitude,
                                                                       self.latitude))
                    if abs(distance) >= self.max_absolute_distance:
                        try:
                            self.print_log_line(" Deleting obsolete camera: %s "
                                                "(max distance %d m > current distance %d m)"
                                                % (str(cam), self.max_absolute_distance, abs(distance)))
                            if index == 0:
                                self.ITEMQUEUE.pop(cam)
                                self.start_times.pop(cam)
                                self.remove_cached_camera(cam)
                                self.update_calculator_cams(cam_attributes)
                            else:
                                self.ITEMQUEUE_BACKUP.pop(cam)
                                self.start_times_backup.pop(cam)
                        except Exception as e:
                            pass
                    else:
                        if cam_attributes[6] > self.max_storage_time:
                            if cam_attributes[11] is False:
                                try:
                                    self.print_log_line(" Deleting obsolete camera: %s "
                                                        "because of storage time "
                                                        "(max: %d seconds, current: %f seconds)"
                                                        % (str(cam),
                                                           self.max_storage_time,
                                                           cam_attributes[6]))
                                    if index == 0:
                                        self.ITEMQUEUE.pop(cam)
                                        self.start_times.pop(cam)
                                        self.remove_cached_camera(cam)
                                        self.update_calculator_cams(cam_attributes)
                                    else:
                                        self.ITEMQUEUE_BACKUP.pop(cam)
                                        self.start_times_backup.pop(cam)
                                except Exception as e:
                                    pass
                            else:
                                self.print_log_line(f"Camera {cam} is new. Ignore deletion")
                else:
                    distance = self.check_distance_between_two_points(cam, cam_attributes[2]) \
                               - self.check_distance_between_two_points((self.longitude,
                                                                         self.latitude),
                                                                        cam_attributes[2])
                    if distance < 0 and abs(distance) >= self.max_absolute_distance:
                        try:
                            self.print_log_line(" Deleting obsolete camera: %s "
                                                "(max distance %d m > current distance %d m)"
                                                % (str(cam), self.max_absolute_distance, abs(distance)))
                            if index == 0:
                                self.ITEMQUEUE.pop(cam)
                                self.start_times.pop(cam)
                                self.remove_cached_camera(cam)
                                self.update_calculator_cams(cam_attributes)
                            else:
                                self.ITEMQUEUE_BACKUP.pop(cam)
                                self.start_times_backup.pop(cam)
                        except Exception as e:
                            pass
                    else:
                        if distance < 0 and cam_attributes[5] == -1 and cam_attributes[6] > \
                                self.max_storage_time:
                            if cam_attributes[11] is False:
                                try:
                                    self.print_log_line(" Deleting obsolete camera: %s "
                                                        "because of storage time "
                                                        "(max: %d seconds, current: %f seconds)"
                                                        % (str(cam),
                                                           self.max_storage_time,
                                                           cam_attributes[6]))
                                    if index == 0:
                                        self.ITEMQUEUE.pop(cam)
                                        self.start_times.pop(cam)
                                        self.remove_cached_camera(cam)
                                        self.update_calculator_cams(cam_attributes)
                                    else:
                                        self.ITEMQUEUE_BACKUP.pop(cam)
                                        self.start_times_backup.pop(cam)
                                except Exception as e:
                                    pass
                            else:
                                self.print_log_line(f"Camera {cam} is new. Ignore deletion")

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
