import time, sys, threading, errno, socket

import utils
from utils import DEBUG_LEVEL, COLORS

import client_trainer

debug_level = DEBUG_LEVEL.INFO

class Client():
    def __init__(self, server):
        # Socket for communication
        self.server = server
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.connected = False

        # Communication interface
        self.comm_handler = None

        self.TIMEOUT = 5

    # Attempt to connect to Server
    def attempt_to_connect(self):
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

    def connect(self):
        if debug_level >= DEBUG_LEVEL.INFO:
            print(COLORS.OKCYAN + 'Attempting to connect to {} (Timeout: {}s)'.format(self.server, self.TIMEOUT) + COLORS.ENDC)

        # Retry to connect to the server
        start = time.time()

        while (time.time() - start) < self.TIMEOUT:
            self.attempt_to_connect()

            if self.connected:
                break

        # Run the client (if connection succesful)
        if not self.connected:
            if debug_level >= DEBUG_LEVEL.INFO:
                print(COLORS.FAIL + 'Connection timed out. Server {} not found'.format(SERVER) + COLORS.ENDC)
        else:
            if debug_level >= DEBUG_LEVEL.INFO:
                print(COLORS.OKGREEN + 'Successfully connected as Client {}'.format(client.socket.getsockname()) + COLORS.ENDC)
            self.run()


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
            if debug_level >= DEBUG_LEVEL.INFO:
                print(COLORS.OKCYAN + 'Waiting for model from server...(Timeout ' + str(self.TIMEOUT) + 's)' + COLORS.ENDC)

            start = time.time()

            while not self.comm_handler.has_message():
                # TODO: sleep a bit
                continue

            if not self.comm_handler.has_message():
                if debug_level >= DEBUG_LEVEL.INFO:
                    print(COLORS.WARNING + "Time Limit Exceeded: Weights not received." + COLORS.ENDC)
            else:
                if debug_level >= DEBUG_LEVEL.INFO:
                    print(COLORS.OKGREEN + "Weights received." + COLORS.ENDC)

                # Get message
                weights = self.comm_handler.get_message()

                # sleep communication
                self.comm_handler.pause()

                if debug_level >= DEBUG_LEVEL.INFO:
                    print(COLORS.OKCYAN + "Training local model..." + COLORS.ENDC)

                # Load weights
                self.trainer.load_weights(weights)

                # Train model
                self.trainer.train()

                if debug_level >= DEBUG_LEVEL.INFO:
                    print(COLORS.OKGREEN + "Training complete." + COLORS.ENDC)
                    print(COLORS.OKCYAN + "Sending update to server..." + COLORS.ENDC)

                # Compute focused update
                update = self.trainer.focused_update()
                print(len(update))

                # start communication
                self.comm_handler.start()

                # Send update to the server
                self.comm_handler.queue_message(update)

                if debug_level >= DEBUG_LEVEL.INFO:
                    print(COLORS.OKGREEN + "Update sent." + COLORS.ENDC)


### Main Code ###

SERVER = (socket.gethostbyname('localhost'), 8080)
#SERVER = ('192.168.2.26', 12050)   # TODO: pickle message gets truncated over local network

if __name__ == '__main__':

    # Get client index from command line
    idx = int(sys.argv[1])
    nums = [[3, 5, 7, 9], [0, 1, 8], [2, 4, 6]]

    # Instantiate FL client with Training program
    client = FLClient(SERVER, client_trainer.ClientTrainer(nums[idx]))
    client.connect()
