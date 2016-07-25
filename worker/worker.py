import psycopg2
import os
import logging
from urllib.parse import urlparse
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models import Pokemon, Pokestop, Gym, Spawn
from api import get_map_objects

# from apscheduler.schedulers.blocking import BlockingScheduler

Session = sessionmaker()

Base = declarative_base()

# urlparse.uses_netloc.append('postgres')
url = urlparse(os.environ['DATABASE_URL'])
dburl = 'postgresql+psycopg2://%s:%s@%s:%s/%s' % (url.username, url.password,
                                                  url.hostname, url.port, url.path[1:])

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s [%(module)10s] [%(levelname)5s] %(message)s')
# logging.getLogger('requests').setLevel(logging.WARNING)
# logging.getLogger('pgoapi').setLevel(logging.INFO)
# logging.getLogger('rpc_api').setLevel(logging.INFO)

log = logging.getLogger(__name__)
# log.setLevel(logging.INFO)

logging.getLogger('requests').setLevel(logging.DEBUG)
logging.getLogger('pgoapi').setLevel(logging.DEBUG)
logging.getLogger('rpc_api').setLevel(logging.DEBUG)
log.setLevel(logging.DEBUG)

auth, username, password = os.environ['AUTH'], os.environ['USERNAME'], os.environ['PASSWORD']

def run():
    pokemon, gyms, stops, spawns = get_map_objects(log, auth, username, password)
    session = Session()
    for poke in pokemon:
        p = Pokemon(encounter_id=poke['id'], last_modified=poke['last_mod'],
                    position='POINT({} {})'.format(poke['lng'], poke['lat']),
                    poke_id=poke['pokeid'], spawn_id=poke['spawnpoint'],
                    disappears=datetime.fromtimestamp(datetime.fromtimestamp(poke['disappears'])))
        session.add(p)
    for gym in gyms:
        g = Gym(fort_id=gym['id'], last_modified=gym['last_mod'],
                position='POINT({} {})'.format(gym['lng'], gym['lat']),
                enabled=gym['enabled'], points=gym['points'],
                guard_poke_id=gym['guard_pokeid'], team=gym['team'])
        session.add(g)
    for stop in stops:
        s = Stop(fort_id=stop['id'], last_modified=stop['last_mod'],
                 position='POINT({} {})'.format(gym['lng'], gym['lat']),
                 enabled=gym['enabled'])
        session.add(s)
    for spawn in spawns:
        s = Spawn(position='POINT({} {})'.format(spawn['lng'], spawn['lat']),
                  decimated=spawn['decimated'])
        session.add(s)
    session.commit()

def init_db():
    Base.metadata.create_all(engine)

if __name__ == '__main__':
    engine = create_engine(dburl, echo=True)
    Session.configure(bind=engine)

    # scheduler = BlockingScheduler()
    # scheduler.add_jobstore('sqlalchemy', url=url)

    run()
