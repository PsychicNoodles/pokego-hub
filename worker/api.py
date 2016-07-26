# setup imports for the submodule
import os
import sys
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), '../pgoapi'))

# general use
import argparse
import time
import collections
import random
from pprint import pformat
from functools import partial
from enum import IntEnum
from copy import deepcopy

# pgo api
from pgoapi import PGoApi
from pgoapi.utilities import f2i, h2f

from models import Teams

# geography
from google.protobuf.internal import encoder
from geopy.geocoders import GoogleV3
from s2sphere import CellId, LatLng

# Grinnell coords
lat = 41.749714
lng = -92.719516

class FortType(IntEnum):
    gym = 0
    stop = 1

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

def get_map_objects(log, auth, username, password):
    log.debug('Initializing api')
    api = PGoApi()

    log.debug('Setting map center to above position')

    log.debug('Setting api position')
    api.set_position(lat, lng, 0)

    log.debug('Logging in with %s auth as %s (password is %s chars long)' % (auth, username,
                                                                             len(password)))
    if not api.login(auth, username, password):
        log.info('An error occurred while logging in, server is probably down')
        return

    return scan(api, generate_spiral(lat, lng, 0.0015, 49), log)

def scan(api, coords, log):
    for lat, lng in [(d['lat'], d['lng']) for d in coords]:
        log.debug('Updating map objects around %s, %s' % (lat, lng))

        log.debug('Getting cell ids')
        cell_ids = get_cell_ids(lat, lng)
        log.debug('Cell ids are: %s' % cell_ids)

        response_dict = api.get_map_objects(latitude=f2i(lat),
                                            longitude=f2i(lng),
                                            since_timestamp_ms=[0,] * len(cell_ids),
                                            cell_id=cell_ids).call()

        pokemen, gyms, stops, spawns = [], [], [], []
        now = time.time()

        if 'status' in response_dict['responses']['GET_MAP_OBJECTS'] and \
        response_dict['responses']['GET_MAP_OBJECTS']['status'] is 1:
            for cell in response_dict['responses']['GET_MAP_OBJECTS']['map_cells']:
                # log.debug('Map cell:\n\r%s', pformat(cell))

                if 'wild_pokemons' in cell:
                    for pokeman in cell['wild_pokemons']:
                        log.debug('Found a pokeman: {}'.format(pokeman))
                        pokemen.append({
                            'id': pokeman['encounter_id'],
                            'spawnpoint': pokeman['spawnpoint_id'],
                            'lat': pokeman['latitude'],
                            'lng': pokeman['longitude'],
                            'pokeid': pokeman['pokemon_data']['pokemon_id'],
                            'disappears': now + pokeman['time_till_hidden_ms'] / 1000,
                            'last_mod': pokeman['last_modified_timestamp_ms'] / 1000 # dunno what this does
                        })
                if 'forts' in cell:
                    for fort in cell['forts']:
                        f = {
                            'id': fort['id'],
                            'lat': fort['latitude'],
                            'lng': fort['longitude'],
                            'type': FortType(fort.get('type', 0)), # gyms are type 0, but aren't listed
                            'enabled': fort['enabled'], # dunno what this does
                            'last_mod': fort['last_modified_timestamp_ms'] / 1000 # dunno what this does
                        }
                        if f['type'] is FortType.gym:
                            f.update({
                                'points': fort.get('gym_points', 0),
                                'guard_pokeid': fort.get('guard_pokemon_id', 0),
                                'team': Teams(fort.get('owned_by_team', 0))
                            })
                            log.debug('Found a gym: {}'.format(fort))
                            gyms.append(f)
                        else:
                            #lure info
                            log.debug('Found a stop: {}'.format(fort))
                            stops.append(f)
                if 'spawn_points' in cell:
                    for spawn in cell['spawn_points']:
                        log.debug('Found a spawn: {}'.format(spawn))
                        spawns.append({
                            'lat': spawn['latitude'],
                            'lng': spawn['longitude'],
                            'decimated': False
                        })
                if 'decimated_spawn_points' in cell:
                    for spawn in cell['decimated_spawn_points']:
                        log.debug('Found a spawn (decimated): {}'.format(spawn))
                        spawns.append({
                            'lat': spawn['latitude'],
                            'lng': spawn['longitude'],
                            'decimated': True
                        })

        log.debug('Retrieved Pokemon: {}'.format(pokemen))
        log.debug('Retrieved gyms: {}'.format(gyms))
        log.debug('Retrieved Pokestops: {}'.format(stops))
        log.debug('Retrieved spawns (+ decimated): {}'.format(spawns))

    return pokemen, gyms, stops, spawns
