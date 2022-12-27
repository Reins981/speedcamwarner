# -*-coding:utf8;-*-
# qpy:2
# ts=4:sw=4:expandtab
'''
Created on 01.07.2014

@author: rkoraschnigg
'''

import os
from Logger import Logger
from ThreadBase import StoppableThread
from kivy.core.audio import SoundLoader

BASE_PATH = os.path.join(os.path.abspath(os.path.dirname(__file__)), "sounds")


class VoicePromptThread(StoppableThread, Logger):
    def __init__(self, resume, cv_voice, voice_prompt_queue, cond):
        StoppableThread.__init__(self)
        Logger.__init__(self, self.__class__.__name__)
        self.resume = resume
        self.cv_voice = cv_voice
        self.voice_prompt_queue = voice_prompt_queue
        self.cond = cond
        # thread lock
        self._lock = False

    def run(self):
        while not self.cond.terminate:
            if not self.resume.isResumed():
                self.voice_prompt_queue.clear_gpssignalqueue(self.cv_voice)
                self.voice_prompt_queue.clear_maxspeedexceededqueue(self.cv_voice)
                self.voice_prompt_queue.clear_onlinequeue(self.cv_voice)
            else:
                self.process()

        self.voice_prompt_queue.clear_gpssignalqueue(self.cv_voice)
        self.voice_prompt_queue.clear_maxspeedexceededqueue(self.cv_voice)
        self.voice_prompt_queue.clear_onlinequeue(self.cv_voice)
        self.print_log_line("VoicePromptThreadThread terminating")
        self.stop()

    def process(self):
        voice_entry = self.voice_prompt_queue.consume_items(self.cv_voice)
        self.cv_voice.release()

        while self._lock:
            pass

        sound = None
        if voice_entry == "EXIT_APPLICATION":
            sound = os.path.join(BASE_PATH, 'app_exit.wav')
        elif voice_entry == "ADDED_POLICE":
            sound = os.path.join(BASE_PATH, 'police_added.wav')
        elif voice_entry == "STOP_APPLICATION":
            sound = os.path.join(BASE_PATH, 'app_stopped.wav')
        elif voice_entry == "OSM_DATA_ERROR":
            # sound = os.path.join(BASE_PATH, 'data_error.wav')
            sound = None
        elif voice_entry == "INTERNET_CONN_FAILED":
            sound = os.path.join(BASE_PATH, 'inet_failed.wav')
        elif voice_entry == "HAZARD":
            sound = os.path.join(BASE_PATH, 'hazard.wav')
            # hazard warning on the road
        elif voice_entry == "EMPTY_DATASET_FROM_SERVER":
            # sound = os.path.join(BASE_PATH, 'empty_data.wav')
            sound = None
        elif voice_entry == "LOW_DOWNLOAD_DATA_RATE":
            sound = os.path.join(BASE_PATH, 'low_download_rate.wav')
        elif voice_entry == "GPS_OFF":
            sound = os.path.join(BASE_PATH, 'gps_off.wav')
        elif voice_entry == "GPS_LOW":
            sound = os.path.join(BASE_PATH, 'gps_weak.wav')
        elif voice_entry == "GPS_ON":
            sound = os.path.join(BASE_PATH, 'gps_established.wav')
        elif voice_entry == "SPEEDCAM_REMOVED":
            # sound = os.path.join(BASE_PATH, 'speed_cam_removed.wav')
            sound = None
        elif voice_entry == "FIX_100":
            sound = os.path.join(BASE_PATH, 'fix_100.wav')
        elif voice_entry == "TRAFFIC_100":
            sound = os.path.join(BASE_PATH, 'traffic_100.wav')
        elif voice_entry == "MOBILE_100":
            sound = os.path.join(BASE_PATH, 'mobile_100.wav')
        elif voice_entry == "DISTANCE_100":
            sound = os.path.join(BASE_PATH, 'distance_100.wav')
        elif voice_entry == "FIX_300":
            sound = os.path.join(BASE_PATH, 'fix_300.wav')
        elif voice_entry == "TRAFFIC_300":
            sound = os.path.join(BASE_PATH, 'traffic_300.wav')
        elif voice_entry == "MOBILE_300":
            sound = os.path.join(BASE_PATH, 'mobile_300.wav')
        elif voice_entry == "DISTANCE_300":
            sound = os.path.join(BASE_PATH, 'distance_300.wav')
        elif voice_entry == "FIX_500":
            sound = os.path.join(BASE_PATH, 'fix_500.wav')
        elif voice_entry == "TRAFFIC_500":
            sound = os.path.join(BASE_PATH, 'traffic_500.wav')
        elif voice_entry == "MOBILE_500":
            sound = os.path.join(BASE_PATH, 'mobile_500.wav')
        elif voice_entry == "DISTANCE_500":
            sound = os.path.join(BASE_PATH, 'distance_500.wav')
        elif voice_entry == "FIX_1000":
            sound = os.path.join(BASE_PATH, 'fix_1000.wav')
        elif voice_entry == "TRAFFIC_1000":
            sound = os.path.join(BASE_PATH, 'traffic_1000.wav')
        elif voice_entry == "MOBILE_1000":
            sound = os.path.join(BASE_PATH, 'mobile_1000.wav')
        elif voice_entry == "DISTANCE_1000":
            sound = os.path.join(BASE_PATH, 'distance_1000.wav')
        elif voice_entry == "FIX_NOW":
            sound = os.path.join(BASE_PATH, 'fix_now.wav')
        elif voice_entry == "TRAFFIC_NOW":
            sound = os.path.join(BASE_PATH, 'traffic_now.wav')
        elif voice_entry == "MOBILE_NOW":
            sound = os.path.join(BASE_PATH, 'mobile_now.wav')
        elif voice_entry == "DISTANCE_NOW":
            sound = os.path.join(BASE_PATH, 'distance_now.wav')
        elif voice_entry == "CAMERA_AHEAD":
            sound = os.path.join(BASE_PATH, 'camera_ahead.wav')
        elif voice_entry == "WATER":
            sound = os.path.join(BASE_PATH, 'water.wav')
        elif voice_entry == "ACCESS_CONTROL":
            sound = os.path.join(BASE_PATH, 'access_control.wav')
        elif voice_entry == "POI_SUCCESS":
            sound = os.path.join(BASE_PATH, 'poi_success.wav')
        elif voice_entry == "POI_FAILED":
            sound = os.path.join(BASE_PATH, 'poi_failed.wav')
        elif voice_entry == "NO_ROUTE":
            sound = os.path.join(BASE_PATH, 'no_route.wav')
        elif voice_entry == "ROUTE_STOPPED":
            sound = os.path.join(BASE_PATH, 'route_stopped.wav')
        elif voice_entry == "POI_REACHED":
            sound = os.path.join(BASE_PATH, 'poi_reached.wav')
        else:
            pass

        if sound is not None:
            self._lock = True
            self.print_log_line(f" Trigger sound {sound}")
            s = SoundLoader.load(sound)
            if s:
                s.play()
                while s.get_pos() != 0:
                    pass
            self._lock = False
