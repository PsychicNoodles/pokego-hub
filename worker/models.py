import enum
from sqlalchemy import Column, SmallInteger, Integer, Float, DateTime, \
                       String, Enum, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from .database import Base
from datetime import datetime

class Teams(enum.IntEnum):
    neutral = 0
    blue = 1
    red = 2
    yellow = 3

class FortType(enum.Enum):
    gym = 0
    stop = 1

class TimestampMixin(object):
    created_at = Column(DateTime, default=datetime.now(), nullable=False)
    updated_at = Column(DateTime, default=datetime.now(), onupdate=datetime.now(), nullable=False)

class Pokemon(TimestampMixin, Base):
    __tablename__ = 'pokemon'

    id = Column(Integer, primary_key=True)
    encounter_id = Column(String)
    last_modified = Column(DateTime)
    spawn_id = Column(Integer, ForeignKey('spawn.id'))
    spawn = relationship('Spawn', backref='pokemon')
    poke_id = Column(SmallInteger)
    disappears = Column(DateTime)

    def __repr__(self):
        return ("<Pokemon(encounter_id='{}', last_modified='{}', spawn_id='{}', " + \
                    "poke_id='{}', disappears='{}')>").format(
                        self.encounter_id, self.last_modified.timestamp(), self.spawn_id,
                        self.poke_id, self.disappears.timestamp()
                    )

class FortTypeInterface(TimestampMixin, Base):
    discriminator = Column(Enum(*[e.name for e in FortTypes], name='fort_types'))

    __mapper_args__ = {'polymorphic_on': discriminator}

class Fort(TimestampMixin):
    # a static item, only created/modified if a new fort appears or the coords change with the same id
    # all data unique to gym vs pokestop is a status
    __tablename__ = 'fort'

    id = Column(Integer, primary_key=True)
    fort_id = Column(String)
    lat = Column(Float)
    lng = Column(Float)
    statuses = relationship('Status', backref='fort')

    def __repr__(self):
        return "<Fort(fort_id='{}', lat='{}', lng='{}')>".format(
                    self.fort_id, self.lat, self.lng
                )

class Status(TimestampMixin, Base):
    __tablename__ = 'status'

    id = Column(Integer, primary_key=True)
    discriminator = Column(Enum(*[e.name for e in FortType]))
    __mapper_args__ = {'polymorphic_on': discriminator}

    def __repr__(self):
        return "<Status(discriminator='{}')>".format(self.discriminator)

class GymStatus(TimestampMixin, Base):
    __tablename__ = 'gymstatus'

    id = Column(Integer, ForeignKey('status.id'), primary_key=True)
    points = Column(Integer)
    guard_poke_id = Column(SmallInteger)
    team = Column(Enum(*[e.name for e in Teams], name='teams'))

    __mapper_args__ = {'polymorphic_identity': FortType.gym.name}

    def __repr__(self):
        return "<GymStatus(points='{}', guard_poke_id='{}', team='{}')>".format(
                    self.points, self.guard_poke_id, self.team
                )

class PokestopStatus(TimestampMixin, Base):
    __tablename__ = 'pokestopstatus'

    id = Column(Integer, Foreignkey('status.id'), primary_key=True)
    lure_active_poke_id = Column(SmallInteger)
    lure_expires = Column(DateTime)

    __mapper_args__ = {'polymorphic_identity': FortType.stop.name}

    def __repr__(self):
        return "<PokestopStatus(lure_active_poke_id='{}', lure_expires='{}')>".format(
                    self.lure_active_poke_id, self.lure_expires
                )

class Spawn(TimestampMixin, Base):
    __tablename__ = 'spawn'

    id = Column(Integer, primary_key=True)
    lat = Column(Float)
    lng = Column(Float)

    def __repr__(self):
        return "<Spawn(lat='{}', lng='{}')>".format(self.lat, self.lng)
