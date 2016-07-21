import os
import sys
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "pgoapi"))

import logging
import argparse
import time
import json
from enum import IntEnum

from pgoapi import PGoApi
from pgoapi.utilities import f2i, h2f

from google.protobuf.internal import encoder
from geopy.geocoders import GoogleV3
from s2sphere import CellId, LatLng

log = logging.getLogger(__name__)

class FortType(IntEnum):
    gym = 0
    stop = 1

class Teams(IntEnum):
    neutral = 0
    blue = 1
    red = 2
    yellow = 3

def get_pos_by_name(location_name, proxy):
    geolocator = GoogleV3(proxies=proxy, timeout=5)
    loc = geolocator.geocode(location_name)

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
    parser.add_argument("-d", "--debug", help="Debug Mode", action='store_true')
    parser.add_argument("-t", "--test", help="Only parse the specified location", action='store_true')
    parser.set_defaults(DEBUG=False, TEST=False)
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
    # log format
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

    log.debug("getting location for %s", config.location)
    position = get_pos_by_name(config.location, proxy)
    log.debug("location is %f, %f at %f altitude", position[0], position[1], position[2])

    log.debug("initializing api")
    api = PGoApi()

    log.debug("setting position")
    api.set_position(*position)

    log.debug("logging in")
    if not api.login(config.auth_service, config.username, config.password):
        log.info("failed to login, exiting")
        return

    log.debug("getting cell ids")
    cell_ids = get_cell_ids(position[0], position[1])
    log.debug("cell ids are: %s" % cell_ids)

    response = api.get_player() \
                  .get_map_objects(latitude=f2i(position[0]), longitude=f2i(position[1]),
                                   since_timestamp_ms=[0,] * len(cell_ids),
                                   cell_id=cell_ids) \
                  .call()

    pokemen, gyms, stops, spawns = [], [], [], []
    if 'status' in response['responses']['GET_MAP_OBJECTS'] and \
    response['responses']['GET_MAP_OBJECTS']['status'] is 1:
        for cell in response['responses']['GET_MAP_OBJECTS']['map_cells']:
            if 'wild_pokemons' in cell:
                for pokeman in cell['wild_pokemons']:
                    pokemen.append({
                        'id': pokeman['encounter_id'],
                        'spawnpoint': pokeman['spawnpoint_id'],
                        'lat': pokeman['latitude'],
                        'lng': pokeman['longitude'],
                        'pokeid': pokeman['pokemon_data']['pokemon_id'],
                        'disappears': time.time() + pokeman['time_till_hidden_ms'] / 1000,
                        'last_mod': pokeman['last_modified_timestamp_ms'] # dunno what this does
                    })
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
                        gyms.append(f)
                    else:
                        stops.append(f)
            if 'spawn_points' in cell:
                for spawn in cell['spawn_points']:
                    spawns.append({
                        'lat': spawn['latitude'],
                        'lng': spawn['longitude'],
                        'decimated': False
                    })
            if 'decimated_spawn_points' in cell:
                for spawn in cell['decimated_spawn_points']:
                    spawns.append({
                        'lat': spawn['latitude'],
                        'lng': spawn['longitude'],
                        'decimated': True
                    })
    print('Pokemen: ', pokemen)
    print('Gyms: ', gyms)
    print('Stops: ', stops)
    print('Spawns: ', spawns)

    # def removeDeci(d):
    #     d.pop('decimated')
    #     return d
    # print('All spawns are unique: ', len([dict(y) for y in set(tuple(x.items()) for x in map(removeDeci, spawns))]) == len(spawns))


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

if __name__ == '__main__':
    main()
