import time, socket, sys, threading
import errno

import utils

class Sender(utils.StoppableThread):
    def __init__(self, server_socket):
        super(Sender, self).__init__(target=self.send, daemon=True)
        self.server_socket = server_socket

    def send(self):
        while not self.isStopped():
            # Wait for user input
            msg = input()

            if msg == 'EXIT':
                self.stop()

            # Send data to server
            self.server_socket.send(msg.encode())

class Receiver(utils.StoppableThread):
    def __init__(self, server_socket):
        super(Receiver, self).__init__(target=self.receive, daemon=True)
        self.server_socket = server_socket

    def receive(self):
        while not self.isStopped():
            try:
                # Wait for data from server
                # TODO: Accept larger messages
                msg = self.server_socket.recv(1024)
            except socket.error as e:
                if e.args[0] in [ errno.EAGAIN, errno.EWOULDBLOCK ]:
                    # No data received
                    # time.sleep(1)
                    continue
                else:
                    # Acutal error
                    print(e)
                    sys.exit(1)
    
            else:
                # Do Something
                print(msg.decode())

class Client():
    def __init__(self):
        # Start socket
        self.server_socket = socket.socket()
        self.connected = False

        self.sender = Sender(self.server_socket)
        self.receiver = Receiver(self.server_socket)
    
    # Attempt to connect to Host
    def connect(self, host):
        try:
            self.server_socket.connect(host)
            self.server_socket.setblocking(False)

            self.connected = True
        except:
            self.connected = False

    # Start Sender + Receiver
    def run(self):
        self.sender.start()
        self.receiver.start()

        while not self.sender.isStopped():
            continue

        self.receiver.stop()
        self.connected = False


### Main Code ###

TIMEOUT = 5 # seconds
SERVER = (socket.gethostname(), 8080)

if __name__ == '__main__':

    # Thread Client receive
    client = Client()

    # Retry to connect to the server
    start = time.time()
    
    print('Attempting to connect to {} - timeout ({} s)'.format(SERVER, TIMEOUT))

    while (time.time() - start) < TIMEOUT:
        client.connect(SERVER)

        if client.connected:
            break

    # Run Client (if connection succesful)
    if not client.connected:
        print('Connection timed out. Server {} not found'.format(SERVER))
    else:
        print('Successfully connected as Client {}'.format(client.server_socket.getsockname()))
        client.run() # blocking.
