# -*-coding:utf8;-*-
# qpy:2
# ts=4:sw=4:expandtab
'''
Created on 01.07.2014

@author: rkoraschnigg
'''

from __future__ import division
import time, calendar
from Logger import Logger
import math
import json
import unicodedata
from random import randint
from urllib.request import urlopen
from urllib.error import URLError, HTTPError
from kivy.clock import Clock
from geopy.geocoders import Nominatim
from decimal import Decimal
from collections import OrderedDict, Counter
from ThreadBase import StoppableThread, ThreadPool
from OSMWrapper import maps
from LinkedListGenerator import DoubleLinkedListNodes
from TreeGenerator import BinarySearchTree
from enum import Enum
from collections import defaultdict


class FilteredRoadClasses(Enum):
    # A = 9
    # B = 10
    # C = 11
    # D = 12
    # E = 13
    # F = 14
    # G = 15
    # H = 16
    # II = 17
    J = 10000

    @classmethod
    def has_value(cls, value):
        return value in cls._value2member_map_


class MostProbableWay(Logger):
    def __init__(self, rectangle_calculator_thread):
        self.mostprobable_road = "<>"
        self.mostprobable_speed = ""
        self.previous_road = "<>"
        self.previous_speed = ""
        self.mostprobable_tags = False
        self.previous_tags = False
        self.first_lookup = True
        self.next_mpr_list_complete = False
        self.last_roadname_list = []
        self.next_possible_mpr_list = []
        self.max_road_names = 0
        self.max_possible_mpr_candidates = 0
        self.unstable_counter = 0
        self.rectangle_calculator_thread = rectangle_calculator_thread

        # MAX for unstable roads
        self.unstable_limit = 3
        Logger.__init__(self, self.__class__.__name__)

    def increase_unstable_counter(self):
        self.unstable_counter += 1

    def get_unstable_counter(self):
        return self.unstable_counter

    def reset_unstable_counter(self):
        self.unstable_counter = 0

    def set_maximum_number_of_road_names(self, maxnum):
        self.max_road_names = maxnum

    def set_maximum_number_of_next_possible_mprs(self, maxnum):
        self.max_possible_mpr_candidates = maxnum

    def get_last_roadname_list(self):
        return self.last_roadname_list

    def get_next_possible_mpr_list(self):
        return self.next_possible_mpr_list

    # list of functional road class -> roadname tuples indicating the road that has a chance of
    # becoming the next most probable road
    def add_attributes_to_next_possible_mpr_list(self, current_fr, roadname):
        if len(
                self.next_possible_mpr_list) >= self.max_possible_mpr_candidates:
            return 'MAX_REACHED'
        self.next_possible_mpr_list.append((current_fr, roadname))
        return 'MAX_NOT_REACHED'

    def clear_next_possible_mpr_list(self):
        del self.next_possible_mpr_list[:]

    # list of most current road name updates
    def add_roadname_to_roadname_list(self, roadname):
        if len(self.last_roadname_list) == self.max_road_names:
            del self.last_roadname_list[:]
        self.last_roadname_list.append(roadname)

    def is_next_possible_mpr_new_mpr(self,
                                     current_fr,
                                     most_probable_road_class,
                                     ramp,
                                     next_mpr_list_complete):

        if 0 <= most_probable_road_class <= 1:
            self.set_maximum_number_of_next_possible_mprs(6)
        else:
            self.set_maximum_number_of_next_possible_mprs(4)

        # dismiss false positive motorway lookups if mpr is on another road class
        if (isinstance(current_fr, int) and 0 <= current_fr <= 1) or ramp:
            if most_probable_road_class > 1:
                try:
                    rc_index = self.rectangle_calculator_thread.road_candidates.index(
                        most_probable_road_class)
                    self.rectangle_calculator_thread.road_candidates[
                        rc_index] = current_fr
                except:
                    return True
                self.print_log_line(
                    ' Dismiss motorway/trunk/ramp, we are still on road class %s'
                    % str(most_probable_road_class))
                return False
            return True

        road_class_entries = []
        road_name_entries = []
        for attributes in self.next_possible_mpr_list:
            road_class_entries.append(attributes[0])
            road_name_entries.append(attributes[1])

        crossroad_0 = None
        crossroad_1 = None
        crossroad_mpr = True
        for road_name in road_name_entries:
            crossroad = road_name.split('/')
            # we found a crossroad
            if len(crossroad) == 2:
                crossroad_0 = crossroad[0]
                crossroad_1 = crossroad[1]
                break
        crossroad_name = ''
        if isinstance(crossroad_0, str) and isinstance(crossroad_1, str):
            crossroad_name = '/'.join((crossroad_0, crossroad_1))
            # check all roadnames if the crossing is a substring of all road names

            # check the first part of the crossroad
            for road_name in road_name_entries:
                if road_name.find(crossroad_0) == -1:
                    crossroad_mpr = False
                    break

            # check the second part of the crossroad
            crossroad_mpr = True
            if not crossroad_mpr:
                for road_name in road_name_entries:
                    if road_name.find(crossroad_0) == -1:
                        crossroad_mpr = False
                        break

        return next_mpr_list_complete and (
                len(set(self.next_possible_mpr_list)) == 1 or
                Counter(road_class_entries)[current_fr] == len(
            road_class_entries) or crossroad_mpr)

    def is_first_lookup(self):
        return self.first_lookup

    def set_first_lookup(self, lookup):
        self.first_lookup = lookup

    def set_most_probable_road(self, roadname):
        self.mostprobable_road = roadname

    def set_most_probable_speed(self, speed):
        self.mostprobable_speed = speed

    def set_previous_road(self, roadname):
        self.previous_road = roadname

    def set_previous_speed(self, speed):
        self.previous_speed = speed

    def set_most_probable_tags(self, combined_tags):
        self.mostprobable_tags = combined_tags

    def set_previous_tags(self, combined_tags):
        self.previous_tags = combined_tags

    def get_most_probable_road(self):
        return self.mostprobable_road

    def get_most_probable_speed(self):
        return self.mostprobable_speed

    def get_most_probable_tags(self):
        return self.mostprobable_tags

    def get_previous_road(self):
        return self.previous_road

    def get_previous_speed(self):
        return self.previous_speed

    def get_previous_tags(self):
        return self.previous_tags


class Point(object):
    # A point identified by (x,y) coordinates.
    def __init__(self, x=0.0, y=0.0):
        self.x = x
        self.y = y

    def add(self, p):
        # Point(x1+x2, y1+y2)
        return Point(self.x + p.x, self.y + p.y)


class Rect(object):
    # A rectangle identified by 2 points or by a point list.
    def __init__(self, pt1=None, pt2=None, point_list=[]):
        self.height = 0
        self.width = 0
        self.ident = ''
        self.rect_string = ''
        # close to border max values
        self.max_close_to_border_value = 0.300
        self.max_close_to_border_value_look_ahead = 0.200
        # initialize a rectangle from 2 points
        self.set_points(pt1, pt2, point_list)

    def delete_rect(self):
        del self

    def set_points(self, pt1, pt2, point_list):
        # reset the rectangle
        x1 = 0
        y1 = 0
        x2 = 0
        y2 = 0

        if 0 < len(point_list) < 4:
            self.left = 0
            self.top = 0
            self.right = 0
            self.bottom = 0
            return

        if len(point_list) == 4:
            self.left = point_list[0]
            self.top = point_list[1]
            self.right = point_list[2]
            self.bottom = point_list[3]
            return

        if pt1 == None or pt2 == None:
            self.left = 0
            self.top = 0
            self.right = 0
            self.bottom = 0
            return

        if isinstance(pt1, Point):
            (x1, y1) = pt1.x, pt1.y
            (x2, y2) = pt2.x, pt2.y
        else:
            (x1, y1) = pt1[0], pt1[1]
            (x2, y2) = pt2[0], pt2[1]

        self.left = min(x1, x2)
        self.top = min(y1, y2)
        self.right = max(x1, x2)
        self.bottom = max(y1, y2)
        return

    def set_rectangle_ident(self, ident):
        self.ident = ident

    def get_rectangle_ident(self):
        return self.ident

    def set_rectangle_string(self, rect_string):
        self.rect_string = rect_string

    def get_rectangle_string(self):
        return self.rect_string

    def rect_height(self):
        self.height = self.bottom - self.top
        return self.height

    def rect_width(self):
        self.width = self.right - self.left
        return self.width

    def top_left(self):
        # returns the top left corner as a point
        return Point(self.left, self.top)

    def bottom_right(self):
        # return the bottom right corner as a point
        return Point(self.right, self.bottom)

    def top_right(self):
        # return the top right corner as a point
        return Point(self.right, self.top)

    def bottom_left(self):
        # return the bottom left corner as a point
        return Point(self.left, self.bottom)

    def expanded_by(self, n):
        """Return a rectangle with extended borders.
        Create a new rectangle that is wider and taller than the
        immediate one. All sides are extended by n points.
        """
        pt1 = Point(self.left - n, self.top - n)
        pt2 = Point(self.right + n, self.bottom + n)
        return Rect(pt1, pt2)

    def intersect_rect_with(self, rect, rectangle_string):
        if isinstance(rect, Rect):
            left = min(self.left, rect.left)
            right = max(self.right, rect.right)
            bottom = min(self.bottom, rect.bottom)
            top = max(self.top, rect.top)

            return rectangle_string, Rect(point_list=[left, top, right, bottom])
        else:
            return None, None

    # parameters: x, y in tile format
    # rect consisting of 4 Points(x,y) given in a list
    def point_in_rect(self, xtile, ytile):
        inside = False
        x, y = xtile, ytile
        if x is None or y is None:
            return False

        rect = [self.top_left(), self.top_right(), self.bottom_left(),
                self.bottom_right()]
        # len of rect
        n = len(rect)

        pt1x, pt1y = rect[0].x, rect[0].y

        for i in range(n + 1):
            pt2x, pt2y = rect[i % n].x, rect[i % n].y
            if y >= min(pt1y, pt2y):
                if y <= max(pt1y, pt2y):
                    if x >= min(pt1x, pt2x):
                        if x <= max(pt1x, pt2x):
                            if pt1y != pt2y:
                                inside = not inside
                                if inside:
                                    return inside
            pt1x, pt1y = pt2x, pt2y

        return inside

    def points_close_to_border(self, xtile, ytile, look_ahead=False):
        x, y = xtile, ytile
        if look_ahead:
            max_val = self.max_close_to_border_value_look_ahead
        else:
            max_val = self.max_close_to_border_value

        rect = [self.top_left(), self.top_right(), self.bottom_left(),
                self.bottom_right()]
        # len of rect
        n = len(rect)

        pt1x, pt1y = rect[0].x, rect[0].y
        for i in range(n + 1):
            pt2x, pt2y = rect[i % n].x, rect[i % n].y
            if abs(y - min(pt1y, pt2y)) <= max_val or abs(
                    y - max(pt1y, pt2y)) <= max_val or abs(
                x - max(pt1x, pt2x)) <= max_val or abs(
                x - min(pt1x, pt2x)) <= max_val:
                return True
            pt1x, pt1y = pt2x, pt2y

        return False


class RectangleCalculatorThread(StoppableThread, Logger):
    thread_lock = False

    def __init__(self,
                 cv_vector,
                 cv_voice,
                 cv_interrupt,
                 cv_speedcam,
                 cv_overspeed,
                 cv_border,
                 cv_border_reverse,
                 voice_prompt_queue,
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
                 vector_data,
                 osm_wrapper,
                 cond):

        StoppableThread.__init__(self)
        Logger.__init__(self, self.__class__.__name__)
        self.cv_vector = cv_vector
        self.cv_voice = cv_voice
        self.cv_interrupt = cv_interrupt
        self.cv_speedcam = cv_speedcam
        self.cv_overspeed = cv_overspeed
        self.cv_border = cv_border
        self.cv_border_reverse = cv_border_reverse
        self.voice_prompt_queue = voice_prompt_queue
        self.interruptqueue = interruptqueue
        self.speed_cam_queue = speedcamqueue
        self.overspeed_queue = overspeed_queue
        self.cv_currentspeed = cv_currentspeed
        self.currentspeed_queue = currentspeed_queue
        self.poi_queue = poi_queue
        self.cv_map = cv_map
        self.map_queue = map_queue
        self.cv_poi = cv_poi
        self.ms = ms
        self.s = s
        self.ml = ml
        self.vector_data = vector_data
        self.cond = cond
        self.osm_wrapper = osm_wrapper
        self.matching_rect = "NOTSET"
        self.previous_rect = "NOTSET"
        self.failed_rect = ""

        # global items
        self.direction_cached = ""
        self.osm_lookup_properties = []
        self.osm_lookup_properties_extrapolated = []
        self.combined_tags_array = []
        self.RECT_ATTRIBUTES_EXTRAPOLATED = {}
        self.RECT_ATTRIBUTES_EXTRAPOLATED_KEYS = []
        self.RECT_ATTRIBUTES = {}
        self.RECT_KEYS = []
        self.RECT_VALUES = []
        self.RECT_VALUES_EXTRAPOLATED = []
        self.RECT_ATTRIBUTES_INTERSECTED = {}
        self.RECT_SPEED_CAM_LOOKAHAEAD = None
        self.speed_cam_dict = []
        self.road_candidates = []

        # default timeout
        self.url_timeout = 25
        self.extrapolated_number = 0
        self.download_time = 0
        self.fix_cams = 0
        self.traffic_cams = 0
        self.distance_cams = 0
        self.mobile_cams = 0
        self.cspeed = 0
        self.cspeed_cached = 0
        self.cspeed_converted = 0
        self.accuracy = 0
        self.number_distance_cams = 0
        self.rectangle_radius = 0.0
        self.longitude_cached = 0.0
        self.latitude_cached = 0.0
        self.bearing_cached = 0.0
        self.longitude_extrapolated = 0.0
        self.latitude_extrapolated = 0.0
        self.XTILE_MIN = None
        self.YTILE_MIN = None
        self.XTILE_MAX = None
        self.YTILE_MAX = None
        self.longitude = None
        self.latitude = None
        self.CURRENT_RECT = None
        self.linkedListGenerator = None
        self.treeGenerator = None
        self.bearing = None
        self.direction = None
        self.gpsstatus = None
        self.current_online_status = None
        self.last_online_status = None
        self.osm_data_error = None
        self.xtile = None
        self.ytile = None
        self.xtile_cached = None
        self.ytile_cached = None
        self.tunnel_node_id = None
        self.last_road_name = None
        self.last_max_speed = None
        self.found_combined_tags = None
        self.isCcpStable = None

        self.startup_extrapolation = False
        self.startup_calculation = True
        self.is_filled = False
        self.is_cam = False
        self.already_online = False
        self.already_offline = False
        self.new_rectangle = True
        self.border_reached = False
        self.osm_error_reported = False
        self.slow_data_reported = False
        self.internet_connection = True
        self.was_speed0 = True
        self.motorway_flag = False
        self.hazards_on_road = False
        self.hazard_voice = False
        self.waterway = False
        self.water_voice = False
        self.access_control = False
        self.access_control_voice = False
        self.empty_dataset_received = False
        self.cam_in_progress = False
        self.empty_dataset_rect = ""

        # set config items
        self.set_configs()

        # create object for most probable way class once during startup,
        # usage is defined by self.enable_mpr
        self.mpw = MostProbableWay(self)
        self.mpw.set_maximum_number_of_road_names(4)
        self.mpw.set_maximum_number_of_next_possible_mprs(4)

    # create an object for the fallback location lookup

    def set_configs(self):
        # Report slow downloads if this time has been reached
        # Also the rect size will be constantly reduced in case of high delays (> this time)
        self.max_download_time = 20
        # download time timeout for osm data (use a larger timeout for
        # motorways since rects are larger)
        self.osm_timeout = 20
        self.osm_timeout_motorway = 30
        # speed cam lookahead distance in km
        self.speed_cam_look_ahead_distance = 300
        # initial rect distance in km after app startup
        self.initial_rect_distance = 0.5
        # increasing the rect boundaries if this defined speed limit is exceeded
        self.speed_influence_on_rect_boundary = 110
        # angle paramter used for current rect in degrees
        # (only for initial rect calculation and look aheads)
        self.current_rect_angle = 90
        # angle paramter used for fallback rect in degrees (only for initial rect calculation)
        self.fallback_rect_angle = 123
        # zoom factor , osm database layer used (1..18), speed cams are available
        # from layer 16 to 18, the higher the number the more data is retrieved
        self.zoom = 17
        # maximum number of cross roads to be displayed (reasonable value is 2 or 3)
        self.max_cross_roads = 3
        # disable road lookup in case the performance on your phone is not good
        self.disable_road_lookup = False
        # Disable all rectangle operations except the Nominatim road lookup if explicitly
        # enabled via parameter alternative_road_lookup. This option safes the most bandwidth.
        self.disable_all = True
        # Use the Nominatim library as alternative method to retrieve a road name
        # Note: This will use more bandwidth
        # Per default the road name is retrieved via the REST API interface to OpenStreetMap
        self.alternative_road_lookup = True
        self.geolocator = Nominatim(user_agent="mozilla")
        # Instead of two extrapolated rects, only one can be used (increases performance
        # but might lead to less speed cameras found)
        # If we are on a motorway only one extrapolated rect larger in size will be used
        # regardless of parameter self.use_only_one_extrapolated_rect
        self.use_only_one_extrapolated_rect = True
        # Calculate a small rectangle in opposite driving direction as fallback
        # instead of a larger extrapolated rect
        # The feature applies for the next calculation cycle in case condition of CCP was
        # outside all rectangle borders
        self.consider_backup_rects = False
        # dismiss POIS if set to True. If set to False
        # POIs will be displayed as following:
        #   -> MaxSpeed: POI
        #   -> RoadName: AMENITY: RoadName|| GASSTATION: RoadName
        #
        # Note this feature is only active
        # if disable_road_lookup is set to False
        self.dismiss_pois = True
        # enable an algorithm for faster rectangle lookup applying to extrapolated rects
        self.enable_ordered_rects_extrapolated = True
        # max number of extrapolated rects to keep.
        # If this number is reached, all extrapolated rects will be deleted
        # and new one is calculated
        self.max_number_exptrapolated_rects = 6
        # defaut speed limits per country, 'motorway' is the default for
        # all countries except Germany and Austria
        self.MAXSPEED_COUNTRIES = {'AT:motorway': 130,
                                   'DE:motorway': 'UNLIMITED',
                                   'motorway_general': 130}
        # speed per road class in OSM
        self.ROAD_CLASSES_TO_SPEED = {'trunk': 100,
                                      'primary': 100,
                                      'unclassified': 70,
                                      'secondary': 50,
                                      'tertiary': 50,
                                      'service': 50,
                                      'track': 30,
                                      'residential': 30,
                                      'bus_guideway': 30,
                                      'escape': 30,
                                      'bridleway': 30,
                                      'living_street': 20,
                                      'path': 20,
                                      'cycleway': 20,
                                      'pedestrian': 10,
                                      'footway': 10,
                                      'road': 10,
                                      # inside urban area
                                      'urban': 50
                                      }
        # FU per road class
        self.FUNCTIONAL_ROAD_CLASSES = {'motorway': 0,
                                        '_link': 0,
                                        'trunk': 1,
                                        'primary': 2,
                                        'unclassified': 3,
                                        'secondary': 4,
                                        'tertiary': 5,
                                        'service': 6,
                                        'residential': 7,
                                        'living_street': 8,
                                        # to be filtered out
                                        'track': 9,
                                        'bridleway': 10,
                                        'cycleway': 11,
                                        'pedestrian': 12,
                                        'footway': 13,
                                        'path': 14,
                                        'bus_guideway': 15,
                                        'escape': 16,
                                        'road': 17
                                        }
        self.FUNCTIONAL_ROAD_CLASSES_REVERSE = {0: 'motorway',
                                                1: 'trunk',
                                                2: 'primary',
                                                3: 'unclassified',
                                                4: 'secondary',
                                                5: 'tertiary',
                                                6: 'service',
                                                7: 'residential',
                                                8: 'living_street',
                                                # to be filtered out
                                                9: 'track',
                                                10: 'bridleway',
                                                11: 'cycleway',
                                                12: 'pedestrian',
                                                13: 'footway',
                                                14: 'path',
                                                15: 'bus_guideway',
                                                16: 'escape',
                                                17: 'road'
                                                }

        ##SpeedLimits Base URL##
        # baseurl = 'http://overpass.osm.rambler.ru/cgi/interpreter?'
        self.baseurl = 'http://overpass-api.de/api/interpreter?'
        self.querystring1 = 'data=[out:json];(node'
        self.querystring2 = ';rel(bn)->.x;way(bn);rel(bw););out+body;'

        self.querystring_amenity = 'data=[out:json];(node["amenity"="*"]'
        self.querystring_cameras1 = 'data=[out:json][timeout:25];(node["highway"="speed_camera"]'
        self.querystring_cameras2 = 'way["highway"="speed_camera"]'
        self.querystring_cameras3 = 'relation["highway"="speed_camera"]'
        self.querystring_hazard1 = 'data=[out:json][timeout:20];(node["hazard"="falling_rocks"]'
        self.querystring_hazard2 = 'node["hazard"="road_narrows"]'
        self.querystring_hazard3 = 'node["hazard"="slippery"]'
        self.querystring_hazard4 = 'node["hazard"="damaged_road"]'
        self.querystring_hazard5 = 'node["hazard"="ice"]'
        self.querystring_hazard6 = 'node["hazard"="fog"]'
        self.querystring_distance_cams = 'data=[out:json][timeout:25];(relation["enforcement"="mindistance"]'

        # rect boundaries
        self.rectangle_periphery_poi_reader = {'TOP-N': (20, 20),
                                               'N': (20, 20),
                                               'NNO': (20, 24),
                                               'NO': (20, 20),
                                               'ONO': (20, 24),
                                               'O': (20, 20),
                                               'TOP-O': (20, 20),
                                               'OSO': (20, 20),
                                               'SO': (20, 20),
                                               'SSO': (20, 20),
                                               'S': (20, 20),
                                               'TOP-S': (20, 20),
                                               'SSW': (20, 20),
                                               'SW': (20, 20),
                                               'WSW': (20, 20),
                                               'W': (20, 20),
                                               'TOP-W': (20, 24),
                                               'WNW': (20, 20),
                                               'NW': (20, 20),
                                               'NNW': (20, 20)
                                               }

        self.rectangle_periphery_lower_roadclass = {'TOP-N': (9, 9),
                                                    'N': (8, 8),
                                                    'NNO': (7, 11),
                                                    'NO': (7, 7),
                                                    'ONO': (10, 14),
                                                    'O': (8, 8),
                                                    'TOP-O': (9, 9),
                                                    'OSO': (5, 5),
                                                    'SO': (5, 5),
                                                    'SSO': (6, 6),
                                                    'S': (8, 8),
                                                    'TOP-S': (8, 8),
                                                    'SSW': (8, 8),
                                                    'SW': (13, 13),
                                                    'WSW': (15, 15),
                                                    'W': (17, 17),
                                                    'TOP-W': (17, 22),
                                                    'WNW': (12, 12),
                                                    'NW': (10, 12),
                                                    'NNW': (9, 9)
                                                    }

        self.rectangle_periphery_fallback_lower_roadclass = {'TOP-N': (6, 6),
                                                             'N': (6, 6),
                                                             'NNO': (5, 9),
                                                             'NO': (6, 6),
                                                             'ONO': (8, 12),
                                                             'O': (8, 8),
                                                             'TOP-O': (6, 6),
                                                             'OSO': (4, 4),
                                                             'SO': (4, 4),
                                                             'SSO': (5, 5),
                                                             'S': (7, 7),
                                                             'TOP-S': (7, 7),
                                                             'SSW': (8, 8),
                                                             'SW': (8, 8),
                                                             'WSW': (8, 8),
                                                             'W': (8, 8),
                                                             'TOP-W': (8, 12),
                                                             'WNW': (8, 8),
                                                             'NW': (8, 12),
                                                             'NNW': (8, 8)
                                                             }
        self.rectangle_periphery_motorway = {'TOP-N': (11, 11),
                                             'N': (11, 11),
                                             'NNO': (9, 13),
                                             'NO': (8, 8),
                                             'ONO': (10, 14),
                                             'O': (10, 10),
                                             'TOP-O': (11, 11),
                                             'OSO': (6, 6),
                                             'SO': (5, 5),
                                             'SSO': (8, 8),
                                             'S': (12, 12),
                                             'TOP-S': (12, 12),
                                             'SSW': (14, 14),
                                             'SW': (14, 14),
                                             'WSW': (18, 18),
                                             'W': (19, 19),
                                             'TOP-W': (19, 24),
                                             'WNW': (12, 12),
                                             'NW': (12, 15),
                                             'NNW': (12, 12)
                                             }

        self.rectangle_periphery_motorway_fallback = {'TOP-N': (7, 7),
                                                      'N': (7, 7),
                                                      'NNO': (7, 9),
                                                      'NO': (7, 7),
                                                      'ONO': (7, 9),
                                                      'O': (7, 7),
                                                      'TOP-O': (8, 8),
                                                      'OSO': (5, 5),
                                                      'SO': (5, 5),
                                                      'SSO': (6, 6),
                                                      'S': (7, 7),
                                                      'TOP-S': (7, 7),
                                                      'SSW': (7, 7),
                                                      'SW': (7, 7),
                                                      'WSW': (7, 7),
                                                      'W': (7, 7),
                                                      'TOP-W': (7, 9),
                                                      'WNW': (7, 7),
                                                      'NW': (7, 7),
                                                      'NNW': (7, 7)
                                                      }

        self.rectangle_periphery_backup = {'TOP-N': (4, 4),
                                           'N': (4, 4),
                                           'NNO': (4, 6),
                                           'NO': (4, 4),
                                           'ONO': (4, 6),
                                           'O': (4, 4),
                                           'TOP-O': (4, 4),
                                           'OSO': (4, 4),
                                           'SO': (4, 4),
                                           'SSO': (4, 4),
                                           'S': (4, 4),
                                           'TOP-S': (4, 4),
                                           'SSW': (4, 4),
                                           'SW': (4, 4),
                                           'WSW': (4, 4),
                                           'W': (4, 4),
                                           'TOP-W': (4, 6),
                                           'WNW': (4, 4),
                                           'NW': (4, 4),
                                           'NNW': (4, 4)
                                           }

        self.rectangle_fallback_directions = {'TOP-N': (
            'TOP-W', 'TOP-O', 'TOP-W-2', 'TOP-O-2', 'TOP-N-2', 'NNW', 'NNO',
            'NW',
            'NO', 'SSW', 'TOP-S', 'ONO'),
            'N': (
                'W', 'O', 'W-2', 'O-2', 'N-2',
                'NNO', 'TOP-N', 'NO', 'NNW',
                'SSO', 'S', 'TOP-W'),
            'NNO': (
                'NNW', 'SSO', 'NNW-2', 'SSO-2',
                'NNO-2', 'NO', 'N', 'ONO',
                'TOP-N', 'SO', 'SSW', 'NW'),
            'NO': (
                'SO', 'NW', 'SO-2', 'NW-2',
                'NO-2', 'ONO', 'NNO', 'O', 'N',
                'OSO', 'SW', 'W'),
            'ONO': (
                'WSW', 'WNW', 'WSW-2', 'WNW-2',
                'ONO-2', 'O', 'NO', 'OSO', 'NNO',
                'S', 'WNW', 'SSO'),
            'O': (
                'N', 'S', 'N-2', 'S-2', 'O-2',
                'OSO', 'ONO', 'SO', 'NO', 'WSW',
                'W', 'N'),
            'TOP-O': (
                'TOP-N', 'TOP-S', 'TOP-N-2',
                'TOP-S-2', 'TOP-O-2', 'OSO', 'O',
                'SO', 'ONO', 'WSW', 'TOP-W',
                'NNO'),
            'OSO': (
                'WNW', 'WSW', 'WNW-2', 'WSW-2',
                'OSO-2', 'SO', 'O', 'SSO',
                'TOP-O', 'NO', 'WNW', 'TOP-S'),
            'SO': (
                'NO', 'SW', 'NO-2', 'SW-2',
                'SO-2', 'SSO', 'OSO', 'S', 'O',
                'NNO', 'NW', 'ONO'),
            'SSO': (
                'SSW', 'NNW', 'SSW-2', 'NNW-2',
                'SSO-2', 'S', 'SO', 'TOP-S',
                'OSO', 'W', 'WNW', 'SW'),
            'S': (
                'W', 'O', 'W-2', 'O-2', 'S-2',
                'TOP-S', 'SSO', 'SSW', 'SO',
                'WNW', 'N', 'W'),
            'TOP-S': (
                'TOP-W', 'TOP-O', 'TOP-W-2',
                'TOP-O-2', 'TOP-S-2', 'SSW', 'S',
                'SW', 'SSO', 'NW', 'TOP-N', 'W'),
            'SSW': (
                'WNW', 'ONO', 'WNW-2', 'ONO-2',
                'SSW-2', 'SW', 'S', 'WSW', 'SSO',
                'NNW', 'NNO', 'S'),
            'SW': (
                'NW', 'NO', 'NW-2', 'NO-2',
                'SW-2', 'WSW', 'SSW', 'SW', 'S',
                'N', 'NO', 'NW'),
            'WSW': (
                'ONO', 'OSO', 'ONO-2', 'OSO-2',
                'WSW-2', 'W', 'SW', 'TOP-W',
                'SSW', 'WNW', 'ONO', 'S'),
            'W': (
                'N', 'S', 'N-2', 'S-2', 'W-2',
                'WSW', 'TOP-W', 'SW', 'WNW',
                'NNO', 'O', 'TOP-S'),
            'TOP-W': (
                'TOP-N', 'TOP-S', 'TOP-N-2',
                'TOP-S-2', 'TOP-W-2', 'W', 'WNW',
                'WSW', 'NW', 'NNO', 'TOP-O',
                'N'),
            'WNW': (
                'ONO', 'S', 'ONO-2', 'S-2',
                'WNW-2', 'W', 'NW', 'WSW', 'NNW',
                'NO', 'SSO', 'SW'),
            'NW': (
                'NO', 'SW', 'NO-2', 'SW-2',
                'NW-2', 'WNW', 'NNW', 'W', 'N',
                'NNO', 'SO', 'WSW'),
            'NNW': (
                'NNO', 'SSW', 'NNO-2', 'SSW-2',
                'NNW-2', 'NW', 'N', 'WNW',
                'TOP-N', 'N', 'SSO', 'W')
        }
        self.rectangle_fallback_directions_motorway = {'TOP-N': ('TOP-N-2'),
                                                       'N': ('N-2'),
                                                       'NNO': ('NNO-2'),
                                                       'NO': ('NO-2'),
                                                       'ONO': ('ONO-2'),
                                                       'O': ('O-2'),
                                                       'TOP-O': ('TOP-O-2'),
                                                       'OSO': ('OSO-2'),
                                                       'SO': ('SO-2'),
                                                       'SSO': ('SSO-2'),
                                                       'S': ('S-2'),
                                                       'TOP-S': ('TOP-S-2'),
                                                       'SSW': ('SSW-2'),
                                                       'SW': ('SW-2'),
                                                       'WSW': ('WSW-2'),
                                                       'W': ('W-2'),
                                                       'TOP-W': ('TOP-W-2'),
                                                       'WNW': ('WNW-2'),
                                                       'NW': ('NW-2'),
                                                       'NNW': ('NNW-2')
                                                       }

        self.rectangle_periphery = self.rectangle_periphery_lower_roadclass
        self.rectangle_periphery_fallback = self.rectangle_periphery_fallback_lower_roadclass

    def run(self):

        while not self.cond.terminate:
            next_action = self.process()
            if next_action == 'EXIT':
                self.print_log_line(' Calculator thread terminating..')
                return
            elif next_action == 'OFFLINE':
                if not self.disable_all:
                    # convert previous CCP longitude,latitude to (x,y).
                    if (isinstance(self.linkedListGenerator,
                                   DoubleLinkedListNodes) and
                            isinstance(self.treeGenerator, BinarySearchTree)):
                        self.matching_rect, close_to_border, delete_rects = self.check_all_rectangles(
                            previous_ccp=True)
            elif next_action == 'CALCULATE':
                # Speed Cam lookahead
                self.start_thread_pool_speed_cam_look_ahead(self.speed_cam_lookup_ahead, 1, False)
                if self.startup_calculation:

                    self.update_kivi_maxspeed_onlinecheck(
                        online_available=False,
                        status='STARTUP_CALC')
                    self.update_kivi_info_page()

                    self.trigger_calculation('STARTUP')
                    self.startup_calculation = False
                else:
                    r_value = self.processInterrupts()
                    if r_value == 'disable_all':
                        self.start_thread_pool_process_disable_all(self.processDisableAllAction, 1)
                    if r_value == 'TERMINATE':
                        break
            elif next_action == 'INIT':
                self.update_kivi_maxspeed_onlinecheck(online_available=False,
                                                      status='INIT')
            else:
                pass

        # send a termination item to our speed warner thread
        self.speed_cam_queue.produce(self.cv_speedcam,
                                     {'ccp': ('EXIT', 'EXIT'),
                                      'fix_cam': (False, 0, 0),
                                      'traffic_cam': (False, 0, 0),
                                      'distance_cam': (False, 0, 0),
                                      'mobile_cam': (False, 0, 0),
                                      'ccp_node': (None, None),
                                      'list_tree': (None, None),
                                      'stable_ccp': self.isCcpStable})

        self.interruptqueue.produce(self.cv_interrupt, 'TERMINATE')
        self.cleanup()
        self.print_log_line(" terminating")
        self.stop()

    def cleanup(self):
        self.RECT_SPEED_CAM_LOOKAHAEAD = None
        self.RECT_ATTRIBUTES_EXTRAPOLATED = {}
        self.RECT_ATTRIBUTES_EXTRAPOLATED_KEYS = []
        self.RECT_ATTRIBUTES = {}
        self.RECT_KEYS = []
        self.RECT_VALUES = []
        self.RECT_VALUES_EXTRAPOLATED = []
        self.RECT_ATTRIBUTES_INTERSECTED = {}
        self.update_kivi_maxspeed("cleanup")
        self.update_kivi_roadname("cleanup")

    def camera_in_progress(self, state):
        self.cam_in_progress = state

    def update_map_queue(self):
        self.map_queue.produce(self.cv_map, "UPDATE")

    def calculate_rectangle_radius(self, a, b):
        diagonale = (math.sqrt(a ** 2 + b ** 2)) * 1000
        return round(float((0.5 * diagonale) / 1000), 1)

    def longlat2tile(self, lat_deg, lon_deg, zoom):
        lat_rad = math.radians(lat_deg)
        n = 2.0 ** zoom
        xtile = (lon_deg + 180.0) / 360.0 * n
        ytile = (1.0 - math.log(
            math.tan(lat_rad) + (1 / math.cos(lat_rad))) / math.pi) / 2.0 * n
        return (xtile, ytile)

    def tile2longlat(self, xtile, ytile, zoom):
        n = 2.0 ** zoom
        lon_deg = xtile / n * 360.0 - 180.0
        lat_rad = math.atan(math.sinh(math.pi * (1 - 2 * ytile / n)))
        lat_deg = math.degrees(lat_rad)
        return (lon_deg, lat_deg)

    def tile2hypotenuse(self, xtile, ytile):
        xtile = xtile ** 2
        ytile = ytile ** 2
        h = math.sqrt(xtile + ytile)
        return h

    def tile2polar(self, xtile, ytile):
        rad = math.atan2(ytile, xtile)
        deg = rad * (180 / math.pi)
        return deg

    def calculatepoints2angle(self, xtile, ytile, distance, angle):
        x_cos = math.cos(angle) * distance
        y_sin = math.sin(angle) * distance

        xtile_min = 0
        xtile_max = 0
        ytile_min = 0
        ytile_max = 0

        if 90 < angle <= 120 or 130 < angle <= 135:
            xtile_min = xtile - x_cos
            xtile_max = xtile + x_cos
            ytile_min = ytile + y_sin
            ytile_max = ytile - y_sin
        elif 120 < angle <= 122:
            xtile_min = xtile - x_cos
            xtile_max = xtile + x_cos
            ytile_min = ytile - y_sin
            ytile_max = ytile + y_sin
        elif 122 < angle <= 130:
            xtile_min = xtile + x_cos
            xtile_max = xtile - x_cos
            ytile_min = ytile - y_sin
            ytile_max = ytile + y_sin
        else:
            xtile_min = xtile + x_cos
            xtile_max = xtile - x_cos
            ytile_min = ytile + y_sin
            ytile_max = ytile - y_sin

        return xtile_min, xtile_max, ytile_min, ytile_max

    def decrease_xtile_left(self, factor=1):
        return self.xtile - factor

    def increase_xtile_right(self, factor=1):
        return self.xtile + factor

    def rotatepoints2angle(self, xtile_min, xtile_max, ytile_min, ytile_max,
                           angle):
        xtile_min = math.cos(-angle) * xtile_min - math.sin(-angle) * ytile_min
        ytile_min = math.sin(-angle) * xtile_min + math.cos(-angle) * ytile_min

        xtile_max = math.cos(-angle) * xtile_max - math.sin(-angle) * ytile_max
        ytile_max = math.sin(-angle) * xtile_max + math.cos(-angle) * ytile_max

        return xtile_min, xtile_max, ytile_min, ytile_max

    def get_vector_sections(self, vector):
        data_sections = vector['vector_data']
        longitude = data_sections[0][0]
        latitude = data_sections[0][1]
        cspeed = data_sections[1]
        bearing = data_sections[2]
        direction = data_sections[3]
        gpsstatus = data_sections[4]
        accuracy = data_sections[5]

        return (longitude, latitude, cspeed, bearing, direction, gpsstatus, accuracy)

    def calculate_rectangle_border(self, pt1, pt2):
        return Rect(pt1, pt2)

    def createGeoJsonTilePolygonAngle(self, zoom, xtile_min, ytile_min,
                                      xtile_max, ytile_max):
        self.XTILE_MIN, self.YTILE_MIN = self.tile2longlat(abs(xtile_min),
                                                           abs(ytile_min),
                                                           zoom)
        self.XTILE_MAX, self.YTILE_MAX = self.tile2longlat(abs(xtile_max),
                                                           abs(ytile_max),
                                                           zoom)
        # self.print_log_line('lon min: %f, lat min: %f, lon max: %f, lat max: %f'
        # %(self.XTILE_MIN, self.YTILE_MIN, self.XTILE_MAX, self.YTILE_MAX))
        return (self.XTILE_MIN, self.YTILE_MIN, self.XTILE_MAX, self.YTILE_MAX)

    def createGeoJsonTilePolygon(self, direction, zoom, xtile, ytile,
                                 rectangle_periphery):
        # Fixed
        if direction == 'TOP-S':
            self.XTILE_MIN, self.YTILE_MIN = self.tile2longlat(
                (abs(xtile) - (rectangle_periphery['TOP-N'][1] / 4.5)),
                abs(ytile) + rectangle_periphery['TOP-N'][0] * 0.8,
                zoom)
            self.XTILE_MAX, self.YTILE_MAX = self.tile2longlat(
                (abs(xtile) + (rectangle_periphery['TOP-N'][1] / 4.5)),
                abs(ytile) - rectangle_periphery['TOP-N'][0] / 2,
                zoom)
        elif direction == 'TOP-S-2':
            self.XTILE_MIN, self.YTILE_MIN = self.tile2longlat(
                (abs(xtile) - (rectangle_periphery['TOP-S'][1] / 4.5)),
                abs(ytile) + 15,
                zoom)
            self.XTILE_MAX, self.YTILE_MAX = self.tile2longlat(
                (abs(xtile) + (rectangle_periphery['TOP-S'][1] / 4.5)),
                abs(ytile) + rectangle_periphery['TOP-S'][0] / 1.5,
                zoom)
        elif direction == 'S':
            self.XTILE_MIN, self.YTILE_MAX = self.tile2longlat(
                (abs(xtile) - (rectangle_periphery['S'][1] / 6)),
                (abs(ytile) - 0.3),
                zoom)
            self.XTILE_MAX, self.YTILE_MIN = self.tile2longlat(
                (abs(xtile) + (rectangle_periphery['S'][1] / 6)),
                abs(ytile) + rectangle_periphery['S'][0] / 1.5,
                zoom)
        elif direction == 'S-2':
            self.XTILE_MIN, self.YTILE_MIN = self.tile2longlat(
                (abs(xtile) - (rectangle_periphery['S'][1] / 6)),
                (abs(ytile) + 15),
                zoom)
            self.XTILE_MAX, self.YTILE_MAX = self.tile2longlat(
                (abs(xtile) + (rectangle_periphery['S'][1] / 6)),
                abs(ytile) + rectangle_periphery['S'][0] / 1.5,
                zoom)
        elif direction == 'SSW':
            self.XTILE_MAX, self.YTILE_MAX = self.tile2longlat(
                (abs(xtile) + (rectangle_periphery['SSW'][0] / 10)),
                (abs(ytile) - 0.5),
                zoom)
            self.XTILE_MIN, self.YTILE_MIN = self.tile2longlat(
                (abs(xtile) - (rectangle_periphery['SSW'][0] / 7)),
                (abs(ytile) + (rectangle_periphery['SSW'][0] / 3)),
                zoom)
        elif direction == 'SSW-2':
            self.XTILE_MAX, self.YTILE_MAX = self.tile2longlat(
                (abs(xtile) - (rectangle_periphery['SSW'][0] / 25)),
                (abs(ytile) + 1.3),
                zoom)
            self.XTILE_MIN, self.YTILE_MIN = self.tile2longlat(
                (abs(xtile) - (rectangle_periphery['SSW'][0] / 3)),
                (abs(ytile) + (rectangle_periphery['SSW'][0] / 1.2)),
                zoom)
        elif direction == 'SW':
            self.XTILE_MAX, self.YTILE_MAX = self.tile2longlat(
                (abs(xtile) + (rectangle_periphery['SW'][0] / 30)),
                (abs(ytile) - 0.3),
                zoom)
            self.XTILE_MIN, self.YTILE_MIN = self.tile2longlat(
                (abs(xtile) - (rectangle_periphery['SW'][0] / 4)),
                (abs(ytile) + (rectangle_periphery['SW'][0] / 6)),
                zoom)
        elif direction == 'SW-2':
            self.XTILE_MAX, self.YTILE_MAX = self.tile2longlat(
                (abs(xtile) - (rectangle_periphery['SW'][0] / 5)),
                (abs(ytile) + 0.5),
                zoom)
            self.XTILE_MIN, self.YTILE_MIN = self.tile2longlat(
                (abs(xtile) - (rectangle_periphery['SW'][0] / 2)),
                (abs(ytile) + (rectangle_periphery['SW'][0] / 4)),
                zoom)
        elif direction == 'WSW':
            self.XTILE_MAX, self.YTILE_MAX = self.tile2longlat(
                (abs(xtile) + (rectangle_periphery['WSW'][0] / 50)),
                (abs(ytile) - 0.5),
                zoom)
            self.XTILE_MIN, self.YTILE_MIN = self.tile2longlat(
                (abs(xtile) - (rectangle_periphery['WSW'][0] / 4)),
                (abs(ytile) + (rectangle_periphery['WSW'][0] / 10)),
                zoom)
        elif direction == 'WSW-2':
            self.XTILE_MAX, self.YTILE_MAX = self.tile2longlat(
                (abs(xtile) - (rectangle_periphery['WSW'][0] / 6)),
                (abs(ytile) + 0.1),
                zoom)
            self.XTILE_MIN, self.YTILE_MIN = self.tile2longlat(
                (abs(xtile) - (rectangle_periphery['WSW'][0] / 2)),
                (abs(ytile) + (rectangle_periphery['WSW'][0] / 6)),
                zoom)
        elif direction == 'W':
            self.XTILE_MAX, self.YTILE_MAX = self.tile2longlat(
                abs(xtile) + rectangle_periphery['W'][1] / 30,
                (abs(ytile) - (rectangle_periphery['W'][0] / 15)),
                zoom)
            self.XTILE_MIN, self.YTILE_MIN = self.tile2longlat(
                abs(xtile) - rectangle_periphery['W'][1] / 5,
                (abs(ytile) + (rectangle_periphery['W'][0] / 15)),
                zoom)
        elif direction == 'W-2':
            self.XTILE_MIN, self.YTILE_MAX = self.tile2longlat(
                abs(xtile) - rectangle_periphery['W'][1] / 2,
                (abs(ytile) - (rectangle_periphery['W'][0] / 15)),
                zoom)
            self.XTILE_MAX, self.YTILE_MIN = self.tile2longlat(
                abs(xtile) - rectangle_periphery['W'][1] / 5,
                (abs(ytile) + (rectangle_periphery['W'][0] / 15)),
                zoom)
        elif direction == 'TOP-W':
            self.XTILE_MAX, self.YTILE_MAX = self.tile2longlat(
                (abs(xtile) + (rectangle_periphery['TOP-W'][1] / 30)),
                (abs(ytile) - (rectangle_periphery['TOP-W'][0] / 20)),
                zoom)
            self.XTILE_MIN, self.YTILE_MIN = self.tile2longlat(
                abs(xtile) - rectangle_periphery['TOP-W'][1] / 5,
                (abs(ytile) + (rectangle_periphery['TOP-W'][0] / 20)),
                zoom)
        elif direction == 'TOP-W-2':
            self.XTILE_MIN, self.YTILE_MAX = self.tile2longlat(
                (abs(xtile) - (rectangle_periphery['TOP-W'][1] / 2)),
                (abs(ytile) - (rectangle_periphery['TOP-W'][0] / 20)),
                zoom)
            self.XTILE_MAX, self.YTILE_MIN = self.tile2longlat(
                abs(xtile) - rectangle_periphery['TOP-W'][1] / 5,
                (abs(ytile) + (rectangle_periphery['TOP-W'][0] / 20)),
                zoom)
        elif direction == 'WNW':
            self.XTILE_MAX, self.YTILE_MAX = self.tile2longlat(
                abs(xtile) + rectangle_periphery['WNW'][1] / 40,
                (abs(ytile) - (rectangle_periphery['WNW'][0] / 9)),
                zoom)
            self.XTILE_MIN, self.YTILE_MIN = self.tile2longlat(
                abs(xtile) - rectangle_periphery['WNW'][1] / 5,
                (abs(ytile) + (rectangle_periphery['WNW'][0] / 30)),
                zoom)
        elif direction == 'WNW-2':
            self.XTILE_MAX, self.YTILE_MAX = self.tile2longlat(
                abs(xtile) - rectangle_periphery['WNW'][1] / 8,
                (abs(ytile) - (rectangle_periphery['WNW'][0] / 5)),
                zoom)
            self.XTILE_MIN, self.YTILE_MIN = self.tile2longlat(
                abs(xtile) - rectangle_periphery['WNW'][1] / 2.5,
                (abs(ytile) - 0.3),
                zoom)
        elif direction == 'NW':
            self.XTILE_MAX, self.YTILE_MAX = self.tile2longlat(
                (abs(xtile) + (rectangle_periphery['NW'][1] / 28)),
                (abs(ytile) - (rectangle_periphery['NW'][0] / 3)),
                zoom)
            self.XTILE_MIN, self.YTILE_MIN = self.tile2longlat(
                (abs(xtile) - (rectangle_periphery['NW'][1] / 5)),
                (abs(ytile) + (rectangle_periphery['NW'][0] / 28)),
                zoom)
        elif direction == 'NW-2':
            self.XTILE_MAX, self.YTILE_MAX = self.tile2longlat(
                (abs(xtile) - (rectangle_periphery['NW'][1] / 11)),
                (abs(ytile) - (rectangle_periphery['NW'][0] / 2)),
                zoom)
            self.XTILE_MIN, self.YTILE_MIN = self.tile2longlat(
                (abs(xtile) - (rectangle_periphery['NW'][1] / 3)),
                (abs(ytile) - 0.8),
                zoom)
        elif direction == 'NNW':
            self.XTILE_MAX, self.YTILE_MAX = self.tile2longlat(
                (abs(xtile) + (rectangle_periphery['NNW'][1] / 30)),
                (abs(ytile) - (rectangle_periphery['NNW'][0] / 4)),
                zoom)
            self.XTILE_MIN, self.YTILE_MIN = self.tile2longlat(
                (abs(xtile) - (rectangle_periphery['NNW'][1] / 6)),
                (abs(ytile) + (rectangle_periphery['NNW'][0] / 30)),
                zoom)
        elif direction == 'NNW-2':
            self.XTILE_MAX, self.YTILE_MAX = self.tile2longlat(
                (abs(xtile) - (rectangle_periphery['NNW'][1] / 10)),
                (abs(ytile) - (rectangle_periphery['NNW'][0] / 2)),
                zoom)
            self.XTILE_MIN, self.YTILE_MIN = self.tile2longlat(
                (abs(xtile) - (rectangle_periphery['NNW'][1] / 3)),
                (abs(ytile) - 0.8),
                zoom)
        elif direction == 'N':
            self.XTILE_MIN, self.YTILE_MIN = self.tile2longlat(
                (abs(xtile) - (rectangle_periphery['N'][1] / 8)),
                abs(ytile) + rectangle_periphery['N'][0] / 10,
                zoom)
            self.XTILE_MAX, self.YTILE_MAX = self.tile2longlat(
                (abs(xtile) + (rectangle_periphery['N'][1] / 8)),
                abs(ytile) - rectangle_periphery['N'][0] / 2,
                zoom)
        elif direction == 'N-2':
            self.XTILE_MIN, self.YTILE_MIN = self.tile2longlat(
                (abs(xtile) - (rectangle_periphery['N'][1] / 8)),
                abs(ytile) - rectangle_periphery['N'][0] / 2,
                zoom)
            self.XTILE_MAX, self.YTILE_MAX = self.tile2longlat(
                (abs(xtile) + (rectangle_periphery['N'][1] / 8)),
                abs(ytile) - rectangle_periphery['N'][0] / 0.8,
                zoom)
        elif direction == 'TOP-N':
            self.XTILE_MIN, self.YTILE_MIN = self.tile2longlat(
                (abs(xtile) - (rectangle_periphery['TOP-N'][1] / 18)),
                abs(ytile) + rectangle_periphery['TOP-N'][0] / 10,
                zoom)
            self.XTILE_MAX, self.YTILE_MAX = self.tile2longlat(
                (abs(xtile) + (rectangle_periphery['TOP-N'][1] / 15)),
                abs(ytile) - rectangle_periphery['TOP-N'][0] / 3,
                zoom)
        elif direction == 'TOP-N-2':
            self.XTILE_MIN, self.YTILE_MIN = self.tile2longlat(
                (abs(xtile) - (rectangle_periphery['TOP-N'][1] / 18)),
                abs(ytile) - rectangle_periphery['TOP-N'][0] / 3,
                zoom)
            self.XTILE_MAX, self.YTILE_MAX = self.tile2longlat(
                (abs(xtile) + (rectangle_periphery['TOP-N'][1] / 15)),
                abs(ytile) - rectangle_periphery['TOP-N'][0] / 2,
                zoom)
        elif direction == 'NNO':
            self.XTILE_MAX, self.YTILE_MIN = self.tile2longlat(
                (abs(xtile) + (rectangle_periphery['NNO'][1] / 6)),
                abs(ytile) + rectangle_periphery['NNO'][0] / 20,
                zoom)
            self.XTILE_MIN, self.YTILE_MAX = self.tile2longlat(
                (abs(xtile) - (rectangle_periphery['NNO'][1] / 30)),
                abs(ytile) - rectangle_periphery['NNO'][0] / 1.7,
                zoom)
        elif direction == 'NNO-2':
            self.XTILE_MAX, self.YTILE_MIN = self.tile2longlat(
                (abs(xtile) + (rectangle_periphery['NNO'][1] / 4)),
                abs(ytile) - rectangle_periphery['NNO'][0] / 2,
                zoom)
            self.XTILE_MIN, self.YTILE_MAX = self.tile2longlat(
                (abs(xtile) + (rectangle_periphery['NNO'][1] / 35)),
                abs(ytile) - rectangle_periphery['NNO'][0] / 0.7,
                zoom)
        elif direction == 'NO':
            self.XTILE_MAX, self.YTILE_MIN = self.tile2longlat(
                (abs(xtile) + (rectangle_periphery['NO'][1] / 2)),
                abs(ytile) + rectangle_periphery['NO'][0] / 18,
                zoom)
            self.XTILE_MIN, self.YTILE_MAX = self.tile2longlat(
                (abs(xtile) - (rectangle_periphery['NO'][1] / 10)),
                abs(ytile) - rectangle_periphery['NO'][0] / 3,
                zoom)
        elif direction == 'NO-2':
            self.XTILE_MAX, self.YTILE_MIN = self.tile2longlat(
                (abs(xtile) + (rectangle_periphery['NO'][1] / 1)),
                abs(ytile) - rectangle_periphery['NO'][0] / 10,
                zoom)
            self.XTILE_MIN, self.YTILE_MAX = self.tile2longlat(
                (abs(xtile) + (rectangle_periphery['NO'][1] / 5)),
                abs(ytile) - rectangle_periphery['NO'][0] / 2,
                zoom)
        elif direction == 'ONO':
            self.XTILE_MAX, self.YTILE_MIN = self.tile2longlat(
                abs(xtile) + rectangle_periphery['ONO'][1] / 4,
                (abs(ytile) + (rectangle_periphery['ONO'][0] / 30)),
                zoom)
            self.XTILE_MIN, self.YTILE_MAX = self.tile2longlat(
                abs(xtile) - rectangle_periphery['ONO'][1] / 40,
                (abs(ytile) - (rectangle_periphery['ONO'][0] / 8)),
                zoom)
        elif direction == 'ONO-2':
            self.XTILE_MAX, self.YTILE_MAX = self.tile2longlat(
                abs(xtile) + rectangle_periphery['ONO'][1] / 1.9,
                (abs(ytile) - 1.7),
                zoom)
            self.XTILE_MIN, self.YTILE_MIN = self.tile2longlat(
                abs(xtile) + rectangle_periphery['ONO'][1] / 6,
                (abs(ytile) - 0.1),
                zoom)
        elif direction == 'O':
            self.XTILE_MAX, self.YTILE_MIN = self.tile2longlat(
                abs(xtile) + rectangle_periphery['O'][1] / 2.5,
                (abs(ytile) + (rectangle_periphery['O'][0] / 14)),
                zoom)
            self.XTILE_MIN, self.YTILE_MAX = self.tile2longlat(
                abs(xtile) - rectangle_periphery['O'][1] / 50,
                (abs(ytile) - (rectangle_periphery['O'][0] / 14)),
                zoom)
        elif direction == 'O-2':
            self.XTILE_MAX, self.YTILE_MIN = self.tile2longlat(
                abs(xtile) + rectangle_periphery['O'][1] / 2.5,
                (abs(ytile) + (rectangle_periphery['O'][0] / 14)),
                zoom)
            self.XTILE_MIN, self.YTILE_MAX = self.tile2longlat(
                (abs(xtile) + 10),
                (abs(ytile) - (rectangle_periphery['O'][0] / 14)),
                zoom)
        elif direction == 'TOP-O':
            self.XTILE_MAX, self.YTILE_MIN = self.tile2longlat(
                abs(xtile) + rectangle_periphery['TOP-O'][1] / 2.5,
                (abs(ytile) + (rectangle_periphery['TOP-O'][0] / 16)),
                zoom)
            self.XTILE_MIN, self.YTILE_MAX = self.tile2longlat(
                abs(xtile) - rectangle_periphery['TOP-O'][1] / 50,
                (abs(ytile) - (rectangle_periphery['TOP-O'][0] / 16)),
                zoom)
        elif direction == 'TOP-O-2':
            self.XTILE_MAX, self.YTILE_MIN = self.tile2longlat(
                abs(xtile) + rectangle_periphery['TOP-O'][1] / 2.5,
                (abs(ytile) + (rectangle_periphery['TOP-O'][0] / 16)),
                zoom)
            self.XTILE_MIN, self.YTILE_MAX = self.tile2longlat(
                (abs(xtile) + 10),
                (abs(ytile) - (rectangle_periphery['TOP-O'][0] / 16)),
                zoom)
        elif direction == 'OSO':
            self.XTILE_MIN, self.YTILE_MIN = self.tile2longlat(
                (abs(xtile) - (rectangle_periphery['OSO'][1] / 15)),
                (abs(ytile) + (rectangle_periphery['OSO'][0] / 2)),
                zoom)
            self.XTILE_MAX, self.YTILE_MAX = self.tile2longlat(
                abs(xtile) + rectangle_periphery['OSO'][1] / 1.1,
                (abs(ytile) - (rectangle_periphery['OSO'][0] / 10)),
                zoom)
        elif direction == 'OSO-2':
            self.XTILE_MIN, self.YTILE_MAX = self.tile2longlat(
                (abs(xtile) + (rectangle_periphery['SSO'][1] / 1.8)),
                (abs(ytile) + 1.3),
                zoom)
            self.XTILE_MAX, self.YTILE_MIN = self.tile2longlat(
                (abs(xtile) + (rectangle_periphery['SSO'][1] / 0.6)),
                (abs(ytile) + (rectangle_periphery['SSO'][0] / 1.3)),
                zoom)
        elif direction == 'SO':
            self.XTILE_MIN, self.YTILE_MIN = self.tile2longlat(
                (abs(xtile) - (rectangle_periphery['SO'][1] / 18)),
                (abs(ytile) + (rectangle_periphery['SO'][0] / 1.5)),
                zoom)
            self.XTILE_MAX, self.YTILE_MAX = self.tile2longlat(
                abs(xtile) + rectangle_periphery['SO'][1] / 2,
                (abs(ytile) - (rectangle_periphery['SO'][0] / 35)),
                zoom)
        elif direction == 'SO-2':
            self.XTILE_MIN, self.YTILE_MAX = self.tile2longlat(
                (abs(xtile) + (rectangle_periphery['SO'][1] / 20)),
                (abs(ytile) + 2),
                zoom)
            self.XTILE_MAX, self.YTILE_MIN = self.tile2longlat(
                (abs(xtile) + (rectangle_periphery['SO'][1] / 1.5)),
                (abs(ytile) + (rectangle_periphery['SO'][0] / 0.8)),
                zoom)
        elif direction == 'SSO':
            self.XTILE_MIN, self.YTILE_MIN = self.tile2longlat(
                (abs(xtile) - (rectangle_periphery['SSO'][1] / 20)),
                (abs(ytile) + (rectangle_periphery['SSO'][0] / 2)),
                zoom)
            self.XTILE_MAX, self.YTILE_MAX = self.tile2longlat(
                abs(xtile) + rectangle_periphery['SSO'][1] / 4,
                (abs(ytile) - (rectangle_periphery['SSO'][0] / 50)),
                zoom)
        elif direction == 'SSO-2':
            self.XTILE_MIN, self.YTILE_MAX = self.tile2longlat(
                (abs(xtile) + (rectangle_periphery['SSO'][1] / 35)),
                (abs(ytile) + 3.5),
                zoom)
            self.XTILE_MAX, self.YTILE_MIN = self.tile2longlat(
                (abs(xtile) + (rectangle_periphery['SSO'][1] / 2.5)),
                (abs(ytile) + (rectangle_periphery['SSO'][0] / 0.9)),
                zoom)
        else:
            self.print_log_line(' Invalid direction! %s' % direction)
            return (0, 0, 0, 0)

        return self.XTILE_MIN, self.YTILE_MIN, self.XTILE_MAX, self.YTILE_MAX

    def process(self, update_ccp_only=False):
        updated_vector = self.vector_data.get_vector_data(self.cv_vector)
        self.cv_vector.release()

        if updated_vector is None:
            return None

        self.longitude, \
        self.latitude, \
        self.cspeed, \
        self.bearing, \
        self.direction, \
        self.gpsstatus, \
        self.accuracy = self.get_vector_sections(updated_vector)

        if update_ccp_only:
            self.print_log_line(" Update CCP only..")
            self.xtile, self.ytile = self.longlat2tile(self.latitude,
                                                       self.longitude,
                                                       self.zoom)

            self.cache_cspeed()
            self.cache_direction()
            self.convert_cspeed()
            self.cache_bearing()
            self.cache_ccp()
            self.cache_tiles(self.xtile, self.ytile)
            return

        if self.gpsstatus == 'CALCULATE':
            # update the SpeedWarner Thread
            self.speed_cam_queue.produce(self.cv_speedcam, {
                'ccp': (self.longitude, self.latitude),
                'fix_cam': (False, 0, 0),
                'traffic_cam': (False, 0, 0),
                'distance_cam': (False, 0, 0),
                'mobile_cam': (False, 0, 0),
                'ccp_node': (None, None),
                'list_tree': (None, None),
                'stable_ccp': self.isCcpStable,
                'bearing': self.bearing})
        elif self.gpsstatus == 'OFFLINE':
            # update the SpeedWarner Thread
            self.calculate_extrapolated_position(self.longitude_cached,
                                                 self.latitude_cached,
                                                 self.cspeed_converted,
                                                 float(self.bearing_cached),
                                                 1)

            if self.longitude_cached > 0 and self.latitude_cached > 0:
                self.speed_cam_queue.produce(self.cv_speedcam, {
                    'ccp': (self.longitude_cached, self.latitude_cached),
                    'fix_cam': (False, 0, 0),
                    'traffic_cam': (False, 0, 0),
                    'distance_cam': (False, 0, 0),
                    'mobile_cam': (False, 0, 0),
                    'ccp_node': (None, None),
                    'list_tree': (None, None),
                    'stable_ccp': self.isCcpStable,
                    'bearing': None})
                # clear any overhead leading to performance bottle necks
                self.currentspeed_queue.produce(self.cv_currentspeed, None)
                self.overspeed_queue.clear_overspeedqueue(self.cv_overspeed)

        else:
            pass

        # offline.
        if self.gpsstatus == 'OFFLINE':
            return 'OFFLINE'
        elif self.gpsstatus == "EXIT":
            self.print_log_line(' Calculator thread exit item received')
            return 'EXIT'
        elif self.gpsstatus == 'CALCULATE':
            self.cache_cspeed()
            self.cache_direction()
            self.convert_cspeed()
            self.cache_bearing()
            self.cache_ccp()
            return 'CALCULATE'
        else:
            return 'INIT'

    def processDisableAllAction(self):
        if self.alternative_road_lookup:
            RectangleCalculatorThread.thread_lock = True
            road_name = self.get_road_name_via_nominatim(self.latitude, self.longitude)
            if road_name is not None:
                if road_name.startswith("ERROR:"):
                    if self.cam_in_progress is False:
                        self.update_maxspeed_status("ERROR",
                                                    internal_error=road_name[road_name.find(":") + 2:])
                else:
                    self.process_road_name(found_road_name=True,
                                           road_name=road_name,
                                           found_combined_tags=False,
                                           road_class='unclassified',
                                           poi=False,
                                           facility=False)
            if self.cam_in_progress is False and self.internet_available():
                self.update_kivi_maxspeed("->->->")
            RectangleCalculatorThread.thread_lock = False

    def processInterrupts(self):
        self.isCcpStable = self.interruptqueue.consume(self.cv_interrupt)
        self.cv_interrupt.release()

        if self.isCcpStable == 'TERMINATE':
            self.print_log_line(' Calculator thread interrupt termination')
            return 'TERMINATE'

        if self.disable_all:
            return 'disable_all'

        if self.border_reached or self.isCcpStable == 'STABLE':
            self.trigger_calculation('CONTINUE')
            return 0

        else:
            # updating tile coords in UNSTABLE mode
            self.xtile, self.ytile = self.longlat2tile(self.latitude,
                                                       self.longitude,
                                                       self.zoom)

            if isinstance(self.CURRENT_RECT, Rect):
                # we are unstable, no need for large rects
                self.update_rectangle_periphery(internet_check=False,
                                                reduce_rect_size=True)

                self.matching_rect, close_to_border, delete_rects = self.check_all_rectangles()
                result = self.extrapolate_rectangle(True,
                                                    "",
                                                    "",
                                                    "",
                                                    close_to_border,
                                                    delete_rects)
                self.previous_rect = self.matching_rect
                if result:
                    self.intersect_rectangle(mode="EXTRAPOLATED")
                    self.osm_wrapper.first_start = True
                else:
                    self.osm_wrapper.first_start = False
            return 0

    def speed_cam_lookup_ahead(self, previous_ccp=False):
        """
        Speed Cam lookup ahead after each interrupt cylce.
        This lookup is independent of a matching Rectangle
        :return:
        """
        if previous_ccp:
            if self.longitude_cached > 0 and self.latitude_cached > 0:
                ccp_lat = self.latitude_cached
                ccp_lon = self.longitude_cached
            else:
                return
            if self.xtile_cached is not None and self.ytile_cached is not None:
                xtile = self.xtile_cached
                ytile = self.ytile_cached
            else:
                return
        else:
            # convert CCP longitude,latitude to (x,y).
            xtile, ytile = self.longlat2tile(self.latitude, self.longitude, self.zoom)
            self.cache_tiles(xtile, ytile)
            ccp_lat = self.latitude
            ccp_lon = self.longitude

        if self.RECT_SPEED_CAM_LOOKAHAEAD and isinstance(self.RECT_SPEED_CAM_LOOKAHAEAD, Rect):
            inside_rect = self.RECT_SPEED_CAM_LOOKAHAEAD.point_in_rect(xtile, ytile)
            close_to_border = self.RECT_SPEED_CAM_LOOKAHAEAD.points_close_to_border(xtile,
                                                                                    ytile,
                                                                                    look_ahead=True)

            if inside_rect and not close_to_border:
                self.print_log_line("Speed cam lookahead not triggered -> CCP within rectangle "
                                    "'CURRENT_CAM'")
                return
        self.print_log_line("Trigger Speed Cam lookahead")

        xtile_min, xtile_max, ytile_min, ytile_max = self.calculatepoints2angle(
            xtile,
            ytile,
            self.speed_cam_look_ahead_distance,
            self.current_rect_angle)
        LON_MIN, LAT_MIN, LON_MAX, LAT_MAX = self.createGeoJsonTilePolygonAngle(
            self.zoom,
            xtile_min,
            ytile_min,
            xtile_max,
            ytile_max)

        # convert each of the 2 points to (x,y).
        pt1_xtile, pt1_ytile = self.longlat2tile(LAT_MIN, LON_MIN, self.zoom)
        pt2_xtile, pt2_ytile = self.longlat2tile(LAT_MAX, LON_MAX, self.zoom)
        # calculate a rectangle from these 2 points
        CURRENT_RECT = self.calculate_rectangle_border(
            [pt1_xtile, pt1_ytile], [pt2_xtile, pt2_ytile])
        CURRENT_RECT.set_rectangle_ident(self.direction)
        CURRENT_RECT.set_rectangle_string('CURRENT_CAM')
        # calculate the radius of the rectangle in km
        rectangle_radius = self.calculate_rectangle_radius(
            CURRENT_RECT.rect_height(),
            CURRENT_RECT.rect_width())
        self.print_log_line(f"Rectangle radius for rect 'CURRENT_CAM' is {rectangle_radius}")
        self.RECT_SPEED_CAM_LOOKAHAEAD = CURRENT_RECT

        # check osm data reception status of favoured rectangle
        speed_cam_dict = dict()
        lookup_types = ["camera_ahead", "distance_cam"]

        for lookup_type in lookup_types:

            RectangleCalculatorThread.thread_lock = True
            (online_available, status, data, internal_error,
             current_rect) = self.trigger_osm_lookup(LON_MIN,
                                                     LAT_MIN,
                                                     LON_MAX,
                                                     LAT_MAX,
                                                     self.direction,
                                                     lookup_type,
                                                     current_rect='CURRENT_CAM')
            RectangleCalculatorThread.thread_lock = False
            self.update_kivi_maxspeed_onlinecheck(
                online_available=online_available,
                status=status,
                internal_error=internal_error,
                alternative_image="UNDEFINED")

            if status != 'OK':
                if self.osm_error_reported:
                    pass
                else:
                    self.ms.update_online_image_layout("INETFAILED")
                    self.voice_prompt_queue.produce_online_status(
                        self.cv_voice, "INTERNET_CONN_FAILED")
                    self.osm_error_reported = True

                # Reset the speed cam rect for a new try if the internet connection got broken or
                # no data was received
                self.RECT_SPEED_CAM_LOOKAHAEAD = None
                break

            if status == 'OK' and len(data) > 0:
                self.osm_error_reported = False
                self.print_log_line("Camera lookup finished!! Found %d cameras ahead (%d km)"
                                    % (len(data), self.speed_cam_look_ahead_distance))

                counter = 80000
                for element in data:
                    name = None
                    direction = None
                    maxspeed = None
                    try:
                        lat = element['lat']
                        lon = element['lon']
                    except KeyError:
                        continue

                    prefix = 'FIX_'
                    if 'tags' in element:
                        if 'speed_camera' in element.get('tags'):
                            value = element.get('tags')['speed_camera']
                            if value == "traffic_signals":
                                prefix = 'TRAFFIC_'

                        try:
                            name = element['tags']['name']
                        except KeyError:
                            name = self.get_road_name_via_nominatim(lat, lon)
                        try:
                            direction = element['tags']['direction']
                        except KeyError:
                            pass
                        try:
                            maxspeed = element['tags']['maxspeed']
                        except KeyError:
                            pass

                    if lookup_type == "distance_cam":
                        prefix = "DISTANCE_"
                        name = self.get_road_name_via_nominatim(lat, lon)

                    key = prefix + str(counter)
                    if prefix == 'FIX_':
                        self.fix_cams += 1
                    elif prefix == 'TRAFFIC_':
                        self.traffic_cams += 1
                    else:
                        self.distance_cams += 1
                    speed_cam_dict[key] = [lat,
                                           lon,
                                           lat,
                                           lon,
                                           True,
                                           None,
                                           None]
                    counter += 1
                    self.speed_cam_queue.produce(self.cv_speedcam, {'ccp': (ccp_lon, ccp_lat),
                                                                    'fix_cam': (True if prefix == 'FIX_' else False,
                                                                                float(lon),
                                                                                float(lat),
                                                                                True),
                                                                    'traffic_cam': (True if prefix == 'TRAFFIC_' else False,
                                                                                    float(lon),
                                                                                    float(lat),
                                                                                    True),
                                                                    'distance_cam': (True if prefix == 'DISTANCE_' else False,
                                                                                     float(lon),
                                                                                     float(lat),
                                                                                     True),
                                                                    'mobile_cam': (False,
                                                                                   float(lon),
                                                                                   float(lat),
                                                                                   True),
                                                                    'ccp_node': ('IGNORE',
                                                                                 'IGNORE'),
                                                                    'list_tree': (None,
                                                                                  None),
                                                                    'name': name,
                                                                    'direction': direction,
                                                                    'maxspeed': maxspeed})

                self.update_kivi_info_page()
                self.cleanup_speed_cams()

                if len(speed_cam_dict) > 0:
                    self.speed_cam_dict.append(speed_cam_dict)

                self.osm_wrapper.update_speed_cams(self.speed_cam_dict)
                self.update_map_queue()
                self.fill_speed_cams()

    @staticmethod
    def start_thread_pool_lookup(func,
                                 worker_threads=1,
                                 lookup_properties=[],
                                 online_available=False,
                                 status='',
                                 data='',
                                 internal_error='',
                                 current_rect='',
                                 extrapolated=False):

        RectangleCalculatorThread.thread_lock = True
        pool = ThreadPool(num_threads=worker_threads,
                          online_available=online_available,
                          status=status,
                          data=data,
                          internal_error=internal_error,
                          current_rect=current_rect,
                          extrapolated=extrapolated)

        for i in range(0, len(lookup_properties)):
            pool.add_task(func,
                          lookup_properties[i][0],
                          lookup_properties[i][1],
                          lookup_properties[i][2],
                          lookup_properties[i][3],
                          lookup_properties[i][4],
                          lookup_properties[i][5],
                          current_rect=lookup_properties[i][6])

        server_responses = pool.wait_completion()
        return server_responses

    def start_thread_pool_data_structure(self, func, worker_threads=1,
                                         server_responses={},
                                         extrapolated=False,
                                         wait_till_completed=True):
        # get matched street data immediately after building our tree and list structure.

        pool = ThreadPool(num_threads=worker_threads, action='CACHE')
        for task, data_list in server_responses.items():
            pool.add_task(func, dataset=data_list[2], rect_preferred=data_list[4])

        if wait_till_completed:
            _ = pool.wait_completion()
        RectangleCalculatorThread.thread_lock = False

        if not extrapolated:
            self.check_specific_rectangle()
            if not self.internet_available():
                self.update_maxspeed_status(status='INIT', internal_error=None)

    @staticmethod
    def start_thread_pool_speed_cam_structure(func, worker_threads=1, linkedList=None, tree=None):
        # get speed cam data immediately after building our tree and list structure.

        pool = ThreadPool(num_threads=worker_threads, action='SPEED')
        pool.add_task(func, linkedList, tree)

    @staticmethod
    def start_thread_pool_speed_cam_look_ahead(func, worker_threads=1, previous_ccp=False):
        # get speed cam data immediately with a look ahead.

        pool = ThreadPool(num_threads=worker_threads, action='SPEED')
        pool.add_task(func, previous_ccp)

    @staticmethod
    def start_thread_pool_process_disable_all(func, worker_threads=1):
        while RectangleCalculatorThread.thread_lock:
            pass
        pool = ThreadPool(num_threads=worker_threads, action='DISABLE')
        pool.add_task(func)
        #_ = pool.wait_completion()

    @staticmethod
    def start_thread_pool_data_lookup(func,
                                      lat=None,
                                      lon=None,
                                      linkedList=None,
                                      tree=None,
                                      c_rect=None,
                                      wait_till_completed=True):

        pool = ThreadPool(num_threads=1, action='LOOKUP')
        pool.add_task(func, lat, lon, linkedList, tree, c_rect)

        if wait_till_completed:
            _ = pool.wait_completion()

    def trigger_calculation(self, *args):
        reason = args[0]

        if self.disable_all:
            return

        # convert CCP longitude,latitude to (x,y).
        self.xtile, self.ytile = self.longlat2tile(self.latitude,
                                                   self.longitude, self.zoom)

        self.print_log_line(f" Trigger calculation: New rectangle is {self.new_rectangle}")
        if self.new_rectangle is True:
            self.osm_wrapper.first_start = True

            self.new_rectangle = False
            self.border_reached = False

            # delete and reset old stuff, cache ccp for extrapolation
            self.delete_old_instances()

            # self.print_log_line(' calculating new rectangle peripheries..')

            # if heading is not known, return.
            if (self.direction == "-" or self.direction == None):
                return

            # update rect periphery based on internet status
            self.update_rectangle_periphery()

            self.print_log_line(' Rectangle CURRENT')
            if reason == 'CONTINUE':
                num_threads = 1
                LON_MIN, LAT_MIN, LON_MAX, LAT_MAX = self.createGeoJsonTilePolygon(
                    self.direction,
                    self.zoom,
                    self.xtile,
                    self.ytile,
                    self.rectangle_periphery)
                self.print_log_line(f' Num Threads is {num_threads}')
            else:
                num_threads = 2
                self.print_log_line(f' Num Threads is {num_threads}')
                h = self.tile2hypotenuse(self.xtile, self.ytile)
                angle = self.tile2polar(self.xtile, self.ytile)

                # self.print_log_line(' Polar coordinates = %f %f degrees' %(h,angle))

                xtile_min, xtile_max, ytile_min, ytile_max = self.calculatepoints2angle(
                    self.xtile,
                    self.ytile,
                    self.initial_rect_distance,
                    self.current_rect_angle)
                LON_MIN, LAT_MIN, LON_MAX, LAT_MAX = self.createGeoJsonTilePolygonAngle(
                    self.zoom,
                    xtile_min,
                    ytile_min,
                    xtile_max,
                    ytile_max)

            self.osm_wrapper.osm_update_geoBounds([[LAT_MAX, LON_MIN],
                                                   [LAT_MIN, LON_MAX]],
                                                  self.direction,
                                                  'CURRENT')
            maps.TRIGGER_RECT_DRAW = True

            # convert each of the 2 points to (x,y).
            pt1_xtile, pt1_ytile = self.longlat2tile(LAT_MIN, LON_MIN,
                                                     self.zoom)
            pt2_xtile, pt2_ytile = self.longlat2tile(LAT_MAX, LON_MAX,
                                                     self.zoom)
            # calculate a rectangle from these 2 points
            self.CURRENT_RECT = self.calculate_rectangle_border(
                [pt1_xtile, pt1_ytile], [pt2_xtile, pt2_ytile])
            self.CURRENT_RECT.set_rectangle_ident(self.direction)
            self.CURRENT_RECT.set_rectangle_string('CURRENT')
            self.linkedListGenerator = DoubleLinkedListNodes()
            self.treeGenerator = BinarySearchTree()
            # expand our rect due to impreciseness of gps position
            # self.CURRENT_RECT = self.CURRENT_RECT.expanded_by(2)
            # calculate the radius of the rectangle in km
            self.rectangle_radius = self.calculate_rectangle_radius(
                self.CURRENT_RECT.rect_height(),
                self.CURRENT_RECT.rect_width())
            self.print_log_line(' Rectangle CURRENT radius %f km' % self.rectangle_radius)
            # update the main view layout
            self.ml.update_speed_cam_txt(self.rectangle_radius)

            # check osm data reception status of favoured rectangle
            RectangleCalculatorThread.thread_lock = True
            (online_available, status, data, internal_error,
             current_rect) = self.trigger_osm_lookup(LON_MIN,
                                                     LAT_MIN,
                                                     LON_MAX,
                                                     LAT_MAX,
                                                     self.direction,
                                                     current_rect='CURRENT')
            RectangleCalculatorThread.thread_lock = False
            self.update_kivi_maxspeed_onlinecheck(
                online_available=online_available,
                status=status,
                internal_error=internal_error)

            if (status == 'ERROR'):
                self.osm_data_error = status
                if self.osm_error_reported:
                    pass
                else:
                    self.voice_prompt_queue.produce_online_status(
                        self.cv_voice, "OSM_DATA_ERROR")
                    self.osm_error_reported = True

            elif (status == 'NOINET'):

                if (reason == 'STARTUP'):
                    self.voice_prompt_queue.produce_online_status(
                        self.cv_voice, "INTERNET_CONN_FAILED")
                    self.ms.update_online_image_layout("INETFAILED")
                    self.osm_error_reported = True
                else:
                    if self.osm_error_reported:
                        pass
                    else:
                        self.voice_prompt_queue.produce_online_status(
                            self.cv_voice, "INTERNET_CONN_FAILED")
                        self.osm_error_reported = True
                        self.ms.update_online_image_layout("INETFAILED")
            else:
                self.osm_data_error = "NO_ERROR"
                self.osm_error_reported = False

                xtile_min = 0
                xtile_max = 0
                ytile_min = 0
                ytile_max = 0
                polygon_lookup_string = ""
                rect_periphery = None

                for i in range(0, num_threads):
                    self.print_log_line(' Rectangle CURRENT_RECT_%s' % str(i))
                    # calculate fallback rectangles in case the ccp is unstable
                    if reason == 'CONTINUE':
                        if not self.consider_backup_rects:
                            rect_periphery = self.rectangle_periphery
                            polygon_lookup_string = self.direction + "-2"
                        else:
                            # backup rectangle if CCP makes a U-Turn
                            rect_periphery = self.rectangle_periphery_backup
                            polygon_lookup_string = \
                                self.rectangle_fallback_directions[
                                    self.direction][
                                    10]

                        LON_MIN, LAT_MIN, LON_MAX, LAT_MAX = self.createGeoJsonTilePolygon(
                            polygon_lookup_string,
                            self.zoom,
                            self.xtile,
                            self.ytile,
                            rect_periphery)
                    else:
                        polygon_lookup_string = \
                            self.rectangle_fallback_directions[self.direction][
                                i]

                        if i == 0:
                            xtile_decreased = self.decrease_xtile_left()
                            xtile_min, xtile_max, ytile_min, ytile_max = self.calculatepoints2angle(
                                xtile_decreased,
                                self.ytile,
                                self.initial_rect_distance,
                                self.fallback_rect_angle)
                        else:
                            xtile_increased = self.increase_xtile_right()
                            xtile_min, xtile_max, ytile_min, ytile_max = self.calculatepoints2angle(
                                xtile_increased,
                                self.ytile,
                                self.initial_rect_distance,
                                self.fallback_rect_angle)
                        LON_MIN, LAT_MIN, LON_MAX, LAT_MAX = self.createGeoJsonTilePolygonAngle(
                            self.zoom,
                            xtile_min,
                            ytile_min,
                            xtile_max,
                            ytile_max)

                    self.osm_wrapper.osm_update_geoBounds([[LAT_MAX, LON_MIN],
                                                           [LAT_MIN, LON_MAX]],
                                                          polygon_lookup_string,
                                                          'CURRENT' + str(i))
                    maps.TRIGGER_RECT_DRAW = True
                    # convert each of the 2 points to (x,y).
                    pt1_xtile, pt1_ytile = self.longlat2tile(LAT_MIN, LON_MIN,
                                                             self.zoom)
                    pt2_xtile, pt2_ytile = self.longlat2tile(LAT_MAX, LON_MAX,
                                                             self.zoom)
                    # calculate a rectangle from these 2 points
                    rect_name = 'CURRENT_RECT_' + str(i)
                    setattr(self, rect_name, self.calculate_rectangle_border(
                        [pt1_xtile, pt1_ytile],
                        [pt2_xtile, pt2_ytile]))

                    linked_list_name = 'linkedListGenerator_' + str(i)
                    setattr(self, linked_list_name, DoubleLinkedListNodes())
                    tree_name = 'treeGenerator_' + str(i)
                    setattr(self, tree_name, BinarySearchTree())

                    getattr(self, rect_name).set_rectangle_ident(
                        polygon_lookup_string)
                    getattr(self, rect_name).set_rectangle_string(
                        'CURRENT_RECT_' + str(i))

                    self.osm_lookup_properties.append((LON_MIN, LAT_MIN,
                                                       LON_MAX, LAT_MAX,
                                                       polygon_lookup_string,
                                                       None,
                                                       getattr(self,
                                                               rect_name).get_rectangle_string()))
                    # calculate the radius of the rectangle in km
                    radius_name = 'rectangle_radius_' + str(i)
                    setattr(self, radius_name, self.calculate_rectangle_radius(
                        getattr(self, rect_name).rect_height(),
                        getattr(self, rect_name).rect_width()))
                    # update the main view layout
                    self.ml.update_speed_cam_txt(
                        self.rectangle_radius + getattr(self, radius_name))
                    self.print_log_line(' Rectangle CURRENT_RECT_%s radius %f km'
                                        % (str(i), getattr(self, radius_name)))

                    self.RECT_ATTRIBUTES[
                        getattr(self, rect_name).get_rectangle_string()] = [
                        getattr(self, rect_name),
                        getattr(self, linked_list_name),
                        getattr(self, tree_name),
                        getattr(self, radius_name)]

                self.RECT_ATTRIBUTES[
                    self.CURRENT_RECT.get_rectangle_string()] = [
                    self.CURRENT_RECT,
                    self.linkedListGenerator,
                    self.treeGenerator,
                    self.rectangle_radius]
                self.RECT_KEYS = list(self.RECT_ATTRIBUTES.keys())
                self.RECT_VALUES = list(self.RECT_ATTRIBUTES.values())

                self.fill_osm_data()

                # start our worker threads for osm lookup
                server_responses = self.start_thread_pool_lookup(
                    self.trigger_osm_lookup,
                    num_threads,
                    self.osm_lookup_properties,
                    online_available,
                    status,
                    data,
                    internal_error,
                    'CURRENT')
                # self.print_log_line(' Tasks completed')
                self.overspeed_queue.clear_overspeedqueue(self.cv_overspeed)
                # we are done getting our data

                # start our worker threads for building data structures
                # self.start_task_data_structure(server_responses)
                self.start_thread_pool_data_structure(
                    self.build_data_structure,
                    num_threads + 1,
                    server_responses,
                    wait_till_completed=True)
                self.osm_wrapper.update_speed_cams(self.speed_cam_dict)
                self.fill_speed_cams()

            # make an intersection between all rects
            self.intersect_rectangle()

        else:
            if isinstance(self.CURRENT_RECT, Rect):
                self.matching_rect, close_to_border, delete_rects = self.check_all_rectangles()
                result = self.extrapolate_rectangle(True,
                                                    "",
                                                    "",
                                                    "",
                                                    close_to_border,
                                                    delete_rects)

                self.previous_rect = self.matching_rect
                if result:
                    self.intersect_rectangle(mode="EXTRAPOLATED")
                    self.osm_wrapper.first_start = True
                else:
                    self.osm_wrapper.first_start = False

    def intersect_rectangle(self, mode='NORMAL'):
        rect_from_index = 0
        rect_to_index = 1

        if mode == 'NORMAL':
            while rect_from_index < len(self.RECT_KEYS) - 1:
                from_rect = \
                    self.RECT_ATTRIBUTES[self.RECT_KEYS[rect_from_index]][0]
                to_rect = self.RECT_ATTRIBUTES[self.RECT_KEYS[rect_to_index]][
                    0]
                rect_ident = self.RECT_KEYS[rect_to_index] + "_" + str(
                    randint(0, 1000))

                rect_string, rect = from_rect.intersect_rect_with(to_rect,
                                                                  rect_ident)

                if rect is not None:
                    self.RECT_ATTRIBUTES_INTERSECTED[rect_string] = rect

                rect_from_index += 1
                rect_to_index += 1

        elif mode == 'EXTRAPOLATED':
            while (rect_from_index < len(
                    self.RECT_ATTRIBUTES_EXTRAPOLATED_KEYS) - 1):
                from_rect = self.RECT_ATTRIBUTES_EXTRAPOLATED[
                    self.RECT_ATTRIBUTES_EXTRAPOLATED_KEYS[rect_from_index]][0]
                to_rect = self.RECT_ATTRIBUTES_EXTRAPOLATED[
                    self.RECT_ATTRIBUTES_EXTRAPOLATED_KEYS[rect_to_index]][0]
                rect_ident = self.RECT_ATTRIBUTES_EXTRAPOLATED_KEYS[
                                 rect_to_index] + "_" + str(randint(0, 1000))
                rect_string, rect = from_rect.intersect_rect_with(to_rect,
                                                                  rect_ident)

                if rect is not None:
                    self.RECT_ATTRIBUTES_INTERSECTED[rect_string] = rect

                rect_from_index += 1
                rect_to_index += 1

        self.print_log_line(' Number of intersected rectangles: %d'
                            % len(self.RECT_ATTRIBUTES_INTERSECTED))

    def point_in_intersected_rect(self, xtile, ytile):
        for rect_string, rect in self.RECT_ATTRIBUTES_INTERSECTED.items():
            if rect.point_in_rect(xtile, ytile):
                # TODO: Fix this Hack because intersected rect calculation wrong for SSW, SW
                if self.direction == "SSW" or self.direction == "SW":
                    return False
                return True
        return False

    def hasSameDirection(self):
        return self.matching_rect.get_rectangle_ident() == self.direction

    def isExtrapolatedRectMatching(self):
        return 'EXTRAPOLATED' in self.matching_rect.get_rectangle_string()

    def isExtrapolatedRectPrevious(self):
        return self.previous_rect != "NOTSET" \
               and 'EXTRAPOLATED' in self.previous_rect.get_rectangle_string()

    def delete_old_instances(self, delete_rects=False, mode='CURRENT'):

        if mode == 'CURRENT':
            # delete old key references and dicts
            del self.osm_lookup_properties[:]
            del self.RECT_KEYS[:]
            del self.RECT_VALUES[:]

            # save original coords for extrapolation only
            # if new rectangles are calculated (do extrapolated stuff)
            self.startup_extrapolation = True
            self.extrapolated_number = 0
            self.longitude_extrapolated = self.longitude
            self.latitude_extrapolated = self.latitude
            # reset geo bounds
            Clock.schedule_once(self.osm_wrapper.reset_geo_bounds_extrapolated, 0)
            Clock.schedule_once(self.osm_wrapper.reset_geo_bounds, 0)

            for rect, attributes in self.RECT_ATTRIBUTES.items():
                # remove old original list and tree objects,
                # not the reference before creating a new structure.
                if isinstance(attributes[0], Rect):
                    attributes[0].delete_rect()
                    if isinstance(attributes[1], DoubleLinkedListNodes):
                        attributes[1].deleteLinkedList()
                    if isinstance(attributes[2], BinarySearchTree):
                        attributes[2].deleteTree()

            for rect, attributes in self.RECT_ATTRIBUTES_EXTRAPOLATED.items():
                if isinstance(attributes[0], Rect):
                    attributes[0].delete_rect()
                    if isinstance(attributes[1], DoubleLinkedListNodes):
                        attributes[1].deleteLinkedList()
                    if isinstance(attributes[2], BinarySearchTree):
                        attributes[2].deleteTree()

            for rect_string, rect in self.RECT_ATTRIBUTES_INTERSECTED.items():
                if isinstance(rect, Rect):
                    rect.delete_rect()

            self.RECT_ATTRIBUTES_EXTRAPOLATED = {}
            self.RECT_ATTRIBUTES = {}
            self.RECT_ATTRIBUTES_INTERSECTED = {}

            # reset cam statistics if we are outside all rects or
            # if extrapolated rects get deleted
            # self.number_distance_cams = 0
            # self.fix_cams = 0
            # self.traffic_cams = 0
            # self.distance_cams = 0
            # self.mobile_cams = 0

        else:
            if (delete_rects or (self.isExtrapolatedRectMatching() and len(
                    self.RECT_ATTRIBUTES_EXTRAPOLATED) >= self.max_number_exptrapolated_rects)):
                for i in self.RECT_ATTRIBUTES_EXTRAPOLATED_KEYS:
                    self.print_log_line(
                        ' Deleting old extrapolated rect %s' % i)
                    if isinstance(self.RECT_ATTRIBUTES_EXTRAPOLATED[i][0],
                                  Rect):
                        self.RECT_ATTRIBUTES_EXTRAPOLATED[i][0].delete_rect()
                    if isinstance(self.RECT_ATTRIBUTES_EXTRAPOLATED[i][1],
                                  DoubleLinkedListNodes):
                        self.RECT_ATTRIBUTES_EXTRAPOLATED[i][
                            1].deleteLinkedList()
                    if isinstance(self.RECT_ATTRIBUTES_EXTRAPOLATED[i][2],
                                  BinarySearchTree):
                        self.RECT_ATTRIBUTES_EXTRAPOLATED[i][2].deleteTree()
                    self.RECT_ATTRIBUTES_EXTRAPOLATED.pop(i)

                for rect_string in list(self.RECT_ATTRIBUTES_INTERSECTED):
                    if 'EXTRAPOLATED' in rect_string:
                        self.RECT_ATTRIBUTES_INTERSECTED.pop(rect_string)

                self.extrapolated_number = 0
                # update osm map drawer thread
                Clock.schedule_once(self.osm_wrapper.reset_geo_bounds_extrapolated, 0)

                # reset cam statistics if we are outside all rects
                # or if extrapolated rects get deleted
                # self.number_distance_cams = 0
                # self.fix_cams = 0
                # self.traffic_cams = 0
                # self.distance_cams = 0
                # self.mobile_cams = 0

            # reset osm lookup array every time new extrapolated rects are going to be calculated
            del self.osm_lookup_properties_extrapolated[:]

    def extrapolate_rectangle(self,
                              online_available=None,
                              status=None,
                              data=None,
                              internal_error=None,
                              close_to_border=False,
                              delete_rects=False):

        self.process(update_ccp_only=True)

        if self.matching_rect is None or self.previous_rect is None:
            self.print_log_line(" Extrapolation criteria not fulfilled -> no matching rect")
            return False

        if self.matching_rect == 'NOTSET':
            self.print_log_line(" Extrapolation criteria not fulfilled -> no matching rect")
            return False

        if int(self.cspeed) == 0:
            self.print_log_line(" Extrapolation criteria not fulfilled -> speed == 0")
            return False

        if not delete_rects and self.point_in_intersected_rect(self.xtile,
                                                               self.ytile):
            self.print_log_line(" Extrapolation criteria not fulfilled "
                                "-> point in intersected rect")
            return False
        # if a new rect was already extrapolated shortly before and we are
        # still close to the border of the matching rect (low speed),
        # do not extrapolate again for the next CCP received
        if close_to_border:
            self.print_log_line(" Extrapolating new Rects...")
        else:
            if not self.internet_available() and self.failed_rect == 'EXTRAPOLATED':
                self.print_log_line(" Retry network link for extrapolated rects")
            else:
                self.print_log_line(" Extrapolation criteria not fulfilled -> not close to border")
                return False

        # delete old stuff
        self.delete_old_instances(delete_rects, mode='EXTRAPOLATED')

        extrapolated = True
        self.extrapolated_number = self.extrapolated_number + 1

        if self.startup_extrapolation:
            self.startup_extrapolation = False

            if self.hasSameDirection():
                self.print_log_line(
                    " CCP in same direction as matching rect %s"
                    % self.matching_rect.get_rectangle_string())
                polygon_lookup_string = self.matching_rect.get_rectangle_ident() + "-2"
                self.xtile, self.ytile = self.longlat2tile(
                    self.latitude_extrapolated,
                    self.longitude_extrapolated, self.zoom)
            else:
                self.print_log_line(
                    " CCP has other direction as matching rect %s"
                    % self.matching_rect.get_rectangle_string())
                polygon_lookup_string = self.direction
        else:
            polygon_lookup_string = self.direction

        self.print_log_line(' rectangle EXTRAPOLATED_%s' % str(self.extrapolated_number))
        LON_MIN, LAT_MIN, LON_MAX, LAT_MAX = self.createGeoJsonTilePolygon(
            polygon_lookup_string,
            self.zoom,
            self.xtile,
            self.ytile,
            self.rectangle_periphery)
        self.osm_wrapper.osm_update_geoBounds_extrapolated([[LAT_MAX, LON_MIN],
                                                            [LAT_MIN,
                                                             LON_MAX]],
                                                           polygon_lookup_string,
                                                           'EXTRAPOLATED_' + str(
                                                               self.extrapolated_number))
        maps.TRIGGER_RECT_DRAW_EXTRAPOLATED = True

        # convert each of the 2 points to (x,y).
        pt1_xtile, pt1_ytile = self.longlat2tile(LAT_MIN, LON_MIN, self.zoom)
        pt2_xtile, pt2_ytile = self.longlat2tile(LAT_MAX, LON_MAX, self.zoom)
        # calculate a rectangle from these 2 points

        rect_name = 'CURRENT_RECT_EXTRAPOLATED_' + str(
            self.extrapolated_number)
        setattr(self, rect_name,
                self.calculate_rectangle_border([pt1_xtile, pt1_ytile],
                                                [pt2_xtile, pt2_ytile]))

        linked_list_name = 'linkedListGenerator_extrapolated_' + 'P_' + str(
            self.extrapolated_number)
        setattr(self, linked_list_name, DoubleLinkedListNodes())
        tree_name = 'treeGenerator_extrapolated_' + 'P_' + str(
            self.extrapolated_number)
        setattr(self, tree_name, BinarySearchTree())

        getattr(self, rect_name).set_rectangle_ident(polygon_lookup_string)
        getattr(self, rect_name).set_rectangle_string(
            'EXTRAPOLATED_' + str(self.extrapolated_number))
        # expand our rect due to impreciseness of gps position
        # setattr(self, rect_name, getattr(self, rect_name).expanded_by(1))

        self.osm_lookup_properties_extrapolated.append((LON_MIN,
                                                        LAT_MIN,
                                                        LON_MAX,
                                                        LAT_MAX,
                                                        polygon_lookup_string,
                                                        None,
                                                        getattr(self,
                                                                rect_name).get_rectangle_string()))

        # calculate the radius of the rectangle in km
        radius_name = 'rectangle_radius_extrapolated_' + str(
            self.extrapolated_number)
        setattr(self, radius_name, self.calculate_rectangle_radius(
            getattr(self, rect_name).rect_height(),
            getattr(self, rect_name).rect_width()))
        # update the main view layout
        self.ml.update_speed_cam_txt(getattr(self, radius_name))
        self.print_log_line(' rectangle EXTRAPOLATED_%s radius %f km'
                            % (str(self.extrapolated_number), getattr(self, radius_name)))

        ########################################################################
        # ####################################################################
        self.extrapolated_number = self.extrapolated_number + 1

        if self.motorway_flag or self.use_only_one_extrapolated_rect:
            num_threads = 1
            self.RECT_ATTRIBUTES_EXTRAPOLATED[
                getattr(self, rect_name).get_rectangle_string()] = [
                getattr(self, rect_name),
                getattr(self, linked_list_name),
                getattr(self, tree_name),
                getattr(self, radius_name)]
        else:
            num_threads = 2

            if self.hasSameDirection():
                polygon_lookup_string = self.matching_rect.get_rectangle_ident()

            self.print_log_line(' rectangle EXTRAPOLATED_%s' % str(self.extrapolated_number))
            LON_MIN, LAT_MIN, LON_MAX, LAT_MAX = self.createGeoJsonTilePolygon(
                polygon_lookup_string + "-2",
                self.zoom,
                self.xtile,
                self.ytile,
                self.rectangle_periphery_fallback)

            self.osm_wrapper.osm_update_geoBounds_extrapolated(
                [[LAT_MAX, LON_MIN], [LAT_MIN, LON_MAX]],
                polygon_lookup_string + "-2",
                'EXTRAPOLATED_' + str(self.extrapolated_number))
            maps.TRIGGER_RECT_DRAW_EXTRAPOLATED = True

            # convert each of the 2 points to (x,y).
            pt1_xtile, pt1_ytile = self.longlat2tile(LAT_MIN, LON_MIN,
                                                     self.zoom)
            pt2_xtile, pt2_ytile = self.longlat2tile(LAT_MAX, LON_MAX,
                                                     self.zoom)
            # calculate a rectangle from these 2 points

            rect_name_2 = 'CURRENT_RECT_EXTRAPOLATED_' + str(
                self.extrapolated_number)
            setattr(self, rect_name_2,
                    self.calculate_rectangle_border([pt1_xtile, pt1_ytile],
                                                    [pt2_xtile, pt2_ytile]))

            linked_list_name_2 = 'linkedListGenerator_extrapolated_' + 'P_' + str(
                self.extrapolated_number)
            setattr(self, linked_list_name_2, DoubleLinkedListNodes())
            tree_name_2 = 'treeGenerator_extrapolated_' + 'P_' + str(
                self.extrapolated_number)
            setattr(self, tree_name_2, BinarySearchTree())

            getattr(self, rect_name_2).set_rectangle_ident(
                polygon_lookup_string + "-2")
            getattr(self, rect_name_2).set_rectangle_string(
                'EXTRAPOLATED_' + str(self.extrapolated_number))

            self.osm_lookup_properties_extrapolated.append((LON_MIN,
                                                            LAT_MIN,
                                                            LON_MAX,
                                                            LAT_MAX,
                                                            polygon_lookup_string + "-2",
                                                            None,
                                                            getattr(self,
                                                                    rect_name_2).get_rectangle_string()))

            # calculate the radius of the rectangle in km
            radius_name_2 = 'rectangle_radius_extrapolated_' + str(
                self.extrapolated_number)
            setattr(self, radius_name_2, self.calculate_rectangle_radius(
                getattr(self, rect_name_2).rect_height(),
                getattr(self, rect_name_2).rect_width()))
            # update the main view layout
            self.ml.update_speed_cam_txt(
                getattr(self, radius_name) + getattr(self, radius_name_2))
            self.print_log_line(' rectangle EXTRAPOLATED_%s radius %f km'
                                % (str(self.extrapolated_number), getattr(self, radius_name_2)))

            # add the more far (second) rectangle first, this is needed
            # for not extrapolating uneccessarily if we switch to the second rect.
            # Otherwise extraploation would be done on the first rect.
            self.RECT_ATTRIBUTES_EXTRAPOLATED[
                getattr(self, rect_name_2).get_rectangle_string()] = [
                getattr(self, rect_name_2),
                getattr(self, linked_list_name_2),
                getattr(self, tree_name_2),
                getattr(self, radius_name_2)]
            self.RECT_ATTRIBUTES_EXTRAPOLATED[
                getattr(self, rect_name).get_rectangle_string()] = [
                getattr(self, rect_name),
                getattr(self, linked_list_name),
                getattr(self, tree_name),
                getattr(self, radius_name)]
        ###################################################################################

        self.RECT_ATTRIBUTES_EXTRAPOLATED_KEYS = list(self.RECT_ATTRIBUTES_EXTRAPOLATED.keys())
        self.RECT_VALUES_EXTRAPOLATED = list(self.RECT_ATTRIBUTES_EXTRAPOLATED.values())
        self.osm_wrapper.setExtrapolation(extrapolated)

        # start our worker threads for osm lookup
        server_responses = self.start_thread_pool_lookup(
            self.trigger_osm_lookup,
            num_threads,
            self.osm_lookup_properties_extrapolated,
            online_available,
            status,
            data,
            internal_error,
            'EXTRAPOLATED',
            True)

        # start our worker threads for building data structures
        # self.start_task_data_structure(server_responses,True)
        self.start_thread_pool_data_structure(self.build_data_structure,
                                              num_threads,
                                              server_responses,
                                              extrapolated,
                                              wait_till_completed=True)

        self.osm_wrapper.update_speed_cams(self.speed_cam_dict)
        self.fill_speed_cams()
        return True

    def check_all_rectangles(self, previous_ccp=False):
        xtile = None
        ytile = None
        longitude = None
        latitude = None
        close_to_border = False
        delete_rects = False

        self.print_log_line(' Checking all rectangles..')

        if not previous_ccp:
            self.process(update_ccp_only=True)

        if previous_ccp:
            self.print_log_line(
                ' Tunnel mode active, using cached CCP coords..')
            xtile = self.xtile_cached
            ytile = self.ytile_cached
            longitude = self.longitude_cached
            latitude = self.latitude_cached
        else:
            xtile = self.xtile
            ytile = self.ytile
            longitude = self.longitude
            latitude = self.latitude
            self.cache_tiles(xtile, ytile)

        if int(self.cspeed) == 0 and not self.was_speed0:
            # improce performance when ccp is not moving, a lookup is not necessary
            self.print_log_line(" Ignoring data lookup -> speed == 0")
            return self.matching_rect, False, False
        elif int(self.cspeed) == 0 and self.was_speed0:
            self.was_speed0 = False
        else:
            self.was_speed0 = True

        if not self.osm_error_reported and self.osm_data_error == "NO_ERROR":

            ORDERED_RECTS = OrderedDict()

            if self.matching_rect is not None and self.matching_rect != 'NOTSET' \
                    and self.isExtrapolatedRectMatching():

                for rect, attributes in self.RECT_ATTRIBUTES_EXTRAPOLATED.items():
                    self.print_log_line(' check_all_rectangles() -> rectangle %s\n' % rect)
                    if attributes[0].point_in_rect(xtile, ytile):
                        # fallback road name lookup
                        if self.empty_dataset_received and rect == self.empty_dataset_rect:
                            delete_rects = True
                            # get out immediately of empty rects
                            self.print_log_line(
                                ' Leaving rect %s immediately!' % rect)
                            return attributes[0], True, delete_rects

                        close_to_border = attributes[0].points_close_to_border(xtile, ytile)
                        self.print_log_line(' CCP lon: %f lat: %f, '
                                            'reusing previously calculated rectangle %s\n'
                                            % (longitude, latitude, rect))
                        self.start_thread_pool_data_lookup(self.trigger_cache_lookup,
                                                           latitude,
                                                           longitude,
                                                           attributes[1],
                                                           attributes[2],
                                                           attributes[0],
                                                           wait_till_completed=False)
                        self.ms.update_online_image_layout(False)
                        # self.ml.update_speed_cam_txt(attributes[3])

                        if self.enable_ordered_rects_extrapolated:
                            rectangle_string = rect
                            self.sort_rectangles(rectangle_string,
                                                 ORDERED_RECTS)

                        return attributes[0], close_to_border, delete_rects

            for rect, attributes in self.RECT_ATTRIBUTES.items():
                self.print_log_line(' check_all_rectangles() -> rectangle %s\n' % rect)
                if attributes[0].point_in_rect(xtile, ytile):
                    # fallback road name lookup
                    if self.empty_dataset_received and rect == self.empty_dataset_rect:
                        # get out immediately of empty rects
                        self.print_log_line(
                            ' Leaving rect %s immediately!' % rect)
                        return attributes[0], True, delete_rects

                    close_to_border = attributes[0].points_close_to_border(
                        xtile, ytile)
                    self.print_log_line(' CCP lon: %f lat: %f, reusing previously '
                                        'calculated rectangle %s\n' % (longitude, latitude, rect))
                    self.start_thread_pool_data_lookup(self.trigger_cache_lookup,
                                                       latitude,
                                                       longitude,
                                                       attributes[1],
                                                       attributes[2],
                                                       attributes[0],
                                                       wait_till_completed=False)
                    self.ms.update_online_image_layout(False)
                    # self.ml.update_speed_cam_txt(attributes[3])

                    return attributes[0], close_to_border, delete_rects

            if self.matching_rect is not None and self.matching_rect != 'NOTSET' \
                    and not self.isExtrapolatedRectMatching():
                for rect, attributes in self.RECT_ATTRIBUTES_EXTRAPOLATED.items():
                    self.print_log_line(' check_all_rectangles() -> rectangle %s\n' % rect)
                    if attributes[0].point_in_rect(xtile, ytile):
                        # fallback road name lookup
                        if self.empty_dataset_received and rect == self.empty_dataset_rect:
                            delete_rects = True
                            # get out immediately of empty rects
                            self.print_log_line(
                                ' Leaving rect %s immediately!' % rect)
                            return attributes[0], True, delete_rects

                        close_to_border = attributes[0].points_close_to_border(
                            xtile, ytile)
                        self.print_log_line(' CCP lon: %f lat: %f, reusing previously '
                                            'calculated rectangle %s\n'
                                            % (longitude, latitude, rect))
                        self.start_thread_pool_data_lookup(self.trigger_cache_lookup,
                                                           latitude,
                                                           longitude,
                                                           attributes[1],
                                                           attributes[2],
                                                           attributes[0],
                                                           wait_till_completed=False)
                        self.ms.update_online_image_layout(False)
                        # self.ml.update_speed_cam_txt(attributes[3])

                        if self.enable_ordered_rects_extrapolated:
                            rectangle_string = rect
                            self.sort_rectangles(rectangle_string,
                                                 ORDERED_RECTS)

                        return attributes[0], close_to_border, delete_rects

            self.print_log_line(' CCP lon: %f lat: %f is '
                                'outside ALL rectangle borders\n' % (longitude, latitude))
            self.new_rectangle = True
            self.border_reached = True

            return None, False, False

        # retry network link immediately in case the previous network connection attempt failed
        # or a data error occured based on CURRENT_RECT.
        else:
            self.print_log_line("Previous Network was unstable: "
                                "Retry Network link for Rect calculation immediately")
            self.new_rectangle = True
            self.border_reached = True
            return None, False, False

    def sort_rectangles(self, rectangle_string, ORDERED_RECTS):
        matched_index = self.RECT_ATTRIBUTES_EXTRAPOLATED_KEYS.index(
            rectangle_string)
        if matched_index == 0:
            pass
        else:
            ORDERED_RECTS[
                self.RECT_ATTRIBUTES_EXTRAPOLATED_KEYS[matched_index]] = \
                self.RECT_VALUES_EXTRAPOLATED[matched_index]

            for index_b in range(0, matched_index):
                ORDERED_RECTS[
                    self.RECT_ATTRIBUTES_EXTRAPOLATED_KEYS[index_b]] = \
                    self.RECT_VALUES_EXTRAPOLATED[index_b]
            for index_a in range(matched_index + 1,
                                 len(self.RECT_ATTRIBUTES_EXTRAPOLATED)):
                ORDERED_RECTS[
                    self.RECT_ATTRIBUTES_EXTRAPOLATED_KEYS[index_a]] = \
                    self.RECT_VALUES_EXTRAPOLATED[index_a]

            self.RECT_ATTRIBUTES_EXTRAPOLATED = ORDERED_RECTS

    def check_specific_rectangle(self, *args):

        xtile = self.xtile
        ytile = self.ytile
        longitude = self.longitude
        latitude = self.latitude

        for rect, generator in self.RECT_ATTRIBUTES.items():
            linkedListGenerator = generator[1]
            treeGenerator = generator[2]
            current_rect = generator[0]

            if isinstance(linkedListGenerator,
                          DoubleLinkedListNodes) and isinstance(treeGenerator,
                                                                BinarySearchTree):

                if (isinstance(current_rect,
                               Rect) and current_rect.point_in_rect(xtile,
                                                                    ytile)):
                    self.start_thread_pool_data_lookup(self.trigger_cache_lookup,
                                                       latitude,
                                                       longitude,
                                                       linkedListGenerator,
                                                       treeGenerator,
                                                       current_rect,
                                                       wait_till_completed=False)
                    '''self.trigger_cache_lookup(latitude=latitude,
                                              longitude=longitude,
                                              linkedListGenerator=linkedListGenerator,
                                              treeGenerator=treeGenerator,
                                              current_rect=current_rect)'''

                    self.ms.update_online_image_layout(False)
                    # self.ml.update_speed_cam_txt(generator[3])
                    break
            else:
                self.print_log_line(
                    " Linked list and Binary Search tree not yet "
                    "created for rect %s\n" % rect)

    def resolve_dangers_on_the_road(self, way, treeGenerator):
        # any dangers on the road?
        if treeGenerator.hasHazardAttribute(way):
            self.hazards_on_road = True
            hazard = treeGenerator.getHazardValue(way)
            hazard = unicodedata.normalize('NFKD',
                                           hazard.replace(u'\xdf',
                                                          'ss')).encode(
                'utf-8', 'ignore')
            hazard = hazard.decode()
            self.print_log_line(' Hazard %s found!' % hazard.upper())

            if not self.hazard_voice:
                self.voice_prompt_queue.produce_gpssignal(self.cv_voice, 'HAZARD')
                self.hazard_voice = True
            self.ms.update_cam_road(hazard.upper(), m_type="HAZARD")
        else:
            if self.hazards_on_road:
                self.ms.update_cam_road(reset=True)
                self.hazards_on_road = False
                self.hazard_voice = False

        if treeGenerator.hasWaterwayAttribute(way):
            self.waterway = True
            water = treeGenerator.getWaterwayValue(way)
            water = unicodedata.normalize('NFKD',
                                          water.replace(u'\xdf',
                                                        'ss')).encode(
                'utf-8', 'ignore')
            water = water.decode()
            self.print_log_line(' %s found' % water.upper())
            if not self.water_voice:
                self.voice_prompt_queue.produce_gpssignal(self.cv_voice, 'WATER')
                self.water_voice = True
            self.ms.update_cam_road(water.upper(), m_type="WATER")
        else:
            if self.waterway:
                self.ms.update_cam_road(reset=True)
                self.waterway = False
                self.water_voice = False

        if treeGenerator.hasAccessConditionalAttribute(way):
            self.access_control = True
            access = treeGenerator.getAccessConditionalValue(way)
            access = unicodedata.normalize('NFKD',
                                           access.replace(u'\xdf',
                                                          'ss')).encode(
                'utf-8', 'ignore')
            access = access.decode()
            boundary_result = treeGenerator.hasBoundaryAttribute(way)
            access = access + ": " + treeGenerator.getBoundaryValue(way) \
                if boundary_result else access
            self.print_log_line(' %s found' % access)
            if not self.access_control_voice:
                self.voice_prompt_queue.produce_gpssignal(self.cv_voice, 'ACCESS_CONTROL')
                self.access_control_voice = True
            self.ms.update_cam_road(access, m_type="ACCESS_CONTROL")
        else:
            if self.access_control:
                self.ms.update_cam_road(reset=True)
                self.access_control = False
                self.access_control_voice = False

    def resolve_max_speed(self, way, treeGenerator):
        maxspeed = ""
        maxspeed_conditional = ""
        maxspeed_lanes = ""
        found_maxspeed = False

        if treeGenerator.hasMaxspeedAttribute(way):
            self.print_log_line(f' Maxspeed in tree {treeGenerator}')
            found_maxspeed = True

            if treeGenerator.hasMaxspeedConditionalAttribute(way):
                maxspeed_conditional = treeGenerator.getMaxspeedConditionalValue(
                    way)
            elif treeGenerator.hasMaxspeedLaneAttribute(way):
                maxspeed_lanes = treeGenerator.getMaxspeedLaneValue(
                    way)
            else:
                maxspeed = treeGenerator.getMaxspeedValue(way)

            maxspeed = str(maxspeed) + u" " + str(
                maxspeed_conditional) + str(maxspeed_lanes)

        return found_maxspeed, maxspeed

    def resolve_roadname_and_max_speed(self, way, treeGenerator):
        road_name = ""
        maxspeed = ""
        maxspeed_conditional = ""
        maxspeed_lanes = ""
        road_class = ""
        found_road_name = False
        found_maxspeed = False
        reset_maxspeed = False
        found_combined_tags = False
        motorway = False
        poi = False
        urban = False
        facility = None
        ramp = False

        # Do we have a road name and a max speed attribute?
        if (treeGenerator.hasRoadNameAttribute(
                way) and treeGenerator.hasMaxspeedAttribute(way)):
            self.print_log_line(f' Road name in tree {treeGenerator}')
            self.print_log_line(f' maxspeed in tree {treeGenerator}')
            found_road_name = True
            found_maxspeed = True

            # Are we on a Highway?
            if treeGenerator.hasHighwayAttribute(way):
                road_class = treeGenerator.getHighwayValue(way)
                if '_link' in road_class:
                    ramp = True
            else:
                reset_maxspeed = True
                poi = True
                if treeGenerator.hasAmenityAttribute(
                        way) and treeGenerator.is_fuel_station(way):
                    facility = 'GASSTATION'
                elif treeGenerator.hasAmenityAttribute(way):
                    facility = "AMENITY"

            # Get the actual road name value
            road_name = treeGenerator.getRoadNameValue(way)
            # Get additional attributes
            if treeGenerator.hasMaxspeedConditionalAttribute(way):
                maxspeed_conditional = treeGenerator.getMaxspeedConditionalValue(
                    way)
            elif treeGenerator.hasMaxspeedLaneAttribute(way):
                maxspeed_lanes = treeGenerator.getMaxspeedLaneValue(
                    way)
            else:
                maxspeed = treeGenerator.getMaxspeedValue(way)

            # Assemble maxspeed
            maxspeed = str(maxspeed) + u" " + str(
                maxspeed_conditional) + str(maxspeed_lanes)

            # Combined tags?
            if treeGenerator.hasCombinedTags(way):
                found_combined_tags = True
                combined_tags = treeGenerator.getCombinedTags(way)
                road_name, motorway = self.check_combined_tags(road_name,
                                                               combined_tags)

            # Is it a Tunnel?
            if treeGenerator.hasTunnelAttribute(way):
                road_name = 'Tunnel: ' + road_name

        # Do we have only a road name attribute?
        elif treeGenerator.hasRoadNameAttribute(way):
            self.print_log_line(f' Road name in tree {treeGenerator}')
            found_road_name = True

            if treeGenerator.hasHighwayAttribute(way):
                road_class = treeGenerator.getHighwayValue(way)
                if '_link' in road_class:
                    ramp = True
            else:
                reset_maxspeed = True
                poi = True
                if treeGenerator.hasAmenityAttribute(
                        way) and treeGenerator.is_fuel_station(way):
                    facility = 'GASSTATION'
                elif treeGenerator.hasAmenityAttribute(way):
                    facility = "AMENITY"

            if treeGenerator.hasExtendedRoadNameAttribute(way):
                name = treeGenerator.getRoadNameValue(way)
                road_name = treeGenerator.getExtendedRoadNameValue(way)
                road_name = ": ".join((name, road_name))
            else:
                road_name = treeGenerator.getRoadNameValue(way)

                if treeGenerator.hasCombinedTags(way):
                    found_combined_tags = True
                    combined_tags = treeGenerator.getCombinedTags(way)
                    road_name, motorway = self.check_combined_tags(road_name,
                                                                   combined_tags)

            if treeGenerator.hasTunnelAttribute(way):
                road_name = 'Tunnel: ' + road_name

            if treeGenerator.hasBoundaryAttribute(
                    way) and treeGenerator.is_urban(way):
                urban = True

        # Do we have a max speed attribute?
        elif treeGenerator.hasMaxspeedAttribute(way):
            self.print_log_line(f' Maxspeed in tree {treeGenerator}')
            found_maxspeed = True

            if treeGenerator.hasMaxspeedConditionalAttribute(way):
                maxspeed_conditional = treeGenerator.getMaxspeedConditionalValue(
                    way)
            elif treeGenerator.hasMaxspeedLaneAttribute(way):
                maxspeed_lanes = treeGenerator.getMaxspeedLaneValue(
                    way)
            else:
                maxspeed = treeGenerator.getMaxspeedValue(way)

            maxspeed = str(maxspeed) + u" " + str(
                maxspeed_conditional) + str(maxspeed_lanes)

            # We found also a Ref Attribute
            if treeGenerator.hasRefAttribute(way):
                self.print_log_line(f' Reference Road Name in tree {treeGenerator}')
                found_road_name = True
                road_name = treeGenerator.getRefValue(way)

                if treeGenerator.hasHighwayAttribute(way):
                    road_class = treeGenerator.getHighwayValue(way)
                    if '_link' in road_class:
                        ramp = True
                else:
                    reset_maxspeed = True
                    poi = True
                    if treeGenerator.hasAmenityAttribute(
                            way) and treeGenerator.is_fuel_station(way):
                        facility = 'GASSTATION'
                    elif treeGenerator.hasAmenityAttribute(way):
                        facility = "AMENITY"

        else:
            # Do we only have a Ref attribute?
            if treeGenerator.hasRefAttribute(way):
                self.print_log_line(f' Reference Road Name in tree {treeGenerator}')
                found_road_name = True
                road_name = treeGenerator.getRefValue(way)

                if treeGenerator.hasHighwayAttribute(way):
                    road_class = treeGenerator.getHighwayValue(way)
                    if '_link' in road_class:
                        ramp = True
                else:
                    reset_maxspeed = True
                    poi = True
                    if treeGenerator.hasAmenityAttribute(
                            way) and treeGenerator.is_fuel_station(way):
                        facility = 'GASSTATION'
                    elif treeGenerator.hasAmenityAttribute(way):
                        facility = "AMENITY"

                if treeGenerator.hasBoundaryAttribute(
                        way) and treeGenerator.is_urban(way):
                    urban = True

        return found_road_name, road_name, maxspeed, reset_maxspeed, found_maxspeed, \
               found_combined_tags, road_class, poi, urban, facility, motorway, ramp

    def process_road_name(self, found_road_name,
                          road_name,
                          found_combined_tags,
                          road_class,
                          poi,
                          facility):
        if found_road_name:
            road_name = unicodedata.normalize('NFKD',
                                              road_name.replace(u'\xdf',
                                                                'ss')).encode(
                'utf-8', 'ignore')

            road_name = road_name.decode()
            road_name = road_name.replace("ü", "ue")
            road_name = road_name.replace("ö", "oe")
            road_name = road_name.replace("ä", "ae")
            # current functional road class
            current_fr = self.get_road_class_value(road_class)

            # apply filters
            if FilteredRoadClasses.has_value(current_fr):
                self.print_log_line(' Filtering out road class %s' % str(
                    road_class))
                return False
            if poi and self.dismiss_pois:
                return False

            road_name = facility + ": " + road_name if facility else road_name
            self.update_kivi_roadname(road_name, found_combined_tags)
            self.last_road_name = road_name
            self.found_combined_tags = found_combined_tags
            self.print_log_line(" Road Name is: %s" % road_name)
        else:
            if self.last_road_name is not None:
                self.print_log_line(f"Using last Road Name: {self.last_road_name}")
                self.update_kivi_roadname(self.last_road_name, self.found_combined_tags)

    def process_max_speed(self,
                          maxspeed,
                          found_maxspeed,
                          road_name=None,
                          motorway=False,
                          reset_maxspeed=False,
                          ramp=False):
        if reset_maxspeed and not self.dismiss_pois:
            self.print_log_line("Resetting Overspeed to 10000")
            # Clear the max speed in case it is a POI
            self.overspeed_queue.clear_overspeedqueue(self.cv_overspeed)
            self.overspeed_queue.produce(self.cv_overspeed, {'maxspeed': 10000})
            self.print_log_line("Final Maxspeed value is POI")
            self.update_kivi_maxspeed("POI")
            return "MAX_SPEED_IS_POI"

        if found_maxspeed or len(maxspeed) > 0:
            # maxspeed may get overwritten in prepare_data_for_speed_check()
            return_string = "MAX_SPEED_FOUND"
            if ramp:
                self.overspeed_queue.produce(self.cv_overspeed, {'maxspeed': 10000})
                self.print_log_line("Final Maxspeed value is RAMP")
                self.update_kivi_maxspeed("RAMP")
                self.last_max_speed = "RAMP"
            else:
                maxspeed, overspeed_reset = self.prepare_data_for_speed_check(maxspeed, motorway)
                overspeed = maxspeed
                if overspeed_reset:
                    maxspeed = ""
                    overspeed = 10000
                self.print_log_line(f"Final Maxspeed value is {overspeed}")
                self.overspeed_queue.produce(self.cv_overspeed, {'maxspeed': overspeed})
                self.update_kivi_maxspeed(maxspeed)
                self.last_max_speed = maxspeed
        else:
            # default
            if self.last_max_speed is not None and self.last_road_name == road_name:
                return_string = "LAST_MAX_SPEED_USED"
                self.print_log_line(" Using previous Maxspeed value %s" % str(self.last_max_speed))
                self.update_kivi_maxspeed(self.last_max_speed)
                self.overspeed_queue.produce(self.cv_overspeed, {'maxspeed': self.last_max_speed})
                self.last_max_speed = None
            else:
                return_string = "MAX_SPEED_NOT_FOUND"
                self.last_max_speed = None

        return return_string

    def trigger_cache_lookup(self, latitude=0,
                             longitude=0,
                             linkedListGenerator=None,
                             treeGenerator=None,
                             current_rect=None):

        if current_rect is not None:
            self.print_log_line(f"Trigger Cache lookup from current Rect {str(current_rect)}")

        if not isinstance(linkedListGenerator, DoubleLinkedListNodes):
            self.print_log_line(
                ' trigger_cache_lookup: linkedListGenerator instance not created!')
            return False

        linkedListGenerator.set_tree_generator_instance(treeGenerator)

        node_id = linkedListGenerator.match_node((latitude, longitude))
        if node_id:
            if node_id in treeGenerator:
                # Get the way attributes in gps and offline mode
                way = treeGenerator[node_id]
                self.resolve_dangers_on_the_road(way, treeGenerator)
                # Resolve both: road name and max speed (Note: More Performance intensive)
                if self.disable_road_lookup is False:

                    if self.alternative_road_lookup:
                        road_name = self.get_road_name_via_nominatim(latitude, longitude)
                        if road_name:
                            self.process_road_name(found_road_name=True,
                                                   road_name=road_name,
                                                   found_combined_tags=False,
                                                   road_class='unclassified',
                                                   poi=False,
                                                   facility=False)
                        # Now get the max speed which is independent from the road name
                        found_maxspeed, maxspeed = self.resolve_max_speed(way, treeGenerator)
                        status = self.process_max_speed(maxspeed, found_maxspeed)
                        if status == "MAX_SPEED_NOT_FOUND":
                            self.process_max_speed_for_road_class(way, treeGenerator)
                    else:
                        found_road_name, \
                        road_name, \
                        maxspeed, \
                        reset_maxspeed, \
                        found_maxspeed, \
                        found_combined_tags, \
                        road_class, \
                        poi, \
                        urban, \
                        facility, \
                        motorway, \
                        ramp = self.resolve_roadname_and_max_speed(way, treeGenerator)

                        self.process_road_name(found_road_name,
                                               road_name,
                                               found_combined_tags,
                                               road_class,
                                               poi,
                                               facility)
                        status = self.process_max_speed(maxspeed,
                                                        found_maxspeed,
                                                        road_name,
                                                        motorway,
                                                        reset_maxspeed,
                                                        ramp)
                else:
                    # Only resolve max speed
                    found_maxspeed, maxspeed = self.resolve_max_speed(way, treeGenerator)

                    status = self.process_max_speed(maxspeed, found_maxspeed)
                    if status == "MAX_SPEED_NOT_FOUND":
                        self.process_max_speed_for_road_class(way, treeGenerator)

                # get the speed cams in gps and offline mode with a lookahead.
                '''self.process_speed_cameras_on_the_way(way,
                                                      treeGenerator,
                                                      linkedListGenerator)'''
        # Update speed cameras on the way
        self.osm_wrapper.update_speed_cams(self.speed_cam_dict)

        return True

    def get_road_name_via_nominatim(self, latitude, longitude):
        """
        Get the road name via the Nominatim library
        Note: This will use more bandwidth
        :param latitude:
        :param longitude:
        :return:
        """
        if self.latitude is None or self.longitude is None:
            self.print_log_line(f" Could not resolve Road Name -> No valid coordinates given!")
            return None

        try:
            coords = str(latitude) + " " + str(longitude)
            # try to not fetch buildings, only major and minor streets
            location = self.geolocator.reverse(coords, zoom=17)
            self.internet_connection = True
        except Exception as e:
            self.print_log_line(f" Road lookup via Nominatim failed! -> "
                                f"{str(e)}", log_level="ERROR")
            self.internet_connection = False
            return "ERROR: " + str(e)

        if location:
            loc = location.address.split(",")
            if loc:
                # If the first entry is a house number, return the second
                if loc[0].isnumeric() or loc[0][0].isdigit():
                    if len(loc) >= 2:
                        return loc[1]
                    else:
                        return loc[0]
                else:
                    return loc[0]
            else:
                return None
        else:
            return None

    def process_max_speed_for_road_class(self, way, treeGenerator):
        self.print_log_line(f"Trying to get Speed from Road Class..")
        if treeGenerator.hasHighwayAttribute(way):
            road_class = treeGenerator.getHighwayValue(way)
            speed = self.get_road_class_speed(road_class)
            if speed:
                self.print_log_line(f"Using speed {speed} "
                                    f"from road class {road_class}")
                self.update_kivi_maxspeed(speed)
                self.overspeed_queue.produce(self.cv_overspeed,
                                             {'maxspeed': speed})

    # check if at least 4 subsequent position updates resulted in the same road class
    @staticmethod
    def is_road_class_stable(road_candidates, road_class_value):
        if not isinstance(road_class_value, int):
            return False

        counter = 0
        for x, y in zip(road_candidates, road_candidates[1:]):
            if x == y and x == road_class_value:
                counter += 1
        # Example:
        # 1 1
        # 1 1
        return counter == 2

    def get_road_class_speed(self, road_class):
        self.print_log_line(' Correcting speed for road class %s' % road_class)
        if 'trunk' in road_class:
            return str(self.ROAD_CLASSES_TO_SPEED['trunk'])
        elif 'primary' in road_class:
            return str(self.ROAD_CLASSES_TO_SPEED['primary'])
        elif 'unclassified' in road_class:
            return str(self.ROAD_CLASSES_TO_SPEED['unclassified'])
        elif 'secondary' in road_class:
            return str(self.ROAD_CLASSES_TO_SPEED['secondary'])
        elif 'tertiary' in road_class:
            return str(self.ROAD_CLASSES_TO_SPEED['tertiary'])
        elif 'residential' in road_class:
            return str(self.ROAD_CLASSES_TO_SPEED['residential'])
        elif 'service' in road_class:
            return str(self.ROAD_CLASSES_TO_SPEED['service'])
        elif 'living_street' in road_class:
            return str(self.ROAD_CLASSES_TO_SPEED['living_street'])
        elif 'pedestrian' in road_class:
            return str(self.ROAD_CLASSES_TO_SPEED['pedestrian'])
        elif 'track' in road_class:
            return str(self.ROAD_CLASSES_TO_SPEED['track'])
        elif 'bus_guideway' in road_class:
            return str(self.ROAD_CLASSES_TO_SPEED['bus_guideway'])
        elif 'escape' in road_class:
            return str(self.ROAD_CLASSES_TO_SPEED['escape'])
        elif 'footway' in road_class:
            return str(self.ROAD_CLASSES_TO_SPEED['footway'])
        elif 'bridleway' in road_class:
            return str(self.ROAD_CLASSES_TO_SPEED['bridleway'])
        elif 'path' in road_class:
            return str(self.ROAD_CLASSES_TO_SPEED['path'])
        elif 'cycleway' in road_class:
            return str(self.ROAD_CLASSES_TO_SPEED['cycleway'])
        # sliproad
        elif '_link' in road_class:
            return "RAMP"
        elif 'urban' in road_class:
            return str(self.ROAD_CLASSES_TO_SPEED['urban'])
        # nothing matched
        else:
            return ""

    def get_road_class_txt(self, road_class):
        if not isinstance(road_class, int):
            return 'None'
        return self.FUNCTIONAL_ROAD_CLASSES_REVERSE[road_class]

    def get_road_class_value(self, road_class):
        # motorway or slip road
        if 'motorway' in road_class or '_link' in road_class:
            return self.FUNCTIONAL_ROAD_CLASSES['motorway']
        elif 'trunk' in road_class:
            return self.FUNCTIONAL_ROAD_CLASSES['trunk']
        elif 'primary' in road_class:
            return self.FUNCTIONAL_ROAD_CLASSES['primary']
        elif 'unclassified' in road_class:
            return self.FUNCTIONAL_ROAD_CLASSES['unclassified']
        elif 'secondary' in road_class:
            return self.FUNCTIONAL_ROAD_CLASSES['secondary']
        elif 'tertiary' in road_class:
            return self.FUNCTIONAL_ROAD_CLASSES['tertiary']
        elif 'service' in road_class:
            return self.FUNCTIONAL_ROAD_CLASSES['service']
        elif 'residential' in road_class:
            return self.FUNCTIONAL_ROAD_CLASSES['residential']
        elif 'living_street' in road_class:
            return self.FUNCTIONAL_ROAD_CLASSES['living_street']
        elif 'track' in road_class:
            return self.FUNCTIONAL_ROAD_CLASSES['track']
        elif 'bridleway' in road_class:
            return self.FUNCTIONAL_ROAD_CLASSES['bridleway']
        elif 'cycleway' in road_class:
            return self.FUNCTIONAL_ROAD_CLASSES['cycleway']
        elif 'pedestrian' in road_class:
            return self.FUNCTIONAL_ROAD_CLASSES['pedestrian']
        elif 'footway' in road_class:
            return self.FUNCTIONAL_ROAD_CLASSES['footway']
        elif 'path' in road_class:
            return self.FUNCTIONAL_ROAD_CLASSES['path']
        elif 'bus_guideway' in road_class:
            return self.FUNCTIONAL_ROAD_CLASSES['bus_guideway']
        elif 'escape' in road_class:
            return self.FUNCTIONAL_ROAD_CLASSES['escape']
        elif 'road' in road_class:
            return self.FUNCTIONAL_ROAD_CLASSES['road']
        else:
            return 'POI'

    def add_additional_attributes_to_speedcams(self, speed_cam_dict=None,
                                               linkedListGenerator=None,
                                               treeGenerator=None):
        for key, coords in speed_cam_dict.items():
            # keep GUI alive
            self.ms.update_gui()
            speed_cam_dict[key].append(linkedListGenerator)
            speed_cam_dict[key].append(treeGenerator)

        return speed_cam_dict

    def check_combined_tags(self, road_name, combined_tags):
        is_motorway = False

        self.clear_combined_tags()
        self.add_combined_tags(road_name)

        combined_length = len(combined_tags)

        if combined_length < self.max_cross_roads:
            self.max_cross_roads = combined_length

        for i in range(0, self.max_cross_roads):
            for key, value in combined_tags[i].items():
                if key == 'name' and not self.inside_combined_tags(value):
                    road_name = "/".join((road_name, value))

                elif (
                        key == 'destination:ref' and not self.inside_combined_tags(value)):
                    road_name = "/".join((road_name, value))

                elif (key == 'destination' and not self.inside_combined_tags(
                        value)):
                    road_name = "/direction".join(
                        (road_name, value))

                elif key == 'highway' and value.find('motorway') != -1:
                    self.print_log_line(' Found a motorway link')
                    is_motorway = True
                else:
                    pass

                self.add_combined_tags(value)

        return road_name, is_motorway

    def clear_combined_tags(self):
        self.combined_tags_array = []

    def add_combined_tags(self, tag):
        self.combined_tags_array.append(tag)

    def inside_combined_tags(self, road_name):
        if road_name in self.combined_tags_array:
            return True
        return False

    def prepare_data_for_speed_check(self, maxspeed, motorway=False):
        # the rect periphery may get overriden in case of a motorway
        self.update_rectangle_periphery(internet_check=False)
        overspeed_reset = False

        try:
            speed = int(maxspeed)
            maxspeed = speed
        except ValueError:

            if maxspeed.find('@') == -1:
                if maxspeed.find('AT:motorway') != -1:
                    speed = self.MAXSPEED_COUNTRIES['AT:motorway']
                    self.print_log_line(
                        ' Using austrian motorway speed %d for overspeed check'
                        % speed)
                    self.update_rectangle_periphery(mode='MOTORWAY',
                                                    internet_check=False)
                    maxspeed = speed

                elif maxspeed.find('DE:motorway') != -1:
                    speed = self.MAXSPEED_COUNTRIES['DE:motorway']
                    self.print_log_line(
                        ' Using german motorway speed %d for overspeed check'
                        % speed)
                    self.update_rectangle_periphery(mode='MOTORWAY',
                                                    internet_check=False)
                    overspeed_reset = True

                elif motorway:
                    speed = self.MAXSPEED_COUNTRIES['motorway_general']
                    self.print_log_line(
                        ' Using motorway speed %d for overspeed check' % speed)
                    self.update_rectangle_periphery(mode='MOTORWAY',
                                                    internet_check=False)
                    maxspeed = speed

                elif "mph" in maxspeed:
                    pass
                else:
                    # invalid speed
                    overspeed_reset = True
            else:
                # combined speed tag like 100@22:00-06:00
                overspeed_reset = True

        finally:
            return maxspeed, overspeed_reset

    def update_rectangle_periphery(self, mode='LOWER_CLASS',
                                   internet_check=True,
                                   reduce_rect_size=False):
        # try small rect boundaries in case last internet connection attempt failed
        if ((
                internet_check and not self.internet_available()) or reduce_rect_size):
            self.print_log_line(' Reducing rect size -> internet = %s, reduce_rect_size = %s'
                                % (str(self.internet_available()), str(reduce_rect_size)))
            self.rectangle_periphery = self.rectangle_periphery_fallback_lower_roadclass
            self.rectangle_periphery_fallback = self.rectangle_periphery_fallback_lower_roadclass
            self.url_timeout = self.osm_timeout
            self.motorway_flag = False
            return

        if mode == 'LOWER_CLASS' and self.cspeed <= self.speed_influence_on_rect_boundary:
            # make sure the rect size is constantly reduced in case of high delays
            if self.download_time >= self.max_download_time:
                self.print_log_line(f"Reducing rect size for road class: {mode}")
                self.rectangle_periphery = self.rectangle_periphery_fallback_lower_roadclass
            else:
                self.rectangle_periphery = self.rectangle_periphery_lower_roadclass

            self.rectangle_periphery_fallback = self.rectangle_periphery_fallback_lower_roadclass
            self.url_timeout = self.osm_timeout
            self.motorway_flag = False
        else:
            # make sure the rect size is constantly reduced in case of high delays
            if self.download_time >= self.max_download_time:
                self.print_log_line(f"Reducing rect size for road class: {mode}")
                self.rectangle_periphery = self.rectangle_periphery_motorway_fallback
            else:
                self.print_log_line(
                    ' Mode = %s, speed = %s, extending motorway rectangle '
                    'in preferred direction' % (mode, str(self.cspeed)))
                self.rectangle_periphery = self.rectangle_periphery_motorway

            self.rectangle_periphery_fallback = self.rectangle_periphery_motorway_fallback
            self.url_timeout = self.osm_timeout_motorway
            self.motorway_flag = True

    def process_all_speed_cameras(self, speed_cam_dict=None):
        for key, data in speed_cam_dict.items():
            # keep GUI alive
            self.ms.update_gui()
            if key.find("FIX") == 0:
                self.print_log_line(' Fix Camera found')
                fix_cam = True
                traffic_cam = False
                mobile_cam = False
            elif key.find("TRAFFIC") == 0:
                self.print_log_line(' Traffic Camera found')
                traffic_cam = True
                fix_cam = False
                mobile_cam = False
            elif key.find("MOBILE") == 0:
                self.print_log_line(' Mobile Camera found')
                mobile_cam = True
                traffic_cam = False
                fix_cam = False
            else:
                continue
            # update the SpeedWarner Thread
            self.speed_cam_queue.produce(self.cv_speedcam, {
                'ccp': (self.longitude, self.latitude),
                'fix_cam': (fix_cam, float(data[3]), float(data[2]), data[4]),
                'traffic_cam': (traffic_cam, float(data[3]), float(data[2]), data[4]),
                'distance_cam': (False, 0, 0, False),
                'mobile_cam': (mobile_cam, float(data[3]), float(data[2]), data[4]),
                'ccp_node': (float(data[1]), float(data[0])),
                'list_tree': (data[5], data[6]),
                'stable_ccp': self.isCcpStable})

    def process_speed_cameras_on_the_way(self, way=None,
                                         treeGenerator=None,
                                         linkedListGenerator=None):
        node_map = []
        fix_cam = False
        traffic_cam = False
        distance_measure_cam = False
        mobile_cam = False
        enforcement = False
        speed_cam_dict = {}
        cam_index = 10000
        fix = None
        traffic = None
        distance = None
        mobile = None

        node = linkedListGenerator.getNode()
        node_map.append(node)

        if linkedListGenerator.hasNextNode():
            self.print_log_line(' Checking cameras on the way for next node')
            node_next = linkedListGenerator.getNextNode()
            node_map.append(node_next)

            for lookup_node in node_map:
                node = lookup_node
                if linkedListGenerator.hasHighwayAttribute(
                        node) and linkedListGenerator.hasSpeedCam(node):
                    enforcement = True
                    fix_cam = True
                    self.fix_cams += 1
                    cam_index += 1
                    fix = "FIX_" + str(cam_index)
                elif way is not None and treeGenerator is not None:
                    if treeGenerator.hasHighwayAttribute(way) and \
                            treeGenerator.hasSpeedCam(way):
                        enforcement = True
                        fix_cam = True
                        self.fix_cams += 1
                        cam_index += 1
                        fix = "FIX_" + str(cam_index)
                elif linkedListGenerator.hasEnforcementAttribute2(
                        node) and linkedListGenerator.hasTrafficCamEnforcement(node):
                    enforcement = True
                    traffic_cam = True
                    cam_index += 1
                    self.traffic_cams += 1
                    traffic = "TRAFFIC_" + str(cam_index)
                elif linkedListGenerator.hasCrossingAttribute(
                        node) and linkedListGenerator.hasTrafficCamCrossing(node):
                    enforcement = False
                    traffic_cam = True
                    cam_index += 1
                    self.traffic_cams += 1
                    traffic = "TRAFFIC_" + str(cam_index)
                elif (linkedListGenerator.hasSpeedCamAttribute(
                        node) and linkedListGenerator.hasTrafficCam(node)):
                    enforcement = True
                    traffic_cam = True
                    cam_index += 1
                    self.traffic_cams += 1
                    traffic = "TRAFFIC_" + str(cam_index)
                elif linkedListGenerator.hasDeviceAttribute(
                        node) and linkedListGenerator.hasTrafficCamDevice(node):
                    enforcement = True
                    traffic_cam = True
                    cam_index += 1
                    self.traffic_cams += 1
                    traffic = "TRAFFIC_" + str(cam_index)
                elif way is not None and treeGenerator is not None:
                    if (treeGenerator.hasRoleAttribute(
                            way) and treeGenerator.hasSpeedcamAttribute(way)):
                        enforcement = True
                        distance_measure_cam = True
                        cam_index += 1
                        self.distance_cams += 1
                        distance = "DISTANCE_" + str(cam_index)
                elif linkedListGenerator.hasRoleAttribute(
                        node) and linkedListGenerator.hasSection(node) or \
                        (linkedListGenerator.hasEnforcementAttribute2(node) and
                         linkedListGenerator.hasEnforcementAverageSpeed(node)):
                    enforcement = True
                    mobile_cam = True
                    self.mobile_cams += 1
                    cam_index += 1
                    mobile = "MOBILE_" + str(cam_index)
                elif way is not None and treeGenerator is not None:
                    if treeGenerator.hasRoleAttribute(
                            node) and treeGenerator.hasSection(node):
                        enforcement = True
                        mobile_cam = True
                        self.mobile_cams += 1
                        cam_index += 1
                        mobile = "MOBILE_" + str(cam_index)
                else:
                    pass

                if fix_cam or traffic_cam or distance_measure_cam or mobile_cam:
                    self.print_log_line(' Speed Camera on the way found')
                    # get the corrdinates based on the ccp matching the current node
                    # and the start coordinates of the speed cam matching the next node.
                    if lookup_node == node:
                        latitude_start_current_node, longitude_start_current_node = \
                            linkedListGenerator.getSpeedCamStartCoordinates(node)
                        latitude_start_next_node, longitude_start_next_node = \
                            linkedListGenerator.getSpeedCamEndCoordinates(
                                lookup_node)
                    # get the corrdinates based on the ccp matching the current node
                    # and the end coordinates of the speed cam matching the current node.
                    else:
                        latitude_start_current_node, longitude_start_current_node = \
                            linkedListGenerator.getSpeedCamStartCoordinates(node)
                        latitude_start_next_node, longitude_start_next_node = \
                            linkedListGenerator.getSpeedCamStartCoordinates(lookup_node)
                    # update the SpeedWarner Thread
                    if traffic is not None:
                        name = traffic
                    elif fix is not None:
                        name = fix
                    elif mobile is not None:
                        name = mobile
                    else:
                        name = distance
                    speed_cam_dict[name] = [latitude_start_next_node,
                                            longitude_start_next_node,
                                            latitude_start_next_node,
                                            longitude_start_next_node,
                                            enforcement,
                                            linkedListGenerator,
                                            treeGenerator]
                    self.speed_cam_queue.produce(self.cv_speedcam,
                                                 {'ccp': (self.longitude,
                                                          self.latitude),
                                                  'fix_cam': (fix_cam,
                                                              float(
                                                                  longitude_start_next_node),
                                                              float(
                                                                  latitude_start_next_node),
                                                              enforcement),
                                                  'traffic_cam': (traffic_cam,
                                                                  float(
                                                                      longitude_start_next_node),
                                                                  float(
                                                                      latitude_start_next_node),
                                                                  enforcement),
                                                  'distance_cam': (
                                                      distance_measure_cam,
                                                      float(
                                                          longitude_start_next_node),
                                                      float(
                                                          latitude_start_next_node),
                                                      enforcement),
                                                  'mobile_cam': (
                                                      mobile_cam,
                                                      float(
                                                          longitude_start_next_node),
                                                      float(
                                                          latitude_start_next_node),
                                                      enforcement),
                                                  'ccp_node': (float(
                                                      longitude_start_current_node),
                                                               float(
                                                                   latitude_start_current_node)),
                                                  'list_tree': (
                                                      linkedListGenerator,
                                                      treeGenerator),
                                                  'stable_ccp': self.isCcpStable})
        else:
            if linkedListGenerator.hasHighwayAttribute(
                    node) and linkedListGenerator.hasSpeedCam(node):
                enforcement = True
                fix_cam = True
                self.fix_cams += 1
                cam_index += 1
                fix = "FIX_" + str(cam_index)
            elif way is not None and treeGenerator is not None:
                if treeGenerator.hasHighwayAttribute(way) and \
                        treeGenerator.hasSpeedCam(way):
                    enforcement = True
                    fix_cam = True
                    self.fix_cams += 1
                    cam_index += 1
                    fix = "FIX_" + str(cam_index)
            elif linkedListGenerator.hasEnforcementAttribute2(
                    node) and linkedListGenerator.hasTrafficCamEnforcement(node):
                enforcement = True
                traffic_cam = True
                cam_index += 1
                self.traffic_cams += 1
                traffic = "TRAFFIC_" + str(cam_index)
            elif linkedListGenerator.hasCrossingAttribute(
                    node) and linkedListGenerator.hasTrafficCamCrossing(node):
                enforcement = False
                traffic_cam = True
                cam_index += 1
                self.traffic_cams += 1
                traffic = "TRAFFIC_" + str(cam_index)
            elif (linkedListGenerator.hasSpeedCamAttribute(
                    node) and linkedListGenerator.hasTrafficCam(node)):
                enforcement = True
                traffic_cam = True
                cam_index += 1
                self.traffic_cams += 1
                traffic = "TRAFFIC_" + str(cam_index)
            elif linkedListGenerator.hasDeviceAttribute(
                    node) and linkedListGenerator.hasTrafficCamDevice(node):
                enforcement = True
                traffic_cam = True
                cam_index += 1
                self.traffic_cams += 1
                traffic = "TRAFFIC_" + str(cam_index)
            elif way is not None and treeGenerator is not None:
                if (treeGenerator.hasRoleAttribute(
                        way) and treeGenerator.hasSpeedcamAttribute(way)):
                    enforcement = True
                    distance_measure_cam = True
                    cam_index += 1
                    self.distance_cams += 1
                    distance = "DISTANCE_" + str(cam_index)
            elif linkedListGenerator.hasRoleAttribute(
                    node) and linkedListGenerator.hasSection(node) or \
                    (linkedListGenerator.hasEnforcementAttribute2(node) and
                     linkedListGenerator.hasEnforcementAverageSpeed(node)):
                enforcement = True
                mobile_cam = True
                self.mobile_cams += 1
                cam_index += 1
                mobile = "MOBILE_" + str(cam_index)
            elif way is not None and treeGenerator is not None:
                if treeGenerator.hasRoleAttribute(
                        node) and treeGenerator.hasSection(node):
                    enforcement = True
                    mobile_cam = True
                    self.mobile_cams += 1
                    cam_index += 1
                    mobile = "MOBILE_" + str(cam_index)
            else:
                pass

            if fix_cam or traffic_cam or distance_measure_cam or mobile_cam:
                self.print_log_line(' Speed Camera on the way found')
                # get the corrdinates based on the ccp matching the current node and
                # the end coordinates of the speed cam matching the current node.
                latitude_start_current_node, longitude_start_current_node = \
                    linkedListGenerator.getSpeedCamStartCoordinates(node)
                latitude_start_next_node, longitude_start_next_node = \
                    linkedListGenerator.getSpeedCamEndCoordinates(node)
                # update the SpeedWarner Thread
                if traffic is not None:
                    name = traffic
                elif fix is not None:
                    name = fix
                elif mobile is not None:
                    name = mobile
                else:
                    name = distance
                speed_cam_dict[name] = [latitude_start_next_node,
                                        longitude_start_next_node,
                                        latitude_start_next_node,
                                        longitude_start_next_node,
                                        enforcement,
                                        linkedListGenerator,
                                        treeGenerator]
                self.speed_cam_queue.produce(self.cv_speedcam,
                                             {'ccp': (self.longitude,
                                                      self.latitude),
                                              'fix_cam': (fix_cam,
                                                          float(
                                                              longitude_start_next_node),
                                                          float(
                                                              latitude_start_next_node),
                                                          enforcement),
                                              'traffic_cam': (traffic_cam,
                                                              float(
                                                                  longitude_start_next_node),
                                                              float(
                                                                  latitude_start_next_node),
                                                              enforcement),
                                              'distance_cam': (
                                                  distance_measure_cam,
                                                  float(
                                                      longitude_start_next_node),
                                                  float(
                                                      latitude_start_next_node),
                                                  enforcement),
                                              'mobile_cam': (
                                                  mobile_cam,
                                                  float(
                                                      longitude_start_next_node),
                                                  float(
                                                      latitude_start_next_node),
                                                  enforcement),
                                              'ccp_node': (float(
                                                  longitude_start_current_node),
                                                           float(
                                                               latitude_start_current_node)),
                                              'list_tree': (
                                                  linkedListGenerator,
                                                  treeGenerator),
                                              'stable_ccp': self.isCcpStable})
        if len(speed_cam_dict) > 0:
            self.speed_cam_dict.append(speed_cam_dict)

    def build_data_structure(self, *args, **kwargs):
        dataset = kwargs['dataset']
        rect_preferred = kwargs['rect_preferred']

        error = False
        match = False
        node_id = None
        way_id = None
        node_lat_start = None
        node_lon_start = None
        node_lat_end = None
        node_lon_end = None
        typedef = None
        node_tags = {}
        way_tags = {}
        nodes = []

        linkedListGenerator = None
        treeGenerator = None

        self.print_log_line(' Building data structure for rect %s' % rect_preferred)
        if dataset is not None:
            for rect, attributes in self.RECT_ATTRIBUTES.items():
                if rect == rect_preferred:
                    self.empty_dataset_rect = rect
                    match = True
                    linkedListGenerator = attributes[1]
                    treeGenerator = attributes[2]
                    break

            if not match:
                for rect, attributes in self.RECT_ATTRIBUTES_EXTRAPOLATED.items():
                    if rect == rect_preferred:
                        self.empty_dataset_rect = rect
                        linkedListGenerator = attributes[1]
                        treeGenerator = attributes[2]
                        break

        if dataset is not None:
            self.empty_dataset_received = False

            for index, obj in enumerate(dataset):
                # keep GUI alive
                self.ms.update_gui()
                for key, value in obj.items():
                    if (key == "type" and value == "node"):
                        typedef = value
                    elif (key == "type" and value == "way"):
                        typedef = value
                    elif (key == "id" and typedef == "node"):
                        node_id = value
                    elif (key == "id" and typedef == "way"):
                        way_id = value
                    elif (key == "lat"):
                        node_lat_start = Decimal(value)
                        if (index < len(dataset) - 1 and dataset[index + 1][
                            "type"] == "node"):
                            node_lat_end = Decimal(dataset[index + 1]["lat"])
                    elif (key == "lon"):
                        node_lon_start = Decimal(value)
                        if (index < len(dataset) - 1 and dataset[index + 1][
                            "type"] == "node"):
                            node_lon_end = Decimal(dataset[index + 1]["lon"])
                    elif (key == "tags" and typedef == "node"):
                        if type(value) is dict:
                            node_tags = value
                    elif (key == "tags" and typedef == "way"):
                        if type(value) is dict:
                            way_tags = value
                            # these cameras are part of a way, not a node.
                            self.update_number_of_distance_cameras(way_tags)
                    elif (key == "nodes" and typedef == "way"):
                        if type(value) is list:
                            nodes = value
                    else:
                        pass

                if typedef == "node":
                    # self.print_log_line('adding node')
                    if isinstance(linkedListGenerator, DoubleLinkedListNodes):
                        linkedListGenerator.append_node(node_id,
                                                        node_lat_start,
                                                        node_lon_start,
                                                        node_lat_end,
                                                        node_lon_end,
                                                        node_tags)
                elif typedef == "way":
                    # self.print_log_line('adding way')
                    if isinstance(treeGenerator, BinarySearchTree):
                        for node_id in nodes:
                            treeGenerator.insert(node_id, way_id, way_tags)
                else:
                    # nothing to insert.
                    pass
        else:
            error = True
            self.empty_dataset_received = True
            self.print_log_line(f' Empty dataset from server {self.baseurl} received!')
            self.voice_prompt_queue.produce_gpssignal(self.cv_voice,
                                                      'EMPTY_DATASET_FROM_SERVER')
        if not error:
            if isinstance(linkedListGenerator, DoubleLinkedListNodes):
                self.start_thread_pool_speed_cam_structure(self.speed_cam_lookup,
                                                           linkedList=linkedListGenerator,
                                                           tree=treeGenerator)
            # clear the vector queue, otherwise outdated positions and
            # speed values are provided if building process takes long
            self.print_log_line("building data structure succeeded")
            self.vector_data.clear_vector_data(self.cv_vector)

    def speed_cam_lookup(self, *args):
        linkedListGenerator = args[0]
        treeGenerator = args[1]

        self.print_log_line(' Speed Cam lookup in progress..')
        number_fix_cams, number_traffic_cams, number_mobile_cams, speed_cam_dict = \
            linkedListGenerator.getAttributesOfSpeedCameras(self.ms)

        self.fix_cams += number_fix_cams
        self.traffic_cams += number_traffic_cams
        self.mobile_cams += number_mobile_cams
        self.print_log_line(" Traffic Cams: %d" % self.traffic_cams)
        self.print_log_line(" Fix Cams: %d" % self.fix_cams)
        self.print_log_line(" Mobile Cams: %d" % self.mobile_cams)

        speed_cam_dict = self.add_additional_attributes_to_speedcams(
            speed_cam_dict,
            linkedListGenerator,
            treeGenerator)

        # get ALL the speed cams found
        self.process_all_speed_cameras(speed_cam_dict)
        # prepare osm cam updates
        if len(speed_cam_dict) > 0:
            self.speed_cam_dict.append(speed_cam_dict)

        self.remove_duplicate_cameras()

        # update specific cams per rect (sum of all rects)
        self.update_kivi_info_page()
        self.cleanup_speed_cams()
        self.print_log_line(' Speed Cam lookup FINISHED')

    def cleanup_speed_cams(self):
        # do a cleanup if the speed cam struture increases this limit
        if len(self.speed_cam_dict) >= 100:
            self.print_log_line(" Limit %d reached! Deleting all speed cameras")
            del self.speed_cam_dict[:]

    def remove_duplicate_cameras(self):
        # Remove duplicate cameras for Map Renderer per speed cam dict
        duplicate_list = list()
        for speed_cam_d in self.speed_cam_dict:
            duplicates = defaultdict(lambda: defaultdict(list))
            duplicate_list.append(duplicates)
            for key, entry in speed_cam_d.items():
                coords = (entry[2], entry[3])
                if coords in duplicates:
                    self.print_log_line(
                        f"Coordinates {coords} for Camera {key} are duplicate. "
                        f"-> Camera will be removed"
                    )
                    duplicates[(entry[2], entry[3])][key].append("DUPLICATE")
                else:
                    duplicates[(entry[2], entry[3])][key].append("UNIQUE")

        for i, dup in enumerate(duplicate_list):
            speed_cam_dict = self.speed_cam_dict[i]
            for dup_indexes in dup.values():
                for key, value in dup_indexes.items():
                    if value[0] == "DUPLICATE":
                        if key in list(speed_cam_dict.keys()):
                            del speed_cam_dict[key]

    def update_number_of_distance_cameras(self, way_tags={}):
        if 'role' in way_tags.keys():
            if way_tags['role'] == 'device':
                self.print_log_line(' Distance camera found')
                self.number_distance_cams += 1

    def cache_ccp(self):
        self.longitude_cached = self.longitude
        self.latitude_cached = self.latitude

    def cache_tiles(self, xtile, ytile):
        self.xtile_cached = xtile
        self.ytile_cached = ytile

    def cache_cspeed(self):
        self.cspeed_cached = self.cspeed

    def cache_direction(self):
        self.direction_cached = self.direction

    def cache_bearing(self):
        self.bearing_cached = self.bearing

    # timer in seconds
    def convert_cspeed(self, timer=1):
        # convert km/h to m/s
        self.cspeed_converted = ((self.cspeed_cached * 1000) / 3600) * timer

    def calculate_extrapolated_position(self, longitude, latitude,
                                        cspeed_converted, direction, dtime,
                                        mode='OFFLINE'):

        if longitude > 0 and latitude > 0 and cspeed_converted > 0:
            self.print_log_line(" Calculating extrapolated position based on speed and bearing")
            x = cspeed_converted * math.sin(
                direction * math.pi / 180) * dtime / 3600
            y = cspeed_converted * math.cos(
                direction * math.pi / 180) * dtime / 3600

            if mode == 'OFFLINE':
                self.latitude_cached = latitude + 180 / math.pi * y / 6378137.0
                self.longitude_cached = longitude + 180 / math.pi / math.sin(
                    latitude * math.pi / 180) * x / 6378137.0
                self.print_log_line(' Tunnel mode: New longitude cached %f, '
                                    'New latitude cached %f' % (self.longitude_cached,
                                                                self.latitude_cached))
            else:
                self.latitude = latitude + 180 / math.pi * y / 6378137.0
                self.longitude = longitude + 180 / math.pi / math.sin(
                    latitude * math.pi / 180) * x / 6378137.0

    def trigger_osm_lookup(self, *args, **kwargs):
        lon_min = args[0]
        lat_min = args[1]
        lon_max = args[2]
        lat_max = args[3]
        direction = args[4]
        amenity = None

        self.print_log_line(f"Trigger OSM lookup ({self.baseurl}) with direction {direction}")

        if len(args) == 6:
            amenity = args[5]
        current_rect = kwargs['current_rect']

        querystring = self.querystring1
        querystring2 = self.querystring2
        if amenity is not None:
            if amenity == "camera_ahead":
                querystring = self.querystring_cameras1
                querystring2 = ");out+body;"
            elif amenity == "hazard":
                querystring = self.querystring_hazard1
                querystring2 = ");out+body;"
            elif amenity == "distance_cam":
                querystring = self.querystring_distance_cams
                querystring2 = ");out+body;"
            else:
                querystring = self.querystring_amenity.replace("*", amenity)
        if amenity == "camera_ahead":
            bbox = '(' + str(
                lat_min) + ',' + str(lon_min) + ',' + str(lat_max) + ',' + str(
                lon_max) + ');'
            osm_url = self.baseurl + querystring + bbox + self.querystring_cameras2 + bbox + \
                self.querystring_cameras3 + bbox + querystring2
        elif amenity == "hazard":
            bbox = '(' + str(
                lat_min) + ',' + str(lon_min) + ',' + str(lat_max) + ',' + str(
                lon_max) + ');'
            osm_url = self.baseurl + querystring + bbox + self.querystring_hazard2 + bbox + \
                self.querystring_hazard3 + bbox + self.querystring_hazard4 + bbox + \
                self.querystring_hazard5 + bbox + self.querystring_hazard6 + bbox + querystring2
        elif amenity == "distance_cam":
            bbox = '(' + str(
                lat_min) + ',' + str(lon_min) + ',' + str(lat_max) + ',' + str(
                lon_max) + ');'
            osm_url = self.baseurl + querystring + bbox + querystring2
        else:
            osm_url = self.baseurl + querystring + '(' + str(
                lat_min) + ',' + str(lon_min) + ',' + str(lat_max) + ',' + str(
                lon_max) + ')' + querystring2

        s_time = calendar.timegm(time.gmtime())

        try:
            response = urlopen(osm_url, timeout=self.url_timeout)
            data = response.read().decode('utf-8')
            data_json = json.loads(data)
            response.close()
        except HTTPError as e:
            self.print_log_line(f" The server {osm_url} couldn't fulfill the request")
            self.print_log_line(str(e))
            internal_error = str(e)
            self.internet_connection = False
            self.failed_rect = current_rect
            self.check_worker_thread_status(internal_error, 'ERROR', current_rect)
            e_time = calendar.timegm(time.gmtime())
            return False, 'ERROR', None, internal_error, current_rect

        except URLError as e:
            self.print_log_line(f' We failed to reach the server {self.baseurl}')
            self.print_log_line(str(e))
            self.internet_connection = False
            self.failed_rect = current_rect
            internal_error = str(e)
            self.check_worker_thread_status(internal_error, 'NOINET',
                                            current_rect)
            e_time = calendar.timegm(time.gmtime())
            return False, 'NOINET', None, internal_error, current_rect

        except Exception as e:
            self.print_log_line(f' Read failed from server {self.baseurl}')
            self.print_log_line(str(e))
            self.internet_connection = False
            self.failed_rect = current_rect
            internal_error = str(e)
            self.check_worker_thread_status(internal_error, 'READ FAILED',
                                            current_rect)
            e_time = calendar.timegm(time.gmtime())
            return False, 'NOINET', None, internal_error, current_rect

        e_time = calendar.timegm(time.gmtime())
        self.download_time = int(e_time - s_time)
        self.internet_connection = True
        self.report_download_time()

        return True, 'OK', data_json['elements'], '', current_rect

    def check_worker_thread_status(self, internal_error, status, current_rect):
        if 'CURRENT' not in current_rect:
            self.ms.update_online_image_layout("INETFAILED")
            self.update_maxspeed_status(status, internal_error)

    def report_download_time(self):
        if self.download_time >= self.max_download_time:
            self.update_maxspeed_status('SLOW', None)
            # if the delay is so high that the CCP is constantly
            # outside ALL rectangle borders we have to reduce the rect size here
            self.update_rectangle_periphery(internet_check=False,
                                            reduce_rect_size=True)

            if self.slow_data_reported:
                pass
            else:
                self.voice_prompt_queue.produce_gpssignal(self.cv_voice,
                                                          "LOW_DOWNLOAD_DATA_RATE")
                self.slow_data_reported = True
        else:
            self.slow_data_reported = False

    def update_kivi_maxspeed(self, maxspeed=None):
        if maxspeed:
            if maxspeed == "cleanup":
                self.ms.maxspeed.text = ""
                Clock.schedule_once(self.ms.maxspeed.texture_update)
            else:
                if self.disable_road_lookup:
                    font_size = 250
                    font_size_alternative = 110
                else:
                    font_size = 230
                    font_size_alternative = 100

                if self.ms.maxspeed.text != str(maxspeed):
                    if isinstance(maxspeed, str) and len(maxspeed) >= 10:
                        self.ms.maxspeed.text = maxspeed
                        self.ms.maxspeed.color = (0, 1, .3, .8)
                        self.ms.maxspeed.font_size = font_size_alternative
                    else:
                        self.ms.maxspeed.text = str(maxspeed)
                        self.ms.maxspeed.color = (0, 1, .3, .8)
                        self.ms.maxspeed.font_size = font_size
                    Clock.schedule_once(self.ms.maxspeed.texture_update)

    def update_kivi_roadname(self, roadname=None, found_combined_tags=False):
        if roadname:
            roadname = str(roadname)

            if roadname == "cleanup":
                self.ms.roadname.text = ""
                Clock.schedule_once(self.ms.roadname.texture_update)
            else:
                num_cross_roads = roadname.split('/')
                num_cross_roads = list(filter(None, num_cross_roads))
                length_cross_roads = len(num_cross_roads)

                num_cross_roads.reverse()
                # reverse the road name because the first element is always the current road
                roadname = "/".join(num_cross_roads)

                if found_combined_tags:

                    if length_cross_roads == 1:
                        self.ms.roadname.font_size = 75
                    elif length_cross_roads == 2:
                        self.ms.roadname.font_size = 65
                    elif length_cross_roads == 3:
                        self.ms.roadname.font_size = 55
                    else:
                        self.ms.roadname.font_size = 50
                else:
                    if ":" in roadname:
                        self.ms.roadname.font_size = 50
                    else:
                        self.ms.roadname.font_size = 60

                if self.ms.roadname.text != roadname:
                    self.ms.roadname.text = roadname
                    Clock.schedule_once(self.ms.roadname.texture_update)

    def update_cam_radius(self, radius):
        if isinstance(radius, int) or isinstance(radius, float):
            self.ml.update_speed_cam_txt(radius)

    def update_kivi_info_page(self, poi_cams=None, poi_cams_mobile=0):
        if poi_cams is not None and isinstance(poi_cams, int):
            self.fix_cams += poi_cams

        self.mobile_cams += poi_cams_mobile

        self.ml.update_speed_cams(self.fix_cams, self.mobile_cams,
                                  self.traffic_cams, self.distance_cams)

    def update_kivi_maxspeed_onlinecheck(self, online_available=True,
                                         status='OK', internal_error='', alternative_image=None):
        self.current_online_status = status

        if online_available:
            if (
                    self.already_online and self.current_online_status == self.last_online_status):
                pass
            else:
                self.update_maxspeed_status(self.current_online_status,
                                            internal_error)
                if alternative_image is not None:
                    self.ms.update_online_image_layout(alternative_image)
                else:
                    self.ms.update_online_image_layout(online_available)
                self.already_online = True
                self.already_offline = False
        else:
            if (
                    self.already_offline and self.current_online_status == self.last_online_status):
                pass
            else:
                self.update_maxspeed_status(self.current_online_status,
                                            internal_error)
                self.already_offline = True
                self.already_online = False

        self.last_online_status = self.current_online_status

    def update_maxspeed_status(self, status, internal_error):
        # check current and additional rects
        if status == 'NOINET':
            self.ms.maxspeed.text = "CONNECTION FAILED"
            self.ms.maxspeed.font_size = 65
            self.ms.maxspeed.color = (1, 0, 0, 3)
            Clock.schedule_once(self.ms.maxspeed.texture_update)
        elif status == 'SLOW':
            self.ms.maxspeed.text = "HIGH DOWNLOAD TIME: " + str(
                self.download_time) + "s"
            self.ms.maxspeed.font_size = 50
            self.ms.maxspeed.color = (1, 0, 0, 3)
            Clock.schedule_once(self.ms.maxspeed.texture_update)
        # check current and additional rects
        elif status == 'ERROR':
            self.ms.maxspeed.text = internal_error
            self.ms.maxspeed.color = (1, 0, 0, 3)
            self.ms.maxspeed.font_size = 40
            Clock.schedule_once(self.ms.maxspeed.texture_update)
        elif status == 'STARTUP_CALC':
            self.ms.maxspeed.text = ''
            self.ms.maxspeed.color = (1, 1, 1, 1)
            self.ms.maxspeed.font_size = 80
            Clock.schedule_once(self.ms.maxspeed.texture_update)
            # reset the roadname from the previous session
            self.update_kivi_roadname("")
        elif status == 'INIT':
            self.ms.maxspeed.text = ''
            self.ms.maxspeed.color = (1, 1, 1, 1)
            self.ms.maxspeed.font_size = 80
            Clock.schedule_once(self.ms.maxspeed.texture_update)
        elif status == 'DOWNLOAD_FINISHED':
            self.ms.maxspeed.text = 'DOWNLOAD DONE'
            self.ms.maxspeed.color = (1, .9, 0, 2)
            self.ms.maxspeed.font_size = 80
            Clock.schedule_once(self.ms.maxspeed.texture_update)
        elif status == 'BUILD_FINISHED':
            self.ms.maxspeed.text = 'BUILDING DATA STRUCTS FINISHED'
            self.ms.maxspeed.color = (1, .9, 0, 2)
            self.ms.maxspeed.font_size = 60
            Clock.schedule_once(self.ms.maxspeed.texture_update)
        elif status == 'INTERSECTION_FINISHED':
            self.ms.maxspeed.text = 'INTERSECTING RECTS FINISHED'
            self.ms.maxspeed.color = (1, .9, 0, 2)
            self.ms.maxspeed.font_size = 60
            Clock.schedule_once(self.ms.maxspeed.texture_update)
        # check status of additional rects
        elif status == 'READ FAILED':
            self.ms.maxspeed.text = "DATA READ FAILED: " + internal_error
            self.ms.maxspeed.color = (1, 0, 0, 3)
            self.ms.maxspeed.font_size = 50
            Clock.schedule_once(self.ms.maxspeed.texture_update)
        else:
            pass

    def get_osm_data_state(self):
        return self.is_filled

    def get_speed_cam_state(self):
        return self.is_cam

    def fill_speed_cams(self):
        self.is_cam = True

    def reset_speed_cams(self):
        self.is_cam = False

    def fill_osm_data(self):
        self.is_filled = True

    def internet_available(self):
        return self.internet_connection
