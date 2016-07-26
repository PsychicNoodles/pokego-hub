import os
from urllib.parse import urlparse
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base

Session = sessionmaker()

Base = declarative_base()

# urlparse.uses_netloc.append('postgres')
url = urlparse(os.environ['DATABASE_URL'])
dburl = 'postgresql+psycopg2://%s:%s@%s:%s/%s' % (url.username, url.password,
                                                  url.hostname, url.port, url.path[1:])

engine = create_engine(dburl, echo=True)
Session.configure(bind=engine)

db_session = Session()

def init_db():
    Base.metadata.create_all(engine)
