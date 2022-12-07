# -*-coding:utf8;-*-
# qpy:2
# ts=4:sw=4:expandtab
'''
Created on 01.07.2014

@author: rkoraschnigg
'''

from kivy.clock import Clock
from ThreadBase import StoppableThread
from Logger import Logger


class DeviationCheckerThread(StoppableThread, Logger):
    def __init__(self, resume, cv_average_angle, cv_interrupt, average_angle_queue,
                 interruptqueue, av_bearing_value, cond):
        StoppableThread.__init__(self)
        Logger.__init__(self, self.__class__.__name__)
        self.resume = resume
        self.cv_average_angle = cv_average_angle
        self.cv_interrupt = cv_interrupt
        self.average_angle_queue = average_angle_queue
        self.interruptqueue = interruptqueue
        self.av_bearing_value = av_bearing_value
        self.cond = cond
        self.av_bearing = float(0.0)
        self.av_bearing_current = 0
        self.av_bearing_prev = 0
        self.first_bearing_set_available = False

    def run(self):
        while not self.cond.terminate:
            self.process()

        self.average_angle_queue.clear_average_angle_data(self.cv_average_angle)
        self.interruptqueue.produce(self.cv_interrupt, 'TERMINATE')
        self.print_log_line("Deviation Checker terminating")
        self.stop()

    def cleanup(self):
        self.first_bearing_set_available = False
        self.average_angle_queue.clear_average_angle_data(self.cv_average_angle)

    def process(self):
        current_bearing_queue = self.average_angle_queue.get_average_angle_data(
            self.cv_average_angle)
        self.cv_average_angle.release()
        self.calculate_average_bearing(current_bearing_queue)

    def calculate_average_bearing(self, current_bearing_queue):
        self.av_bearing = float(0.0)

        if current_bearing_queue == 0.001:
            self.update_average_bearing('---.-')
            return
        elif current_bearing_queue == 0.002:
            self.print_log_line(' Deviation Checker Thread got a termination item')
            return
        elif current_bearing_queue == 0.0:
            self.update_average_bearing('0')
            return
        elif current_bearing_queue == 'TERMINATE':
            return
        else:
            pass

        for entry in current_bearing_queue:
            self.av_bearing += entry

        if len(current_bearing_queue) > 0:
            av_bearing_final = self.av_bearing / len(current_bearing_queue)
            self.update_average_bearing(av_bearing_final)

            av_first_entry = current_bearing_queue[0]
            first_av_entry_current = av_first_entry

            if not self.first_bearing_set_available:
                self.first_bearing_set_available = True
                self.av_bearing_current = av_bearing_final
            else:
                self.av_bearing_prev = self.av_bearing_current
                self.av_bearing_current = av_bearing_final

                '''
                Check first if we are inside a tolerance limit in degrees between 
                2 position pair lists consisting of 5 positions each.
                If the difference between bearing of first position and average bearing 
                is less or equal than 13 degrees, ccp is considered stable.
                '''

                av_bearing_diff_position_pair_queues = self.av_bearing_current - self.av_bearing_prev
                av_bearing_diff_current_queue = first_av_entry_current - self.av_bearing_current

                if (-22 <= av_bearing_diff_position_pair_queues <= 22) \
                        and (-13 <= av_bearing_diff_current_queue <= 13):
                    self.interruptqueue.produce(self.cv_interrupt, 'STABLE')
                else:
                    self.interruptqueue.produce(self.cv_interrupt, 'UNSTABLE')
                    self.print_log_line(' waiting for CCP to become stable again')
        return

    def update_average_bearing(self, av_bearing=None):
        if av_bearing is not None:
            self.av_bearing_value.text = str(av_bearing) + '°'
            Clock.schedule_once(self.av_bearing_value.texture_update)
