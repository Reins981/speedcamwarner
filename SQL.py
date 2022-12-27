# -*-coding:utf8;-*-
# qpy:2
# ts=4:sw=4:expandtab
'''
Created on 01.07.2014

@author: rkoraschnigg
'''

import sqlite3
import os
from threading import Timer
from CalculatorThreads import Rect
from Logger import Logger


class POIReader(Logger):
    def __init__(self,
                 cv_speedcam,
                 speedcamqueue,
                 gps_producer,
                 calculator):
        Logger.__init__(self, self.__class__.__name__)
        self.cv_speedcam = cv_speedcam
        self.speed_cam_queue = speedcamqueue
        self.gps_producer = gps_producer
        self.calculator = calculator
        # global members
        self.connection = None
        self.poi_raw_data = None
        self.last_valid_driving_direction = None
        self.last_valid_longitude = None
        self.last_valid_latitude = None
        self.pois_converted_fix = []
        self.pois_converted_mobile = []
        self.result_pois_fix = []
        self.result_pois_mobile = []
        # timer instance
        self.timer = None
        # OSM layer
        self.zoom = 17
        # OSM Rect
        self.POI_RECT = None

        self.process()

    # called from main GUI thread
    def stop_timer(self):
        self.timer.cancel()

    def process(self):
        self.open_connection()
        self.execute()
        self.convert_cam_morton_codes()
        self.update_pois()

        self.timer = Timer(10.0, self.update_pois)
        self.timer.start()

    def open_connection(self):
        if not os.path.isfile(os.path.join(os.path.abspath(os.path.dirname(__file__)),
                                           "poidata.db3")):
            self.connection = None
            return
        try:
            # conn = sqlite3.connect('/sdcard/com.hipipal.qpyplus/scripts/database/poidata.db3')
            conn = sqlite3.connect(
                os.path.join(os.path.abspath(os.path.dirname(__file__)), "poidata.db3"))
            self.connection = conn.cursor()
        except:
            self.connection = None

    def execute(self):
        if self.connection is not None:
            # 2014 fix, 2015 mobile
            catids = ('2014', '2015')

            self.connection.execute(
                'SELECT a.catId, a.mortonCode from pPoiCategoryTable c inner join pPoiAddressTable a on c.catId = a.catId and c.catId between ? and ?',
                catids)
            self.poi_raw_data = self.connection.fetchall()
        else:
            self.print_log_line('Could not open database poidata.db3')
            self.poi_raw_data = None

    def convert_cam_morton_codes(self):
        if self.poi_raw_data != None:
            for cam_tuple in self.poi_raw_data:
                longitude, latitude = self.calculator.tile2longlat(
                    self.DecodeMorton2X(cam_tuple[1]), self.DecodeMorton2Y(cam_tuple[1]), 17)
                if cam_tuple[0] == 2014:
                    self.pois_converted_fix.append((longitude, latitude))
                elif cam_tuple[0] == 2015:
                    self.pois_converted_mobile.append((longitude, latitude))
                else:
                    pass
            self.print_log_line(" Number of fix cams: %d" % len(self.pois_converted_fix))
            self.print_log_line(" Number of mobile cams: %d" % len(self.pois_converted_mobile))
            self.print_log_line("#######################################################################")

    # Inverse of Part1By1 - "delete" all odd-indexed bits
    def Compact1By1(self, x):
        x &= 0x55555555  # x = -f-e -d-c -b-a -9-8 -7-6 -5-4 -3-2 -1-0
        x = (x ^ (x >> 1)) & 0x33333333  # x = --fe --dc --ba --98 --76 --54 --32 --10
        x = (x ^ (x >> 2)) & 0x0f0f0f0f  # x = ---- fedc ---- ba98 ---- 7654 ---- 3210
        x = (x ^ (x >> 4)) & 0x00ff00ff  # x = ---- ---- fedc ba98 ---- ---- 7654 3210
        x = (x ^ (x >> 8)) & 0x0000ffff  # x = ---- ---- ---- ---- fedc ba98 7654 3210
        return x

    # Inverse of Part1By2 - "delete" all bits not at positions divisible by 3
    def Compact1By2(self, x):
        x &= 0x09249249  # x = ---- 9--8 --7- -6-- 5--4 --3- -2-- 1--0
        x = (x ^ (x >> 2)) & 0x030c30c3  # x = ---- --98 ---- 76-- --54 ---- 32-- --10
        x = (x ^ (x >> 4)) & 0x0300f00f  # x = ---- --98 ---- ---- 7654 ---- ---- 3210
        x = (x ^ (x >> 8)) & 0xff0000ff  # x = ---- --98 ---- ---- ---- ---- 7654 3210
        x = (x ^ (x >> 16)) & 0x000003ff  # x = ---- ---- ---- ---- ---- --98 7654 3210
        return x

    def DecodeMorton2X(self, code):
        return self.Compact1By1(code >> 0)

    def DecodeMorton2Y(self, code):
        return self.Compact1By1(code >> 1)

    def print_converted_codes(self):
        self.print_log_line(' Fix cameras:')
        self.print_log_line(self.pois_converted_fix)
        self.print_log_line(' Mobile cameras:')
        self.print_log_line(self.pois_converted_mobile)

    def update_pois(self):
        del self.result_pois_fix[:]
        del self.result_pois_mobile[:]

        if isinstance(self.POI_RECT, Rect):
            self.POI_RECT.delete_rect()

        # get the current driving direction
        direction = self.gps_producer.get_direction()
        longitude, latitude = self.gps_producer.get_lon_lat()

        # check if we have a valid driving direction, otherwise use the last valid one
        if direction == '-' or direction is None:
            if self.last_valid_driving_direction is not None and self.last_valid_longitude is not None:
                direction = self.last_valid_driving_direction
                longitude = self.last_valid_longitude
                latitude = self.last_valid_latitude
            else:
                self.print_log_line(' Waiting for valid direction once')
                return
        else:
            self.last_valid_driving_direction = direction
            self.last_valid_longitude = longitude
            self.last_valid_latitude = latitude

        self.print_log_line(' Updating Speed Cam Warner Thread')
        # convert CCP longitude,latitude to (x,y).
        xtile, ytile = self.calculator.longlat2tile(latitude, longitude, self.zoom)

        LON_MIN, LAT_MIN, LON_MAX, LAT_MAX = self.calculator.createGeoJsonTilePolygon(direction,
                                                                                      self.zoom,
                                                                                      xtile,
                                                                                      ytile,
                                                                                      self.calculator.rectangle_periphery_poi_reader)

        # convert each of the 2 points to (x,y).
        pt1_xtile, pt1_ytile = self.calculator.longlat2tile(LAT_MIN, LON_MIN, self.zoom)
        pt2_xtile, pt2_ytile = self.calculator.longlat2tile(LAT_MAX, LON_MAX, self.zoom)
        # calculate a rectangle from these 2 points
        self.POI_RECT = self.calculator.calculate_rectangle_border([pt1_xtile, pt1_ytile],
                                                                   [pt2_xtile, pt2_ytile])
        self.POI_RECT.set_rectangle_ident(direction)
        self.POI_RECT.set_rectangle_string('POIRECT')

        # calculate the radius of the rectangle in km
        rectangle_radius = self.calculator.calculate_rectangle_radius(self.POI_RECT.rect_height(),
                                                                      self.POI_RECT.rect_width())
        self.print_log_line(' rectangle POI radius %f' % rectangle_radius)
        self.calculator.update_cam_radius(rectangle_radius)

        for camera in self.pois_converted_fix:
            longitude = float(camera[0])
            latitude = float(camera[1])

            xtile_cam, ytile_cam = self.calculator.longlat2tile(latitude, longitude, self.zoom)
            if self.POI_RECT.point_in_rect(xtile_cam, ytile_cam):
                self.print_log_line(' Found a fix speed cam')
                self.result_pois_fix.append(camera)

        for camera in self.pois_converted_mobile:
            longitude = float(camera[0])
            latitude = float(camera[1])

            xtile_cam, ytile_cam = self.calculator.longlat2tile(latitude, longitude, self.zoom)
            if self.POI_RECT.point_in_rect(xtile_cam, ytile_cam):
                self.print_log_line(' Found a mobile speed cam')
                self.result_pois_mobile.append(camera)

        self.print_log_line(" fix cameras: %d, mobile cameras %d"
              % (len(self.result_pois_fix), len(self.result_pois_mobile)))
        self.calculator.update_kivi_info_page(len(self.result_pois_fix),
                                              len(self.result_pois_mobile))

        # update the SpeedWarner Thread
        for camera_fix in self.result_pois_fix:
            longitude = camera_fix[0]
            latitude = camera_fix[1]
            self.speed_cam_queue.produce(self.cv_speedcam, {'ccp': ('IGNORE',
                                                                    'IGNORE'),
                                                            'fix_cam': (True,
                                                                        float(longitude),
                                                                        float(latitude),
                                                                        True),
                                                            'traffic_cam': (False,
                                                                            float(longitude),
                                                                            float(latitude),
                                                                            True),
                                                            'distance_cam': (False,
                                                                             float(longitude),
                                                                             float(latitude),
                                                                             True),
                                                            'mobile_cam': (False,
                                                                           float(longitude),
                                                                           float(latitude),
                                                                           True),
                                                            'ccp_node': ('IGNORE',
                                                                         'IGNORE'),
                                                            'list_tree': (None,
                                                                          None)})

        for camera_mobile in self.result_pois_mobile:
            longitude = camera_mobile[0]
            latitude = camera_mobile[1]
            self.speed_cam_queue.produce(self.cv_speedcam, {'ccp': ('IGNORE',
                                                                    'IGNORE'),
                                                            'fix_cam': (False,
                                                                        float(longitude),
                                                                        float(latitude),
                                                                        True),
                                                            'traffic_cam': (False,
                                                                            float(longitude),
                                                                            float(latitude),
                                                                            True),
                                                            'distance_cam': (False,
                                                                             float(longitude),
                                                                             float(latitude),
                                                                             True),
                                                            'mobile_cam': (True,
                                                                           float(longitude),
                                                                           float(latitude),
                                                                           True),
                                                            'ccp_node': ('IGNORE',
                                                                         'IGNORE'),
                                                            'list_tree': (None,
                                                                          None)})
        return
