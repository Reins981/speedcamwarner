# -*-coding:utf8;-*-
# qpy:2
# ts=4:sw=4:expandtab
'''
Created on 01.07.2014

@author: rkoraschnigg
'''

import threading
import time
from threading import Condition, currentThread
from collections import deque
from queue import Queue, Empty
from Logger import Logger


class StoppableThread(threading.Thread, Logger):
    def __init__(self):
        threading.Thread.__init__(self)
        Logger.__init__(self, self.__class__.__name__)
        self.stop_event = threading.Event()

    def stop(self):

        if self.is_alive():
            # logger.print_log_line("sending event to thread %s" % (currentThread()))
            # set event to signal thread to terminate
            self.stop_event.set()
            # block calling thread until thread really has terminated
            # logger.print_log_line("finally joining thread %s" % (currentThread()))
            try:
                self.join()

            except RuntimeError:
                pass
                # logger.print_log_line( '%s already terminated' % (currentThread()))

    def stop_specific(self):

        if self.isAlive():
            # logger.print_log_line("terminating thread %s" % (currentThread()))
            try:
                self.join()

            except RuntimeError:
                self.print_log_line('%s already terminated' % (currentThread()))


class ThreadCondition(object):
    def __init__(self, cond):
        self.terminate = cond

    def set_terminate_state(self, state):
        self.terminate = state


class InterruptQueue(object):
    def __init__(self):
        self.INTERRUPTQUEUE = deque()

    def an_item_is_available(self):
        return bool(self.INTERRUPTQUEUE)

    def get_an_available_item(self):
        return self.INTERRUPTQUEUE.pop()

    def make_an_item_available(self, item):
        self.INTERRUPTQUEUE.append(item)

    def clear_interruptqueue(self, cv):
        cv.acquire()
        self.INTERRUPTQUEUE.clear()
        cv.notify()
        cv.release()

    def consume(self, cv):
        cv.acquire()
        while not self.an_item_is_available():
            cv.wait()
        return self.get_an_available_item()

    def produce(self, cv, item):
        cv.acquire()
        self.make_an_item_available(item)
        cv.notify()
        cv.release()


class OverspeedQueue(object):
    def __init__(self):
        self.OVERSPEEDQUEUE = deque()

    def an_item_is_available(self):
        return bool(self.OVERSPEEDQUEUE)

    def get_an_available_item(self):
        return self.OVERSPEEDQUEUE.pop()

    def make_an_item_available(self, item):
        self.OVERSPEEDQUEUE.append(item)

    def clear_overspeedqueue(self, cv):
        cv.acquire()
        self.OVERSPEEDQUEUE.clear()
        cv.notify()
        cv.release()

    def consume(self, cv):
        cv.acquire()
        if not self.an_item_is_available():
            return {}
        return self.get_an_available_item()

    def produce(self, cv, item):
        cv.acquire()
        self.make_an_item_available(item)
        cv.notify()
        cv.release()


class PoiQueue(object):
    def __init__(self):
        self.POIQUEUE = Queue()

    def get_an_available_item(self):
        return self.POIQUEUE.get(block=False)

    def make_an_item_available(self, item):
        self.POIQUEUE.put(item, block=False)

    def clear(self, cv):
        pass

    def consume(self, cv):
        cv.acquire()
        try:
            return self.get_an_available_item()
        except Empty:
            return None

    def produce(self, cv, item):
        cv.acquire()
        self.make_an_item_available(item)
        cv.notify()
        cv.release()

    def size(self):
        return self.POIQUEUE.qsize()


class BorderQueue(object):
    def __init__(self):
        self.BORDERQUEUE = Queue()

    def get_an_available_item(self):
        return self.BORDERQUEUE.get(block=False)

    def make_an_item_available(self, item):
        self.BORDERQUEUE.put(item, block=False)

    def clear(self, cv):
        pass

    def consume(self, cv):
        cv.acquire()
        try:
            return self.get_an_available_item()
        except Empty:
            return None

    def produce(self, cv, item):
        cv.acquire()
        self.make_an_item_available(item)
        cv.notify()
        cv.release()

    def size(self):
        return self.BORDERQUEUE.qsize()


class BorderQueueReverse(object):
    def __init__(self):
        self.BORDERQUEUEREV = Queue()

    def get_an_available_item(self):
        return self.BORDERQUEUEREV.get(block=False)

    def make_an_item_available(self, item):
        self.BORDERQUEUEREV.put(item, block=False)

    def clear(self, cv):
        pass

    def consume(self, cv):
        cv.acquire()
        try:
            return self.get_an_available_item()
        except Empty:
            return None

    def produce(self, cv, item):
        cv.acquire()
        self.make_an_item_available(item)
        cv.notify()
        cv.release()

    def size(self):
        return self.BORDERQUEUEREV.qsize()


class GpsDataQueue(object):
    def __init__(self):
        self.GPS = deque()

    def an_item_is_available(self):
        return bool(self.GPS)

    def get_an_available_item(self):
        return self.GPS.pop()

    def make_an_item_available(self, item):
        self.GPS.append(item)

    def clear(self, cv):
        cv.acquire()
        self.GPS.clear()
        cv.notify()
        cv.release()

    def consume(self, cv):
        cv.acquire()
        while not self.an_item_is_available():
            cv.wait()
        return self.get_an_available_item()

    def produce(self, cv, item):
        cv.acquire()
        self.make_an_item_available(item)
        cv.notify()
        cv.release()


class CurrentSpeedQueue(object):
    def __init__(self):
        self.CURRENTSPEEDQUEUE = deque()

    def an_item_is_available(self):
        return bool(self.CURRENTSPEEDQUEUE)

    def get_an_available_item(self):
        return self.CURRENTSPEEDQUEUE.pop()

    def make_an_item_available(self, item):
        self.CURRENTSPEEDQUEUE.append(item)

    def clear(self, cv):
        cv.acquire()
        self.CURRENTSPEEDQUEUE.clear()
        cv.notify()
        cv.release()

    def consume(self, cv):
        cv.acquire()
        while not self.an_item_is_available():
            cv.wait()
        return self.get_an_available_item()

    def produce(self, cv, item):
        cv.acquire()
        self.make_an_item_available(item)
        cv.notify()
        cv.release()


class MapQueue(object):
    def __init__(self):
        self.MAPQUEUE = deque()
        self.CAMERAQUEUE_OSM = Queue()
        self.CAMERASQUEUE_CLOUD = Queue()
        self.CAMERASQUEUE_DB = Queue()

    def get_an_available_item_osm(self):
        return self.CAMERAQUEUE_OSM.get(block=False)

    def make_an_item_available_osm(self, item):
        self.CAMERAQUEUE_OSM.put(item, block=False)

    def clear_osm(self, cv):
        pass

    def consume_osm(self, cv):
        cv.acquire()
        try:
            return self.get_an_available_item_osm()
        except Empty:
            return []

    def produce_osm(self, cv, item):
        cv.acquire()
        self.make_an_item_available_osm(item)
        cv.notify()
        cv.release()

    def get_an_available_item_cloud(self):
        return self.CAMERASQUEUE_CLOUD.get(block=False)

    def make_an_item_available_cloud(self, item):
        self.CAMERASQUEUE_CLOUD.put(item, block=False)

    def clear_cloud(self, cv):
        pass

    def consume_cloud(self, cv):
        cv.acquire()
        try:
            return self.get_an_available_item_cloud()
        except Empty:
            return []

    def produce_cloud(self, cv, item):
        cv.acquire()
        self.make_an_item_available_cloud(item)
        cv.notify()
        cv.release()

    def get_an_available_item_db(self):
        return self.CAMERASQUEUE_DB.get(block=False)

    def make_an_item_available_db(self, item):
        self.CAMERASQUEUE_DB.put(item, block=False)

    def clear_db(self, cv):
        pass

    def consume_db(self, cv):
        cv.acquire()
        try:
            return self.get_an_available_item_db()
        except Empty:
            return []

    def produce_db(self, cv, item):
        cv.acquire()
        self.make_an_item_available_db(item)
        cv.notify()
        cv.release()

    def an_item_is_available(self):
        return bool(self.MAPQUEUE)

    def get_an_available_item(self):
        return self.MAPQUEUE.pop()

    def make_an_item_available(self, item):
        self.MAPQUEUE.append(item)

    def clear_map_update(self, cv):
        try:
            cv.acquire()
            self.MAPQUEUE.clear()
            cv.notify()
            cv.release()
        except:
            self.MAPQUEUE.clear()

    def consume(self, cv):
        cv.acquire()
        while not self.an_item_is_available():
            cv.wait()
        return self.get_an_available_item()

    def produce(self, cv, item):
        cv.acquire()
        self.make_an_item_available(item)
        cv.notify()
        cv.release()


class VectorDataPoolQueue(object):
    def __init__(self):
        self.vector_data = {}
        self.VECTORDATAQUEUE = deque()

    def set_vector_data(self, cv, key, longitude, latitude, cspeed, bearing, direction, gpsstatus,
                        accuracy):
        cv.acquire()
        if not isinstance(longitude, float):
            longitude = float(longitude)
        if not isinstance(latitude, float):
            latitude = float(latitude)
        if not isinstance(cspeed, float):
            cspeed = float(cspeed)
        if not isinstance(bearing, float):
            bearing = float(bearing)
        self.vector_data[key] = (
        [longitude, latitude], cspeed, bearing, direction, gpsstatus, accuracy)
        self.VECTORDATAQUEUE.append(self.vector_data)
        cv.notify()
        cv.release()

    def vector_item_is_available(self):
        return bool(self.VECTORDATAQUEUE)

    def get_an_available_vector_item(self):
        return self.VECTORDATAQUEUE.pop()

    def get_vector_data(self, cv):
        cv.acquire()
        while not self.vector_item_is_available():
            cv.wait()
        return self.get_an_available_vector_item()

    def clear_vector_data(self, cv):
        cv.acquire()
        self.VECTORDATAQUEUE.clear()
        cv.notify()
        cv.release()


class AverageAngleQueue(object):
    def __init__(self):
        self.AVERAGEANGLEDATAQUEUE = deque()

    def set_average_angle_data(self, current_bearings):
        self.AVERAGEANGLEDATAQUEUE.append(current_bearings)

    def average_angle_item_is_available(self):
        return bool(self.AVERAGEANGLEDATAQUEUE)

    def get_an_available_average_angle_item(self):
        return self.AVERAGEANGLEDATAQUEUE.pop()

    def get_average_angle_data(self, cv):
        cv.acquire()
        while not self.average_angle_item_is_available():
            cv.wait()
        return self.get_an_available_average_angle_item()

    def clear_average_angle_data(self, cv):
        cv.acquire()
        self.AVERAGEANGLEDATAQUEUE.clear()
        cv.notify()
        cv.release()

    def produce(self, cv, item):
        cv.acquire()
        self.set_average_angle_data(item)
        cv.notify()
        cv.release()


class GPSQueue(object):
    def __init__(self):
        self.GPSQUEUE = deque()

    def an_item_is_available(self):
        return bool(self.GPSQUEUE)

    def get_an_available_item(self):
        return self.GPSQUEUE.pop()

    def make_an_item_available(self, item):
        self.GPSQUEUE.append(item)

    def clear_gpsqueue(self, cv):
        cv.acquire()
        self.GPSQUEUE.clear()
        cv.notify()
        cv.release()

    def consume(self, cv):
        cv.acquire()
        while not self.an_item_is_available():
            cv.wait()
        return self.get_an_available_item()

    def produce(self, cv, item):
        cv.acquire()
        self.make_an_item_available(item)
        cv.notify()
        cv.release()


class SpeedCamQueue(object):
    def __init__(self):
        self.SPEEDCAMQUEUE = deque()

    def an_item_is_available(self):
        return bool(self.SPEEDCAMQUEUE)

    def get_an_available_item(self):
        return self.SPEEDCAMQUEUE.pop()

    def make_an_item_available(self, item):
        self.SPEEDCAMQUEUE.append(item)

    def clear_camqueue(self, cv):
        cv.acquire()
        self.SPEEDCAMQUEUE.clear()
        cv.notify()
        cv.release()

    def consume(self, cv):
        cv.acquire()
        while not self.an_item_is_available():
            cv.wait()
        return self.get_an_available_item()

    def produce(self, cv, item):
        cv.acquire()
        self.make_an_item_available(item)
        cv.notify()
        cv.release()


logger = Logger("VoicePromptQueue")


class VoicePromptQueue(object):
    def __init__(self):
        self.GPSSIGNALQUEUE = deque()
        self.MAXSPEEDEXCEEDEDQUEUE = deque()
        self.ONLINEQUEUE = deque()
        self.POIQUEUE = deque()
        self.CAMERAQUEUE = deque()
        self.INFOQUEUE = deque()

    def an_item_is_available_gpssignal(self):
        return bool(self.GPSSIGNALQUEUE)

    def an_item_is_available_maxspeed_exceeded(self):
        return bool(self.MAXSPEEDEXCEEDEDQUEUE)

    def an_item_is_available_online(self):
        return bool(self.ONLINEQUEUE)

    def an_item_is_available_poi(self):
        return bool(self.POIQUEUE)

    def an_item_is_available_info(self):
        return bool(self.INFOQUEUE)

    def an_item_is_available_camera(self):
        return bool(self.CAMERAQUEUE)

    def get_an_available_item_gpssignal(self):
        return self.GPSSIGNALQUEUE.pop()

    def get_an_available_item_maxspeed_exceeded(self):
        return self.MAXSPEEDEXCEEDEDQUEUE.pop()

    def get_an_available_item_online(self):
        return self.ONLINEQUEUE.pop()

    def get_an_available_item_poi(self):
        return self.POIQUEUE.pop()

    def get_an_available_item_camera(self):
        return self.CAMERAQUEUE.pop()

    def get_an_available_item_info(self):
        return self.INFOQUEUE.pop()

    def make_an_item_available_camera(self, item):
        self.CAMERAQUEUE.append(item)

    def make_an_item_available_gpssignal(self, item):
        self.GPSSIGNALQUEUE.append(item)

    def make_an_item_available_info(self, item):
        self.INFOQUEUE.append(item)

    def make_an_item_available_maxspeed_exceeded(self, item):
        self.MAXSPEEDEXCEEDEDQUEUE.append(item)

    def make_an_item_available_online(self, item):
        self.ONLINEQUEUE.append(item)

    def make_an_item_available_poi(self, item):
        self.POIQUEUE.append(item)

    def clear_gpssignalqueue(self, cv):
        cv.acquire()
        self.GPSSIGNALQUEUE.clear()
        cv.notify()
        cv.release()

    def clear_infoqueue(self, cv):
        cv.acquire()
        self.INFOQUEUE.clear()
        cv.notify()
        cv.release()

    def clear_maxspeedexceededqueue(self, cv):
        cv.acquire()
        self.MAXSPEEDEXCEEDEDQUEUE.clear()
        cv.notify()
        cv.release()

    def clear_onlinequeue(self, cv):
        cv.acquire()
        self.ONLINEQUEUE.clear()
        cv.notify()
        cv.release()

    def clear_cameraqueue(self, cv):
        cv.acquire()
        self.CAMERAQUEUE.clear()
        cv.notify()
        cv.release()

    def consume_items(self, cv):
        cv.acquire(blocking=False)
        while not self.an_item_is_available_gpssignal() \
                and not self.an_item_is_available_maxspeed_exceeded() \
                and not self.an_item_is_available_online() \
                and not self.an_item_is_available_poi() \
                and not self.an_item_is_available_camera() \
                and not self.an_item_is_available_info():
            cv.wait()

        if self.an_item_is_available_camera() and self.an_item_is_available_gpssignal():
            unusedItem1 = self.get_an_available_item_gpssignal()
            logger.print_log_line(f"Dismiss voice prompt(s) (GPS) "
                                  f"-> Prefer voice prompt (CAMERA)")
            return self.get_an_available_item_camera()

        if self.an_item_is_available_camera() and self.an_item_is_available_info():
            unusedItem1 = self.get_an_available_item_info()
            logger.print_log_line(f"Dismiss voice prompt(s) (INFO) "
                                  f"-> Prefer voice prompt (CAMERA)")
            return self.get_an_available_item_camera()

        if self.an_item_is_available_camera() and self.an_item_is_available_online():
            unusedItem1 = self.get_an_available_item_online()
            logger.print_log_line(f"Dismiss voice prompt(s) (ONLINE) "
                                  f"-> Prefer voice prompt (CAMERA)")
            return self.get_an_available_item_camera()

        if self.an_item_is_available_gpssignal() \
                and self.an_item_is_available_maxspeed_exceeded() \
                and self.an_item_is_available_online():
            unusedItem1 = self.get_an_available_item_gpssignal()
            unusedItem2 = self.get_an_available_item_online()
            logger.print_log_line(f"Dismiss voice prompt(s) (GPS, ONLINE) "
                                  f"-> Prefer voice prompt (MAXSPEED_EXCEEDED)")
            return self.get_an_available_item_maxspeed_exceeded()
        elif self.an_item_is_available_gpssignal() \
                and self.an_item_is_available_maxspeed_exceeded():
            unusedItem1 = self.get_an_available_item_gpssignal()
            logger.print_log_line(f"Dismiss voice prompt(s) (GPS) "
                                  f"-> Prefer voice prompt (MAXSPEED_EXCEEDED)")
            return self.get_an_available_item_maxspeed_exceeded()
        elif self.an_item_is_available_gpssignal() and self.an_item_is_available_online():
            unusedItem1 = self.get_an_available_item_online()
            logger.print_log_line(f"Dismiss voice prompt(s) (ONLINE) "
                                  f"-> Prefer voice prompt (GPS)")
            return self.get_an_available_item_gpssignal()
        elif self.an_item_is_available_maxspeed_exceeded() and self.an_item_is_available_online():
            unusedItem1 = self.get_an_available_item_online()
            logger.print_log_line(f"Dismiss voice prompt(s) (ONLINE) "
                                  f"-> Prefer voice prompt (MAXSPEED_EXCEEDED)")
            return self.get_an_available_item_maxspeed_exceeded()
        elif self.an_item_is_available_maxspeed_exceeded():
            return self.get_an_available_item_maxspeed_exceeded()
        elif self.an_item_is_available_gpssignal():
            return self.get_an_available_item_gpssignal()
        elif self.an_item_is_available_online():
            return self.get_an_available_item_online()
        elif self.an_item_is_available_poi():
            return self.get_an_available_item_poi()
        elif self.an_item_is_available_camera():
            return self.get_an_available_item_camera()
        elif self.an_item_is_available_info():
            return self.get_an_available_item_info()
        else:
            pass

    def produce_gpssignal(self, cv, item):
        cv.acquire(blocking=False)
        self.make_an_item_available_gpssignal(item)
        cv.notify()
        cv.release()

    def produce_info(self, cv, item):
        cv.acquire(blocking=False)
        self.make_an_item_available_info(item)
        cv.notify()
        cv.release()

    def produce_maxspeed_exceeded(self, cv, item):
        cv.acquire(blocking=False)
        self.make_an_item_available_maxspeed_exceeded(item)
        cv.notify()
        cv.release()

    def produce_online_status(self, cv, item):
        cv.acquire(blocking=False)
        self.make_an_item_available_online(item)
        cv.notify()
        cv.release()

    def produce_poi_status(self, cv, item):
        cv.acquire(blocking=False)
        self.make_an_item_available_poi(item)
        cv.notify()
        cv.release()

    def produce_camera_status(self, cv, item):
        cv.acquire(blocking=False)
        self.make_an_item_available_camera(item)
        cv.notify()
        cv.release()


class TaskCounter(object):
    def __init__(self):
        self.task_counter = 0

    def set_task_counter(self):
        self.task_counter += 1

    def get_task_counter(self):
        return self.task_counter


class ResultMapper(Logger):
    def __init__(self):
        Logger.__init__(self, self.__class__.__name__)
        self.server_response = {}

    def set_server_response(self, task_counter, online_available, status, data, internal_error,
                            current_rect):
        self.print_log_line(" Adding server results..")
        self.server_response[task_counter] = (
            online_available, status, data, internal_error, current_rect)

    def set_build_response(self, task_counter, current_rect):
        self.print_log_line(" Adding building results..")
        self.server_response[task_counter] = current_rect

    def set_google_drive_upload_response(self, task_counter, result):
        self.print_log_line(" Adding google drive result..")
        self.server_response[task_counter] = result

    def get_server_response(self):
        return self.server_response


class CyclicThread(threading.Thread, Logger):
    def __init__(self, cycle_time, task, *args, **kwargs):
        threading.Thread.__init__(self)
        Logger.__init__(self, self.__class__.__name__)
        self._stop_event = threading.Event()
        self.cycle_time = cycle_time
        self.task = task
        self.args = args
        self.kwargs = kwargs

    def __str__(self):
        return "Cyclic Thread with {cycle_time} sec cycle time".format(cycle_time=self.cycle_time)

    def stop(self):
        self.print_log_line(f"Stopping {self}")
        self._stop_event.set()

    def run(self):
        while not self._stop_event.is_set():
            time.sleep(self.cycle_time)
            self.task(*self.args, **self.kwargs)

    def set_time(self, m_time):
        self.cycle_time = m_time


class Worker(StoppableThread, Logger):
    # executing tasks from a given tasks queue
    def __init__(self, tasks, mcond=None, task_counter=None, result_map=None, action='NETWORK'):
        StoppableThread.__init__(self)
        Logger.__init__(self, self.__class__.__name__)
        self.tasks = tasks
        self.Mcond = mcond
        self.TaskCounter = task_counter
        self.ResultMap = result_map
        self.action = action

        # global variables
        self.online_available = False
        self.status = 'NOINET'
        self.data = None
        self.rect = None
        self.current_rect = None
        self.internal_error = ''

        # execute run()
        self.start()

    def run(self):
        while True:
            raise_exception = False
            error_msg = None
            # self.print_log_line(' %s starting..' %(currentThread()))
            func, args, kwargs = self.tasks.get()
            try:
                if len(args) == 0:
                    if self.action == 'NETWORK':
                        (self.online_available, self.status, self.data, self.internal_error,
                         self.current_rect) = func(**kwargs)
                    elif self.action == 'CACHE':
                        self.rect = kwargs['rect_preferred']
                        self.print_log_line(' Building data structure for rect %s' % self.rect)
                        func(**kwargs)
                    elif self.action == 'SPEED' \
                            or self.action == 'DISABLE':
                        func(**kwargs)
                    elif self.action == 'UPLOAD':
                        self.status = func(**kwargs)
                    elif self.action == 'LOOKUP':
                        _ = func(**kwargs)
                    else:
                        pass
                else:
                    if self.action == 'NETWORK':
                        (self.online_available, self.status, self.data, self.internal_error,
                         self.current_rect) = func(*args, **kwargs)
                    elif self.action == 'CACHE':
                        self.rect = kwargs['rect_preferred']
                        self.print_log_line(' Building data structure for rect %s' % self.rect)
                        func(*args, **kwargs)
                    elif self.action == 'SPEED' \
                            or self.action == 'DISABLE':
                        func(*args, **kwargs)
                    elif self.action == 'UPLOAD':
                        self.status = func(*args, **kwargs)
                    elif self.action == 'LOOKUP':
                        _ = func(*args, **kwargs)
                    else:
                        pass
            except Exception as e:
                raise_exception = True
                error_msg = str(e)
            finally:
                # self.print_log_line(' %s finished task' %(currentThread()))
                self.TaskCounter.set_task_counter()

                if self.action == 'NETWORK':
                    self.ResultMap.set_server_response(self.TaskCounter.get_task_counter(),
                                                       self.online_available,
                                                       self.status,
                                                       self.data,
                                                       self.internal_error,
                                                       self.current_rect)
                elif self.action == 'CACHE':
                    self.ResultMap.set_build_response(self.TaskCounter.get_task_counter(),
                                                      self.rect)
                elif self.action == 'UPLOAD':
                    self.ResultMap.set_google_drive_upload_response(
                        self.TaskCounter.get_task_counter(),
                        self.status
                    )
                else:
                    pass

                # self.print_log_line(' %s releasing lock' %(currentThread()))
                self.tasks.task_done()
                self.stop()
                break
        if raise_exception:
            raise RuntimeError(error_msg)


class ThreadPool(Logger):
    # Pool of threads consuming tasks from a queue
    def __init__(self, num_threads=0, online_available=False,
                 status='',
                 data='',
                 internal_error='',
                 current_rect='',
                 extrapolated=False,
                 action='NETWORK'):
        Logger.__init__(self, self.__class__.__name__)

        self.num_threads = num_threads
        self.action = action
        # self.print_log_line(' %s %s initializing task queue with %d tasks..'
        # %(action, currentThread(), num_threads))
        self.tasks = Queue(self.num_threads)
        Mcond = Condition()
        self.taskCounter = TaskCounter()
        self.resultMap = ResultMapper()

        if action == 'NETWORK' and not extrapolated:
            # set the response for the current rect once
            self.resultMap.set_server_response(0, online_available, status, data, internal_error,
                                               current_rect)

        for _ in range(self.num_threads):
            # self.print_log_line(' %s -> starting Worker Thread' %(currentThread()))
            Worker(
                self.tasks,
                mcond=Mcond,
                task_counter=self.taskCounter,
                result_map=self.resultMap,
                action=self.action
            )

    def add_task(self, func, *args, **kwargs):
        # Add a task to the queue
        # self.print_log_line(' %s adding task to the queue' %(currentThread()))
        self.tasks.put((func, args, kwargs))

    def wait_completion(self):
        self.print_log_line(' %s waiting for task completion..' % (currentThread()))
        # Wait for completion of all the tasks in the queue
        while self.taskCounter.get_task_counter() < self.num_threads:
            pass
        self.print_log_line(" %d tasks completed" % self.num_threads)

        try:
            self.tasks.join()
        except RuntimeError:
            self.print_log_line(' %s could not join! Tasks already completed' % (currentThread()))

        # self.print_log_line(' all tasks completed!')
        return self.resultMap.get_server_response()

    def wait_completion_perf(self):
        # Wait for completion of all the tasks in the queue
        while self.taskCounter.get_task_counter() < self.num_threads:
            yield self.resultMap.get_server_response()
        self.print_log_line(" %d tasks completed" % self.num_threads)

        try:
            self.tasks.join()
        except RuntimeError:
            self.print_log_line(' %s could not join! Tasks already completed' % (currentThread()))

    def get_task_counter(self):
        return self.taskCounter.get_task_counter()

    def get_server_response(self):
        return self.resultMap.get_server_response()
