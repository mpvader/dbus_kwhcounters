#!/usr/bin/env python
# -*- coding: utf-8 -*-

import logging

"""
On startup, pass DbusDeltas a list of device classes that you want to monitor, and the paths of those
classes. An example of a device class is com.victronenergy.battery. Then, call DbusDeltas.get_deltas()
periodically. For each device in a class that it finds, for example battery1 and battery2 etcetera, it
will calculate the difference between the old and the new value of all the paths. Then it adds all of
them up and give you the result. At the same time store all new values, so when called again you get
the new deltas.

Notes and exceptions:
    - We expect counts to always count upwards. Because of it a delta can never be < 0. In case
      (New - Old) is < 0, probably that counter has reset or overflowed. Right now this code just returns
      0 in that case.
      TODO: could be improved and just return the new value. Do make sure that if a device has came
      online in between the previous call and the current call to get_deltas(), the new value is not
      being returned.
"""
class DbusDeltas(object):
    # __init__ parameters:
    #   - dbusmonitor: an initialized instance of DbusMonitor
    #   - classes_and_paths: dictionary, with deviceclasses as the key, and a list of paths as the value:
    #     {'com.victronenergy.vebus': ['/kWhcounter1, 'kwhcounter2']}
    def __init__(self, dbusmonitor, classes_and_paths):
        self._dbusmonitor = dbusmonitor
        self._snapshot = {}
        self._classes_and_paths = classes_and_paths

        # Store the initial snapshot
        self.get_deltas()

    def device_added(self, dbusservicename, instance):
        # TODO: if you want to be perfect, you could add the current values to the store.
        pass

    def device_removed(self, dbusservicename, instance):
        # no need to do anything here. The old value will be removed on the next call to get_deltas() and
        # skipped during delta calculations. OR? Do we need to throw its values away, in case a BMV goes
        # offline and then another one comes back with some entirely different (higher) value? While thinking
        # of this, it is perhaps even better to also store the serial number and check that we are still
        # comparing the same serialnumber? To prevent messing everything up.
        pass

    # Gets the new value from the dbus, adds the delta to the result dict, and stores the new value (unless
    # you don't want it to store the new value).
    def get_deltas(self, keepoldsnapshot=False):
        newsnapshot = {}
        deltas = {}
        import pprint
        logging.debug(pprint.pformat(self._snapshot))
        for serviceclass, paths in self._classes_and_paths.iteritems():
            services = self._dbusmonitor.get_service_list(serviceclass)
            deltas[serviceclass] = {}
            for path in paths:
                delta = 0
                for service in services.values():
                    newvalue = self._dbusmonitor.get_value(service, path)
                    if newvalue:
                        if service not in newsnapshot:
                            newsnapshot[service] = {}

                        # there is a new value, so store it:
                        newsnapshot[service][path] = newvalue

                        if service in self._snapshot and path in self._snapshot[service]:
                            # and there was an old value, add it to the delta:
                            delta = delta + max(newvalue - self._snapshot[service][path], 0)

                # Store the delta in the result
                if not keepoldsnapshot:
                    deltas[serviceclass][path] = delta

        # throw away the old snapshot, and replace with the new one.
        self._snapshot = newsnapshot

        return deltas
