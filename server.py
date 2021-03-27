import time, sys, threading, errno, socket, queue, pickle, random
from random import sample

import utils
from utils import DEBUG_LEVEL, COLORS

import server_trainer

debug_level = DEBUG_LEVEL.INFO

class Server():
    def __init__(self, host):
        if debug_level >= DEBUG_LEVEL.INFO:
            print(COLORS.OKCYAN + 'Started server at ' + str(host) + COLORS.ENDC)

        # Listening socket.
        self.s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.s.bind(host)

        # Threads
        self.listener_thread = None

        # a dictionary of client communication handlers indexed by client address.
        self.client_comm_handlers = {}
        self.client_lock = threading.Lock()

    # Starts listener thread to add connected clients.
    def start(self):
        self.listener_thread = utils.StoppableThread(target=self.listener, daemon=True)
        self.listener_thread.start()

        with self.client_lock:
            for comm_handler in self.client_comm_handlers.values():
                comm_handler.start()

    # Pauses communication threads
    def pause(self):
        self.listener_thread.stop()

        with self.client_lock:
            for comm_handler in self.client_comm_handlers.values():
                comm_handler.pause()

    # Connects to the clients (and cache them).
    def listener(self):
        # TODO: make number bigger/variable
        self.s.listen(5)

        while not self.listener_thread.isStopped():
            # Accept connection.
            client_sock, client_addr = self.s.accept()
            client_sock.setblocking(False)

            print(COLORS.OKGREEN + 'Established connection to {}'.format(client_addr) + COLORS.ENDC)

            # Create handlers for communication with clients.
            client_comm_handler = utils.Comm_Handler((client_sock, client_addr))

            # Cache Client Handler
            with self.client_lock:
                self.client_comm_handlers[client_addr] = client_comm_handler

            # Start Client Handler on new thread
            client_comm_handler.start()

    # Removes clients that do not communicate with the server anymore.
    def remove_broken_clients(self):
        with self.client_lock:
            broken_clients = []

            # Find broken clients.
            for client_addr in self.client_comm_handlers:
                if self.client_comm_handlers[client_addr].error:
                    broken_clients.append(client_addr)

            # Remove broken clients
            for client_addr in broken_clients:
                self.client_comm_handlers.pop(client_addr)

        return broken_clients

    # Broadcasts a message to a subset of the clients
    def broadcast(self, client_subset, msg):
        with self.client_lock:
            for client_addr in client_subset:
                self.client_comm_handlers[client_addr].queue_message(msg)


class FLServer(Server):

    def __init__(self, host, trainer):
        super(FLServer, self).__init__(host)

        # Client selected for FL
        self.client_subset = []

        # Flags / Cache for FL loop
        self.aggregated_update = None # whether the current updates have been aggreated.
        self.broadcasted = False # whether the aggreated update has been broadcasted.

        # TODO: Encapsulate these in a class.
        # FL Model trainer
        self.trainer = trainer
        self.subset_size = 3 # Default

        # Cypher for encryption and decryption of data.
        self.cypher = None

        # Timeout.
        self.TIMEOUT = 30

    # Executes FL Training Loop
    def train(self):
        while len(self.client_comm_handlers) > 0:
            # select a subset of the clients and broadcast the model.
            if not self.broadcasted:
                if debug_level >= DEBUG_LEVEL.INFO:
                    print(COLORS.OKCYAN + "Selecting clients..." + COLORS.ENDC)

                self.select_clients(self.subset_size)

                if debug_level >= DEBUG_LEVEL.INFO:
                    print(COLORS.OKCYAN + "Broadcasting model..." + COLORS.ENDC)

                self.broadcast_model()

            if debug_level >= DEBUG_LEVEL.INFO:
                print(COLORS.OKCYAN + "Waiting for updates (Timeout: 30s)..." + COLORS.ENDC)

            start = time.time()

            # while clients exist and a model has been broadcasted but no aggreated update has been created...
            while (self.aggregated_update is None) and len(self.client_subset) > 0 and time.time() - start < self.TIMEOUT:
                # Try to create an aggregated update.
                self.aggregated_update = self.aggregate_updates()

            # if an aggregated update has been created...
            if self.aggregated_update is not None:
                # Pause communication
                self.pause()

                if debug_level >= DEBUG_LEVEL.INFO:
                    print(COLORS.OKGREEN + "All updates received." + COLORS.ENDC)
                    print(COLORS.OKCYAN + "Aggregating updates..." + COLORS.ENDC)

                # Update the model using aggregated update.
                self.update_model(self.aggregated_update)
                self.aggregated_update = None

                # Reset client subset (to be re-selected)
                self.client_subset = []

                if debug_level >= DEBUG_LEVEL.INFO:
                    print(COLORS.OKCYAN + "Sending aggregated update to clients..." + COLORS.ENDC)

                # Restart communication
                self.start()
            else:
                if debug_level >= DEBUG_LEVEL.INFO:
                    print(COLORS.WARNING + "Time-limit exceeded: Some updates were not received." + COLORS.ENDC)

        if debug_level >= DEBUG_LEVEL.INFO:
            print(COLORS.FAIL + "All clients disconected." + COLORS.ENDC)

    ### FL Training Loop ###

    # Randomly select subset of all client to train on
    # TODO: Customizable random selection
    def select_clients(self, subset_size):
        with self.client_lock:
            num_clients = len(self.client_comm_handlers)
            self.client_subset = sample(self.client_comm_handlers.keys(), min(subset_size, num_clients))

    # Broadcast model to selected clients so they can train
    def broadcast_model(self):
        # Verify there are clients
        if len(self.client_subset) > 0:
            self.broadcast(self.client_subset, self.trainer.model.state_dict())

            return True

        return False

    # Retrieve updates of selected clients
    def get_updates(self):
        updates = []

        with self.client_lock:
            for client_addr in self.client_comm_handlers:
                update = self.client_comm_handlers[client_addr].get_message()

                if client_addr in self.client_subset:
                    updates.append(update)

        return updates

    # Aggregate Updates once Subset of Clients are Ready
    def aggregate_updates(self):
        # Remove all broken clients
        broken_clients = self.remove_broken_clients()

        for client in self.client_subset:
            if client in broken_clients:
                self.client_subset.remove(client)

        # Verify there are still clients to aggregate from.
        if len(self.client_subset) == 0:
            return None

        # Verify that the selected subset of clients have updates.
        if not self.do_all_selected_clients_have_updates():
            return None

        # Aggregate the updates.
        return self.trainer.aggregate(self.get_updates())

    # Update server model (centralized model)
    def update_model(self, aggregated_update):
        self.trainer.update(aggregated_update)

    ## Helper Functions ###

    # Ensure all selected clients have an update
    def do_all_selected_clients_have_updates(self):
        with self.client_lock:
            for client_addr in self.client_subset:
                if not self.client_comm_handlers[client_addr].has_message():
                    return False

        return True

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
    print(COLORS.OKCYAN + 'Waiting for clients to connect...(Timeout: ' + str(BUFFER_TIME) + 's)' + COLORS.ENDC)
    time.sleep(BUFFER_TIME)

    if len(flServer.client_comm_handlers) == 0:
        print(COLORS.FAIL + "Time limit exceeed: No clients connected." + COLORS.ENDC)
    else:
        # Train the FL server model.
        print(COLORS.WARNING + 'Time limit exceeded: ' + str(len(flServer.client_comm_handlers)) + ' client(s) connected.' + COLORS.ENDC)
        print(COLORS.OKCYAN + "Starting FL training loop..." + COLORS.ENDC)
        flServer.train()
