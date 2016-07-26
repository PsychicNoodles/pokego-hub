# general use

from datetime import datetime

# web server
from flask import Flask, request, json, render_template

# database
from worker.database import create_session
from worker.models import Pokemon, Pokestop, Gym, Spawn
from sqlalchemy.orm import class_mapper

app = Flask(__name__)

# from http://stackoverflow.com/a/14929005
def serialize(model):
    cols = [c.key for c in class_mapper(model.__class__).columns]
    return dict((c, getattr(model, c)) for c in cols)

def fmt_map_objects():
    session = create_session()
    # it is assumed that the database tables only list map objects in the relevant area
    # pokemon = [serialize(p) for p in session.query(Pokemon).distinct()
    #                                                        .filter(Pokemon.disappears > datetime.now())
    #                                                        .order_by(Pokemon.created_at.desc())]
    # gyms = [serialize(g) for g in session.query(Gym).distinct()
    #                                                 .order_by(Gym.created_at.desc())]
    # stops = [serialize(s) for s in session.query(Pokestop).distinct()
    #                                                       .order_by(Pokestop.created_at.desc())]
    # spawns = [serialize(s) for s in session.query(Spawn).distinct()
    #                                                     .order_by(Spawn.created_at.desc())]
    # return json.dumps({'pokemon': pokemon, 'gyms': gyms, 'stops': stops, 'spawns': spawns})
    return json.dumps({'result': [serialize(p) for p in session.query(Pokemon)]})

@app.route('/api/map_objects')
def map_objects():
    return json.dumps(fmt_map_objects())

@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve(path):
    return render_template('app.html')

if __name__ == '__main__':
    app.run()
