import enum
from sqlalchemy import Column, SmallInteger, Integer, Float, DateTime, \
                       String, Enum, Boolean
from .database import Base
from datetime import datetime

class Teams(enum.IntEnum):
    neutral = 0
    blue = 1
    red = 2
    yellow = 3

class TimestampMixin(object):
    created_at = Column(DateTime, default=datetime.now(), nullable=False)
    updated_at = Column(DateTime, default=datetime.now(), onupdate=datetime.now(), nullable=False)

class Pokemon(TimestampMixin, Base):
    __tablename__ = 'pokemon'

    id = Column(Integer, primary_key=True)
    encounter_id = Column(String)
    last_modified = Column(DateTime)
    lat = Column(Float)
    lng = Column(Float)
    poke_id = Column(SmallInteger)
    spawn_id = Column(String)
    disappears = Column(DateTime)

    def __repr__(self):
        return "<Pokemon(encounter_id='%s', last_modified='%s', lat='%s', " + \
                    "lng='%s', poke_id='%s', spawn_id='%s', disappears='%s')" % (
                    self.encounter_id, self.last_modified.timestamp(), self.lat,
                    self.lng, self.poke_id, self.spawn_id, self.disappears.timestamp())

class Fort(TimestampMixin): # abstract type
    id = Column(Integer, primary_key=True)
    fort_id = Column(String)
    last_modified = Column(DateTime)
    lat = Column(Float)
    lng = Column(Float)
    enabled = Column(Boolean)

class Gym(Fort, Base):
    __tablename__ = 'gym'

    points = Column(Integer)
    guard_poke_id = Column(SmallInteger)
    team = Column(Enum(*[e.name for e in Teams], name='teams'))

    def __repr__(self):
        return "<Gym(ford_id='%s', last_modified='%s', lat='%s', lng='%s', " + \
                    "enabled='%s', points='%s', guard_poke_id='%s', team='%s')" % (
                    self.fort_id, self.last_modified, self.lat, self.lng,
                    self.enabled, self.points, self.guard_poke_id, self.team)

class Pokestop(Fort, Base):
    __tablename__ = 'pokestop'

    lure_active_poke_id = Column(SmallInteger)
    lure_expires = Column(DateTime)

    def __repr__(self):
        return "<Gym(ford_id='%s', last_modified='%s', lat='%s', lng='%s', " + \
                    "enabled='%s')" % (self.fort_id, self.last_modified, self.lat,
                    self.lng, self.enabled)

class Spawn(TimestampMixin, Base):
    __tablename__ = 'spawn'

    id = Column(Integer, primary_key=True)
    lat = Column(Float)
    lng = Column(Float)
    decimated = Column(Boolean)

    def __repr__(self):
        return "<Spawn(lat='%s', lng='%s', decimated='%s')" % (self.lat, self.lng,
                    self.decimated)
