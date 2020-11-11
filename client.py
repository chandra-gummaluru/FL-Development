import time, socket, sys
 
socket_server = socket.socket()
server_host_name = socket.gethostname()
server_port = 8080
  
socket_server.connect((server_host_name, server_port))
 
while True:
    message = input()
    socket_server.send(message.encode())  
    message = (socket_server.recv(1024)).decode()
    print(message)