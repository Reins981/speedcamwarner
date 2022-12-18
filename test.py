from geopy.geocoders import Nominatim

geolocator = Nominatim(user_agent="mozilla")
lat = 53.563218757860106
long = 10.210500290046626
coords = str(lat) + " " + str(long)
location = geolocator.reverse(coords)
print(location.address.split(","))
print(location.address.split(",")[0].isnumeric() or location.address.split(",")[0][0].isdigit())
print((location.latitude, location.longitude))
