#!/usr/bin/env python

"""Save weather station history to file
::

%s

This program / module gets data from the weather station's memory and
stores it to file. Each time it is run it fetches all data that is
newer than the last stored data, so it only needs to be run every hour
or so. As the weather station typically stores two weeks' readings
(depending on the logging interval), LogData.py could be run quite
infrequently if you don't need up-to-date data.

There is no date or time information in the raw weather station data,
so LogData.py creates a time stamp for each reading. It uses the
computer's clock, rather than the weather station clock which can not
be read accurately by the computer. A networked computer should have
its clock set accurately by `ntp
<http://en.wikipedia.org/wiki/Network_Time_Protocol>`_.

Synchronisation with the weather station is achieved by waiting for a
change in the current data. There are two levels of synchronisation,
set by the config file or a command line option. Level 0 is quicker,
but is only accurate to around twelve seconds. Level 1 waits until the
weather station stores a new logged record, and gets time stamps
accurate to a couple of seconds. Note that this could take a long
time, if the logging interval is greater than the recommended five
minutes.

"""

__docformat__ = "restructuredtext en"
__usage__ = """
 usage: python LogData.py [options] data_dir
 options are:
  -h   | --help     display this help
  -c   | --clear    clear weather station's memory full indicator
  -s n | --sync n   set quality of synchronisation to weather station (0 or 1)
  -v   | --verbose  increase number of informative messages
 data_dir is the root directory of the weather data
"""
__doc__ %= __usage__
__usage__ = __doc__.split('\n')[0] + __usage__

from datetime import datetime, timedelta
import getopt
import logging
import os
import sys
import time

import DataStore
from Logger import ApplicationLogger
from TimeZone import Local
#import WeatherStation

def Catchup(ws, logger, raw_data, last_date, last_ptr):
    fixed_block = ws.get_fixed_block(unbuffered=True)
    # get time to go back to
    last_stored = raw_data.before(datetime.max)
    if last_stored == None:
        last_stored = datetime.min
    if datetime.utcnow() < last_stored:
        raise ValueError('Computer time is earlier than last stored data')
    last_stored += timedelta(seconds=fixed_block['read_period'] * 30)
    # data_count includes record currently being updated every 48 seconds
    max_count = fixed_block['data_count'] - 1
    count = 0
    while last_date > last_stored and count < max_count:
        data = ws.get_data(last_ptr)
        if data['delay'] is None or data['delay'] > 30:
            logger.error('invalid data at %04x, %s',
                         last_ptr, last_date.isoformat(' '))
            last_date -= timedelta(minutes=fixed_block['read_period'])
        else:
            raw_data[last_date] = data
            count += 1
            last_date -= timedelta(minutes=data['delay'])
        last_ptr = ws.dec_ptr(last_ptr)
    if count > 0:
        logger.info("%d catchup records", count)
    raw_data.flush()

def CheckFixedBlock(ws, params, logger):
    fixed_block = ws.get_fixed_block(unbuffered=True)
    if not fixed_block:
        return None
    # check clocks
    try:
        s_time = DataStore.safestrptime(
            fixed_block['date_time'], '%Y-%m-%d %H:%M')
    except Exception:
        s_time = None
    if s_time:
        c_time = datetime.now().replace(second=0, microsecond=0)
        diff = abs(s_time - c_time)
        if diff > timedelta(minutes=2):
            logger.warning(
                "Computer and weather station clocks disagree by %s (H:M:S).", str(diff))
    # store weather station type
    params.set('fixed', 'ws type', ws.ws_type)
    # store info from fixed block
    pressure_offset = fixed_block['rel_pressure'] - fixed_block['abs_pressure']
    old_offset = eval(params.get('fixed', 'pressure offset', 'None'))
    if old_offset and abs(old_offset - pressure_offset) > 0.01:
        # re-read fixed block, as can get incorrect values
        logger.warning('Re-read fixed block')
        fixed_block = ws.get_fixed_block(unbuffered=True)
        if not fixed_block:
            return None
        pressure_offset = fixed_block['rel_pressure'] - fixed_block['abs_pressure']
    if old_offset and abs(old_offset - pressure_offset) > 0.01:
        logger.warning(
            'Pressure offset change: %g -> %g', old_offset, pressure_offset)
    params.set('fixed', 'pressure offset', '%g' % (pressure_offset))
    params.set('fixed', 'fixed block', str(fixed_block))
    params.flush()
    return fixed_block

def LogData(params, raw_data, sync=None, clear=False):
    logger = logging.getLogger('pywws.LogData')
    # connect to weather station
    ws_type = params.get('config', 'ws type')
    if ws_type:
        params._config.remove_option('config', 'ws type')
        params.set('fixed', 'ws type', ws_type)
    ws_type = params.get('fixed', 'ws type', 'Unknown')
 #   ws = WeatherStation.weather_station(ws_type=ws_type)
 #   fixed_block = CheckFixedBlock(ws, params, logger)
 #   if not fixed_block:
 #       logger.error("Invalid data from weather station")
 #       return 3
    # check for valid weather station type
    ws=1
    ws.ws_type = 1080  
    if ws.ws_type not in ('1080', '3080'):
        print "Unknown weather station type. Please edit weather.ini"
        print "and set 'ws type' to '1080' or '3080', as appropriate."
        if fixed_block['lux_wm2_coeff'] == 0.0:
            print "Your station is probably a '1080' type."
        else:
            print "Your station is probably a '3080' type."
        sys.exit(1)
    # get sync config value
    if sync is None:
        if fixed_block['read_period'] <= 5:
            sync = int(params.get('config', 'logdata sync', '1'))
        else:
            sync = int(params.get('config', 'logdata sync', '0'))
    # get address and date-time of last complete logged data
    logger.info('Synchronising to weather station')
    range_hi = datetime.max
    range_lo = datetime.min
    #last_delay = ws.get_data(ws.current_pos())['delay']
    #if last_delay == 0:
    #    prev_date = datetime.min
    #else:
    #    prev_date = datetime.utcnow()
    sys.exit(0)
    for data, last_ptr, logged in ws.live_data(logged_only=(sync > 0)):
        last_date = data['idx']
        logger.debug('Reading time %s', last_date.strftime('%H:%M:%S'))
        if logged:
            break
        hi = last_date - timedelta(minutes=data['delay'])
        if last_date - prev_date > timedelta(seconds=50):
            lo = hi - timedelta(seconds=60)
        elif data['delay'] == last_delay:
            lo = hi - timedelta(seconds=60)
            hi = hi - timedelta(seconds=48)
        else:
            lo = hi - timedelta(seconds=48)
        last_delay = data['delay']
        prev_date = last_date
        range_hi = min(range_hi, hi)
        range_lo = max(range_lo, lo)
        err = (range_hi - range_lo) / 2
        last_date = range_lo + err
        logger.debug('est log time %s +- %ds (%s..%s)',
                     last_date.strftime('%H:%M:%S'), err.seconds,
                     lo.strftime('%H:%M:%S'), hi.strftime('%H:%M:%S'))
        if sync < 1 and err < timedelta(seconds=15):
            last_ptr = ws.dec_ptr(last_ptr)
            break
    # go back through stored data, until we catch up with what we've already got
    logger.info('Fetching data')
    Catchup(ws, logger, raw_data, last_date, last_ptr)
    if clear:
        logger.info('Clearing weather station memory')
        ptr = ws.fixed_format['data_count'][0]
        ws.write_data([(ptr, 1), (ptr+1, 0)])

def main(argv=None):
    if argv is None:
        argv = sys.argv
    try:
        opts, args = getopt.getopt(
            argv[1:], "hcs:v", ('help', 'clear', 'sync=', 'verbose'))
    except getopt.error, msg:
        print >>sys.stderr, 'Error: %s\n' % msg
        print >>sys.stderr, __usage__.strip()
        return 1
    # process options
    clear = False
    sync = None
    verbose = 0
    for o, a in opts:
        if o in ('-h', '--help'):
            print __usage__.strip()
            return 0
        elif o in ('-c', '--clear'):
            clear = True
        elif o in ('-s', '--sync'):
            sync = int(a)
        elif o in ('-v', '--verbose'):
            verbose += 1
    # check arguments
    if len(args) != 1:
        print >>sys.stderr, 'Error: 1 argument required\n'
        print >>sys.stderr, __usage__.strip()
        return 2
    logger = ApplicationLogger(verbose)
    root_dir = args[0]
    return LogData(
        DataStore.params(root_dir), DataStore.data_store(root_dir),
        sync=sync, clear=clear)

if __name__ == "__main__":
    sys.exit(main())
