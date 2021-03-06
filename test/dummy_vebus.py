#!/usr/bin/env python

# takes data from the dbus, does calculations with it, and puts it back on
from dbus.mainloop.glib import DBusGMainLoop
import gobject
import argparse
import logging
import sys
import os

# our own packages
sys.path.insert(1, os.path.join(os.path.dirname(__file__), '../ext/velib_python'))
from dbusdummyservice import DbusDummyService

# Argument parsing
parser = argparse.ArgumentParser(
    description='dbusMonitor.py demo run'
)

parser.add_argument("-n", "--name", help="the D-Bus service you want me to claim",
                type=str, default="com.victronenergy.vebus.ttyO1")

parser.add_argument("-d", "--debug", help="set logging level to debug",
                action="store_true")

args = parser.parse_args()

# Init logging
logging.basicConfig(level=(logging.DEBUG if args.debug else logging.DEBUG))
logging.info(__file__ + " is starting up")
logLevel = {0: 'NOTSET', 10: 'DEBUG', 20: 'INFO', 30: 'WARNING', 40: 'ERROR'}
logging.info('Loglevel set to ' + logLevel[logging.getLogger().getEffectiveLevel()])

# Have a mainloop, so we can send/receive asynchronous calls to and from dbus
DBusGMainLoop(set_as_default=True)

pvac_output = DbusDummyService(
    servicename='com.victronenergy.vebus.ttyO1',
    deviceinstance=0,
    paths={
        '/Energy/AcIn1ToInverter': {'initial': 0, 'update': 1},
        '/Energy/AcIn2ToInverter': {'initial': 0, 'update': 0},
        '/Energy/AcIn1ToAcOut': {'initial': 0, 'update': 10},
        '/Energy/AcIn2ToAcOut': {'initial': 0, 'update': 0},
        '/Energy/InverterToAcIn1': {'initial': 0, 'update': 100},
        '/Energy/InverterToAcIn2': {'initial': 0, 'update': 0},
        '/Energy/AcOutToAcIn1': {'initial': 0, 'update': 1000},
        '/Energy/AcOutToAcIn2': {'initial': 0, 'update': 0},
        '/Energy/InverterToAcOut': {'initial': 0, 'update': 10000},
        '/Energy/OutToInverter': {'initial': 0, 'update': 5}})

print 'Connected to dbus, and switching over to gobject.MainLoop() (= event based)'
mainloop = gobject.MainLoop()
mainloop.run()




