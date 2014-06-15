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
import os
import sys
import time
import pprint

# Victron imports
sys.path.insert(1, os.path.join(os.path.dirname(__file__), './ext/velib_python'))
from dbusmonitor import DbusMonitor
from vedbus import VeDbusService
from settingsdevice import SettingsDevice
from dbusdeltas import DbusDeltas

softwareversion = '0.10'

dbusservice = None
kwhdeltas = None

def pr(name):
    print("%s: %s" % (name, dbusservice[name]))

def rename_dict_key(dict, old_key, new_key):
    dict[new_key] = dict.pop(old_key)

class KwhDeltas:
    def __init__(self):
        self.store = {
            'vebus': {
                'services': [], 'class': 'com.victronenergy.vebus',
                'paths': [
                    '/Energy/AcIn1ToInverter',
                    '/Energy/AcIn2ToInverter',
                    '/Energy/AcIn1ToAcOut',
                    '/Energy/AcIn2ToAcOut',
                    '/Energy/InverterToAcIn1',
                    '/Energy/InverterToAcIn2',
                    '/Energy/AcOutToAcIn1',
                    '/Energy/AcOutToAcIn2',
                    '/Energy/InverterToAcOut',
                    '/Energy/OutToInverter']},
            'pvac.output': {
                'services': [], 'class': 'com.victronenergy.pvinverter',
                'paths': [
                    '/Ac/Energy/Forward',
                    '/Position']}}
        """
            'battery': {
                'services': [], 'class': 'com.victronenergy.battery',
                'paths': [
                    '/History/DischargedEnergy',
                    '/History/ChargedEnergy']},
            'pvac.grid': {
                'services': [], 'class': 'com.victronenergy.pvinverter',
                'paths': [
                    '/Ac/Energy/Forward',
                    '/Position']},
            'pvac.genset': {
                'services': [], 'class': 'com.victronenergy.pvinverter',
                'paths': [
                    '/Ac/Energy/Forward',
                    '/Position']},
            'pvdc': {
                'services': [], 'class': 'com.victronenergy.solarcharger',
                'paths': [
                    '/Yield/System']}
        """

        self.dbusmonitor = self._initdbusmonitor()

        # init all instances already existing on the dbus
        services = self.dbusmonitor.get_service_list()
        logging.debug("services at startup: %s" % services)
        for name, instance in services.iteritems():
            self._handle_new_service(name, instance)

        logging.debug("KwhDeltas.init() finished. self.store: \n%s" % pprint.pformat(self.store))

        self.dbusdeltas = DbusDeltas(self.dbusmonitor, self.store)

    def _initdbusmonitor(self):
        # Get all unique serviceclasses from self.store, and all paths.
        dbusmonitoritems = {}
        # dummy data since DbusMonitor wants it:
        dummy = {'code': None, 'whenToLog': 'configChange', 'accessLevel': None}
        for d in self.store.values():
            if d['class'] not in dbusmonitoritems:
                dbusmonitoritems[d['class']] = {}

            for path in d['paths']:
                dbusmonitoritems[d['class']][path] = dummy

        return DbusMonitor(
            dbusmonitoritems,
            deviceAddedCallback=self._handle_new_service,
            deviceRemovedCallback=self._handle_removed_service)

    def _handle_new_service(self, servicename, instance):
        logging.debug("handle_new_service: %s" % servicename)

        serviceclass = servicename.split('.')
        if len(serviceclass) < 3 or serviceclass[1] != 'victronenergy':
            return

        serviceclass = serviceclass[2]
        if serviceclass == 'vebus':
            # Use the last found vebus device
            # TODO: don't use the last vebus device, use some setting.
            self.store['vebus']['services'] = [servicename]
        elif serviceclass == 'battery':
            # Use the last battery
            # TODO: don't use the last battery, use the main battery (needs to be added as a setting)
            self.store['battery']['services'] = [servicename]
        elif serviceclass == 'pvinverter':
            # Split pv inverters in three groups: grid, genset and mains
            position = self.dbusmonitor.get_value(servicename, '/Position')
            pvtype = {0: 'pvac.genset', 1: 'pvac.output', 2: 'pvac.grid'}
            self.store[pvtype[position]]['services'].append(servicename)
        elif serviceclass == 'solarcharger':
            # Group all solarchargers together
            self.store['solarcharger']['services'].append(servicename)

    def _handle_removed_service(self, servicename, instance):
        # TODO: Implement removing of services (and when BMV dissapears, choose another one? Or wait for
        # general setting to change?)
        pass

    def getdeltas(self):
        # Calculation status
        # The calculation only calculates a simple hub-2 system.
        # TODO: add pv on dc (hub-1) to the calculations
        # TODO: add pv on grid (hub-3) to the calculations
        # TODO: add paralled storage (hub-4) to the calculations
        # TODO: Add possible DC consumption into the calculations

        os.system('clear')

        print "==== get_deltas() %s ====" % time.time()
        deltas = self.dbusdeltas.get_deltas(True)

        # ======= Change acin 1 and acin 2 into genset and mains =======
        # TODO: use some setting for this, instead of just taking ACin1 = genset and ACin2 = mains.

        """
            if settings[AcIn1Type] == inputtype.GRID:
            else
            #setting grid, will contain AcIn1 or AcIn2
            #setting genset1, will contain Acin1 or AcIn2
        """

        vebus = deltas['vebus']
        # Note that AcIn1 and AcIn2 are swapped here because of the testsystem: Matthijs his house
        rename_dict_key(vebus, '/Energy/AcIn2ToAcOut', '/Energy/GensetToAcOut')
        rename_dict_key(vebus, '/Energy/AcIn1ToAcOut', '/Energy/GridToAcOut')
        rename_dict_key(vebus, '/Energy/AcIn2ToInverter', '/Energy/GensetToDc')
        rename_dict_key(vebus, '/Energy/AcIn1ToInverter', '/Energy/GridToDc')
        rename_dict_key(vebus, '/Energy/AcOutToAcIn2', '/Energy/AcOutToGenset')
        rename_dict_key(vebus, '/Energy/AcOutToAcIn1', '/Energy/AcOutToGrid')
        rename_dict_key(vebus, '/Energy/InverterToAcIn2', '/Energy/DcToGenset')
        rename_dict_key(vebus, '/Energy/InverterToAcIn1', '/Energy/DcToGrid')

        # Rename Inverter to Dc, so we are consistent with above
        rename_dict_key(vebus, '/Energy/InverterToAcOut', '/Energy/DcToAcOut')
        rename_dict_key(vebus, '/Energy/OutToInverter', '/Energy/AcOutToDc')

        print("Result of converting ACin 1 and 2 to Genset and mains:")
        pprint.pprint(deltas)

        # ======= Do the calculations and set values on the dbus =======
        pvac_output = deltas['pvac.output']['/Ac/Energy/Forward']

        pvac_to_battery = min(vebus['/Energy/AcOutToDc'], pvac_output)
        # Max is for measurement inaccuracies. If pvac_output is counting slower than AcOutToGrid, you could
        # get values below 0.
        pvac_to_consumers = max(pvac_output - vebus['/Energy/AcOutToGrid'] - vebus['/Energy/AcOutToDc'], 0)
        pvac_to_grid = min(vebus['/Energy/AcOutToGrid'], pvac_output)

        pvdc_to_battery = 0
        pvdc_to_grid = 0
        pvdc_to_consumers = 0

        global dbusservice
        dbusservice['/GridToConsumers'] = vebus['/Energy/GridToAcOut']
        dbusservice['/GridToBattery'] = vebus['/Energy/GridToDc']
        dbusservice['/GensetToConsumers'] = vebus['/Energy/GensetToAcOut']
        dbusservice['/GensetToBattery'] = vebus['/Energy/GensetToDc']
        dbusservice['/PvToBattery'] = pvac_to_battery + pvdc_to_battery
        dbusservice['/PvToConsumers'] = pvac_to_consumers + pvdc_to_consumers
        dbusservice['/PvToGrid'] = pvac_to_grid + pvdc_to_grid
        dbusservice['/BatteryToConsumers'] = vebus['/Energy/DcToAcOut']
        dbusservice['/BatteryToGrid'] = vebus['/Energy/DcToGrid']

        pr('/GridToConsumers')
        pr('/GridToBattery')
        pr('/GensetToConsumers')
        pr('/GensetToBattery')
        pr('/PvToBattery')
        pr('/PvToConsumers')
        pr('/PvToGrid')
        pr('/BatteryToConsumers')
        pr('/BatteryToGrid')

        return True


def main():
    global dbusservice
    global kwhdeltas

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

    kwhdeltas = KwhDeltas()

    gobject.timeout_add(1000, kwhdeltas.getdeltas)

    # Start and run the mainloop
    logging.info("Starting mainloop, responding on only events from now on. Press ctrl-Z to see the deltas")
    mainloop = gobject.MainLoop()
    mainloop.run()


if __name__ == "__main__":
    main()
