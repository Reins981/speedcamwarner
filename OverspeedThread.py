#-*-coding:utf8;-*-
#qpy:2
#ts=4:sw=4:expandtab
'''
Created on 01.07.2014

@author: rkoraschnigg
'''

from ThreadBase import StoppableThread
from Logger import Logger


class OverspeedCheckerThread(StoppableThread, Logger):
    def __init__(self, resume,
                 cv_overspeed,
                 overspeed_queue,
                 cv_currentspeed,
                 currentspeed_queue,
                 s,
                 cond):
        StoppableThread.__init__(self)
        Logger.__init__(self, self.__class__.__name__)
        self.resume = resume
        self.cv_overspeed = cv_overspeed
        self.overspeed_queue = overspeed_queue
        self.cv_currentspeed = cv_currentspeed
        self.currentspeed_queue = currentspeed_queue
        self.speedlayout = s
        self.cond = cond

    def run(self):
        while not self.cond.terminate:
            if not self.resume.isResumed():
                self.overspeed_queue.clear(self.cv_overspeed)
            else:
                status = self.process()
                if status == 'TERMINATE':
                    break

        self.overspeed_queue.clear(self.cv_overspeed)
        self.print_log_line(" terminating")
        self.stop()

    def process(self):
            current_speed = self.currentspeed_queue.consume(self.cv_currentspeed)
            self.cv_currentspeed.release()

            overspeed_entry = self.overspeed_queue.consume(self.cv_overspeed)
            self.cv_overspeed.release()
            self.print_log_line(f" Received overspeed entry {overspeed_entry}")

            if overspeed_entry is None:
                return 0

            try:
                condition = list(overspeed_entry.keys())[0]
            except AttributeError:
                return 1

            if condition == 'EXIT':
                return 'TERMINATE'

            if current_speed is None:
                return 0
            self.print_log_line(f"Received Current Speed: {current_speed}")

            try:
                max_speed = list(overspeed_entry.values())[0]
            except AttributeError:
                return 1
            self.print_log_line(f"Received Max Speed: {max_speed}")

            if condition == "maxspeed":
                if isinstance(max_speed, str) and "mph" in max_speed:
                    max_speed = int(max_speed.strip(" mph"))

                if isinstance(max_speed, int):
                    if current_speed > max_speed:
                        self.print_log_line(f" Driver is too fast: expected speed {max_speed}, "
                                            f"actual speed {current_speed}")
                        s_color = (1, 0, 0, 3)
                        self.speedlayout.overspeed.color = s_color
                        self.speedlayout.overspeed.texture_update()
                        self.process_entry(current_speed - max_speed)
                    else:
                        self.process_entry(10000)
            return 0

    def process_entry(self, value):
            if value == 10000:
                self.speedlayout.reset_overspeed()
            else:
                self.speedlayout.update_overspeed(value)


