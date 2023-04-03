import json

from geopy.geocoders import Nominatim

geolocator = Nominatim(user_agent="mozilla")
location = geolocator.reverse("53.563218757860106, 10.210500290046626")
print(location.address.split(","))
print(location.address.split(",")[0].isnumeric() or location.address.split(",")[0][0].isdigit())
print((location.latitude, location.longitude))
