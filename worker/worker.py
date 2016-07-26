import psycopg2
import os
import logging
from datetime import datetime
from models import Pokemon, Pokestop, Gym, Spawn
from database import init_db, db_session
from api import get_map_objects

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s [%(module)10s] [%(levelname)5s] %(message)s')
logging.getLogger('requests').setLevel(logging.WARNING)
logging.getLogger('pgoapi').setLevel(logging.INFO)
logging.getLogger('rpc_api').setLevel(logging.INFO)

log = logging.getLogger(__name__)
log.setLevel(logging.INFO)

# logging.getLogger('requests').setLevel(logging.DEBUG)
# logging.getLogger('pgoapi').setLevel(logging.DEBUG)
# logging.getLogger('rpc_api').setLevel(logging.DEBUG)
# log.setLevel(logging.DEBUG)

auth, username, password = os.environ['AUTH'], os.environ['USERNAME'], os.environ['PASSWORD']

def run():
    pokemon, gyms, stops, spawns = get_map_objects(log, auth, username, password)
    for poke in pokemon:
        p = Pokemon(encounter_id=poke['id'],
                    last_modified=datetime.fromtimestamp(poke['last_mod']),
                    lat=poke['lat'], lng=poke['lng'], poke_id=poke['pokeid'],
                    spawn_id=poke['spawnpoint'],
                    disappears=datetime.fromtimestamp(poke['disappears']))
        db_session.add(p)
    for gym in gyms:
        g = Gym(fort_id=gym['id'], last_modified=datetime.fromtimestamp(gym['last_mod']),
                lat=gym['lat'], lng=gym['lng'], enabled=gym['enabled'],
                points=gym['points'], guard_poke_id=gym['guard_pokeid'], team=gym['team'].name)
        db_session.add(g)
    for stop in stops:
        s = Pokestop(fort_id=stop['id'], last_modified=datetime.fromtimestamp(stop['last_mod']),
                     lat=stop['lat'], lng=stop['lng'], enabled=stop['enabled'],
                     lure_active_poke_id=stop['lure_active_pokeid'],
                     lure_expires=(datetime.fromtimestamp(stop['lure_expires'])
                                   if stop['lure_expires'] != None else None))
        db_session.add(s)
    for spawn in spawns:
        s = Spawn(lat=spawn['lat'], lng=spawn['lng'], decimated=spawn['decimated'])
        db_session.add(s)
    db_session.commit()
    log.info('Successfully updated %s Pokemon, %s gyms, %s Pokestops, and %s spawns' % (
        len(pokemon), len(gyms), len(stops), len(spawns)
    ))

if __name__ == '__main__':
    init_db()
    run()
