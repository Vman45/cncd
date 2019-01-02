import logging as log
from plugins.pluginskel import SkeletonPlugin
import os, asyncio, re
from time import time
from collections import defaultdict

class Plugin(SkeletonPlugin):

    PLUGIN_API_VERSION = 1
    NAME = "Temperature"
    PREHOOKS = {}
    POSTHOOKS = {}
    HANDLES = []

    def __init__(self, datastore, gctx:dict):
        super().__init__(datastore, gctx)
        Plugin.PREHOOKS = {
            ('robot', 'Device.disconnect'):[self.disconnect],
        }
        Plugin.POSTHOOKS = {
            ('robot', 'Device.connect'):[self.connect],
            ('robot', 'Device.incoming'):[self.incoming],
        }
        self.tasks_by_handle = {}
        self.tmp_pttrn = re.compile(r"[^\s:]+:\d+(?:\.\d+)?(?: /\d+(?:\.\d+)?)?")

    async def poll(self, device):
        handle = device.handle
        await asyncio.sleep(5)
        while True:
            if not await device.inject('M105'):
                log.warning("Sending time probe failed. Backing off")
                break
            await self.datastore.update(handle, "last_temp_request", time())
            await asyncio.sleep(3)

    async def connect(self, device):
        handle = device.handle
        if handle in self.tasks_by_handle:
            return
        connected = self.datastore.get(handle, "connected")
        if not connected:
            return 
        await self.datastore.update(handle, "last_temp_request", 0)
        task = asyncio.ensure_future(self.poll(device))
        ## TODO add exception handler
        self.tasks_by_handle[handle] = task

    async def disconnect(self, device):
        task = self.tasks_by_handle.pop(device.handle, None)
        if task:
            task.cancel()

    async def incoming(self, device, response):
        handle = device.handle
        groups = self.tmp_pttrn.findall(response)
        if groups:
            await self.datastore.update(handle, "temperature", str(groups))
