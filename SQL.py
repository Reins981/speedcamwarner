# -*-coding:utf8;-*-
# qpy:2
# ts=4:sw=4:expandtab
'''
Created on 01.07.2014

@author: rkoraschnigg
'''

import sqlite3
import os
import json
from threading import Timer
from CalculatorThreads import Rect
from Logger import Logger
from ThreadBase import CyclicThread
from ServiceAccount import download_file_from_google_drive, FILE_ID, \
    FILENAME, build_drive_from_credentials


class UserCamera(object):
    def __init__(self, c_id, name, lon, lat):
        self.__id = c_id
        self.__name = name
        self.__lon = lon
        self.__lat = lat

    @property
    def name(self):
        return self.__name

    @property
    def c_id(self):
        return self.__id

    @property
    def lon(self):
        return self.__lon

    @property
    def lat(self):
        return self.__lat


class POIReader(Logger):
    def __init__(self,
                 cv_speedcam,
                 speedcamqueue,
                 gps_producer,
                 calculator,
                 osm_wrapper,
                 map_queue,
                 cv_map,
                 cv_map_cloud,
                 cv_map_db,
                 log_viewer):
        Logger.__init__(self, self.__class__.__name__, log_viewer)
        self.cv_speedcam = cv_speedcam
        self.speed_cam_queue = speedcamqueue
        self.gps_producer = gps_producer
        self.calculator = calculator
        self.osm_wrapper = osm_wrapper
        self.map_queue = map_queue
        self.cv_map = cv_map
        self.cv_map_cloud = cv_map_cloud
        self.cv_map_db = cv_map_db
        self.log_viewer = log_viewer

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
        self.speed_cam_dict = dict()
        self.speed_cam_list = list()
        self.speed_cam_dict_db = dict()
        self.speed_cam_list_db = list()
        # timer instances
        self.timer_1 = None
        self.timer_2 = None
        # OSM layer
        self.zoom = 17
        # OSM Rect
        self.POI_RECT = None
        # initial download status
        self.__initial_download_finished = False

        # set config items
        self.set_configs()

        self.process()

    @property
    def initial_download_finished(self):
        return self.__initial_download_finished

    def set_configs(self):
        # Cloud cyclic update time in seconds (Runs every x seconds).
        # The first time after x seconds
        self.u_time_from_cloud = 60
        # Initial update time from cloud (one time operation)
        self.init_time_from_cloud = 10
        # POIs from database update time in seconds (Runs after x seconds one time)
        self.u_time_from_db = 30

    # called from main GUI thread
    def stop_timer(self):
        self.timer_1.cancel()
        self.timer_2.stop()
        self.timer_2.join()

    def process(self):
        self.open_connection()
        self.execute()
        self.convert_cam_morton_codes()

        self.timer_1 = Timer(self.u_time_from_db, self.update_pois_from_db)
        self.timer_1.start()

        self.timer_2 = CyclicThread(self.init_time_from_cloud,
                                    self.update_pois_from_cloud,
                                    self.log_viewer)
        self.timer_2.daemon = True
        self.timer_2.start()
        self.timer_2.set_time(self.u_time_from_cloud)

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
                'SELECT a.catId, a.mortonCode from pPoiCategoryTable c '
                'inner join pPoiAddressTable a on c.catId = a.catId and c.catId between ? and ?',
                catids)
            self.poi_raw_data = self.connection.fetchall()
        else:
            self.print_log_line('Could not open database poidata.db3', log_level="WARNING")
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
            self.print_log_line(
                "#######################################################################")

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

    def propagate_camera(self, name, longitude, latitude, camera_type):
        self.speed_cam_queue.produce(self.cv_speedcam, {'ccp': ('IGNORE',
                                                                'IGNORE'),
                                                        'fix_cam': (
                                                            True if camera_type == 'fix_cam' else False,
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
                                                        'mobile_cam': (
                                                            True if camera_type == 'mobile_cam' else False,
                                                            float(longitude),
                                                            float(latitude),
                                                            True),
                                                        'ccp_node': ('IGNORE',
                                                                     'IGNORE'),
                                                        'list_tree': (None,
                                                                      None),
                                                        'name': name if name else ""})

    def prepare_camera_for_osm_wrapper(self, camera_key, lon, lat,
                                       name=None, camera_source='cloud'):
        if camera_source == 'cloud':
            self.speed_cam_dict[camera_key] = [lat,
                                               lon,
                                               lat,
                                               lon,
                                               True,
                                               None,
                                               None,
                                               name if name else "---"]
        elif camera_source == 'db':
            self.speed_cam_dict_db[camera_key] = [lat,
                                                  lon,
                                                  lat,
                                                  lon,
                                                  True,
                                                  None,
                                                  None,
                                                  name if name else "---"]

    def cleanup_speed_cams(self):
        # do a cleanup if the speed cam structure increases this limit
        cameras = [self.speed_cam_list, self.speed_cam_list_db]
        for camera_list in cameras:
            if len(camera_list) >= 100:
                self.print_log_line(" Limit of speed camera list (100) reached! "
                                    "Deleting all speed cameras from source list",
                                    log_level="WARNING")
                del camera_list[:]

    def update_map_queue(self):
        self.map_queue.produce(self.cv_map, "UPDATE")

    def update_speed_cams_cloud(self, speed_cams):
        self.map_queue.produce_cloud(self.cv_map, speed_cams)

    def update_speed_cams_db(self, speed_cams):
        self.map_queue.produce_db(self.cv_map, speed_cams)

    def update_osm_wrapper(self, camera_source='cloud'):
        processing_dict = self.speed_cam_dict if camera_source == 'cloud' \
            else self.speed_cam_dict_db
        processing_list = self.speed_cam_list if camera_source == 'cloud' \
            else self.speed_cam_list_db
        if len(processing_dict) > 0:
            processing_list.append(processing_dict)
        self.update_speed_cams_cloud(processing_list) \
            if camera_source == 'cloud' \
            else self.update_speed_cams_db(processing_list)
        self.update_map_queue()
        self.cleanup_speed_cams()

    def process_pois_from_cloud(self):
        self.print_log_line(f"Processing POI's from cloud..")
        try:
            with open(FILENAME, 'r') as fp:
                user_pois = json.load(fp)
        except FileNotFoundError:
            self.print_log_line(f"Processing POI's from cloud failed: {FILENAME} not found!",
                                log_level="ERROR")
            return

        if 'cameras' not in user_pois:
            self.print_log_line(f"Processing POI's from cloud failed: "
                                f"No POI's to process in {FILENAME}", log_level="WARNING")
            return

        num_cameras = len(user_pois['cameras'])
        self.print_log_line(f"Found {num_cameras} cameras from cloud!")
        self.calculator.update_kivi_info_page(poi_cams_mobile=num_cameras)
        self.__initial_download_finished = True

        cam_id = 200000
        for camera in user_pois['cameras']:
            try:
                name = camera['name']
                lat = camera['coordinates'][0]['latitude']
                lon = camera['coordinates'][0]['longitude']
            except KeyError:
                self.print_log_line(f"Ignore adding camera {camera} from cloud "
                                    f"because of missing attributes", log_level="WARNING")
                continue

            user_cam = UserCamera(cam_id, name, lon, lat)

            self.print_log_line(f"Adding and propagating camera from cloud"
                                f"({user_cam.name, user_cam.lat, user_cam.lon})")
            self.prepare_camera_for_osm_wrapper('MOBILE' + str(cam_id),
                                                user_cam.lon, user_cam.lat, name)
            self.update_osm_wrapper()
            self.propagate_camera(user_cam.name, user_cam.lon, user_cam.lat, 'mobile_cam')
            cam_id += 1

    def update_pois_from_cloud(self, *args, **kwargs):
        self.print_log_line(f"Updating POI's from cloud ..")

        status = download_file_from_google_drive(FILE_ID, build_drive_from_credentials())
        if status != 'success':
            self.print_log_line(f"Updating cameras (file_id: {FILE_ID}) "
                                f"from service account failed! "
                                f"({status})", log_level="ERROR")
        else:
            self.print_log_line(f"Updating cameras (file_id: {FILE_ID}) "
                                f"from service account success!")
            self.process_pois_from_cloud()

    def update_pois_from_db(self):
        self.print_log_line(f"Updating POI's from database ..")

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
        for index, camera_fix in enumerate(self.result_pois_fix):
            longitude = camera_fix[0]
            latitude = camera_fix[1]
            self.print_log_line(f"Adding and propagating fix camera from db"
                                f"({longitude, latitude})")
            self.propagate_camera(None, longitude, latitude, 'fix_cam')

            self.prepare_camera_for_osm_wrapper('FIX_DB' + str(index),
                                                longitude, latitude, camera_source='db')

        for index, camera_mobile in enumerate(self.result_pois_mobile):
            longitude = camera_mobile[0]
            latitude = camera_mobile[1]
            self.print_log_line(f"Adding and propagating mobile camera from db"
                                f"({longitude, latitude})")
            self.propagate_camera(None, longitude, latitude, 'mobile_cam')

            self.prepare_camera_for_osm_wrapper('MOBILE_DB' + str(index),
                                                longitude, latitude, camera_source='db')
        # Finally inform the osm wrapper about cameras originating from the database
        self.update_osm_wrapper(camera_source='db')
