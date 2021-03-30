import time, sys, threading, errno, socket, queue, pickle, random, select
from random import sample

import utils
from utils import DEBUG_LEVEL, TERM, Communication_Handler

import server_trainer
import compressor
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

    def __init__(self, host, trainer, compressor):
        super(FLServer, self).__init__(host)

        # Client selected for FL.
        self.selected_clients_by_addr = {}
        self.selected_clients_by_sock = {}

        self.selected_clients_updates = {}

        # Flags / Cache for FL loop
        self.aggregated_update = None # whether the current updates have been aggreated.

        # TODO: Encapsulate these in a class.
        # FL Model trainer
        self.trainer = trainer
        self.compressor = compressor
        self.subset_size = 3 # Default

        # Timeout.
        self.TIMEOUT = 100000000000

    # Executes FL Training Loop
    def train(self):
        while len(self.connected_clients_by_addr) > 0:
            # select a subset of the clients and broadcast the model.
            if debug_level >= DEBUG_LEVEL.INFO:
                TERM.write_info("Selecting clients...")

            self.select_clients(self.subset_size)

            if debug_level >= DEBUG_LEVEL.INFO:
                TERM.write_info("Broadcasting model...")

            self.broadcast_model()

            if debug_level >= DEBUG_LEVEL.INFO:
                TERM.write_info("Waiting for updates...(Timeout: " + str(self.TIMEOUT) + ")")

            start = time.time()

            # wait for each client's update and then aggregate.
            while (self.aggregated_update is None) and time.time() - start < self.TIMEOUT:

                compressed_update, addr = self.wait_for_next_update()
                # decompress the update here.
                decompressed_update = self.compressor.decompress(compressed_update)

                # cache the decompressed up.
                self.selected_clients_updates[addr] = decompressed_update
                self.attempt_to_aggregate_updates()

            # if an aggregated update has been created...
            if self.aggregated_update is not None:
                # Stop communication (temporarily)
                self.stop()

                if debug_level >= DEBUG_LEVEL.INFO:
                    TERM.write_success("All updates received.")
                    TERM.write_info("Aggregating updates...")

                # Update the model using aggregated update.
                self.update_model(self.aggregated_update)
                self.aggregated_update = None

                # reset the selected client address list (to be re-selected)
                self.selected_clients_by_addr = {}
                self.selected_clients_updates = {}

                if debug_level >= DEBUG_LEVEL.INFO:
                    TERM.write_info("Sending aggregated update to clients...")

                # Restart communication.
                self.start()
            else:
                if debug_level >= DEBUG_LEVEL.INFO:
                    TERM.write_warning("Time-limit exceeded: Some updates were not received.")

        if debug_level >= DEBUG_LEVEL.INFO:
            TERM.write_failure("All clients disconected.")

    ### FL Training Loop ###

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

    # Broadcast model to selected clients so they can train
    def broadcast_model(self):
        # Verify there are clients
        if len(self.selected_clients_by_addr) > 0:
            model = self.trainer.model
            compressed_updates = self.compressor.compress(model)
            self.broadcast(self.selected_clients_by_addr.keys(), compressed_updates)
            return True

        return False

    # Wait for the next update.
    def wait_for_next_update(self):
        # attempt to get a message from more clients.
        readable_clients_socks, _, _ = select.select(self.selected_clients_by_addr.values(), [], [])
        sock = readable_clients_socks[0]
        return Communication_Handler.recv_msg(sock), self.selected_clients_by_sock[sock]
            
            
    # Aggregate Updates once the subset of selected clients are ready
    def attempt_to_aggregate_updates(self):
        # check if all clients have provided data.
        if len(self.selected_clients_updates) == len(self.selected_clients_by_addr):
            # Aggregate the updates.
            self.aggregated_update = self.trainer.aggregate(self.selected_clients_updates)

    # Update server model (centralized model)
    def update_model(self, aggregated_update):
        self.trainer.update(aggregated_update)

### Main Code ###

BUFFER_TIME = 10

if __name__ == '__main__':
    # the socket for the server.
    server_hostname = socket.gethostbyname('localhost')
    server_port = 8080

    # Initialize the FL server.
    flServer = FLServer((server_hostname, server_port),  server_trainer.ServerTrainer(), compressor.Compressor()) 
    #TODO: Create a compressor and put it into the FLServer.

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
        flServer.train()
