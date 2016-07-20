import os
import sys
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "pgoapi"))

import logging
import argparse
import time
import json

from pgoapi import PGoApi
from pgoapi.utilities import f2i, h2f

from google.protobuf.internal import encoder
from geopy.geocoders import GoogleV3
from s2sphere import CellId, LatLng

log = logging.getLogger(__name__)

def get_pos_by_name(location_name, proxy):
    geolocator = GoogleV3(proxies=proxy, timeout=5)
    loc = geolocator.geocode(location_name)

    log.info('Your given location: %s', loc.address.encode('utf-8'))
    log.info('lat/long/alt: %s %s %s', loc.latitude, loc.longitude, loc.altitude)

    return (loc.latitude, loc.longitude, loc.altitude)

def get_cellid(lat, long):
    origin = CellId.from_lat_lng(LatLng.from_degrees(lat, long)).parent(15)
    walk = [origin.id()]

    # 10 before and 10 after
    next = origin.next()
    prev = origin.prev()
    for i in range(10):
        walk.append(prev.id())
        walk.append(next.id())
        next = next.next()
        prev = prev.prev()
    return ''.join(map(encode, sorted(walk)))

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

    response = api.get_player() \
                  .get_map_objects(latitude=f2i(position[0]), longitude=f2i(position[1]),
                                   since_timestamp_ms=time.time() * 1000,
                                   cell_id=get_cellid(position[0], position[1])) \
                  .call()

    print "Response dictionary: \n\r%s" % json.dumps(response, indent=2)

if __name__ == '__main__':
    main()
