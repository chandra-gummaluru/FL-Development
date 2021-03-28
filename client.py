import time, sys, multiprocessing, errno, socket

import utils
from utils import DEBUG_LEVEL, TERM, Communication_Handler

import client_trainer

debug_level = DEBUG_LEVEL.INFO

class Client():
    def __init__(self, server):
        # Socket for communication
        self.server = server
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.connected = False

    # Attempt to connect to the Server.
    def attempt_to_connect(self, TIMEOUT):
        try:
            # Connect socket
            self.sock.connect(self.server)
            self.connected = True
        except:
            self.connected = False

    def connect(self, TIMEOUT):
        if debug_level >= DEBUG_LEVEL.INFO:
            TERM.write_info('Attempting to connect to {} (Timeout: {}s)'.format(self.server, TIMEOUT))

        # Retry to connect to the server
        start = time.time()

        while (time.time() - start) < TIMEOUT:
            self.attempt_to_connect(TIMEOUT)

            if self.connected:
                break

        # Run the client (if connection succesful)
        if not self.connected:
            if debug_level >= DEBUG_LEVEL.INFO:
                TERM.write_failure('Time limit exceeded: {} not found'.format(SERVER))
        else:
            if debug_level >= DEBUG_LEVEL.INFO:
                TERM.write_success('Successfully connected to {} as {}'.format(SERVER, self.sock.getsockname()))
            self.run()


# Handles FL Client training loop logic
class FLClient(Client):
    def __init__(self, server, trainer):
        super(FLClient, self).__init__(server)

        # Training Program (specific to the model being trained)
        self.trainer = trainer

    ### FL Training Loop ###

    def run(self):
        while True:
            # Wait for weights from the FLServer
            if debug_level >= DEBUG_LEVEL.INFO:
                TERM.write_info('Waiting for model from server...(Timeout ' + str(5) + 's)')

                start_time = time.time()
                weights = None
                while ((weights == None) and (time.time() - start_time < 5)):
                    # get the weights.
                    weights = Communication_Handler.recv_msg(self.sock)

                if weights == None:
                    if debug_level >= DEBUG_LEVEL.INFO:
                        TERM.write_warning("Time Limit Exceeded: Weights not received.")
                else:
                    if debug_level >= DEBUG_LEVEL.INFO:
                        TERM.write_success("Weights received.")
                        TERM.write_info("Training local model...")

                    # Load weights
                    self.trainer.load_weights(weights)

                    # Train model
                    self.trainer.train()

                    if debug_level >= DEBUG_LEVEL.INFO:
                        TERM.write_success("Training complete.")
                        TERM.write_info("Sending update to server...")

                    # Compute focused update
                    update = self.trainer.focused_update()

                    # Send update to the server
                    Communication_Handler.send_msg(self.sock, update)

                    if debug_level >= DEBUG_LEVEL.INFO:
                        TERM.write_success("Update sent.")

### Main Code ###

SERVER = (socket.gethostbyname('localhost'), 8080)
#SERVER = ('192.168.2.26', 12050)   # TODO: pickle message gets truncated over local network

if __name__ == '__main__':

    # Get client index from command line
    idx = int(sys.argv[1])
    nums = [[3, 5, 7, 9], [0, 1, 8], [2, 4, 6]]

    # Instantiate FL client with Training program
    client = FLClient(SERVER, client_trainer.ClientTrainer(nums[idx]))
    client.connect(5)
