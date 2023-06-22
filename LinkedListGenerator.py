# -*-coding:utf8;-*-
# qpy:2
# ts=4:sw=4:expandtab
'''
Created on 01.07.2014

@author: rkoraschnigg
'''

from Logger import Logger
from math import sin, cos, sqrt, atan2, radians


class Node(object):

    def __init__(self, node_id=0, latitude_start=0, longitude_start=0,
                 latitude_end=0, longitude_end=0, tags=None, prev=None, next=None):
        self.id = node_id
        self.latitude_start = latitude_start
        self.longitude_start = longitude_start
        self.latitude_end = latitude_end
        self.longitude_end = longitude_end
        if tags is None:
            tags = {}
        self.tags = tags
        self.prev = prev
        self.next = next


class DoubleLinkedListNodes(Logger):

    def __init__(self):
        self.head = None
        self.tail = None
        self.node = None
        self.tree_generator_instance = None
        Logger.__init__(self, self.__class__.__name__)

    def _is_road_name_available(self, node_id):
        if self.tree_generator_instance is not None:
            way = self.tree_generator_instance[node_id]
            if self.tree_generator_instance.hasRoadNameAttribute(
                    way) or self.tree_generator_instance.hasRefAttribute(way):
                return True
        return False

    def set_tree_generator_instance(self, instance):
        self.tree_generator_instance = instance

    def deleteLinkedList(self):
        del self

    def append_node(self, node_id, latitude_start, longitude_start, latitude_end, longitude_end,
                    tags):

        new_node = Node(node_id, latitude_start, longitude_start, latitude_end, longitude_end,
                        tags, None, None)
        if self.head is None:
            self.head = self.tail = new_node
        else:
            new_node.prev = self.tail
            new_node.next = None
            self.tail.next = new_node
            self.tail = new_node

    # returns the id of the matched node or False in case no matched node was returned
    def match_node(self, ccp):
        latitude, longitude = ccp[0], ccp[1]

        node_list = []
        current_node = self.head

        while current_node is not None:
            # consider only nodes for which the way is attached to a roadname
            if self._is_road_name_available(current_node.id):
                node_list.append(current_node)
            current_node = current_node.next

        self.node = self.smallest_distance_node(latitude, longitude, node_list)

        if not self.node:
            self.print_log_line(' No node matched')
            return False

        return self.node.id

    def smallest_distance_node(self, latitude, longitude, node_list):
        # list of calculated beeline distances between the CCP and each node
        distance_list = []

        if len(node_list) == 0:
            self.print_log_line(' Can not calculate smallest distance node: '
                                'Length of Node list is 0')
            return False

        for node in node_list:
            distance_to_start_of_node = self.check_distance_between_two_points(
                (longitude, latitude),
                (node.longitude_start, node.latitude_start)
            )
            distance_to_end_of_node = self.check_distance_between_two_points((longitude, latitude),
                                                                             (node.longitude_end,
                                                                              node.latitude_end)
                                                                             )
            if distance_to_start_of_node != -1:
                entry_1 = (distance_to_start_of_node, node, 'StartNode')
                distance_list.append(entry_1)
            if distance_to_end_of_node != -1:
                entry_2 = (distance_to_end_of_node, node, 'EndNode')
                distance_list.append(entry_2)

        node_attr = min(distance_list, key=lambda n: n[0])

        node_candidate = node_attr[1]
        self.print_log_line(' Most likely node id is %s' % str(node_candidate.id))

        return node_candidate

    # distance between 2 points (lon (x),lat (y)) in meters.
    @staticmethod
    def check_distance_between_two_points(pt1, pt2):
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

    def setNode(self, node):
        self.node = node

    # make sure match_node is invoked first to determine current_node.
    # this is the next_node of current_node
    def hasNextNode(self):
        if self.node.next is None:
            return False
        else:
            return True

    def getNextNode(self):
        return self.node.next

    def getNode(self):
        return self.node

    # return a tuple as numbers of fixed and traffic cams found
    def getAttributesOfSpeedCameras(self, gui_obj):
        fixedcam_size = 0
        trafficcam_size = 0
        mobile_cam_size = 0
        speed_cam_dict = {}
        current_node = self.head

        while current_node is not None:
            # keep GUI alive
            gui_obj.update_gui()
            if self.hasHighwayAttribute(current_node):
                if self.hasSpeedCam(current_node):
                    enforcement = True
                    fixedcam_size += 1
                    fix = "FIX_" + str(fixedcam_size)
                    speed_cam_dict[fix] = [current_node.latitude_start,
                                           current_node.longitude_start,
                                           current_node.latitude_end,
                                           current_node.longitude_end,
                                           enforcement]
            if self.hasEnforcementAttribute2(current_node) and \
                    self.hasTrafficCamEnforcement(current_node):
                enforcement = True
                trafficcam_size += 1
                traffic = "TRAFFIC_" + str(trafficcam_size)
                speed_cam_dict[traffic] = [current_node.latitude_start,
                                           current_node.longitude_start,
                                           current_node.latitude_end,
                                           current_node.longitude_end,
                                           enforcement]
            elif self.hasCrossingAttribute(
                    current_node) and self.hasTrafficCamCrossing(current_node):
                enforcement = False
                trafficcam_size += 1
                traffic = "TRAFFIC_" + str(trafficcam_size)
                speed_cam_dict[traffic] = [current_node.latitude_start,
                                           current_node.longitude_start,
                                           current_node.latitude_end,
                                           current_node.longitude_end,
                                           enforcement]
            elif (self.hasSpeedCamAttribute(
                    current_node) and self.hasTrafficCam(current_node)):
                enforcement = True
                trafficcam_size += 1
                traffic = "TRAFFIC_" + str(trafficcam_size)
                speed_cam_dict[traffic] = [current_node.latitude_start,
                                           current_node.longitude_start,
                                           current_node.latitude_end,
                                           current_node.longitude_end,
                                           enforcement]
            elif self.hasDeviceAttribute(current_node):
                if self.hasTrafficCamDevice(current_node):
                    enforcement = True
                    trafficcam_size += 1
                    traffic = "TRAFFIC_" + str(trafficcam_size)
                    speed_cam_dict[traffic] = [current_node.latitude_start,
                                               current_node.longitude_start,
                                               current_node.latitude_end,
                                               current_node.longitude_end,
                                               enforcement]
            elif self.hasRoleAttribute(
                    current_node) and self.hasSection(current_node) or \
                    (self.hasEnforcementAttribute2(current_node) and
                     self.hasEnforcementAverageSpeed(current_node)):
                enforcement = True
                mobile_cam_size += 1
                mobile = "MOBILE_" + str(mobile_cam_size)
                speed_cam_dict[mobile] = [current_node.latitude_start,
                                          current_node.longitude_start,
                                          current_node.latitude_end,
                                          current_node.longitude_end,
                                          enforcement]
            else:
                pass

            current_node = current_node.next
        return fixedcam_size, trafficcam_size, mobile_cam_size, speed_cam_dict

    @staticmethod
    def hasRoadNameAttribute(node):
        if node is None:
            return False
        else:
            if 'name' in node.tags.keys():
                return True
            else:
                return False

    @staticmethod
    def hasExtendedRoadNameAttribute(node):
        if node is None:
            return False
        else:
            if 'addr:street' in node.tags.keys():
                return True
            else:
                return False

    @staticmethod
    def hasHouseNumberAttribute(node):
        if node is None:
            return False
        else:
            if 'addr:housenumber' in node.tags.keys():
                return True
            else:
                return False

    @staticmethod
    def getRoadNameAttribute(node):
        return node.tags['name']

    @staticmethod
    def getExtendedRoadNameAttribute(node):
        return node.tags['addr:street']

    @staticmethod
    def getHouseNumberAttribute(node):
        return node.tags['addr:housenumber']

    @staticmethod
    def hasHighwayAttribute(node):
        if node is None:
            return False
        else:
            if 'highway' in node.tags.keys():
                return True
            else:
                return False

    @staticmethod
    def hasSpeedCamAttribute(node):
        if node is None:
            return False
        else:
            if 'speed_camera' in node.tags.keys():
                return True
            else:
                return False

    @staticmethod
    def hasCrossingAttribute(node):
        if node is None:
            return False
        else:
            if 'crossing' in node.tags.keys():
                return True
            else:
                return False

    @staticmethod
    def hasEnforcementAttribute(node):
        if node is None:
            return False
        else:
            if 'enforcement_camera' in node.tags.keys():
                return True
            else:
                return False

    @staticmethod
    def hasEnforcementAttribute2(node):
        if node is None:
            return False
        else:
            if 'enforcement' in node.tags.keys():
                return True
            else:
                return False

    @staticmethod
    def hasDeviceAttribute(node):
        if node is None:
            return False
        else:
            if 'device' in node.tags.keys():
                return True
            else:
                return False

    @staticmethod
    def hasRoleAttribute(node):
        if node is None:
            return False
        else:
            if 'role' in node.tags.keys():
                return True
            else:
                return False

    @staticmethod
    def hasExtendedSpeedCam(node):
        if node is None:
            return False
        else:
            return node.tags['role'] == 'device'

    @staticmethod
    def hasSection(node):
        if node is None:
            return False
        else:
            return node.tags['role'] == 'section'

    @staticmethod
    def hasSpeedCam(node):
        if node is None:
            return False
        else:
            return node.tags['highway'] == 'speed_camera'

    @staticmethod
    def hasTrafficCam(node):
        if node is None:
            return False
        else:
            return node.tags['speed_camera'] == 'traffic_signals'

    @staticmethod
    def hasTrafficCamCrossing(node):
        if node is None:
            return False
        else:
            return node.tags['crossing'] == 'traffic_signals'

    @staticmethod
    def hasTrafficCamEnforcement(node):
        if node is None:
            return False
        else:
            return node.tags['enforcement'] == 'traffic_signals'

    @staticmethod
    def hasEnforcementAverageSpeed(node):
        if node is None:
            return False
        else:
            return node.tags['enforcement'] == 'average_speed'

    @staticmethod
    def hasTrafficCamDevice(node):
        if node is None:
            return False
        else:
            return node.tags['device'] == 'red_signal_camera'

    @staticmethod
    def getSpeedCamStartCoordinates(node):
        if node is None:
            return 0.0, 0.0
        else:
            return node.latitude_end, node.longitude_end

    @staticmethod
    def getSpeedCamEndCoordinates(node):
        if node is None:
            return 0.0, 0.0
        else:
            return node.latitude_start, node.longitude_start

    def remove(self, node_id):
        current_node = self.head

        while current_node is not None:
            if current_node.id == node_id:
                # if it's not the first element
                if current_node.prev is not None:
                    current_node.prev.next = current_node.next
                    current_node.next.prev = current_node.prev
                else:
                    # otherwise we have no prev (it's None),
                    # head is the next one, and prev becomes None
                    self.head = current_node.next
                    current_node.next.prev = None

            current_node = current_node.next
