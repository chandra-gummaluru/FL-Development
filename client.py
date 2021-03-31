import time, sys, multiprocessing, errno, socket

import utils
from utils import DEBUG_LEVEL, TERM, Communication_Handler, STATUS

import mphe

import client_trainer

debug_level = DEBUG_LEVEL.INFO

class Client():
    def __init__(self, server, name = None):
        # Socket for communication
        self.server = server
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
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
            self.loop()


# Handles FL Client training loop logic
class FLClient(Client):
    def __init__(self, server, trainer):
        super(FLClient, self).__init__(server)

        # Training Program (specific to the model being trained)
        self.trainer = trainer
        self.encrypter = mphe.MPHEClient()
        self.cpk = None
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
            TERM.write_info('Waiting for selection...')

        # establish individual security parameters with the server.
        security_params = self.wait_for_response()
        if debug_level >= DEBUG_LEVEL.INFO:
            TERM.write_info('Sending CKG share to server...')

        params, secret_key, crs = security_params
        self.encrypter.define_scheme(params, secret_key)
        self.encrypter.crs = crs
        self.encrypter.gen_key()

        Communication_Handler.send_msg(self.sock, self.encrypter.gen_ckg_share())
        self.cpk = self.wait_for_response()

        if debug_level >= DEBUG_LEVEL.INFO:
            TERM.write_success('Recieved CPK result.')
        #TODO: Add failure case.
        return STATUS.SUCCESS

    def train(self):
        if debug_level >= DEBUG_LEVEL.INFO:
            TERM.write_info('Waiting for weights from server...')

        weights = self.wait_for_response()
        self.trainer.model.load_state_dict(weights)
        # print('(CLIENT) Received State dict entry:', self.trainer.model.state_dict()['conv1.weight'][0][0][0])
        #weights = self.encrypter.decrypt(weights)

        if debug_level >= DEBUG_LEVEL.INFO:
            TERM.write_success('Successfully recieved weights from the server.')
            TERM.write_info('Training model...')

        self.trainer.train()
        if debug_level >= DEBUG_LEVEL.INFO:
            TERM.write_success("Successfully trained model.")

        return STATUS.SUCCESS

    def update(self):
        if debug_level >= DEBUG_LEVEL.INFO:
            TERM.write_info("Sending update to server...")
        # print('flat update:', self.trainer.flat_update()[0])
        # print('(CLIENT) Update State dict entry:', self.trainer.model.state_dict()['conv1.weight'][0][0][0])
        encrypted_update = self.encrypter.encrypt(self.cpk, self.trainer.flat_update())
        # Send update to the server
        Communication_Handler.send_msg(self.sock, encrypted_update)

        if debug_level >= DEBUG_LEVEL.INFO:
            TERM.write_success("Update sent.")

        if debug_level >= DEBUG_LEVEL.INFO:
            TERM.write_info("Waiting for aggregate update...")
        aggregate_update = self.wait_for_response()

        if debug_level >= DEBUG_LEVEL.INFO:
            TERM.write_success("Successfully recieved aggregate update.")
            TERM.write_info('Sending CKS share...')

        cks_share = self.encrypter.gen_cks_share(aggregate_update)
        # Send update to the server
        Communication_Handler.send_msg(self.sock, cks_share)

        if debug_level >= DEBUG_LEVEL.INFO:
            TERM.write_success("Successfully sent CKS share.")

        return STATUS.SUCCESS

    def loop(self):
        while True:
            if STATUS.failed(self.setup()): continue
            if STATUS.failed(self.train()): continue
            if STATUS.failed(self.update()): continue

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
