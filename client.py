import time, sys, multiprocessing, errno, socket

import utils
from utils import DEBUG_LEVEL, TERM, Communication_Handler

import mphe

import client_trainer

debug_level = DEBUG_LEVEL.INFO

class Client():
    def __init__(self, server, name = None):
        # Socket for communication
        self.server = server
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.connected = False

        self.name = 'anon_client' if not name else name

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
        self.encrypter = MPHEClient()
        self.TIMEOUT = 100000000000

    ### FL Training Loop ###

    def wait_for_response(self, timeout = None):
        response = None
        if timeout == None:
            while response == None:
                # attempt to get the response.
                response = Communication_Handler.recv_msg(self.sock)
        else:
            start_time = time.time()
            while response == None and (time.time() - start_time < self.TIMEOUT):
                # attempt to get the response.
                response = Communication_Handler.recv_msg(self.sock)
        return response

    def setup(self):
        if debug_level >= DEBUG_LEVEL.INFO:
            TERM.write_info('Idle...')
        
        # establish individual security parameters with the server.
        security_params = wait_for_response()
        if debug_level >= DEBUG_LEVEL.INFO:
            TERM.write_info('Establishing security parameters with server....')

        params, secret_key, crs = security_params
        self.encrypter.define_scheme(params, secret_key)
        self.encrypter.crs = crs

        Communication_Handler.send_msg(self.sock, self.encrypter.define_scheme(params, secret_key))
        cpk = wait_for_response()

        if debug_level >= DEBUG_LEVEL.INFO:
            TERM.write_success('Successfully established security parameters with server.')
        #TODO: Add failure case.

    def train(self):
        if debug_level >= DEBUG_LEVEL.INFO:
            TERM.write_info('Waiting for weights from server...')

        weights = wait_for_response()
        weights = self.encrypter.decrypt(weights)

        if debug_level >= DEBUG_LEVEL.INFO:
            TERM.write_success('Successfully recieved weights from the server.')
            TERM.write_info('Training model...')

        self.trainer.train()
        if debug_level >= DEBUG_LEVEL.INFO:
            TERM.write_success("Successfully trained model.")

    def update(self):
        if debug_level >= DEBUG_LEVEL.INFO:
            TERM.write_info("Sending update to server...")

        self.encrypter.encrypt(cpk, )

    def run(self):
        if debug_level >= DEBUG_LEVEL.INFO:
            TERM.write_info('Setting up secure communication channel with server...')
            
        security_params = wait_for_response()
        if security_params == None:
            if debug_level >= DEBUG_LEVEL.INFO:
                TERM.write_failure('Failed to setup secure communication channel with server.')
            return
        
        params, secret_key, crs = security_params
        Communication_Handler.send_msg(self.sock, self.encrypter.define_scheme(params, secret_key))

        cpk = wait_for_response()
        if cpk == None:
            if debug_level >= DEBUG_LEVEL.INFO:
                TERM.write_failure('Failed to setup secure communication channel with server.')
            return

        while True:
            # Wait for weights from the server
            if debug_level > DEBUG_LEVEL.IFNO:
                TERM.write_info('Waiting for model from server...(Timeout: ' + str(self.TIMEOUT) + ')')

                weights = wait_for_response()
                if weights == None:
                    if debug_level >= DEBUG_LEVEL.INFO:
                        TERM.write_warning("Time Limit Exceeded: Failed to recieve weights from the server.")
                else:
                    if debug_level >= DEBUG_LEVEL.INFO:
                        TERM.write_success("Successfully recieved weights from server.")
                        TERM.write_info("Training local model...")

                    # Load weights
                    self.encrypter.crs = crs
                    weights = self.encrypter.decrypt(weights)
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
