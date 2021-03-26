import time, sys, threading, errno
import socket
import queue
import pickle
import math

DEBUG = True
MAX_BUFFER_SIZE = 4096

class StoppableThread(threading.Thread):

    def __init__(self, *args, **kwargs):
        super(StoppableThread, self).__init__(*args, **kwargs)
        self._stop = threading.Event()

    def stop(self):
        self._stop.set()

    def isStopped(self):
        return self._stop.isSet()


# A generic communication handler.
class Comm_Handler():
    def __init__(self, peer):
        # threads for sending and receiving messages.
        self.sender_thread = None
        self.receiver_thread = None

        # Peer connection
        self.peer_sock, self.peer_addr = peer

        # queues for storing messages to send and receive.
        # incoming messages from the peer.
        self.in_queue = queue.Queue(1)
        self.in_lock = threading.Lock()

        # outgoing messages to the peer.
        self.out_queue = queue.Queue(1)
        self.out_lock = threading.Lock()

        # indicates whether the handler had an error.
        self.error = False

    # starts the handler.
    def start(self):
        self.sender_thread = StoppableThread(target=self.send, daemon=True)
        self.receiver_thread = StoppableThread(target=self.receive, daemon=True)

        self.sender_thread.start()
        self.receiver_thread.start()

    # TODO: how to deal with pause() vs stop()
    # pauses the handler.
    def pause(self):
        self.sender_thread.stop()
        self.receiver_thread.stop()

    # stops the handler.
    def stop(self):
        self.sender_thread.stop()
        self.receiver_thread.stop()

        # close the peer socket.
        self.peer_sock.close()

    # Checks if communication has stopped
    def isStopped(self):
        return self.receiver_thread.isStopped() or self.sender_thread.isStopped()

    # callback to receive messages.
    def receive(self):
        #print('Thread ID (receive):', threading.get_ident())

        # holds the message size for data to be received eventually.
        nt = None

        while not self.receiver_thread.isStopped():
            try:
                # Wait for data from peer
                if nt == None:
                    # receive the message size.
                    nt = int.from_bytes(self.peer_sock.recv(8), 'big')
                    continue
                else:
                    # receive the message.
                    buff = bytearray()
                    for i in range(nt):
                        buff += self.peer_sock.recv(MAX_BUFFER_SIZE)
                    msg = pickle.loads(buff)
                    nt = None
            except socket.error as e:
                if e.args[0] in [ errno.EAGAIN, errno.EWOULDBLOCK ]:
                    # No data received (yet)
                    continue
                else:
                    # Remove broken peer + end thread (by exiting)
                    print('Peer {}: receive error {}'.format(self.peer_addr, e))
                    self.error = True
                    self.stop()
                    return
            else:
                # Only accept messages if the queue is not full.
                with self.in_lock:
                    if self.in_queue.full():
                        continue

                    # Queue message received from peer
                    self.in_queue.put(msg)
                    if DEBUG:
                        print('<{}> {}'.format(self.peer_addr, msg))

    # Determine if peer has an update/message
    def has_message(self):
        with self.in_lock:
            return not self.in_queue.empty()

    # Retrieve message
    def get_message(self):
        if self.in_queue.empty():
            return None

        with self.in_lock:
            msg = self.in_queue.get()

        return msg

    # callback to send messages.
    def send(self):
        #print('Thread ID (send):', threading.get_ident())

        while not self.sender_thread.isStopped():
            # Check there is a message to send
            if self.out_queue.empty():
                continue

            # Send queued message to peer
            with self.out_lock:
                msg = self.out_queue.get()

                try:
                    # serialize the message and determine its size.
                    smsg = pickle.dumps(msg)
                    smsg_size = (len(smsg)).to_bytes(8, byteorder='big')

                    # determine the number of transmissions required.
                    nt = int(math.ceil(len(smsg) / MAX_BUFFER_SIZE))

                    # send the size.
                    self.peer_sock.sendall(nt.to_bytes(8, byteorder='big'))

                    # send the actual message.
                    for i in range(nt - 1):
                        self.peer_sock.sendall(smsg[MAX_BUFFER_SIZE*i : MAX_BUFFER_SIZE * (i+1)])
                    self.peer_sock.sendall(smsg[MAX_BUFFER_SIZE * (nt - 1):])

                    #self.peer_sock.sendall(smsg)
                except:
                    print('Peer {}: Send Error \'{}\''.format(self.peer_addr, sys.exc_info()[0]))
                    self.error = True
                    self.stop()
                    return

    # Put message to send
    def queue_message(self, msg):
        with self.out_lock:
            if self.out_queue.full():
                return

            self.out_queue.put(msg)
