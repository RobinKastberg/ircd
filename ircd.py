import logging
import ssl
from play import Loop
from irc import User, Channel, IRCError
from socket import *
from time import time
LOOP = Loop()
SERVER = "localhost"
VERSION = "0.1"
logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

def to_irc(command,frm="localhost"):
    return (":"+frm +" " + command + "\r\n").encode()
def to_irc2(*args, source="localhost", suffix=""):
    s =  (":"+source + " " + " ".join(str(arg) for arg in args))
    if suffix:
        s += " :" + suffix
    s += "\r\n"
    return s.encode()
async def handle_line(user, raw_line):
    line = raw_line.split(":")
    if len(line) == 2:
        extended = line[1]
    else:
        extended = None
    cmd = line[0].split(" ")
    cmd[-1] = cmd[-1].rstrip()
    log.debug(str(user) +"sent: " + str(line))

    def to_irc3(num, *args, **kwargs):
        return to_irc2(num, user.name, *args, **kwargs)
    async def send_num(num, *args, user=user, **kwargs):
        await LOOP.sock_sendall(user.socket, to_irc2("%03d" % num, user.name, *args, **kwargs))

    if cmd[0] == "PING":
        await LOOP.sock_sendall(user.socket, to_irc("PONG "+cmd[1] + " :" + cmd[1]))
    elif cmd[0] == "QUIT":
        if not extended:
            extended = "leaving"
        print(user.channels)
        for usr in user.connected_to(also_self=True):
            await LOOP.sock_sendall(usr.socket,to_irc("QUIT :"+extended, frm=user.host))
        await LOOP.sock_sendall(user.socket,b"ERROR :Closing link\r\n")
        user.quit()
        user.socket.close()
        return
    elif cmd[0] == "TOPIC" and extended:
        Channel(cmd[1]).topic = extended
        for usr in Channel(cmd[1]):
            await LOOP.sock_sendall(usr.socket, to_irc("TOPIC "+cmd[1] + " :"+extended, frm=user.host))
    elif cmd[0] == "WHO":
        #await LOOP.sock_sendall(user.socket, to_irc3(329, cmd[1], Channel(cmd[1]).created_at))
        await send_num(329, cmd[1], Channel(cmd[1]).created_at)
        for usr in Channel(cmd[1]):
            await send_num(352, cmd[1], usr.user, usr.ip, SERVER,"H", suffix="0 ")
        await send_num(315, cmd[1],suffix="End of /WHO list.")
            
    elif cmd[0] == "MODE":
        # Querying channel mode
        if cmd[1].startswith("#"):
            # General
            if len(cmd) == 2:
                await send_num(324, cmd[1], Channel(cmd[1]).mode())
            # Ban-list
            elif cmd[2] == "b":
                await LOOP.sock_sendall(user.socket, to_irc3(368,cmd[1],suffix="End of Channel Ban List"))
        # Setting own mode
        elif(cmd[1] == user.name):
            await LOOP.sock_sendall(user.socket, to_irc("MODE "+user.name + " :+i"))
        else:
            raise NotImplementedError
            
    elif cmd[0] == "PRIVMSG":
        for usr in Channel(cmd[1]):
            if usr.socket == user.socket:
                continue
            await LOOP.sock_sendall(usr.socket, to_irc(raw_line, frm=user.host))
    elif cmd[0] == "WHOIS":
        try:
            usr = user._users[cmd[1]]
            await send_num(311, usr.name, usr.user, usr.ip,"*",suffix="Real Name")
            await send_num(318, usr.name,suffix="End of /WHOIS list.")
        except KeyError:
            await send_num(401, cmd[1], suffix="Nickname not found")
    elif cmd[0] == "NICK":
        # TODO send
        if user.registered:
            for usr in user.connected_to(also_self=True):
                await LOOP.sock_sendall(usr.socket,to_irc("NICK "+cmd[1], frm=user.host))
        user.nick(cmd[1])
    elif cmd[0] == "USER":
        user.user(cmd[1])
        await send_num(1,"Welcome")
        await send_num(2,"Welcome")
        await send_num(3,"Welcome")
        await send_num(4,"ircd.py", VERSION, "", "")
        await LOOP.sock_sendall(user.socket, to_irc("376 "+user.name + " :End of /MOTD command."))
    elif cmd[0] == "USERHOST":
        await LOOP.sock_sendall(user.socket, to_irc("302 "+user.name+ " :" + user.host))
    elif cmd[0] == "PART":
        for chan in cmd[1].split(","):
            for usr in Channel(chan):
                await LOOP.sock_sendall(usr.socket,to_irc("PART "+chan, frm=user.host))
            user.part(chan)
    elif cmd[0] == "JOIN":
        for chan in cmd[1].split(","):
            user.join(chan)
            for usr in Channel(chan):
                await LOOP.sock_sendall(usr.socket,to_irc("JOIN :"+chan, frm=user.host))
            if Channel(chan).topic:
                await LOOP.sock_sendall(user.socket, to_irc("332 "+ user.name + " " +chan +" :"+Channel(chan).topic))
            else:
                await LOOP.sock_sendall(user.socket, to_irc("331 "+ user.name + " " +chan +" :No topic is set"))
                
            await LOOP.sock_sendall(user.socket, to_irc("353 "+ user.name + " @ " +chan +" :" + " ".join(usr.name for usr in Channel(chan))))
            await LOOP.sock_sendall(user.socket, to_irc("366 "+ user.name + " " +chan +" :End of /NAMES list."))
    else:
        raise IRCError(421, extra=cmd[1])

async def irc_handler(client):
    log.info("Handling: " +str(client.getpeername()))
    user = User(client)
    while True:
        data = await LOOP.sock_recv(client, 512)
        if not data:
            break
        for line in data.decode().split("\r\n"):
            if line:
                try:
                    await handle_line(user, line)
                except IRCError as e:
                    await LOOP.sock_sendall(client, (":localhost "+str(e)).encode())



async def irc_server_ssl(address):
    sock = socket(AF_INET, SOCK_STREAM)
    sock.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
    sock.bind(address)
    sock.listen(5)
    sock.setblocking(False)
    sock = ssl.wrap_socket(sock, server_side=True, keyfile="domain.key", certfile="domain.crt")
    while True:
        client, addr = await LOOP.sock_accept(sock)
        log.info("Connection from" + str(addr))
        LOOP.create_task(irc_handler(client))

async def irc_server(address):
    sock = socket(AF_INET, SOCK_STREAM)
    sock.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
    sock.bind(address)
    sock.listen(5)
    sock.setblocking(False)
    while True:
        client, addr = await LOOP.sock_accept(sock)
        log.info("Connection from" + str(addr))
        LOOP.create_task(irc_handler(client))

LOOP.create_task(irc_server(('', 6667)))
LOOP.create_task(irc_server_ssl(('', 6697)))
LOOP.run_forever()
