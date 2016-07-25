# web server
from flask import Flask, request, json, render_template

app = Flask(__name__)
map_state = {'pokemen': [], 'gyms': [], 'stops': [], 'spawns': []}
map_center = {'lat': 0, 'lng': 0} # default center for map
login = None # partial-ized function to log back in, created in main from config
update_position = None # partial-ized function to set location, created in main from config
restart_update = False # if the update_map_objects function should restart, ie. due to new position

def get_pos_by_name(location_name, proxy):
    geolocator = GoogleV3(proxies=proxy, timeout=10)
    loc = geolocator.geocode(location_name, timeout=5)

    log.info('Your given location: %s', loc.address.encode('utf-8'))
    log.info('lat/long/alt: %s %s %s', loc.latitude, loc.longitude, loc.altitude)

    return (loc.latitude, loc.longitude, loc.altitude)

@app.route('/api/map_objects')
def map_objects():
    return json.dumps(map_state)

@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve(path):
    return render_template('app.html')

if __name__ == '__main__':
    # main()
    app.run()
