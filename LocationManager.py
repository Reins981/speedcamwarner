from jnius import autoclass, cast
from plyer import GPS
from android.runnable import run_on_ui_thread
from Logger import Logger
logger = Logger("LocationManager")

LocationManager = autoclass('android.location.LocationManager')
LocationListener = autoclass('android.location.LocationListener')
Intent = autoclass('android.content.Intent')
PendingIntent = autoclass('android.app.PendingIntent')
Context = autoclass('android.content.Context')
# Define the PythonActivity class
PythonActivity = autoclass('org.kivy.android.PythonActivity')

# Define the context object
context = PythonActivity.mActivity.getApplicationContext()


class GPSAndroidBackground(GPS):
    def __init__(self):
        self._location_manager = cast(LocationManager, context.getSystemService(Context.LOCATION_SERVICE))
        self._pending_intent = PendingIntent.getBroadcast(context, 0, Intent(context, LocationReceiver), PendingIntent.FLAG_UPDATE_CURRENT)

    def _start(self, **kwargs):
        self._location_manager.requestLocationUpdates(LocationManager.GPS_PROVIDER, 0, 0, self._pending_intent)

    def _stop(self):
        self._location_manager.removeUpdates(self._pending_intent)


class LocationReceiverBackground:
    gps_data_queue = None
    cv_gps_data = None

    @staticmethod
    @run_on_ui_thread
    def onReceive(context, intent):
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

