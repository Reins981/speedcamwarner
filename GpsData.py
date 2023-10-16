import gpxpy
import gpxpy.gpx
import os
from random import randint
from Logger import Logger


class GpsTestDataGenerator(Logger):

    def __init__(self, max_num=50000, gpx_f=None):
        super().__init__(self.__class__.__name__)
        self.events = list()
        self.event_index = -1
        self.startup = True
        if gpx_f is not None:
            self._fill_events_from_gpx(gpx_f)
        else:
            self._fill_events(max_num)

    def _fill_events_from_gpx(self, gpx_f):
        self.print_log_line(" Generating Test GPS Data from %s...." % gpx_f)
        gpx_f_handle = open(gpx_f, 'r')

        gpx = gpxpy.parse(gpx_f_handle)

        for track in gpx.tracks:
            for segment in track.segments:
                for point in segment.points:
                    self.print_log_line('Point at ({0},{1}) -> {2}'.format(point.latitude, point.longitude,
                                                             point.elevation))
                    event = {'data': {'gps': {'accuracy': randint(2, 25),
                                              'latitude': point.latitude,
                                              'longitude': point.longitude,
                                              'speed': randint(10, 35),
                                              'bearing': randint(200, 250)
                                              }
                                      },
                             'name': 'location'}
                    self.events.append(event)

    def _fill_events(self, max_num):
        self.print_log_line("Generating %d Test GPS Data...." % max_num)
        # London
        # start_lat = 52.520008
        # start_long = 13.404954
        # Wien
        start_lat = 51.509865
        start_long = -0.118092
        i = 0.0000110
        j = 0.0000110
        counter = 0
        bearing = randint(15, 15)
        for _ in range(max_num):
            event = {'data': {'gps': {'accuracy': randint(0, 8),
                                      'latitude': start_lat,
                                      'longitude': start_long,
                                      'speed': randint(10, 35),
                                      'bearing': bearing
                                      }
                              },
                     'name': 'location'}
            self.events.append(event)
            counter += 1
            if counter > 1000:
                start_lat -= i
                start_long -= j
                bearing = randint(180, 180)
            else:
                start_lat += i
                start_long += j

    def __iter__(self):
        return self

    def __next__(self):
        self.event_index += 1
        if self.event_index < len(self.events):
            return self.events[self.event_index]
        else:
            raise StopIteration

    def __str__(self):
        return "%s" % self.events


if __name__ == '__main__':
    gpx_file = os.path.join(os.path.dirname(__file__), "gpx", "nordspange_tr2.gpx")
    test_iter = GpsTestDataGenerator(gpx_f=gpx_file)
    print("***********************")
    for entry in test_iter:
        print(entry)
    '''print(next(test_iter))
    print(next(test_iter))
    print(next(test_iter))
    print(next(test_iter))
    print(next(test_iter))
    print(next(test_iter))
    print(next(test_iter))
    print(next(test_iter))
    print(next(test_iter))
    print(next(test_iter))
    print(next(test_iter))
    print(next(test_iter))
    print(next(test_iter))
    print(next(test_iter))
    print(next(test_iter))
    print(next(test_iter))
    print(next(test_iter))
    print(next(test_iter))
    print(next(test_iter))
    print(next(test_iter))
    print(next(test_iter))
    print(next(test_iter))
    print(next(test_iter))
    print(next(test_iter))'''
