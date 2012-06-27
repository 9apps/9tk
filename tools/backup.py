# Copyright (C) 2011, 2012 9apps B.V.
#
# This file is part of 9apps ToolKit.
#
# 9apps Tools is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# 9apps Tools is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with 9apps ToolKit. If not, see <http://www.gnu.org/licenses/>.

import os, sys, subprocess, traceback

from time import gmtime, strftime, time
from boto.ec2.connection import EC2Connection

# expiration in the future, calculated like this
from config import Config

DAYS = 24 * 60 * 60

# Ubuntu 12.04 uses recent kernels (/dev/xvdf), EC2 not yet (/dev/sdf)
def DEVICE(device):
    return device.replace('/s', '/xv')

class Backup:
    def __init__(self, config):
        self.config = config
        ud = config.userData
        self.name = "{0}.{1}.{2}".format(ud['name'], ud['environment'], ud['domain'])
        try:
            # we use IAM EC2 role to get the credentials transparently
            self.ec2 = EC2Connection(region=config.regionInfo)
        except Exception as e:
            print("ERROR - Problem connecting to EC2: {0}".format(e))
            print traceback.format_exc()

    def setup(self):
        """Setup cron for the user executing this script"""
        cmd = "{0} {1}".format(sys.executable, os.path.abspath(__file__))

        cronFile = "/etc/cron.d/9apps-backup"
        f = None
        try:
            f = open(cronFile, "w")

            f.write("# this file is auto-generated by 9apps backup\n")
            f.write("# script. (see github.com/9apps for details.)\n")
            f.write("#\n")
            f.write("# generated with 'python backup.py setup'\n")

            backupConfig = self.config.userData["backups"]
            if "hourly" in backupConfig["schedule"]:
                if 'hourly' not in backupConfig:
                    hourly = "0 * * * *"
                else:
                    hourly = backupConfig['hourly']
                f.write("{0} root {1} all hourly > /dev/null 2>&1\n".format(hourly, cmd))

            if "daily" in backupConfig["schedule"]:
                if 'daily' not in backupConfig:
                    daily = "0 0 * * *"
                else:
                    daily = backupConfig['daily']
                f.write("{0} root {1} all daily > /dev/null 2>&1\n".format(daily, cmd))

            if "weekly" in backupConfig["schedule"]:
                if 'weekly' not in backupConfig:
                    weekly = "0 0 * * 0"
                else:
                    weekly = backupConfig['weekly']
                f.write("{0} root {1} all weekly > /dev/null 2>&1\n".format(weekly, cmd))

            if "monthly" in backupConfig["schedule"]:
                if 'monthly' not in backupConfig:
                    monthly = "0 0 1 * *"
                else:
                    monthly = backupConfig['monthly']
                f.write("{0} root {1} all monthly > /dev/null 2>&1\n".format(monthly, cmd))

            everyMidnight = "0 0 * * *"
            f.write("{0} root {1} purge > /dev/null 2>&1\n".format(everyMidnight, cmd))
        except Exception as e:
            print("ERROR - We couldn't create {0}: {1}".format(cronFile, e))
            print traceback.format_exc()
        finally:
            if f:
                f.close()
                print "{0} created successfully".format(cronFile)


    def _expires(self, expiration='hourly'):
        form = "%Y-%m-%d %H:%M:%S"

        backupConfig = self.config.userData["backups"]
        i = backupConfig['schedule'].index(expiration)
        schedule = int(backupConfig['expiration'][i])

        return strftime(form, gmtime(time() + schedule * DAYS))

    def volume(self, device="/dev/sdf", expiration="daily"):
        # first get the mountpoint (requires some energy, but we can...)
        df = subprocess.Popen(["/bin/df", DEVICE(device)], stdout=subprocess.PIPE)

        dummy, size, used, available, percent, mountpoint = df.communicate()[0].split("\n")[1].split()

        # if we have the device (/dev/xvdf) just don't do anything anymore
        mapping = self.ec2.get_instance_attribute(self.config.instanceId, 'blockDeviceMapping')['blockDeviceMapping']
        volume_id = mapping[device].volume_id
        try:
            os.system("/usr/sbin/xfs_freeze -f {0}".format(mountpoint))
            snapshot = self.ec2.create_snapshot(volume_id,
                "Backup of {0} - for {1}{2} - expires {3}".format(
                    volume_id, self.name, mountpoint,
                    self._expires(expiration)))
            params = {"Name": self.name, "Expires": self._expires(expiration)}
            self.ec2.create_tags([snapshot.id], params)
        finally:
            os.system("/usr/sbin/xfs_freeze -u {0}".format(mountpoint))

    def _get_mapping(self, root=False):
        mapping = self.ec2.get_instance_attribute(self.config.instanceId, 'blockDeviceMapping')['blockDeviceMapping']

        # exclude root device
        if not root:
            root = self.ec2.get_instance_attribute(self.config.instanceId, 'rootDeviceName')['rootDeviceName']
            del mapping[root]

        return mapping

    def all(self, expiration="daily"):
        mapping = self._get_mapping()
        for device in mapping:
            self.volume(device, expiration)

    def _get_snapshots(self, expiration='none'):
        params = {"tag:Name": self.name}
        snapshots = self.ec2.get_all_snapshots(filters=params)

        expired = []
        for snapshot in snapshots:
            if snapshot.tags['Expires'] < expiration:
                expired.append(snapshot)

        return expired

    def _delete(self, snapshot):
        self.ec2.delete_snapshot(snapshot)

    # purges past their expiration date, or 'all'
    def purge(self, expiration=strftime("%Y-%m-%d %H:%M:%S", gmtime(time()))):
        snapshots = self._get_snapshots(expiration)
        for snapshot in snapshots:
            print "deleting snapshot {0}".format(snapshot.id)
            self._delete(snapshot.id)

if __name__ == '__main__':
    config = Config.fromAmazon()
    backup = Backup(config)
    getattr(backup, sys.argv[1])(*sys.argv[2:])