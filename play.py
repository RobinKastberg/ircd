import logging
from types import coroutine
from collections import deque
from selectors import DefaultSelector, EVENT_READ, EVENT_WRITE

logging.basicConfig(level=logging.DEBUG)
log = logging.getLogger(__name__)
@coroutine
def read_wait(sock):
    yield 'read_wait', sock

@coroutine
def write_wait(sock):
    yield 'write_wait', sock

class Loop:

    def __init__(self):
        self.ready = deque()
        self.selector = DefaultSelector()


    async def sock_recv(self, sock, maxbytes):
        await read_wait(sock)
        s = sock.recv(maxbytes)
        log.debug("recieved "+str(s) + " from " + str(sock.getpeername()))
        return s

    async def sock_accept(self, sock):
        await read_wait(sock)
        return sock.accept()

    async def sock_sendall(self, sock, data):
        log.debug("sending "+str(data)+ " to " + str(sock.getpeername()))
        while data:
            try:
                nsent = sock.send(data)
                data = data[nsent:]
            except BlockingIOError:
                await write_wait(sock)

    def create_task(self, coro):
        self.ready.append(coro)

    def run_forever(self):
        while True:

            while not self.ready:
                events = self.selector.select()
                for key, _ in events:
                    self.ready.append(key.data)
                    self.selector.unregister(key.fileobj)

            while self.ready:
                self.current_task = self.ready.popleft()
                try:
                    op, *args = self.current_task.send(None)
                    getattr(self, op)(*args)
                except StopIteration:
                    pass

    def read_wait(self, sock):
        if(sock.fileno() != -1):
            self.selector.register(sock, EVENT_READ, self.current_task)

    def write_wait(self, sock):
        if(sock.fileno() != -1):
            self.selector.register(sock, EVENT_WRITE, self.current_task)

