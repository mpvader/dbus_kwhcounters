#!/usr/bin/python -u
# -*- coding: utf-8 -*-

"""
GENERAL PRINCIPLES ON kWh-counters

Output of this process:
every hour, we want to get the kWhs-delta for the last hour. And also the kWh data from minute 0
of the current hour until the actual time. Split up in the following categories:
- Energy from grid to consumers
- Energy from grid to battery
- Energy from genset to consumers
- Energy from genset to battery
- Energy from PV to consumers
- Energy from PV to battery
- Energy from PV to grid
- Energy from Battery to consumers
- Energy from Battery to grid

Input of this process:
- kWh counters (= energy) of all relevant devices (Multi, BMV, PV Inverters and Solar chargers).
  Some of these do not store there counters in flash. So every time a Multi for example starts
  up, it starts counting from 0.
- On the DC side, if you have an MPPT, not all things we need are counted yet, so we will count it:
  request values every x seconds and based on that average do something. This is all in the DC side
  of things.

Notes
1) above calculations all do not yet take DC consumption into account, which will add a lot of
   variables to them.
2) ofcourse PV to battery = PVac-to-battery + PVdc-to-battery, etc.

IMPLEMENTATION
Assuming we have all the necessary counters, the next is to do the following:
- On the hour, make a snapshot of all the counters. Then take the difference and
"""

from dbus.mainloop.glib import DBusGMainLoop
import gobject
import argparse
import logging
import datetime
import platform
import dbus
import os
import sys
import time

# Victron imports
sys.path.insert(1, os.path.join(os.path.dirname(__file__), './ext/velib_python'))
from dbusmonitor import DbusMonitor
from vedbus import VeDbusService
from settingsdevice import SettingsDevice
from dbusdeltas import DbusDeltas

softwareversion = '0.10'

dbusmonitor = None
dbusservice = None
dbusdeltas = None

def getdeltas():
    # TODO: Add possible DC consumption into the calculations.

    os.system('clear')

    import pprint
    print "==== get_deltas() start ===="
    print "time %d" % time.time()
    deltas = dbusdeltas.get_deltas(True)
    print "Result of get_deltas():"
    pprint.pprint(deltas)

    # ======= Change acin 1 and acin 2 into genset and mains =======
    # TODO: use some setting for this, instead of just taking ACin1 = genset and ACin2 = mains.

    """
        if settings[AcIn1Type] == inputtype.GRID:
        else
        #setting grid, will contain AcIn1 or AcIn2
        #setting genset1, will contain Acin1 or AcIn2
    """


    vebus = deltas['com.victronenergy.vebus']
    rename_dict_key(vebus, '/Energy/AcIn1ToAcOut', '/Energy/GensetToAcOut')
    rename_dict_key(vebus, '/Energy/AcIn2ToAcOut', '/Energy/GridToAcOut')
    rename_dict_key(vebus, '/Energy/AcIn1ToInverter', '/Energy/GensetToDc')
    rename_dict_key(vebus, '/Energy/AcIn2ToInverter', '/Energy/GridToDc')
    rename_dict_key(vebus, '/Energy/AcOutToAcIn1', '/Energy/AcOutToGenset')
    rename_dict_key(vebus, '/Energy/AcOutToAcIn2', '/Energy/AcOutToGrid')
    rename_dict_key(vebus, '/Energy/InverterToAcIn1', '/Energy/DcToGenset')
    rename_dict_key(vebus, '/Energy/InverterToAcIn2', '/Energy/DcToGrid')

    # Just rename Inverter to Dc, so we are consistent with above
    rename_dict_key(vebus, '/Energy/InverterToAcOut', '/Energy/DcToAcOut')
    rename_dict_key(vebus, '/Energy/OutToInverter', '/Energy/AcOutToDc')

    print("Result of converting ACin 1 and 2 to Genset and mains:")
    pprint.pprint(deltas)

    # ======= Do the calculations and set values on the dbus =======
    global dbusservice
    pvac_total = deltas['com.victronenergy.pvinverter']['/Ac/Energy/Forward']

    # TODO: Use PVac location, instead of assuming that all is on the output
    pvac_to_battery = min(vebus['/Energy/AcOutToDc'], pvac_total)
    pvac_to_consumers = pvac_total - vebus['/Energy/AcOutToGrid'] - vebus['/Energy/AcOutToDc']
    pvac_to_grid = min(vebus['/Energy/AcOutToGrid'], pvac_total)

    pvdc_to_battery = 0
    pvdc_to_grid = 0
    pvdc_to_consumers = 0

    dbusservice['/GridToConsumers'] = vebus['/Energy/GridToAcOut']
    dbusservice['/GridToBattery'] = vebus['/Energy/GridToDc']
    dbusservice['/GensetToConsumers'] = vebus['/Energy/GensetToAcOut']
    dbusservice['/GensetToBattery'] = vebus['/Energy/GensetToDc']
    dbusservice['/PvToBattery'] = pvac_to_battery + pvdc_to_battery
    dbusservice['/PvToConsumers'] = pvac_to_consumers + pvdc_to_consumers
    dbusservice['/PvToGrid'] = pvac_to_grid + pvdc_to_grid
    dbusservice['/BatteryToConsumers'] = vebus['/Energy/DcToAcOut']
    dbusservice['/BatteryToGrid'] = vebus['/Energy/DcToGrid']

    return True

def rename_dict_key(dict, old_key, new_key):
    dict[new_key] = dict.pop(old_key)

def main():
    global dbusmonitor
    global dbusservice
    global dbusdeltas

    # Argument parsing
    parser = argparse.ArgumentParser(
        description= 'kwhcounters aggregrates information from vebus system, solar chargers, etc. and' +
            'calculates system kWh\n'
    )

    parser.add_argument("-d", "--debug", help="set logging level to debug",
                    action="store_true")

    args = parser.parse_args()

    # Init logging
    logging.basicConfig(level=(logging.DEBUG if args.debug else logging.INFO))
    logging.info("%s v%s is starting up" % (__file__, softwareversion))
    logLevel = {0: 'NOTSET', 10: 'DEBUG', 20: 'INFO', 30: 'WARNING', 40: 'ERROR'}
    logging.info('Loglevel set to ' + logLevel[logging.getLogger().getEffectiveLevel()])

    # Have a mainloop, so we can send/receive asynchronous calls to and from dbus
    DBusGMainLoop(set_as_default=True)

    dbusmonitoritems = {
        'com.victronenergy.vebus' : [
            '/Energy/AcIn1ToInverter',
            '/Energy/AcIn2ToInverter',
            '/Energy/AcIn1ToAcOut',
            '/Energy/AcIn2ToAcOut',
            '/Energy/InverterToAcIn1',
            '/Energy/InverterToAcIn2',
            '/Energy/AcOutToAcIn1',
            '/Energy/AcOutToAcIn2',
            '/Energy/InverterToAcOut',
            '/Energy/OutToInverter'],
        'com.victronenergy.solarcharger' : [
            '/Yield/System'],
        'com.victronenergy.pvinverter': [
            '/Ac/Energy/Forward'
        ],
        'com.victronenergy.battery' : [
            '/History/DischargedEnergy',
            '/History/ChargedEnergy'
        ]
    }

    # Translate above dict into the format that DbusMonitor expects.
    # dummy data since DbusMonitor wants it:
    dummy = {'code': None, 'whenToLog': 'configChange', 'accessLevel': None}
    tree = {}
    for deviceclass, paths in dbusmonitoritems.iteritems():
        tree[deviceclass] = {}
        for path in paths:
            tree[deviceclass][path] = dummy

    # TODO: add device added and device removed callbacks, to prevent missing the little kWhs between
    # the time that the device comes online and the passing of the hour
    dbusmonitor = DbusMonitor(tree)

    # Publish ourselves on the dbus
    dbusservice = VeDbusService("com.victronenergy.kwhcounters.s0")
    dbusservice.add_path('/GridToBattery', value=None)
    dbusservice.add_path('/GridToConsumers', value=None)
    dbusservice.add_path('/GensetToConsumers', value=None)
    dbusservice.add_path('/GensetToBattery', value=None)
    dbusservice.add_path('/PvToBattery', value=None)
    dbusservice.add_path('/PvToGrid', value=None)
    dbusservice.add_path('/PvToConsumers', value=None)
    dbusservice.add_path('/BatteryToConsumers', value=None)
    dbusservice.add_path('/BatteryToGrid', value=None)

    dbusdeltas = DbusDeltas(dbusmonitor, dbusmonitoritems)

    gobject.timeout_add(1000, getdeltas)
    #import signal
    #signal.signal(signal.SIGTSTP, getdeltas)


    # Start and run the mainloop
    logging.info("Starting mainloop, responding on only events from now on. Press ctrl-Z to see the deltas")
    mainloop = gobject.MainLoop()
    mainloop.run()


if __name__ == "__main__":
    main()
