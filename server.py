import time, sys, threading, errno
import socket

import queue
import pickle

import utils
from random import sample

import server_trainer


class Server():
    def __init__(self, host):
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

            print('Established connection to {}'.format(client_addr))

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
        self.aggregated_update = None
        self.broadcasted = False

        # TODO: Encapsulate these in a class.
        # FL Model trainer
        self.trainer = trainer
        self.subset_size = 3 # Default

    # Executes FL Training Loop
    def train(self):
        while True:
            # select clients if no model has been broadcasted.
            if not self.broadcasted:
                self.select_clients(self.subset_size)

            # while clients exist and a model has been broadcasted but no aggreated update has been created...
            while (self.aggregated_update is None) and len(self.client_subset) > 0 and self.broadcasted:
                # Try to create an aggregated update.
                self.aggregated_update = self.aggregate_updates()

            # if an aggregated update has been created...
            if self.aggregated_update is not None:
                # Pause communication
                self.pause()

                # Update the model using aggregated update.
                self.update_model(self.aggregated_update)
                self.aggregated_update = None

                # Reset client subset (to be re-selected)
                self.client_subset = []

                # Restart communication
                self.start()

            # Broadcast to Client Subset
            # NOTE: if client subset empty, broadcast will return False
            self.broadcasted = self.broadcast_model()

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

BUFFER_TIME = 20

if __name__ == '__main__':
    # the socket for the server.
    server_hostname = socket.gethostname()
    server_port = 8080

    # Initialize the FL server.
    flServer = FLServer((server_hostname, server_port),  server_trainer.ServerTrainer())

    # Allow client to connect
    flServer.start()

    # Buffer for clients to connect
    print('Buffer time for Clients to connect:', BUFFER_TIME)
    time.sleep(BUFFER_TIME)

    # Train the FL server model.
    print('Starting FL Training Loop')
    flServer.train()
