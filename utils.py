import time, sys, threading, errno, socket, pickle, math, struct
import numpy as np
import torch
from math import prod

class STATUS:
    SUCCESS = 0
    FAILURE = 1

    def failed(expr):
        return expr == STATUS.FAILURE
    def success(expr):
        return expr == STATUS.SUCCESS

class DEBUG_LEVEL:
    NONE = 0
    ERRORS = 1
    WARNS = 2
    INFO = 3
    ALL = 4

class TERM:
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'

    def write(msg):
        sys.stdout.write(TERM.ENDC + msg + TERM.ENDC + '\n')

    def write_info(msg):
        sys.stdout.write(TERM.OKCYAN + msg + TERM.ENDC + '\n')

    def write_success(msg):
        sys.stdout.write(TERM.OKGREEN + msg + TERM.ENDC + '\n')

    def write_failure(msg):
        sys.stdout.write(TERM.FAIL + msg + TERM.ENDC + '\n')

    def write_warning(msg):
        sys.stdout.write(TERM.WARNING + msg + TERM.ENDC + '\n')

# Handles generic communication between parties
class Communication_Handler():

    def sendall(sock, msg):
        sock.sendall(msg)

    def recvall(sock, msg_len):
        msg = bytearray()
        while len(msg) < msg_len:
            frag = sock.recv(msg_len - len(msg))
            if not frag:
                return None
            msg.extend(frag)
        return msg

    def send_msg(sock, msg):
        try:
            # serialize the message and determine its size.
            smsg = pickle.dumps(msg)
            smsg_len = len(smsg)

            # prefix each message with a 4-byte length (network byte order).
            smsg = struct.pack('>I', smsg_len) + smsg
            # send the message.
            Communication_Handler.sendall(sock, smsg)
        except KeyboardInterrupt:
            exit()
        except:
            TERM.write_failure('Peer {}: Send Error \'{}\''.format('blah', sys.exc_info()[0]))
            return

    def recv_msg(sock):
        try:
            msg_len = Communication_Handler.recvall(sock, 4)
            if msg_len:
                msg_len = struct.unpack('>I', msg_len)[0]
                # receive the message.
                smsg = Communication_Handler.recvall(sock, msg_len)
                msg = pickle.loads(smsg)
                return msg
        except KeyboardInterrupt:
            exit()
        except:
            TERM.write_failure('Peer {}: Receive error {}'.format('blah', sys.exc_info()[0]))
            return None

class NetworkModel:
    def __init__(self, seed=0):
        # names of the layers
        self.layers = []

        # flattened weights of the model
        self.values = []
        
        # seed
        self.seed = seed

        # mapping from linear array to tensors
        self.metadata = { 'layer': {} }
        
    def compress(self, state_dict):
        # Iterate through the state dictionary of the model
        for name, params in state_dict.items():
            self.layers.append(name)
            self.metadata['layer'][name] = {}
            
            weights = np.array(params.cpu())

            self.metadata['layer'][name]['indices'] = len(self.values)
            self.metadata['layer'][name]['shape'] = weights.shape

            weights = weights.flatten()
            self.values.extend(weights.tolist())

        return self

    def reconstruct(self):
        state_dict = {}

        for name in self.layers:
            # Retrieve weights
            idx = self.metadata['layer'][name]['indices']
            shape = self.metadata['layer'][name]['shape']
            numel = prod(shape)

            # Get the weights for the current layer and reshaped appropriately
            weights = np.array(self.values[idx:idx+numel]).reshape(shape)

            state_dict[name] = torch.from_numpy(weights)
        
        return state_dict


# Seed for reproducibility
SEED = 2020204
