import time, sys, threading, errno, socket, queue, pickle, random, select
from random import sample

import utils
from utils import DEBUG_LEVEL, TERM, STATUS, Communication_Handler

import mphe
import server_trainer

debug_level = DEBUG_LEVEL.INFO

class Server():
    def __init__(self, host):
        if debug_level >= DEBUG_LEVEL.INFO:
            TERM.write_info('Started server at ' + str(host))

        # the socket to listen for connections on.
        self.listener_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
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

    def __init__(self, host, trainer):
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
        
        # Encryption module.
        self.encrpyter = MPHEServer()
        
        # Timeout.
        self.TIMEOUT = 100000000000

    def setup(self):
        # select a subset of the clients.
        if debug_level >= DEBUG_LEVEL.INFO:
            TERM.write_info("Selecting clients...")

        self.select_clients(self.subset_size)
        if debug_level >= DEBUG_LEVEL.INFO:
            TERM.write_success('Successfuly selected clients.')
            TERM.write_info("Establishing individual security parameters...")
        # establish the individual security parameters with each client.
        security_params = (self.encrypter.params, self.encrypter.secret_key, self.encrpyter.gen_crs())
        self.broadcast(self.selected_clients_by_addr.keys, security_params)
        
        # attempt to get responses from the clients.
        if STATUS.failure(self.get_responses()):
            if debug_level >= DEBUG_LEVEL.INFO:
                TERM.write_warning('Time Limit Exceeded: Failed to establish individual security parameters.')
            return STATUS.FAILURE

        if debug_level >= DEBUG_LEVEL.INFO:
            TERM.write_success('Successfuly estaablished individual security parameters.')
            TERM.write_info("Establishing collective security parameters...")

        # establish the collective security parameters.
        cpk = server.col_key_gen(list(self.selected_client_responses.values()))
        self.selected_client_responses = {}
        self.broadcast(self.selected_clients_by_addr.keys, cpk)
        
        # attempt to get acknowledgements from the clients.
        if STATUS.failure(self.get_responses()):
            if debug_level >= DEBUG_LEVEL.INFO:
                TERM.write_warning('Time Limit Exceeded: Failed to establish collective security parameters.')
            return STATUS.FAILURE

        if debug_level >= DEBUG_LEVEL.INFO:
            TERM.write_success('Successfuly estaablished collective security parameters.')
        
        return STATUS.SUCCESS

    def train(self):
        if debug_level >= DEBUG_LEVEL.INFO:
            TERM.write_info("Broadcasting model and requesting updates...")
        # send model to all clients.
        self.selected_client_responses = {}
        self.broadcast(self.selected_clients_by_addr.keys(), self.trainer.model.state_dict())
        
        # attempt to get updates from the clients.
        if STATUS.failure(self.get_responses()):
            if debug_level >= DEBUG_LEVEL.INFO:
                TERM.write_warning('Time Limit Exceeded: Failed to receive updates from all clients.')
            return STATUS.FAILURE

        if debug_level >= DEBUG_LEVEL.INFO:
            TERM.write_success("Successfully recieved updates from all clients.")
        return STATUS.SUCCESS

    def aggregate(self):
        if debug_level >= DEBUG_LEVEL.INFO:
            TERM.write_info("Aggregating updates...")
        agg = self.encrpyter.aggregate(list(self.selected_client_responses.values()))

        if debug_level >= DEBUG_LEVEL.INFO:
            TERM.write_success("Successfully aggregated updates.")
            TERM.write_info("Requesting collective security switches...")

        self.selected_client_responses = {}
        self.broadcast(self.selected_clients_by_addr.keys, agg)

        # attempt to get acknowledgement from the clients.
        if STATUS.failure(self.get_responses()):
            if debug_level >= DEBUG_LEVEL.INFO:
                TERM.write_warning('Time Limit Exceeded: Failed to receive acknowledgement from all clients.')
            return STATUS.FAILURE

        if debug_level >= DEBUG_LEVEL.INFO:
            TERM.write_success("Successfully recieved acknowledgement from all clients.")
        
        # perform collective key switching.
        cks_shares = list(self.selected_client_responses.values())
        self.encrpyter.col_key_switch(agg, cks_shares)
        # average the aggregate update.
        self.encrpyter.average(len(cks_shares))
        # load the new model.
        # TODO: HERE.
        return STATUS.SUCCESS

    # Executes FL Training Loop
    def loop(self):
        while len(self.connected_clients_by_addr) > 0:
            if (STATUS.failed(self.setup()): continue
            if (STATUS.failed(self.train()): continue
            if (STATUS.failed(self.aggregate()): continue

        if debug_level >= DEBUG_LEVEL.INFO:
            TERM.write_failure("All clients disconected.")

    # Randomly select subset of all client to train on
    # TODO: Customizable random selection
    def select_clients(self, subset_size):
        with self.client_lock:
            num_clients = len(self.connected_clients_by_addr)
            selected_client_addrs = sample(self.connected_clients_by_addr.keys(), min(subset_size, num_clients))
            for addr in selected_client_addrs:
                sock = self.connected_clients_by_addr[addr]
                self.selected_clients_by_addr[addr] = sock
                self.selected_clients_by_sock[sock] = addr
    
    # Retrieve responses of selected clients
    def get_responses(self, timeout = 1000000):
        self.selected_client_responses = {}
        start = time.time()

        while time.time() - start < self.TIMEOUT:
            # attempt to get a message from another client.
            readable_clients_socks, _, _ = select.select(self.selected_clients_by_addr.values(), [], [])
            for sock in readable_clients_socks:
                self.selected_client_responses[self.selected_clients_by_sock[sock]] = Communication_Handler.recv_msg(sock)
            if len(self.selected_client_responses) == len(self.selected_clients_by_addr):
                return SUCCESS
        return len(self.selected_client_responses)

    # Update server model (centralized model)
    def update_model(self, aggregated_update):
        self.trainer.update(aggregated_update)

### Main Code ###

BUFFER_TIME = 5

if __name__ == '__main__':
    # the socket for the server.
    server_hostname = socket.gethostbyname('localhost')
    server_port = 8080

    # Initialize the FL server.
    flServer = FLServer((server_hostname, server_port),  server_trainer.ServerTrainer())

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
