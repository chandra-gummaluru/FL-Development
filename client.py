import time, sys, threading, errno
import socket
import utils

import client_trainer

class Client():
    def __init__(self, server):
        # Socket for communication
        self.server = server
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.connected = False

        # Communication interface
        self.comm_handler = None
    
    # Attempt to connect to Server
    def connect(self):
        try:
            # Connect socket
            self.socket.connect(self.server)
            self.socket.setblocking(False)
            self.connected = True

            # Start Comm Handler over connected socket
            self.comm_handler = utils.Comm_Handler((self.socket, self.socket.getsockname()))
            self.comm_handler.start()
        except:
            self.connected = False

# Handles FL Client training loop logic
class FLClient(Client):
    def __init__(self, server, trainer):
        super(FLClient, self).__init__(server)

        # Training Program (specific to the model being trained)
        self.trainer = trainer

    ### FL Training Loop ###

    def run(self):
        while not self.comm_handler.isStopped():
            # Wait for weights from the FLServer
            while not self.comm_handler.has_message():
                # TODO: sleep a bit
                continue

            # Get message
            weights = self.comm_handler.get_message()

            # sleep communication
            self.comm_handler.pause()

            # Load weights
            self.trainer.load_weights(weights)

            # Train model
            self.trainer.train()

            # Compute focused update
            update = self.trainer.focused_update()

            # start communication
            self.comm_handler.start()

            # Send update to the server
            self.comm_handler.queue_message(update)


### Main Code ###

TIMEOUT = 5 # seconds

#SERVER = (socket.gethostname(), 8080)
SERVER = ('192.168.2.26', 12050)

if __name__ == '__main__':

    # Get client index from command line
    idx = int(sys.argv[1])
    nums = [[0, 1, 2], [3, 4, 5], [6, 7, 8, 9]]

    # Instantiate FL client with Training program
    client = FLClient(SERVER, client_trainer.ClientTrainer(nums[idx]))

    # Retry to connect to the server
    start = time.time()
    
    print('Attempting to connect to {} - timeout ({} s)'.format(SERVER, TIMEOUT))

    while (time.time() - start) < TIMEOUT:
        client.connect()

        if client.connected:
            break

    # Run Client (if connection succesful)
    if not client.connected:
        print('Connection timed out. Server {} not found'.format(SERVER))
    else:
        print('Successfully connected as Client {}'.format(client.socket.getsockname()))
        client.run()
