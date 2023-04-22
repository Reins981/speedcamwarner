from jnius import autoclass, cast, java_method
from android.runnable import run_on_ui_thread
from plyer.platforms.android.gps import AndroidGPS
from Logger import Logger
logger = Logger("LocationManager")

LocationManager = autoclass('android.location.LocationManager')
LocationListener = autoclass('android.location.LocationListener')
Intent = autoclass('android.content.Intent')
IntentFilter = autoclass('android.content.IntentFilter')
PendingIntent = autoclass('android.app.PendingIntent')
Context = autoclass('android.content.Context')
# Define the PythonActivity class
PythonActivity = autoclass('org.kivy.android.PythonActivity')
BroadcastReceiver = autoclass('android.content.BroadcastReceiver')

# Define the context object
context = PythonActivity.mActivity.getApplicationContext()


class GPSAndroidBackground(AndroidGPS):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._location_manager = cast(LocationManager, context.getSystemService(Context.LOCATION_SERVICE))
        self._location_listener = PendingIntent.getBroadcast(context, 0, Intent(context, LocationReceiverBackground), PendingIntent.FLAG_UPDATE_CURRENT)

    def _start(self, minTime=1000, minDistance=1):
        logger.print_log_line("Start requestLocationUpdates..")
        self._location_manager.requestLocationUpdates(LocationManager.GPS_PROVIDER,
                                                      minTime, minDistance, self._location_listener)

    def _stop(self):
        self._location_manager.removeUpdates(self._location_listener)

    def _configure(self):
        pass


class LocationReceiverBackground(BroadcastReceiver):
    __javaclass__ = 'android/content/BroadcastReceiver'
    gps_data_queue = None
    cv_gps_data = None

    def __init__(self):
        super().__init__()

    @java_method('(Landroid/content/Intent;)V')
    def onReceive(self, intent):
        logger.print_log_line("onReceive called")
        location = intent.getExtras().get(LocationManager.KEY_LOCATION_CHANGED)
        if location:
            event = dict()
            event['data'] = {}
            event['data']['gps'] = {}
            lat = location.getLatitude()
            lon = location.getLongitude()
            speed = location.getSpeed()  # in meters/second
            accuracy = location.getAccuracy()  # in meters
            bearing = location.getBearing()

            event['data']['gps'].update(
                {'latitude': lat,
                 'longitude': lon,
                 'speed': speed,
                 'bearing': bearing,
                 'accuracy': accuracy})
            if LocationReceiverBackground.gps_data_queue and \
                    LocationReceiverBackground.cv_gps_data:
                LocationReceiverBackground.gps_data_queue.produce(
                    LocationReceiverBackground.cv_gps_data, {'event': event})

