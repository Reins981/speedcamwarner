import json

from geopy.geocoders import Nominatim

'''geolocator = Nominatim(user_agent="mozilla")
location = geolocator.reverse("53.563218757860106, 10.210500290046626")
print(location.address.split(","))
print(location.address.split(",")[0].isnumeric() or location.address.split(",")[0][0].isdigit())
print((location.latitude, location.longitude))'''

with open("test_data.json", "r") as fp:
    content = json.load(fp)

data = content["elements"]

for element in data:
    construction_areas_dict = dict()
    lat = None
    lon = None
    if "nodes" in element:
        for node in element['nodes']:
            result_node = list(
                filter(lambda el: el['type'] == 'node' and el['id'] == node, data))
            print(result_node)
            if result_node:
                result_node = result_node[0]
                lat = result_node['lat']
                lon = result_node['lon']
            else:
                continue