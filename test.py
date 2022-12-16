from geopy.geocoders import Nominatim

geolocator = Nominatim(user_agent="mozilla")
location = geolocator.reverse("53.58833543591823, 9.823774028870371")
print(location.address.split(","))
print(location.address.split(",")[0].isnumeric())
print((location.latitude, location.longitude))
