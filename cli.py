import cmd

from tools.config import Config
from tools.eip import EIP

class ToolKit(cmd.Cmd):

    CONFIG = Config.fromAmazon()

    ##########################################################################################

    def help_display(self):
        print '\n'.join(["display", " Display user-data associated with this EC2 instance"])

    def do_display(self, line):
        print self.CONFIG

    ##########################################################################################

    EIP_COMMANDS = ["associate", "disassociate", "install", "uninstall"]

    def help_eip(self):
        print '\n'.join(["eip {0}".format(self.EIP_COMMANDS), " Associate or disassociate EIP configured in user-data"])

    def complete_eip(self, text, line, begidx, endidx):
        if not text:
            completions = self.EIP_COMMANDS[:]
        else:
            completions = [ f
                            for f in self.EIP_COMMANDS
                            if f.startswith(text)
                            ]
        return completions

    def do_eip(self, cmd):
        eip = EIP(self.CONFIG)
        if cmd == self.EIP_COMMANDS[0]:
            eip.associate()
        elif cmd == self.EIP_COMMANDS[1]:
            eip.disassociate()
        elif cmd == self.EIP_COMMANDS[2]:
            eip.install_initd()
        elif cmd == self.EIP_COMMANDS[3]:
            eip.uninstall()

    ##########################################################################################

    # eip associate, dissociate, install, uninstall
    # backup setup (or install)
    # mount -, install, uninstall
    # umount




    def do_EOF(self, line):
        print "Exit"
        return True

if __name__ == '__main__':
    ToolKit().cmdloop("\nWelcome to the 9apps ToolKit CLI.\n")