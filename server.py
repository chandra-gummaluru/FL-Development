import time, socket, sys
import _thread as thread

# TODO: Add locks
list_of_clients = []

client_messages = {}

# TODO: Kill client thread
def remove(conn): 
    if conn in list_of_clients: 
        list_of_clients.remove(conn)

def broadcast(msg):
    # Check all clients have returned
    for (_, add) in list_of_clients:
        if client_messages[add] == None:
            return

    # Broadcast message to all clients
    for (conn, add) in list_of_clients: 
        client_messages[add] = None

        try: 
            print("sending....")
            conn.send(msg.encode()) 
        except: 
            print("i am here....")
            conn.close() 
            # if the link is broken, we remove the client 
            remove(conn) 


def clientthread(conn, addr):
    client_messages[addr] = None
    while True: 
        try: 
            message = conn.recv(2048).decode() 
            if message: 

                """prints the message and address of the 
                user who just sent the message on the server 
                terminal"""
                print("<" + addr[0] + "> " + message) 

                # Calls broadcast function to send message to all 
                message_to_send = "<" + addr[0] + "> " + message
                client_messages[addr] = message_to_send
                broadcast(message_to_send)
                #conn.send(message_to_send.encode())

            else: 
                """message may have no content if the connection 
                is broken, in this case we remove the connection"""
                remove(conn) 

        except: 
            continue
  


sock = socket.socket()
host_name = socket.gethostname()
ip = socket.gethostbyname(host_name)
 
port = 8080
 
sock.bind((host_name, port))
sock.listen(100)

 
while True:

    conn, add = sock.accept()

    print("Received connection from ", add)
    print('Connection Established. Connected From: ', add)

    list_of_clients.append((conn, add))
    thread.start_new_thread(clientthread, (conn, add))
