# setup imports for the submodule
import os
import sys
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "pgoapi"))

# general use
import logging
import argparse
import time
import json
import collections
import random
from pprint import pformat
from functools import partial
from enum import IntEnum
from copy import deepcopy

# worker thread
from threading import Timer, Thread
from queue import Queue

# web server
from flask import Flask, request

# pgo api
from pgoapi import PGoApi
from pgoapi.utilities import f2i, h2f

# geography
from google.protobuf.internal import encoder
from geopy.geocoders import GoogleV3
from s2sphere import CellId, LatLng

log = logging.getLogger(__name__)

app = Flask(__name__)
map_state = {'pokemen': [], 'gyms': [], 'stops': [], 'spawns': []}
map_center = {'lat': 0, 'lng': 0} # default center for map
login = None # partial-ized function to log back in, created in main from config
update_position = None # partial-ized function to set location, created in main from config
restart_update = False # if the update_map_objects function should restart, ie. due to new position

class FortType(IntEnum):
    gym = 0
    stop = 1

class Teams(IntEnum):
    neutral = 0
    blue = 1
    red = 2
    yellow = 3

def get_pos_by_name(location_name, proxy):
    geolocator = GoogleV3(proxies=proxy, timeout=10)
    loc = geolocator.geocode(location_name, timeout=5)

    log.info('Your given location: %s', loc.address.encode('utf-8'))
    log.info('lat/long/alt: %s %s %s', loc.latitude, loc.longitude, loc.altitude)

    return (loc.latitude, loc.longitude, loc.altitude)

def get_cell_ids(lat, long, radius = 10):
    origin = CellId.from_lat_lng(LatLng.from_degrees(lat, long)).parent(15)
    walk = [origin.id()]
    right = origin.next()
    left = origin.prev()

    # Search around provided radius
    for i in range(radius):
        walk.append(right.id())
        walk.append(left.id())
        right = right.next()
        left = left.prev()

    # Return everything
    return sorted(walk)

def encode(cellid):
    output = []
    encoder._VarintEncoder()(output.append, cellid)
    return ''.join(output)

def init_config():
    parser = argparse.ArgumentParser()
    config_file = "config.json"

    # If config file exists, load variables from json
    load   = {}
    if os.path.isfile(config_file):
        with open(config_file) as data:
            load.update(json.load(data))

    # Read passed in Arguments
    required = lambda x: not x in load
    parser.add_argument("-a", "--auth_service", help="Auth Service ('ptc' or 'google')",
        required=required("auth_service"))
    parser.add_argument("-u", "--username", help="Username", required=required("username"))
    parser.add_argument("-p", "--password", help="Password", required=required("password"))
    parser.add_argument("-l", "--location", help="Location", required=required("location"))
    parser.add_argument("-x", "--proxy", help="HTTP Proxy")
    parser.add_argument("-xs", "--proxy-https", help="HTTPS Proxy")
    parser.add_argument("-i", "--interval", help="Update Interval")
    parser.add_argument("-d", "--debug", help="Debug Mode", action='store_true')
    parser.add_argument("-t", "--test", help="Only parse the specified location", action='store_true')
    parser.set_defaults(debug=False, test=False, interval=30)
    config = parser.parse_args()

    # Passed in arguments shoud trump
    for key in config.__dict__:
        if key in load and config.__dict__[key] == None:
            config.__dict__[key] = load[key]

    if config.auth_service not in ['ptc', 'google']:
      log.error("Invalid Auth service specified! ('ptc' or 'google')")
      return None

    return config

def main():
    global position, login, update_position

    # setup logging
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s [%(module)10s] [%(levelname)5s] %(message)s')
    logging.getLogger("requests").setLevel(logging.WARNING)
    logging.getLogger("pgoapi").setLevel(logging.INFO)
    logging.getLogger("rpc_api").setLevel(logging.INFO)
    logging.getLogger("geopy").setLevel(logging.DEBUG)

    # logger and level for app
    log.setLevel(logging.INFO)

    config = init_config()

    if config.debug:
        logging.getLogger("requests").setLevel(logging.DEBUG)
        logging.getLogger("pgoapi").setLevel(logging.DEBUG)
        logging.getLogger("rpc_api").setLevel(logging.DEBUG)
        log.setLevel(logging.DEBUG)

    log.debug("config: %s" % config)

    if config.proxy: proxy = {'http': config.proxy}
    elif config.proxy_https: proxy = {'https': config.proxy_https}
    else: proxy = None
    log.debug("proxy is %s" % proxy)

    log.debug("initializing api")
    api = PGoApi()

    def base_update_position(proxy, api, location):
        global map_center

        log.debug("getting location for %s", location)
        position = get_pos_by_name(location, proxy)
        log.debug("position is %f, %f at %f altitude", position[0], position[1], position[2])

        log.debug("setting map center")
        map_center = {'lat': position[0], 'lng': position[1]}

        log.debug("setting position")
        api.set_position(*position)

    update_position = partial(base_update_position, config.proxy, api)

    update_position(config.location)

    log.debug("partil-izing login")
    def base_login(auth, username, password):
        log.debug("logging in")
        return api.login(auth, username, password)

    login = partial(base_login, config.auth_service, config.username, config.password)

    if not login():
        log.info("failed to login, exiting")
        sys.exit(1)
    else:
        Thread(target=update_map_objects, args=(config.interval, api),
               kwargs={'update_all': True}).start()

def generate_spiral(starting_lat, starting_lng, step_size, step_limit):
    coords = [{'lat': starting_lat, 'lng': starting_lng}]
    steps,x,y,d,m = 1, 0, 0, 1, 1
    rlow = 0.0
    rhigh = 0.0005

    while steps < step_limit:
        while 2 * x * d < m and steps < step_limit:
            x = x + d
            steps += 1
            lat = x * step_size + starting_lat + random.uniform(rlow, rhigh)
            lng = y * step_size + starting_lng + random.uniform(rlow, rhigh)
            coords.append({'lat': lat, 'lng': lng})
        while 2 * y * d < m and steps < step_limit:
            y = y + d
            steps += 1
            lat = x * step_size + starting_lat + random.uniform(rlow, rhigh)
            lng = y * step_size + starting_lng + random.uniform(rlow, rhigh)
            coords.append({'lat': lat, 'lng': lng})

        d = -1 * d
        m = m + 1
    return coords

# If update_all is False, only update and drop stale Pokemon
# coords should be an iterable of dicts with 'lat' and 'lng'
def update_map_objects(update_delay, api, update_all=False, coords=None):
    global map_state

    def should_return(): # check if restart requested and handles starting next run
        if restart_update:
            Thread(target=update_map_objects, args=(update_delay, api),
                   kwargs={'update_all': True}).start()
            return True
        else: return False

    if coords is None:
        coords = generate_spiral(map_center['lat'], map_center['lng'], 0.0015, 49)

    state = deepcopy(map_state) # atomically replaces state at the end of update

    for lat, lng in [(d['lat'], d['lng']) for d in coords]:
        log.debug("updating map objects around %s, %s" % (lat, lng))

        log.debug("getting cell ids")
        cell_ids = get_cell_ids(map_center['lat'], map_center['lng'])
        log.debug("cell ids are: %s" % cell_ids)

        response_dict = api.get_map_objects(latitude=f2i(map_center['lat']),
                                            longitude=f2i(map_center['lng']),
                                            since_timestamp_ms=[0,] * len(cell_ids),
                                            cell_id=cell_ids).call()

        pokemen, gyms, stops, spawns = [], [], [], []
        now = time.time()

        if 'status' in response_dict['responses']['GET_MAP_OBJECTS'] and \
        response_dict['responses']['GET_MAP_OBJECTS']['status'] is 1:
            for cell in response_dict['responses']['GET_MAP_OBJECTS']['map_cells']:
                # log.debug("map cell %s" % pformat(cell))
                if should_return(): return

                if 'wild_pokemons' in cell:
                    for pokeman in cell['wild_pokemons']:
                        log.debug("adding pokeman")
                        pokemen.append({
                            'id': pokeman['encounter_id'],
                            'spawnpoint': pokeman['spawnpoint_id'],
                            'lat': pokeman['latitude'],
                            'lng': pokeman['longitude'],
                            'pokeid': pokeman['pokemon_data']['pokemon_id'],
                            'disappears': now + pokeman['time_till_hidden_ms'] / 1000,
                            'last_mod': pokeman['last_modified_timestamp_ms'] # dunno what this does
                        })
                if update_all:
                    if 'forts' in cell:
                        for fort in cell['forts']:
                            f = {
                                'id': fort['id'],
                                'lat': fort['latitude'],
                                'lng': fort['longitude'],
                                'type': FortType(fort.get('type', 0)), # gyms are type 0, but aren't listed
                                'enabled': fort['enabled'], # dunno what this does
                                'last_mod': fort['last_modified_timestamp_ms'] # dunno what this does
                            }
                            if f['type'] is FortType.gym:
                                f.update({
                                    'points': fort['gym_points'],
                                    'guard_pokeid': fort['guard_pokemon_id'],
                                    'team': Teams(fort.get('owned_by_team', 0))
                                })
                                log.debug("adding gym")
                                gyms.append(f)
                            else:
                                #lure info
                                log.debug("adding stop")
                                stops.append(f)
                    if 'spawn_points' in cell:
                        for spawn in cell['spawn_points']:
                            log.debug("adding spawn")
                            spawns.append({
                                'lat': spawn['latitude'],
                                'lng': spawn['longitude'],
                                'decimated': False
                            })
                    if 'decimated_spawn_points' in cell:
                        for spawn in cell['decimated_spawn_points']:
                            log.debug("adding spawn (decimated)")
                            spawns.append({
                                'lat': spawn['latitude'],
                                'lng': spawn['longitude'],
                                'decimated': True
                            })

        # state update
        log.debug('Retrieved Pokemon: {}'.format(pokemen))
        log.debug('Popped stale Pokemon: {}'.format([state['pokemen'].pop(ind) for ind, p
                                                     in enumerate(state['pokemen'])
                                                     if p['disappears'] < now]))
        log.debug('Retrieved gyms: {}'.format(gyms))
        log.debug('Retrieved Pokestops: {}'.format(stops))
        log.debug('Retrieved spawns (+ decimated): {}'.format(spawns))

        def dedup_by(old, new, keys):
            old_by_key = [(o[k] for k in keys) for o in old]
            return [n for n in new if not (n[k] for k in keys) in old_by_key]

        state['pokemen'].extend(dedup_by(state, pokemen, ['id']))
        state['gyms'].extend(dedup_by(state, gyms, ['id']))
        state['stops'].extend(dedup_by(state, stops, ['id']))
        state['spawns'].extend(dedup_by(state, spawns, ['lat', 'lng']))

        log.debug('New state: {}'.format(state))

    log.debug("atomically replacing state")
    map_state = state

    log.info('Map object update complete, new state:\n\r{}'.format(pformat(map_state)))

    log.debug('scheduling next update in {} secs (at {})'.format(update_delay, now * 1000))

    Timer(update_delay, update_map_objects, args=(update_delay, api)).start()

    # def removeDeci(d):
    #     d.pop('decimated')
    #     return d
    # print('All spawns are unique: ', len([dict(y) for y in set(tuple(x.items()) for x in map(removeDeci, spawns))]) == len(spawns))

@app.route('/api/map_objects')
def map_objects():
    # TODO: serve this
    return

@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve():
    return render_template('app.html')

if __name__ == '__main__':
    main()
    # app.run()
