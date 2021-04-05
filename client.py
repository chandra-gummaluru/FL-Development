import time, sys, multiprocessing, errno, socket, random

import utils
from utils import DEBUG_LEVEL, STATUS, TERM, Communication_Handler

import mphe
from compressor import Compressor
import client_trainer

debug_level = DEBUG_LEVEL.INFO

# NOTE: Seed for determining compression dropout indices. This seed serves simulation
# purposes only. In theory, a completed Federated Dropout compression scheme would
# send the relevant seed to each client over the network at each round.
RANDOM = random.Random(utils.SEED)

class Client():
    def __init__(self, server, name = None):
        # Socket for communication
        self.server = server
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.connected = False

        self.name = 'anon_client' if not name else name

    # Attempt to immediately connect to the Server.
    def attempt_to_connect(self, TIMEOUT):
        try:
            # Connect socket
            self.sock.connect(self.server)
            self.connected = True
        except:
            self.connected = False

    # Try to connect to the Server for TIMEOUT duration
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
    def __init__(self, server, trainer, cipher=None):
        super(FLClient, self).__init__(server)

        # Training Program (specific to the model being trained)
        self.trainer = trainer
        self.cipher = cipher
        self.cpk = None
        self.TIMEOUT = float('inf')

    ### FL Training Loop ###

    # Main loop
    def loop(self):
        while True:
            # Establish Encryption Scheme
            if STATUS.failed(self.setup()): continue

            # Receive and Decompress Server Model + Train on local dataset
            if STATUS.failed(self.train()): continue

            # Compress, Encrypt and Send Update + Reset Encryption Scheme
            if STATUS.failed(self.update()): continue

    # Establish Encryption Scheme
    def setup(self):
        if debug_level >= DEBUG_LEVEL.INFO:
            TERM.write_info('Waiting for selection...')

        # TODO: Acknowledge selection by the Server

        if self.cipher is not None:
            # Cache security parameters from the Server
            security_params = self.wait_for_response()
            params, secret_key, crs = security_params

            # TODO: Check if what was actually received is a set of security parameters

            self.cipher.define_scheme(params, secret_key)
            self.cipher.crs = crs

            # Send CKG Share to the Server (for collective public key generation)
            self.cipher.gen_key()

            if debug_level >= DEBUG_LEVEL.INFO:
                TERM.write_info('Sending CKG share to server...')

            Communication_Handler.send_msg(self.sock, self.cipher.gen_ckg_share())

            # Cache collective public key
            self.cpk = self.wait_for_response()

            # TODO: Check if what was actually received is the Collective Public Key

            if debug_level >= DEBUG_LEVEL.INFO:
                TERM.write_success('Recieved CPK result.')

        return STATUS.SUCCESS

    # Receive and Decompress Server Model + Train on local dataset
    # NOTE: in theory client receives encrypted server weights, but for now it does not
    def train(self):
        if debug_level >= DEBUG_LEVEL.INFO:
            TERM.write_info('Waiting for weights from server...')

        # Receive Server model weights
        weights = self.wait_for_response()

        # TODO: Decompress weights

        # Initialize Client model with Server's weights
        self.trainer.load_weights(weights)

        if debug_level >= DEBUG_LEVEL.INFO:
            TERM.write_success('Successfully recieved weights from the server.')
            TERM.write_info('Training model...')

        # Train model on local dataset
        self.trainer.train()

        if debug_level >= DEBUG_LEVEL.INFO:
            TERM.write_success("Successfully trained model.")

        return STATUS.SUCCESS

    # Compress, Encrypt and Send Update + Reset Encryption Scheme
    def update(self):
        focused_update = self.trainer.focused_update()

        # TODO: Compress update
        # NOTE: the following simulates compression by setting a fraction of
        # the model weights to zero but sends the full model nonetheless.
        if debug_level >= DEBUG_LEVEL.INFO:
            TERM.write_info("Simulate Compression!")
        
        zeros_seed = RANDOM.randint(0, utils.SEED)
        Compressor.dropout_weights(self.trainer.model, zeros_seed)

        # Encrypt update
        if self.cipher is not None:
            flat_update = utils.state_dict_to_list(focused_update)
            focused_update = self.cipher.encrypt(self.cpk, flat_update)
        
        if debug_level >= DEBUG_LEVEL.INFO:
            TERM.write_info("Sending update to server...")

        # Send update to the Server
        Communication_Handler.send_msg(self.sock, focused_update)

        if debug_level >= DEBUG_LEVEL.INFO:
            TERM.write_success("Update sent.")

        # Reset encryption scheme
        if self.cipher is not None:
            # Retrieve aggregate from the Server that we want to key switch
            if debug_level >= DEBUG_LEVEL.INFO:
                TERM.write_info("Waiting for aggregate update...")
            
            # TODO: Check if what was actually received is the aggregate update

            aggregate_update = self.wait_for_response()

            # Send CKS Share to the Server (for collective key switching)
            if debug_level >= DEBUG_LEVEL.INFO:
                TERM.write_success("Successfully recieved aggregate update.")
                TERM.write_info('Sending CKS share...')

            cks_share = self.cipher.gen_cks_share(aggregate_update)
            Communication_Handler.send_msg(self.sock, cks_share)

            if debug_level >= DEBUG_LEVEL.INFO:
                TERM.write_success("Successfully sent CKS share.")

        return STATUS.SUCCESS

    ### Helper Functions ###

    def wait_for_response(self):
        response = None
        start_time = time.time()

        # Attempt to get a response from the Server
        while response == None and (time.time() - start_time < self.TIMEOUT):
            response = Communication_Handler.recv_msg(self.sock)
            
        return response


### MAIN CODE ###

SERVER = (socket.gethostbyname('localhost'), 8080)

if __name__ == '__main__':

    # Get client index from command line
    idx = int(sys.argv[1])
    nums = [[3, 5, 7, 9], [0, 1, 8], [2, 4, 6]]

    # Instantiate FL client with Training program
    client = FLClient(SERVER, client_trainer.ClientTrainer(nums[idx]), cipher=mphe.MPHEClient())
    client.connect(5)
