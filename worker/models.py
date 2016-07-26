import enum
from sqlalchemy import Column, BigInteger, SmallInteger, Integer, DateTime, \
                       String, Enum, Boolean
from geoalchemy2 import Geometry
from database import Base

class Teams(enum.IntEnum):
    neutral = 0
    blue = 1
    red = 2
    yellow = 3

class Pokemon(Base):
    __tablename__ = 'pokemon'

    id = Column(Integer, primary_key=True)
    encounter_id = Column(BigInteger)
    last_modified = Column(DateTime)
    position = Column(Geometry('POINT'))
    poke_id = Column(SmallInteger)
    spawn_id = Column(String)
    disappears = Column(DateTime)

    def __repr__(self):
        return "<Pokemon(encounter_id='%s', last_modified='%s', lat='%s', " + \
                    "lng='%s', poke_id='%s', spawn_id='%s', disappears='%s'" % (
                    self.encounter_id, self.last_modified.timestamp(),
                    self.position.y, self.position.x, self.poke_id, self.spawn_id,
                    self.disappears.timestamp())

class Fort(object): # abstract type
    id = Column(Integer, primary_key=True)
    fort_id = Column(String)
    last_modified = Column(DateTime)
    position = Column(Geometry('POINT'))
    enabled = Column(Boolean)

class Gym(Fort, Base):
    __tablename__ = 'gym'

    points = Column(Integer)
    guard_poke_id = Column(SmallInteger)
    team = Column('team', Enum([e.value for e in Teams], name='teams'))

class Pokestop(Fort, Base):
    __tablename__ = 'pokestop'

class Spawn(Base):
    __tablename__ = 'spawn'

    id = Column(Integer, primary_key=True)
    position = Column(Geometry('POINTS'))
    decimated = Column(Boolean)
