import logging
logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)
from time import time

class IRCError(Exception):
    _strs = {
        401: "Unknown nickname",
        421: "Unknown command",
        442: "You're not on that channel"
    }
    def __init__(self, num_id, extra=""):
        super()
        self.num_id = num_id
        self.extra = extra
    def __str__(self):
        return str(self.num_id) + " " + self.extra + " :"+IRCError._strs[self.num_id] + "\r\n"

class User:
    _users = {}
    def __init__(self, sock):
        mode = ["i"]
        self.channels = []
        self.socket = sock
        self.registered = False
        self.now = time()
        self.ip = self.socket.getpeername()[0]
    def tick(self):
        now = time()
        if self.now < now:
            self.now = now
        now += 2
    def nick(self, name):
        self.name = name
        if self.registered:
            self.host = self.name + "!"+self.user + "@" + self.socket.getpeername()[0]
        User._users[self.name] = self
    def user(self, user):
        self.user = user
        self.host = self.name + "!"+self.user + "@" + self.socket.getpeername()[0]
        if not self.registered: 
            log.info(self.host + " joins server")
        self.registered = True
    def join(self, channel):
        assert self.registered
        log.info(self.name + " -> " + channel)
        chan = Channel(channel)
        chan.users[self] = self
        self.channels.append(chan)
    def part(self, channel):
        assert self.registered
        log.info(self.name + " <- " + channel)
        chan = Channel(channel)
        try:
            del chan.users[self]
        except KeyError:
            raise IRCError(442, extra=channel)
        self.channels.remove(chan)
    def quit(self):
        for c in self.channels:
            del c.users[self]
    def __str__(self):
        if hasattr(self, "host"):
            return self.host
        else:
            return str(self.socket.getpeername())
    def connected_to(self, also_self=False):
        for c in self.channels:
            for usr in c:
                if usr != self:
                    yield usr
        if also_self:
            yield self
class Channel:
    _channels = {}
    def __new__(cls, name):
        if name in cls._channels:
            return cls._channels[name]
        else:
            s = super().__new__(cls)
            cls._channels[name] = s
            return s
    def __init__(self, name):
        if not hasattr(self, "name"):
            self.name = name
        if not hasattr(self, "users"):
            self.users = {}
        if not hasattr(self, "created_at"):
            self.created_at = int(time())
        if not hasattr(self, "topic"):
            self.topic = None
    def __iter__(self):
        for k, v in self.users.items():
            yield v
    def mode(self):
        return "+tn"
    def __str__(self):
        users = " ".join(user.name for user in self)
        return "<channel:"+self.name+ " " + str(id(self)) + " users: "+users+">"
    def __repr__(self):
        return self.__str__()
if __name__ == "__main__":
    user = User()
    user.nick("kastberg")
    user.user("kastberg")
    s = Channel("#test")
    user.join("#test")
    print(s)
    s2 = Channel("#test")
    print(s2)
