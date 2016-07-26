# setup imports for the submodule
import os
import sys
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), '../pgoapi'))

# general use
import time
import random
# from pprint import pformat
from enum import IntEnum

# pgo api
from pgoapi import PGoApi
from pgoapi.utilities import f2i, h2f

from .models import Teams

# geography
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
    pokemen, gyms, stops, spawns = [], [], [], []
    poke_ids, fort_ids, spawn_coords = [], [], [] # for dedup check

    for lat, lng in [(d['lat'], d['lng']) for d in coords]:
        log.debug('Updating map objects around %s, %s' % (lat, lng))

        log.debug('Getting cell ids')
        cell_ids = get_cell_ids(lat, lng)
        log.debug('Cell ids are: %s' % cell_ids)

        response_dict = api.get_map_objects(latitude=f2i(lat),
                                            longitude=f2i(lng),
                                            since_timestamp_ms=[0,] * len(cell_ids),
                                            cell_id=cell_ids).call()

        now = time.time()

        if 'status' in response_dict['responses']['GET_MAP_OBJECTS'] and \
        response_dict['responses']['GET_MAP_OBJECTS']['status'] is 1:
            for cell in response_dict['responses']['GET_MAP_OBJECTS']['map_cells']:
                # log.debug('Map cell:\n\r%s', pformat(cell))

                if 'wild_pokemons' in cell:
                    for pokeman in cell['wild_pokemons']:
                        log.debug('Found a pokeman: {}'.format(pokeman))
                        if pokeman['encounter_id'] not in poke_ids:
                            pokemen.append({
                                'id': pokeman['encounter_id'],
                                'spawnpoint': pokeman['spawnpoint_id'],
                                'lat': pokeman['latitude'],
                                'lng': pokeman['longitude'],
                                'pokeid': pokeman['pokemon_data']['pokemon_id'],
                                'disappears': now + pokeman['time_till_hidden_ms'] / 1000,
                                'last_mod': pokeman['last_modified_timestamp_ms'] / 1000 # dunno what this does
                            })
                            poke_ids.append(pokeman['encounter_id'])
                        else:
                            log.debug('Not new, skipping')
                if 'forts' in cell:
                    for fort in cell['forts']:
                        log.debug('Found a fort...')
                        if fort['id'] not in fort_ids:
                            f = {
                                'id': fort['id'],
                                'lat': fort['latitude'],
                                'lng': fort['longitude'],
                                'type': FortType(fort.get('type', 0)), # gyms are type 0, but aren't listed
                                'enabled': fort['enabled'], # dunno what this does
                                'last_mod': fort['last_modified_timestamp_ms'] / 1000 # dunno what this does
                            }
                            if f['type'] is FortType.gym:
                                log.debug('Found a gym: {}'.format(fort))
                                f.update({
                                    'points': fort.get('gym_points', 0),
                                    'guard_pokeid': fort.get('guard_pokemon_id', 0),
                                    'team': Teams(fort.get('owned_by_team', 0))
                                })
                                gyms.append(f)
                            else:
                                log.debug('Found a stop: {}'.format(fort))
                                #lure info
                                if 'lure_info' in fort:
                                    f.update({
                                        'lure_active_pokeid': fort['lure_info']['active_pokemon_id'],
                                        'lure_expires': fort['lure_info']['lure_expires_timestamp_ms'] / 1000
                                    })
                                else:
                                    f.update({
                                        'lure_active_pokeid': None,
                                        'lure_expires': None
                                    })
                                stops.append(f)
                            fort_ids.append(fort['id'])
                        else:
                            log.debug('Not new, skipping')
                if 'spawn_points' in cell:
                    for spawn in cell['spawn_points']:
                        if (spawn['latitude'], spawn['longitude']) not in spawn_coords:
                            log.debug('Found a spawn: {}'.format(spawn))
                            spawns.append({
                                'lat': spawn['latitude'],
                                'lng': spawn['longitude'],
                                'decimated': False
                            })
                            spawn_coords.append((spawn['latitude'], spawn['longitude']))
                        else:
                            log.debug('Not new, skipping')
                if 'decimated_spawn_points' in cell:
                    for spawn in cell['decimated_spawn_points']:
                        if (spawn['latitude'], spawn['longitude']) not in spawn_coords:
                            log.debug('Found a spawn (decimated): {}'.format(spawn))
                            spawns.append({
                                'lat': spawn['latitude'],
                                'lng': spawn['longitude'],
                                'decimated': True
                            })
                            spawn_coords.append((spawn['latitude'], spawn['longitude']))
                        else:
                            log.debug('Not new, skipping')

        log.debug('Retrieved Pokemon: {}'.format(pokemen))
        log.debug('Retrieved gyms: {}'.format(gyms))
        log.debug('Retrieved Pokestops: {}'.format(stops))
        log.debug('Retrieved spawns (+ decimated): {}'.format(spawns))

    return pokemen, gyms, stops, spawns
