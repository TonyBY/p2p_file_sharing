import socket
import threading
import os
import sys
import time
import pickle
import subprocess
import random
from socketserver import BaseRequestHandler, ThreadingTCPServer

PEER_ID = 1
ftp_client_default_port = 8000
upload_neighbor_port = 8050  # The neighbor get chunks from you
download_neighbor_port = 8010  # The neighbor gives you chunks

BUFSIZE = 1024
CONNECTION_STATE = False
finished_running = False
peer_socket_timeout = False
threads = {}  # used to record the log in status for each thread
WHOLE_FILE_LIST = []
LOCAL_FILE_LIST = []


def setup_ports(upload_port, download_port):
    global upload_neighbor_port, download_neighbor_port
    upload_neighbor_port = upload_port
    download_neighbor_port = download_port


def join_subfiles(file_name):
    prefix = file_name.split(".")[0]
    surfix = file_name.split(".")[1]
    subprocess.run("cat " + prefix + "_*" + " > " + prefix + "." + surfix, shell=True, check=True)


class FTP_data_thread(threading.Thread):
    def __init__(self, cmd, filename):
        self.dataPort = 6548
        self.sock = socket.socket()
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind(("127.0.0.1", self.dataPort))
        self.sock.listen(1)
        self.sock.settimeout(1)

        self.cmd = cmd
        self.filename = filename
        self.current_dir = os.path.abspath(".")
        self.download_dir = os.path.abspath("./")

        threading.Thread.__init__(self)

    def run(self):
        try:
            self.dataConn, addr = self.sock.accept()
        except Exception as e:
            print("Exception: ", e)
            return
        if self.cmd == "dir":
            self.dir()
        elif self.cmd == "getlist":
            self.getlist()
        elif self.cmd == "getchunks":
            self.getchunks()
        elif self.cmd == "upload":
            self.upload()
        else:
            print('Unhandled data thread command')

    def dir(self):
        print("\nReceiving file list\n")
        total_payload = ""  # Concatenate list of files
        data = str(self.dataConn.recv(1024), "utf-8")
        while data:
            total_payload += data
            data = str(self.dataConn.recv(1024), "utf-8")

        # Print the entire list
        print("\nFTP File List\n--------------\n" + total_payload + "\n")
        self.dataConn.close()

    def getlist(self):

        print("Retrieving complete chunk list: " + self.filename)
        try:
            data = bytearray()
            packet = self.dataConn.recv(1024)
            data.extend(packet)
            while packet:
                packet = self.dataConn.recv(1024)
                data.extend(packet)
            global PEER_ID, LOCAL_FILE_LIST, WHOLE_FILE_LIST
            subset_for_clients = pickle.loads(data)
            LOCAL_FILE_LIST = subset_for_clients[PEER_ID]
            for key in subset_for_clients.keys():
                WHOLE_FILE_LIST = WHOLE_FILE_LIST + subset_for_clients[key]
            print("WHOLE_FILE_LIST: ", WHOLE_FILE_LIST)
            print("PEER_ID: ", PEER_ID)
            print("LOCAL_FILE_LIST: ", LOCAL_FILE_LIST)
        except:
            print("Problem receiving data")

        # f.close()
        print("Chunk list received.")

        self.dataConn.close()

    def getchunks(self):
        # try:
        # Establish full directory path
        full_filename = os.path.join(self.download_dir, self.filename)
        print("Full Dir: " + full_filename)
        f = open(full_filename, "wb+")  # Opens/creates file to copy data over
        print("Retrieving file: " + self.filename)
        try:

            data = self.dataConn.recv(1024)
            while data:
                f.write(data)
                data = self.dataConn.recv(1024)

        except:
            print("Problem receiving data")

        f.close()
        print("File received.")
        self.dataConn.close()

    def upload(self):
        # Establish full directory path
        full_filename = os.path.join("./", self.filename)
        print("Full Dir " + full_filename)

        try:
            f = open(full_filename, "rb")  # Opens file, if it exists
            print("Uploading to file: " + self.filename)
        except:
            print("File not found")
            self.dataConn.close()
            return

        # Send all data in file
        while True:
            self.data = f.read(8)
            if not self.data:
                break
            self.dataConn.sendall(self.data)
        f.close()


class PeerDataThread(threading.Thread):
    def __init__(self, cmd, filename):
        self.dataPort = download_neighbor_port + 5
        print("Trying to connect to peer port: ", self.dataPort)
        self.sock = socket.socket()
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind(("127.0.0.1", self.dataPort))
        self.sock.listen(1)
        self.sock.settimeout(1)

        self.cmd = cmd
        self.filename = filename
        self.current_dir = os.path.abspath(".")
        self.download_dir = os.path.abspath("./")

        threading.Thread.__init__(self)

    def run(self):
        try:
            self.dataConn, addr = self.sock.accept()
        except Exception as e:
            print("Check point: PeerDataThread.run")
            print("Exception: ", e)
            print(e)
            print("Check point: peer_socket_timeout")
            global peer_socket_timeout
            peer_socket_timeout = True
            print("peer_socket_timeout: ", peer_socket_timeout)
            return
        if self.cmd == "getchunks":
            self.getchunks()
        else:
            print('Unhandled data thread command')

    def getchunks(self):
        # try:
        # Establish full directory path
        full_filename = os.path.join(self.download_dir, self.filename)
        print("Full Dir: " + full_filename)
        f = open(full_filename, "wb+")  # Opens/creates file to copy data over
        print("Retrieving file: " + self.filename)
        try:

            data = self.dataConn.recv(1024)
            while data:
                f.write(data)
                data = self.dataConn.recv(1024)

        except:
            print("Problem receiving data")

        f.close()
        print("File received.")
        # except:
        #     if not f.closed:
        #         f.close()
        #
        #     print("Cannot open file.")

        self.dataConn.close()


class response_thread(threading.Thread):
    def __init__(self, conn):
        self.conn = conn
        threading.Thread.__init__(self)

    def run(self):
        while True:
            self.empty()

    def empty(self):
        try:
            response = str(self.conn.recv(1024), "utf-8")
            print(response)
        except:
            return


class Handler(BaseRequestHandler):
    def handle(self):
        # self.send_ctrl_response("220 awaiting input")

        client_address, client_port = self.client_address[0], self.client_address[1]
        cur_thread = threading.current_thread()
        global threads
        if cur_thread not in threads.keys():
            threads[cur_thread] = False
        print("%s %d connected!" % (client_address, client_port))
        print(cur_thread)

        while True:
            # wait for commands
            cmd = str(self.request.recv(1024), "utf-8")
            if cmd:
                if not cmd.endswith("\r\n"):
                    print("checkpoint 2")
                    self.send_ctrl_response("500 Syntax error, command unrecognized.")
                    continue
                else:
                    cmd = cmd.rstrip("\r\n")

                split = cmd.lower().split(" ")
                print("cmd: ", split[0])
                print("input: ", split)

                try:
                    self.upload(split)
                except Exception as e:
                    print("checkpoint 3")
                    print(str(e))
                    self.send_ctrl_response("500 Syntax error, command unrecognized.")

            global finished_running
            if finished_running:
                return

    def upload(self, commands):
        if len(commands) is not 2:
            self.send_parameter_error_response()
            print("G error: No filename.")
            return

        filename = commands[1]
        print("server received get cmd filename: " + filename)
        filename = os.path.join("./", filename)
        print("abs path: " + filename)

        if not os.path.exists(filename):
            self.send_ctrl_response("550 File Unavailable")
            return

        print("file exists")

        if os.access(filename, os.R_OK):
            data_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            print('OK!!!!')
            file_data = ""
            try:
                file = open(filename, 'rb')
                file_data = file.read()
                global data_thread_status
                try:
                    print("Sending chunk: ", commands[1])
                    data_socket.connect(("127.0.0.1", upload_neighbor_port + 5))
                    data_socket.sendall(bytearray(file_data))
                    data_socket.close()
                    data_thread_status = "226 Closing data connection"
                    print("Done!")
                except:
                    data_thread_status = "425 Can't open data connection"
                file.close()
                # self.send_ctrl_response('150 About to open data connection.')
                if data_thread_status == "":
                    self.send_ctrl_response("226 Closing data connection, requested file action successful")
                else:
                    self.send_ctrl_response(data_thread_status)
            except:
                self.send_ctrl_response("450 File Unavailable")
        else:
            self.send_ctrl_response("550 File Unavailable")
            return

    def send_ctrl_response(self, message, encoding="utf-8"):
        print("Sending CTRL response: " + message)
        self.request.sendall(bytearray(message + "\r\n", encoding))

    def send_parameter_error_response(self):
        self.send_ctrl_response("501 Syntax error in parameters or arguments.")


class upload_thread(threading.Thread):
    def __init__(self):
        threading.Thread.__init__(self)

    def run(self):
        HOST = "localhost"
        PORT = upload_neighbor_port
        ADDR = ("localhost", PORT)
        print("ADDR: ", ADDR)
        server = ThreadingTCPServer(ADDR, Handler)  # Handler: the Handler class whose connection has been established.
        print("waiting for connection on " + HOST + ":" + str(PORT))
        server.serve_forever()


class ftp_client:
    def __init__(self):
        self.clientSock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.clientSock.settimeout(2)
        self.download_dir = os.path.abspath("./ftp-downloads/")

        # MAIN LOOP
        ################
        while True:
            time.sleep(1)
            entry_array = input("\nPlease enter command: ").lower().split(" ")
            if entry_array[0] == "connect":
                self.connect(entry_array)

            elif entry_array[0] == "login":
                self.login(entry_array)
            elif entry_array[0] == "dir":
                self.dir(entry_array)

            elif entry_array[0] == "get":
                self.get(entry_array)

            elif entry_array[0] == "upload":
                self.upload(entry_array)

            elif entry_array[0] == "logout":
                self.logout(entry_array)

            elif entry_array[0] == "quit":
                self.quit(entry_array)
            else:
                print("Unknown command: '" + entry_array[0] + "'")

            try:
                self.response_thread.empty()
                self.peer_response_thread.empty()
            except:
                continue

    # CONNECT FUNCTION
    def connect(self, entry_array):
        global ftp_client_default_port
        # user_name = entry_array[-2]
        # password = entry_array[-1]

        # Make sure correct amount of parameters were passed
        if len(entry_array) != 3:
            print("Invalid command - CONNECT Parameters: <server name/IP address> <server port><user name><password>")
            print("USING DEFAULT TO MAKE OUR LIVES EASIER")
            entry_array = ["connect", "127.0.0.1", ftp_client_default_port]

        # Parse control port to integer value
        try:
            ctrlPort = int(entry_array[2])
        except ValueError:
            print("Invalid port number!")
            return

        global CONNECTION_STATE
        if CONNECTION_STATE == False:
            # Establish control connection
            try:
                self.clientSock.connect((entry_array[1], ctrlPort))
                # try:
                #   self.dataConn, addr = self.clientSock.accept()
                # except:
                #   print("FAILED TO BUILD CONNECTION")
                #   return

                # after connection is established, we need to wait for the 220 response from the server "awaiting input"

                self.response_thread = response_thread(self.clientSock)
                self.response_thread.setDaemon(True)
                self.response_thread.start()
                CONNECTION_STATE = True

            except ConnectionRefusedError:
                print("Connection refused - check port number")
                self.clientSock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.clientSock.settimeout(2)
                return
            except Exception as e:
                # print(e)
                print("Connection refused - check server's IP address")
                self.clientSock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.clientSock.settimeout(2)
                return

            print("Connection established on port {}.".format(ctrlPort))
        else:
            print("Invalid request! Connection has been established already!")

    def login(self, entry_array):
        # Make sure correct amount of parameters were passed
        if len(entry_array) != 3:
            print("Invalid command - LOGIN Parameters: Username Password")
            return

        # Make sure ctrl connection is established
        try:
            cmd = entry_array[0]
            username = entry_array[1]
            password = entry_array[2]
            user_info = cmd + " " + username + " " + password
            self.send(user_info)
        except Exception as e:
            print(e)
            print("You must connect to the server before using this command")
            return

    # DIR FUNCTION
    def dir(self, entry_array):
        # Make sure correct amount of parameters were passed
        if len(entry_array) != 1:
            print("Invalid command - DIR requires no additional parameters")
            return

        # Make sure ctrl connection is established
        try:
            self.send("DIR")
        except:
            print("You must log into the server before using this command")
            return
        self.openDataPort(cmd="dir")

    # RETRIEVE FUNCTION
    def get(self, entry_array):
        # Make sure correct amount of parameters were passed
        if len(entry_array) != 2:
            print("Invalid command - GET Parameters: <filename>")
            return

        filename = entry_array[1]

        # Make sure ctrl connection is established
        try:
            print("Getting Whole Chunk list")
            self.send("GETLIST " + filename)
        except:
            print("You must log into the server before using this command")
            return

        # Open data port and retrieve file
        self.openDataPort(cmd="getlist", filename=filename)

        # Get chunks from the file owner
        global LOCAL_FILE_LIST
        for chunk in LOCAL_FILE_LIST:
            try:
                print("Downloading chunks from the file owner.")
                self.send("GETCHUNKS " + chunk)
            except:
                print("Failed to download chunks from the file owner.")
                return

            # Open data port and retrieve file
            self.openDataPort(cmd="getchunks", filename=chunk)
        print("Got all assigned chunks from the file owner.")
        print("Initialization fished!\n")

        print("-------------------------------------")
        print("Start listening to uploading neighbor")
        self.upload_thread = upload_thread()
        self.upload_thread.setDaemon(True)
        self.upload_thread.start()

        input("please press enter to start downloading from peers.")
        print("Start downloading rest chunks form other peers")
        self.download_neighbor_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.download_neighbor_socket.settimeout(2)

        # Keep trying to connect to the downloading neighbor
        print("Start trying to connect to the downloading neighbor")
        while 1:
            try:
                global download_neighbor_port
                self.download_neighbor_socket.connect(("127.0.0.1", int(download_neighbor_port)))
                print("Connected to the downloading neighbor!")
                self.peer_response_thread = response_thread(self.download_neighbor_socket)
                self.peer_response_thread.setDaemon(True)
                self.peer_response_thread.start()
                break
            except:
                print("Failed to connect to the downloading neighbor.")
                print("Sleep briefly & try again")
                time.sleep(5)
                continue

        rest_chunk_list = list(set(WHOLE_FILE_LIST) - set(LOCAL_FILE_LIST))
        while rest_chunk_list:
            print("length of rest_chunk_list:", len(rest_chunk_list))
            chunk = rest_chunk_list[0]
            print("Trying to download chunk: %s" % chunk)
            try:
                print("Trying to Download chunks from the downloading neighbor.")
                self.peer_send("GETCHUNKS " + chunk)
                # Open data port and retrieve file
                self.openPeerDataPort(cmd="getchunks", filename=chunk)
                global peer_socket_timeout
                if peer_socket_timeout:
                    peer_socket_timeout = False
                    j = random.randint(0, len(rest_chunk_list) - 1)
                    rest_chunk_list[0], rest_chunk_list[j] = rest_chunk_list[j], rest_chunk_list[0]
                    continue

            except Exception as e:
                print("Exception: ", e)
                print("Failed to download chunks")
                return
            # global LOCAL_FILE_LIST
            LOCAL_FILE_LIST.append(chunk)
            print("Downloaded Chunk: ", chunk)
            rest_chunk_list.pop(0)
            print("POP!")

        print("Downloaded all required chunks!")
        print("Start join the chunks...")
        join_subfiles(filename)
        print("Done! Successfully joined the chunks!")

    # UPLOAD FUNCTION
    def upload(self, entry_array):
        # Make sure correct amount of parameters were passed
        if len(entry_array) != 2:
            print("Invalid command - UPLOAD Parameters: <filename>")
            return

        filename = entry_array[1]

        # Make sure ctrl connection is established
        try:
            self.send("UPLOAD " + filename)
        except:
            print("You must log into the server before using this command")
            return

        # Open data port and send file
        self.openDataPort(cmd="upload", filename=filename)

    # LOGOUT FUNCTION
    def logout(self, entry_array):
        # Make sure correct amount of parameters were passed
        if len(entry_array) != 1:
            print("Invalid command - LOGOUT requires no additional parameters")
            return
        else:
            try:
                self.send("LOGOUT")
            except:
                return

    # QUIT FUNCTION
    def quit(self, entry_array):
        # Make sure correct amount of parameters were passed
        if len(entry_array) != 1:
            print("Invalid command - QUIT requires no additional parameters")
            return
        else:
            try:
                self.send("QUIT")
            except:
                exit()

            # self.clientSock().close()
            self.response_thread.empty()
            exit()

    def send(self, message, encoding="utf-8"):
        self.clientSock.sendall(bytearray(message + "\r\n", encoding))

    def peer_send(self, message, encoding="utf-8"):
        self.download_neighbor_socket.sendall(bytearray(message + "\r\n", encoding))

    def openDataPort(self, cmd, filename=""):
        try:
            fct = FTP_data_thread(cmd=cmd, filename=filename)
            fct.start()
            fct.join()

        except:
            print(str(cmd))
            print("Unexpected error: ", sys.exc_info()[0])
            print("Unexpected error: ", sys.exc_info()[1])
            print("Unexpected error: ", sys.exc_info()[2])
            exit()

    def openPeerDataPort(self, cmd, filename=""):
        try:
            fct = PeerDataThread(cmd=cmd, filename=filename)
            fct.start()
            fct.join()

        except:
            print(str(cmd))
            print("Unexpected error: ", sys.exc_info()[0])
            print("Unexpected error: ", sys.exc_info()[1])
            print("Unexpected error: ", sys.exc_info()[2])
            exit()


if __name__ == '__main__':
    upload_port = int(input("Please input the port for upload neighbor: "))
    download_port = int(input("Please input the port for download neighbor: "))
    setup_ports(upload_port, download_port)

    client = ftp_client()
