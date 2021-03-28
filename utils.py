import time, sys, threading, errno, socket, pickle, math, struct

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
        except:
            TERM.write_failure('Peer {}: Receive error {}'.format('blah', sys.exc_info()[0]))
            return None