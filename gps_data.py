from random import randint, uniform


class GpsTestDataGenerator(object):

    def __init__(self, max):
        self.events = list()
        self.event_index = -1
        self.startup = True
        self._fill_events(max)

    def _fill_events(self, max):
        print("Generating %d Test GPS Data...." % max)
        # London
        # start_lat = 52.520008
        # start_long = 13.404954
        # Wien
        start_lat = 51.509865
        start_long = -0.118092
        i = 0.0000010
        j = 0.0000110
        counter = 0
        bearing = randint(15, 15)
        for _ in range(max):
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
            if counter > 500:
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

    test_iter = iter(GpsTestDataGenerator(20000000))
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
