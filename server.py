import time, socket, sys, threading, queue
import errno
import utils
from random import sample


# the socket for the server.
server_hostname = socket.gethostname()
server_port = 8080

# A generic client handler.
class Client_Handler():
    def __init__(self, client_sock, client_addr):
        # threads for sending and receiving messages.
        self.sender_thread = utils.StoppableThread(target=self.send, daemon=True)
        self.receiver_thread = utils.StoppableThread(target=self.receive, daemon=True)

        # Client Connection
        self.client_sock = client_sock
        self.client_addr = client_addr

        # queues for storing messages to send and receive.
        # incoming messages from the client.
        self.in_queue = queue.Queue(1)
        self.in_lock = threading.Lock()

        # outgoing messages to the client.
        self.out_queue = queue.Queue(1)
        self.out_lock = threading.Lock()

        # indicates whether the handler had an error.
        self.error = False

    # starts the handler.
    def start(self):
        self.sender_thread.start()
        self.receiver_thread.start()

    # stops the handler.
    def stop(self):
        self.sender_thread.stop()
        self.receiver_thread.stop()

        # close the client socket.
        self.client_sock.close()

    # callback to receive messages.
    def receive(self):
        while not self.receiver_thread.isStopped():
            try:
                # Wait for data from client
                # TODO: Accept larger messages
                msg = self.client_sock.recv(1024).decode()
            except socket.error as e:
                if e.args[0] in [ errno.EAGAIN, errno.EWOULDBLOCK ]:
                    # No data received (yet)
                    continue
                else:
                    # Remove broken client + end thread (by exiting)
                    print('Client {}: receive error {}'.format(self.client_addr, e))
                    self.error = True
                    self.stop()

                    return
            else:
                # Only accept messages if the queue is not full.
                with self.in_lock:
                    if self.in_queue.full():
                        continue

                    # Queue message received from client
                    self.in_queue.put(msg)
                    print('<{}> {}'.format(self.client_addr, msg)) # DEBUG
    
    # Determine if Client has an update/message
    def has_message(self):
        with self.in_lock:
            return not self.in_queue.empty()
    
    # Retrieve message (Client -> Server)
    def get_message(self):
        if self.in_queue.empty():
            return None
        
        with self.in_lock:
            msg = self.in_queue.get()
        
        return msg

    # callback to send messages.
    def send(self):
        while not self.sender_thread.isStopped():
            # Check there is a message to send
            if self.out_queue.empty():
                continue
            
            # Send queued message to Client
            with self.out_lock:
                msg = self.out_queue.get()

                try:
                    self.client_sock.send(msg.encode())
                except:
                    print('Client {}: Send Error \'{}\''.format(self.client_addr, sys.exc_info()[0]))
                    self.error = True
                    self.stop()

                    return

    # Put message to send (Server --> Client)
    def queue_message(self, msg):
        with self.out_lock:
            if self.out_queue.full():
                return
            
            self.out_queue.put(msg)

class Server():
    def __init__(self, host):
        # Listening Socket
        self.s = socket.socket()
        self.s.bind(host)

        # Threads
        self.listener_thread = utils.StoppableThread(target=self.listener, daemon=True)
        self.client_handlers = {}
        self.client_lock = threading.Lock()

    # Starts listener thread to add connected clients
    def start(self):
        self.listener_thread.start()
        
    # Connect to Clients (+ Cache them)
    def listener(self):
        # TODO: make number bigger/variable
        self.s.listen(5)

        while not self.listener_thread.isStopped():
            # Accept connection
            client_sock, client_addr = self.s.accept()
            client_sock.setblocking(False)

            print('Established connection to {}'.format(client_addr))

            # Create Client Handlers
            client_handler = Client_Handler(client_sock, client_addr)

            # Cache Client Handler
            with self.client_lock:
                self.client_handlers[client_addr] = client_handler

            # Start Client Handler on new thread
            client_handler.start()
    
    # Remove clients that do not communicate with the server anymore
    def remove_broken_clients(self):
        with self.client_lock:
            broken_clients = []

            # Find broken client
            for client_addr in self.client_handlers:
                if self.client_handlers[client_addr].error:
                    broken_clients.append(client_addr)
            
            # Remove broken clients
            for client_addr in broken_clients:
                self.client_handlers.pop(client_addr)
            
        return broken_clients
    
    # Broadcast a message to a subset of the clients
    def broadcast(self, client_subset, msg):
        with self.client_lock:
            for client_addr in client_subset:
                self.client_handlers[client_addr].queue_message(msg)


class FLServer(Server):
    def __init__(self, host):
        super(FLServer, self).__init__(host)

        # Client selected for FL
        self.client_subset = []

        # Flags / Cache for FL loop
        self.aggregated_update = None
        self.broadcasted = False
        
        # TODO: Encapsulate these in a class.
        # FL Model Hyperparameters
        self.model = "model"
        self.aggregator = lambda updates: updates[0]    # Default
        self.update_rule = lambda model, update: None
        self.subset_size = 2
    
    # Executes FL Training Loop
    def train(self):
        while True:
            # select clients if no model has been broadcasted.
            if not self.broadcasted:
                self.select_clients(self.subset_size)

            # while clients exist and a model has been broadcasted but no aggreated update has been created...
            while (not self.aggregated_update) and len(self.client_subset) > 0 and self.broadcasted:
                # Try to create an aggregated update.
                self.aggregated_update = self.aggregate_updates()
            
            # if an aggregated update has been created...
            if self.aggregated_update:
                # Update the model using aggregated update.
                self.update_model(self.aggregated_update)
                self.aggregated_update = None

                # Reset client subset (to be re-selected)
                self.client_subset = []
            
            # Broadcast to Client Subset
            # NOTE: if client subset empty, broadcast will return False
            self.broadcasted = self.broadcast_model()

    ### FL Training Loop ###
    
    # Randomly select subset of all client to train on
    # TODO: Customizable random selection
    def select_clients(self, subset_size):
        with self.client_lock:
            num_clients = len(self.client_handlers)
            self.client_subset = sample(self.client_handlers.keys(), min(subset_size, num_clients))
    
    # Broadcast model to selected clients so they can train
    def broadcast_model(self):
        # Verify there are clients
        if len(self.client_subset) > 0:
            self.broadcast(self.client_subset, self.model)
            
            return True
        
        return False
    
    # Retrieve updates of selected clients
    def get_updates(self):
        updates = []

        with self.client_lock:
            for client_addr in self.client_handlers:
                update = self.client_handlers[client_addr].get_message()

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
        return self.aggregator(self.get_updates())
    
    # Update server model (centralized model)
    def update_model(self, aggregated_update):
        self.update_rule(self.model, aggregated_update)
    
    ## Helper Functions ###
    
    # Ensure all selected clients have an update
    def do_all_selected_clients_have_updates(self):
        with self.client_lock:
            for client_addr in self.client_subset:
                if not self.client_handlers[client_addr].has_message():
                    return False

        return True


### Main Code ###

BUFFER_TIME = 5

if __name__ == '__main__':
    # Initialize the FL server.
    flServer = FLServer((server_hostname, server_port))

    # Allow client to connect
    flServer.start()
    
    # Buffer for clients to connect
    print('Buffer time for Clients to connect:', BUFFER_TIME)
    time.sleep(BUFFER_TIME)
    
    # Train the FL server model.
    print('Starting FL Training Loop')
    flServer.train()
