# -*-coding:utf8;-*-
# qpy:2
# ts=4:sw=4:expandtab
'''
Created on 01.07.2014

@author: rkoraschnigg
'''

import sys
from Logger import Logger
logger = Logger("BinarySearchTree")


class BinarySearchTree(object):

    def __init__(self):
        self.root = None
        self.way = None
        self.size = 0
        sys.setrecursionlimit(10000)

    def deleteTree(self):
        del self

    def length(self):
        return self.size

    def __len__(self):
        return self.size

    def __iter__(self):
        return self.root.__iter__()

    def __getitem__(self, node_id):
        return self.get(node_id)

    def __contains__(self, node_id):
        if self._get(node_id, self.root):
            return True
        else:
            return False

    def __delitem__(self, node_id):
        self.delete(node_id)

    def insert(self, node_id, way_id, tags):
        if self.root:
            self._insert(node_id, way_id, tags, self.root)
        else:
            self.root = TreeNode(node_id, way_id, tags)
        self.size += 1

    def _insert(self, node_id, way_id, tags, current_node):
        if node_id < current_node.key:
            if current_node.hasLeftChild():
                self._insert(node_id, way_id, tags, current_node.leftChild)
            else:
                current_node.leftChild = TreeNode(node_id, way_id, tags, parent=current_node)
        elif node_id > current_node.key:
            if current_node.hasRightChild():
                self._insert(node_id, way_id, tags, current_node.rightChild)
            else:
                current_node.rightChild = TreeNode(node_id, way_id, tags, parent=current_node)
        # in case the node_id is already present, add additional tags for the new node_id
        # to the present node_id
        else:
            current_node.combined_tags.append(tags)
            current_node.additional_way_id.append(way_id)

    # execute get() or __contains()__ before hasCombinedTags(), hasHighwayAttribute(),
    # hasMaxSpeedAttribute, hasRoadNameAttribute(),
    # getMaxSpeedValue(), getRoadNameValue() and getHighwayValue()
    def get(self, node_id):
        if self.root:
            res = self._get(node_id, self.root)
            if res:
                self.way = res
                return res
            else:
                return None
        else:
            return None

    def _get(self, node_id, currentNode):
        if not currentNode:
            return None
        elif currentNode.key == node_id:
            self.way = currentNode
            return currentNode
        elif node_id < currentNode.key:
            return self._get(node_id, currentNode.leftChild)
        else:
            return self._get(node_id, currentNode.rightChild)

    def _getNextNode(self, node_id, currentNode):
        if not currentNode:
            return None
        elif currentNode.key == node_id:
            self.way = currentNode.hasRightChild()
            return currentNode.hasRightChild()
        elif node_id < currentNode.key:
            return self._get(node_id, currentNode.leftChild)
        else:
            return self._get(node_id, currentNode.rightChild)

    def getNextNode(self, node_id):
        if self.root:
            res = self._getNextNode(node_id, self.root)
            if res:
                self.way = res
                return res
            else:
                return None
        else:
            return None

    # way is the currentNode object.
    @staticmethod
    def hasCombinedTags(way):
        if len(way.combined_tags) == 0:
            return False
        else:
            logger.print_log_line(" Combined tags found")
            return True

    # way is the currentNode object.
    @staticmethod
    def hasHighwayAttribute(way):
        if way is None:
            return False
        else:
            if 'highway' in way.tags.keys():
                logger.print_log_line(" Highway attribute found")
                return True
            else:
                return False

    # way is the currentNode object.
    @staticmethod
    def hasHazardAttribute(way):
        if way is None:
            return False
        else:
            if 'hazard' in way.tags.keys():
                logger.print_log_line(" Hazard found")
                return True
            else:
                return False

    @staticmethod
    def hasWaterwayAttribute(way):
        if way is None:
            return False
        else:
            if 'waterway' in way.tags.keys():
                logger.print_log_line(" Waterway found")
                return True
            else:
                return False

    @staticmethod
    def hasAccessConditionalAttribute(way):
        if way is None:
            return False
        else:
            if 'access:conditional' in way.tags.keys():
                logger.print_log_line(" Access Conditional found")
                return True
            else:
                return False

    @staticmethod
    def hasBoundaryAttribute(way):
        if way is None:
            return False
        else:
            if 'boundary' in way.tags.keys():
                logger.print_log_line(" Boundary found")
                return True
            else:
                return False

    # way is the currentNode object.
    @staticmethod
    def hasRoleAttribute(way):
        if way is None:
            return False
        else:
            if 'role' in way.tags.keys():
                Logger.print_log_line(" Role attribute found")
                return True
            else:
                return False

    # way is the currentNode object.
    @staticmethod
    def hasSpeedcamAttribute(way):
        logger.print_log_line(" Speedcam attribute found")
        return way.tags['role'] == 'device'

    # way is the currentNode object.
    @staticmethod
    def hasSpeedCam(way):
        logger.print_log_line(" Speedcam found")
        return way.tags['highway'] == 'speed_camera'

    # way is the currentNode object.
    @staticmethod
    def hasSection(way):
        logger.print_log_line(" Section attribute found")
        return way.tags['role'] == 'section'

    # way is the currentNode object.
    @staticmethod
    def hasMaxspeedAttribute(way):
        if way is None:
            return False
        else:
            if 'maxspeed' in way.tags.keys():
                logger.print_log_line(" Maxspeed attribute found")
                return True
            else:
                return False

    # way is the currentNode object.
    @staticmethod
    def hasBoundaryAttribute(way):
        if way is None:
            return False
        else:
            if 'boundary' in way.tags.keys():
                # logger.print_log_line(" Maxspeed attribute found")
                return True
            else:
                return False

    # inside city
    @staticmethod
    def is_urban(way):
        logger.print_log_line(" Administrative area found")
        return way.tags['boundary'] == 'administrative'

    # way is the currentNode object.
    @staticmethod
    def hasMaxspeedConditionalAttribute(way):
        if way is None:
            return False
        else:
            if 'maxspeed:conditional' in way.tags.keys():
                logger.print_log_line(" Maxspeed conditional attribute found")
                return True
            else:
                return False

    # way is the currentNode object.
    @staticmethod
    def hasMaxspeedLaneAttribute(way):
        if way is None:
            return False
        else:
            if 'maxspeed:lanes' in way.tags.keys():
                logger.print_log_line(" Maxspeed lanes attribute found")
                return True
            else:
                return False

    # way is the currentNode object.
    @staticmethod
    def hasRoadNameAttribute(way):
        if way is None:
            return False
        else:
            if 'name' in way.tags.keys():
                # logger.print_log_line(" Road name attribute found")
                return True
            else:
                return False

    # way is the currentNode object.
    @staticmethod
    def hasTunnelAttribute(way):
        if way is None:
            return False
        else:
            if 'tunnel' in way.tags.keys():
                logger.print_log_line(" Tunnel attribute found")
                return True
            else:
                return False

    # way is the currentNode object.
    @staticmethod
    def hasRefAttribute(way):
        if way is None:
            return False
        else:
            if 'ref' in way.tags.keys():
                # logger.print_log_line(" Ref attribute found")
                return True
            else:
                return False

    # way is the currentNode object.
    @staticmethod
    def hasExtendedRoadNameAttribute(way):
        if way is None:
            return False
        else:
            if 'addr:street' in way.tags.keys():
                logger.print_log_line(" Extended road name  attribute found")
                return True
            else:
                return False

    # facility attribute
    @staticmethod
    def hasAmenityAttribute(way):
        if way is None:
            return False
        else:
            if 'amenity' in way.tags.keys():
                logger.print_log_line(" Facility attribute found")
                return True
            else:
                return False

    # is it a fuel station
    @staticmethod
    def is_fuel_station(way):
        return way.tags['amenity'] == 'fuel'

    # way is the currentNode object
    @staticmethod
    def getMaxspeedValue(way):
        logger.print_log_line(' Maxspeed value is %s' % str(way.tags['maxspeed']))
        return way.tags['maxspeed']

    # way is the currentNode object.
    @staticmethod
    def getMaxspeedConditionalValue(way):
        logger.print_log_line(' %s' % str(way.tags['maxspeed:conditional']))
        return way.tags['maxspeed:conditional']

    # way is the currentNode object.
    @staticmethod
    def getMaxspeedLaneValue(way):
        logger.print_log_line(' %s' % str(way.tags['maxspeed:lanes']))
        return way.tags['maxspeed:lanes']

    # way is the currentNode object.
    @staticmethod
    def getCombinedTags(way):
        return way.combined_tags

    # way is the currentNode object.
    @staticmethod
    def getRoadNameValue(way):
        return way.tags['name']

    # way is the currentNode object.
    @staticmethod
    def getExtendedRoadNameValue(way):
        return way.tags['addr:street']

    # way is the currentNode object.
    @staticmethod
    def getRefValue(way):
        return way.tags['ref']

    # way is the currentNode object.
    @staticmethod
    def getHighwayValue(way):
        return way.tags['highway']

    # way is the currentNode object.
    @staticmethod
    def getHazardValue(way):
        return way.tags['hazard']

    @staticmethod
    def getWaterwayValue(way):
        return way.tags['waterway']

    @staticmethod
    def getBoundaryValue(way):
        return way.tags['boundary']

    @staticmethod
    def getAccessConditionalValue(way):
        return way.tags['access:conditional']

    # remove the node_id
    def delete(self, node_id):
        if self.size > 1:
            nodeToRemove = self._get(node_id, self.root)
            if nodeToRemove:
                self.remove(nodeToRemove)
                self.size = self.size - 1
            else:
                raise KeyError(' Error, key not in tree')
        elif self.size == 1 and self.root.key == node_id:
            self.root = None
            self.size = self.size - 1
        else:
            raise KeyError(' Error, key not in tree')

    def findMin(self):
        current = self
        while current.hasLeftChild():
            current = current.leftChild
        return current

    def remove(self, currentNode):
        if currentNode.isLeaf():  # leaf
            if currentNode == currentNode.parent.leftChild:
                currentNode.parent.leftChild = None
            else:
                currentNode.parent.rightChild = None
        elif currentNode.hasBothChildren():  # interior
            succ = currentNode.findSuccessor()
            succ.spliceOut()
            currentNode.key = succ.key
            currentNode.payload = succ.payload

        else:  # this node has one child
            if currentNode.hasLeftChild():
                if currentNode.isLeftChild():
                    currentNode.leftChild.parent = currentNode.parent
                    currentNode.parent.leftChild = currentNode.leftChild
                elif currentNode.isRightChild():
                    currentNode.leftChild.parent = currentNode.parent
                    currentNode.parent.rightChild = currentNode.leftChild
                else:
                    currentNode.replaceNodeData(currentNode.leftChild.key,
                                                currentNode.leftChild.payload,
                                                currentNode.leftChild.leftChild,
                                                currentNode.leftChild.rightChild)
            else:
                if currentNode.isLeftChild():
                    currentNode.rightChild.parent = currentNode.parent
                    currentNode.parent.leftChild = currentNode.rightChild
                elif currentNode.isRightChild():
                    currentNode.rightChild.parent = currentNode.parent
                    currentNode.parent.rightChild = currentNode.rightChild
                else:
                    currentNode.replaceNodeData(currentNode.rightChild.key,
                                                currentNode.rightChild.payload,
                                                currentNode.rightChild.leftChild,
                                                currentNode.rightChild.rightChild)


# our node object in form of a way since a way consists of nodes.
class TreeNode(object):

    def __init__(self, node_id=None, way_id=None, tags=None, left=None, right=None, parent=None):
        self.key = node_id
        self.way_id = way_id
        self.additional_way_id = []
        if tags is None:
            tags = {}
        self.tags = tags
        self.combined_tags = []
        self.leftChild = left
        self.rightChild = right
        self.parent = parent

    def hasLeftChild(self):
        if self.leftChild is not None:
            return True
        return False

    def hasRightChild(self):
        if self.rightChild is not None:
            return True
        return False

    def isLeftChild(self):
        return self.parent and self.parent.leftChild == self

    def isRightChild(self):
        return self.parent and self.parent.rightChild == self

    def isRoot(self):
        return not self.parent

    def isLeaf(self):
        return not (self.rightChild or self.leftChild)

    def hasAnyChildren(self):
        return self.rightChild or self.leftChild

    def hasBothChildren(self):
        return self.rightChild and self.leftChild

    def replaceNodeData(self, key, value, lc, rc):
        self.key = key
        self.payload = value
        self.leftChild = lc
        self.rightChild = rc
        if self.hasLeftChild():
            self.leftChild.parent = self
        if self.hasRightChild():
            self.rightChild.parent = self

    def spliceOut(self):
        if self.isLeaf():
            if self.isLeftChild():
                self.parent.leftChild = None
            else:
                self.parent.rightChild = None
        elif self.hasAnyChildren():
            if self.hasLeftChild():
                if self.isLeftChild():
                    self.parent.leftChild = self.leftChild
                else:
                    self.parent.rightChild = self.leftChild
                    self.leftChild.parent = self.parent
            else:
                if self.isLeftChild():
                    self.parent.leftChild = self.rightChild
                else:
                    self.parent.rightChild = self.rightChild
                    self.rightChild.parent = self.parent

    def findSuccessor(self):
        succ = None
        if self.hasRightChild():
            succ = self.rightChild.findMin()
        else:
            if self.parent:
                if self.isLeftChild():
                    succ = self.parent
                else:
                    self.parent.rightChild = None
                    succ = self.parent.findSuccessor()
                    self.parent.rightChild = self
        return succ
