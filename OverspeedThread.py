#-*-coding:utf8;-*-
#qpy:2
#ts=4:sw=4:expandtab
'''
Created on 01.07.2014

@author: rkoraschnigg
'''

from ThreadBase import StoppableThread
from Logger import Logger
from copy import deepcopy


class OverspeedCheckerThread(StoppableThread, Logger):
    def __init__(self, main_app, resume,
                 cv_overspeed,
                 overspeed_queue,
                 cv_currentspeed,
                 currentspeed_queue,
                 s,
                 cond, log_viewer):
        StoppableThread.__init__(self)
        Logger.__init__(self, self.__class__.__name__, log_viewer)
        self.main_app = main_app
        self.resume = resume
        self.cv_overspeed = cv_overspeed
        self.overspeed_queue = overspeed_queue
        self.cv_currentspeed = cv_currentspeed
        self.currentspeed_queue = currentspeed_queue
        self.speedlayout = s
        self.cond = cond
        self.last_max_speed = None

    def run(self):
        while not self.cond.terminate:
            if self.main_app.run_in_back_ground:
                self.main_app.main_event.wait()
            if not self.resume.isResumed():
                self.overspeed_queue.clear_overspeedqueue(self.cv_overspeed)
                self.currentspeed_queue.clear(self.cv_currentspeed)
            else:
                status = self.process()
                if status == 'TERMINATE':
                    break

        self.overspeed_queue.clear_overspeedqueue(self.cv_overspeed)
        self.print_log_line(f"{self.__class__.__name__} terminating")
        self.stop()

    def process(self):
            current_speed = self.currentspeed_queue.consume(self.cv_currentspeed)
            self.cv_currentspeed.release()
            self.print_log_line(f"Received Current Speed: {current_speed}")

            if current_speed is None:
                return None

            if isinstance(current_speed, str) and current_speed == 'EXIT':
                return 'TERMINATE'

            overspeed_entry = self.overspeed_queue.consume(self.cv_overspeed)
            self.cv_overspeed.release()

            for condition, max_speed in overspeed_entry.items():
                self.print_log_line(f"Received Max Speed: {max_speed}")

                if isinstance(max_speed, str) and "mph" in max_speed:
                    max_speed = int(max_speed.strip(" mph"))

                if isinstance(max_speed, int):
                    self.last_max_speed = max_speed
                    self.calculate(current_speed, max_speed)

            if not overspeed_entry and self.last_max_speed:
                self.print_log_line(f" Recalculating over speed entry according to last max speed")
                self.calculate(current_speed, self.last_max_speed)

    def calculate(self, current_speed, max_speed):
        if current_speed > max_speed:
            self.print_log_line(f" Driver is too fast: expected speed {max_speed}, "
                                f"actual speed {current_speed}")
            self.process_entry(current_speed - max_speed)
        else:
            self.process_entry(10000)

    def process_entry(self, value):
            if value == 10000:
                self.speedlayout.reset_overspeed()
            else:
                self.speedlayout.update_overspeed(value)


