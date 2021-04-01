import time, sys, threading, errno, socket, queue, pickle, random, select
from random import sample

import utils
from utils import DEBUG_LEVEL, TERM, STATUS, Communication_Handler

import mphe
from compressor import Compressor
import server_trainer

debug_level = DEBUG_LEVEL.INFO

# NOTE: Seed for determining compression dropout indices. This seed serves simulation
# purposes only. In theory, a completed Federated Dropout compression scheme would
# send the relevant seed to each client over the network at each round.
RANDOM = random.Random(utils.SEED)

class Server():
    def __init__(self, host):
        if debug_level >= DEBUG_LEVEL.INFO:
            TERM.write_info('Started server at ' + str(host))

        # the socket to listen for connections on.
        self.listener_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.listener_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.listener_sock.bind(host)

        self.listener_process = None
        self.listening = False

        self.client_lock = threading.Lock()

        # the set of connected clients.
        self.connected_clients_by_sock = {}
        self.connected_clients_by_addr = {}

    # Connects to the clients (and caches them).
    def listen_for_clients(self):
        # TODO: make number bigger/variable
        self.listener_sock.listen(5)

        while self.listening:
            # Accept connection.
            client_sock, client_addr = self.listener_sock.accept()

            if debug_level >= DEBUG_LEVEL.INFO:
                TERM.write_success('Established connection to {}'.format(client_addr))

            # cache the client socket.
            self.connected_clients_by_addr[client_addr] = client_sock
            self.connected_clients_by_sock[client_sock] = client_addr

    # Starts listener thread to add connected clients.
    def start(self):
        self.listening = True
        self.listener_process = threading.Thread(target = self.listen_for_clients, daemon = True)
        self.listener_process.start()

    # Stops listener thread.
    def stop(self):
        self.listening = False

    # Removes the specified client if it exists.
    def remove_client(self, addr):
        with self.client_lock:
            sock = self.connected_clients_by_addr.pop(addr)
            self.connected_clients_by_sock.pop(sock)

            if sock:
                sock.close()

    # Broadcasts a message to a subset of the clients
    def broadcast(self, client_addrs, msg):
        with self.client_lock:
            for client_addr in client_addrs:
                Communication_Handler.send_msg(self.connected_clients_by_addr[client_addr], msg)

class FLServer(Server):
    def __init__(self, host, trainer, cipher=None):
        super(FLServer, self).__init__(host)

        # Client selected for FL.
        self.selected_clients_by_addr = {}
        self.selected_clients_by_sock = {}

        self.selected_client_responses = {}

        # Flags / Cache for FL loop
        self.aggregated_update = None # whether the current updates have been aggreated.

        # TODO: Encapsulate these in a class.
        # FL Model trainer
        self.trainer = trainer
        self.subset_size = 3 # Default

        # Encryption module
        self.cipher = cipher

        # Timeout.
        self.TIMEOUT = float('inf')

    ### FL Training Loop ###

    # Main loop
    def loop(self):
        while len(self.connected_clients_by_addr) > 0:
            # Select Clients + Establish Encryption Scheme
            if STATUS.failed(self.setup()): continue

            # Compress and Send Model + Wait for Client Updates
            if STATUS.failed(self.train()): continue

            # Aggregate Client Updates + Reset Encryption Scheme + Decompress Model
            if STATUS.failed(self.aggregate()): continue

        if debug_level >= DEBUG_LEVEL.INFO:
            TERM.write_failure("All clients disconected.")

    # Select Clients + Establish Encryption Scheme
    def setup(self):
        # Select a subset of the clients
        if debug_level >= DEBUG_LEVEL.INFO:
            TERM.write_info("Selecting clients...")

        self.select_clients(self.subset_size)

        if debug_level >= DEBUG_LEVEL.INFO:
            TERM.write_success('Successfuly selected clients.')
        
        # Establish encryption scheme between all parties
        if self.cipher is not None:
            if debug_level >= DEBUG_LEVEL.INFO:
                TERM.write_info("Requesting CKG shares...")

            # Send the security parameters to all clients
            security_params = (self.cipher.params, self.cipher.secret_key, self.cipher.gen_crs())
            self.broadcast(self.selected_clients_by_addr.keys(), security_params)

            # Receive CKG Shares from Clients (for collective public key generation)
            if STATUS.failed(self.get_responses()):
                if debug_level >= DEBUG_LEVEL.INFO:
                    TERM.write_warning('Time Limit Exceeded: Failed to receive CKG shares from all clients.')
                return STATUS.FAILURE
            
            # TODO: Check if what was actually received is a CKG Share

            if debug_level >= DEBUG_LEVEL.INFO:
                TERM.write_success('Successfuly received CKG shares from all clients.')
                TERM.write_info("Performing CKG...")

            # Distribute collective public key (for Encryption)
            cpk = self.cipher.col_key_gen(list(self.selected_client_responses.values()))
            
            self.selected_client_responses = {}
            self.broadcast(self.selected_clients_by_addr.keys(), cpk)

            if debug_level >= DEBUG_LEVEL.INFO:
                TERM.write_success('Successfully performed CKG.')

        return STATUS.SUCCESS

    # Compress and Send Model + Wait for Client Updates
    # NOTE: in theory server should send encrypted model weights, but for now it does not
    def train(self):
        # TODO: Compress model
        # NOTE: the following simulates compression by setting a fraction of
        # the model weights to zero but sends the full model nonetheless.
        if debug_level >= DEBUG_LEVEL.INFO:
            TERM.write_info("Simulate Compression!")
        
        zeros_seed = RANDOM.randint(0, utils.SEED)
        Compressor.dropout_weights(self.trainer.model, zeros_seed)

        # Broadcast Server model to Clients
        if debug_level >= DEBUG_LEVEL.INFO:
            TERM.write_info("Broadcasting model and requesting updates...")

        self.selected_client_responses = {}
        self.broadcast(self.selected_clients_by_addr.keys(), self.trainer.model.state_dict())

        # Wait until Clients complete training and Server receives updates
        if STATUS.failed(self.get_responses()):
            if debug_level >= DEBUG_LEVEL.INFO:
                TERM.write_warning('Time Limit Exceeded: Failed to receive updates from all clients.')
            return STATUS.FAILURE

        if debug_level >= DEBUG_LEVEL.INFO:
            TERM.write_success("Successfully recieved updates from all clients.")
        
        return STATUS.SUCCESS

    # Aggregate Client Updates + Reset Encryption Scheme + Decompress Model
    def aggregate(self):
        # ASSUME: Client updates can be decompressed post-aggregation
        
        updates = list(self.selected_client_responses.values())

        if debug_level >= DEBUG_LEVEL.INFO:
            TERM.write_info("Aggregating updates...")

        if self.cipher is None:
            # Aggregate Client updates
            update = self.trainer.aggregate(updates)

            if debug_level >= DEBUG_LEVEL.INFO:
                TERM.write_success("Successfully aggregated updates.")
        else:
            # Aggregate encrypted Client updates
            agg = self.cipher.aggregate(updates)

            if debug_level >= DEBUG_LEVEL.INFO:
                TERM.write_success("Successfully aggregated updates.")
                TERM.write_info("Requesting CKS shares...")

            # Commence encryption scheme reset by sending aggregate to Clients
            self.selected_client_responses = {}
            self.broadcast(self.selected_clients_by_addr.keys(), agg)

            # Retrieve CKS Shares from Clients (for collective key switching)
            if STATUS.failed(self.get_responses()):
                if debug_level >= DEBUG_LEVEL.INFO:
                    TERM.write_warning('Time Limit Exceeded: Failed to receive CKS shares from all clients.')
                return STATUS.FAILURE

            # TODO: Check if what was actually received is a CKS Share

            if debug_level >= DEBUG_LEVEL.INFO:
                TERM.write_success("Successfully recieved CKS shares from all clients.")

            # Perform collective key switching
            cks_shares = list(self.selected_client_responses.values())
            self.cipher.col_key_switch(agg, cks_shares)

            # Average the aggregate update
            self.cipher.average(len(cks_shares))

            # Decrypted update
            update = utils.list_to_state_dict(self.cipher.decrypt(), self.trainer.model)

        # Update Server model
        self.trainer.update(update)

        # TODO: Decompress Server model
        
        return STATUS.SUCCESS

    ### Helper Functions ###

    # Randomly select subset of all client to train on
    # TODO: Customizable random selection
    def select_clients(self, subset_size):
        with self.client_lock:
            # Sample Clients
            num_clients = len(self.connected_clients_by_addr)
            selected_client_addrs = sample(self.connected_clients_by_addr.keys(), min(subset_size, num_clients))
            
            # Cache selected Clients
            for addr in selected_client_addrs:
                sock = self.connected_clients_by_addr[addr]
                self.selected_clients_by_addr[addr] = sock
                self.selected_clients_by_sock[sock] = addr

    # Retrieve responses of selected clients
    def get_responses(self):
        self.selected_client_responses = {}

        # Try for at most TIMEOUT seconds
        start = time.time()

        while time.time() - start < self.TIMEOUT:
            # Attempt to get a message from another client
            readable_clients_socks, _, _ = select.select(self.selected_clients_by_addr.values(), [], [])
            
            for sock in readable_clients_socks:
                self.selected_client_responses[self.selected_clients_by_sock[sock]] = Communication_Handler.recv_msg(sock)
            
            # All responses received
            if len(self.selected_client_responses) == len(self.selected_clients_by_addr):
                return STATUS.SUCCESS
        
        return STATUS.FAILURE


### MAIN CODE ###

BUFFER_TIME = 5

if __name__ == '__main__':
    # the socket for the server.
    server_hostname = socket.gethostbyname('localhost')
    server_port = 8080

    # Initialize the FL server.
    flServer = FLServer((server_hostname, server_port),  server_trainer.ServerTrainer(), cipher=mphe.MPHEServer())

    # Allow client to connect
    flServer.start()

    # Buffer for clients to connect
    TERM.write_info('Waiting for clients to connect...(Timeout: ' + str(BUFFER_TIME) + 's)')
    time.sleep(BUFFER_TIME)

    if len(flServer.connected_clients_by_addr) == 0:
        TERM.write_failure("Time limit exceeed: No clients connected.")
    else:
        # Train the FL server model.
        TERM.write_warning('Time limit exceeded: ' + str(len(flServer.connected_clients_by_addr)) + ' client(s) connected.')
        TERM.write_info("Starting FL training loop...")
        flServer.loop()
