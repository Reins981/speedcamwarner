from geopy.geocoders import Nominatim

geolocator = Nominatim(user_agent="mozilla")
location = geolocator.reverse("52.36584558119477, 9.707620046994666")
print(location.address.split(","))
print((location.latitude, location.longitude))
