import os
import socket
from socketserver import BaseRequestHandler, ThreadingTCPServer
import threading
import subprocess
import copy
import pickle

BUF_SIZE = 1024
CHUNK_SIZE = 100000  # 100KB
data_thread_status = ""
finished_running = False
threads = {}  # used to record the log in status for each thread

subset_for_clients = {}

current_dir = os.path.abspath("./")
clients = {"peer1": 111,
           "peer2": 222,
           "peer3": 333,
           "peer4": 444,
           "peer5": 555}
num_clients = len(clients)
file_name = "test.pdf"
file_path = os.path.join(current_dir, file_name)
username = ""
password = ""


# Split file
def split_file(file_name):
    global CHUNK_SIZE
    cmd_split = ["split", "-b", str(CHUNK_SIZE), file_name, file_name.split(".")[0] + '_']
    subprocess.check_call(cmd_split)


# get list of sub_files
def get_subfile_list(file_name):
    prefix = file_name.split(".")[0]
    subfile_list = []
    global current_dir
    for file in os.listdir(current_dir):
        if file.startswith(prefix + "_"):
            subfile_list.append(file)
    return subfile_list


# Split the subfile_list into five subset
def split_subfile_list(subfile_list, num_clients):
    copy_of_subfile_list = copy.deepcopy(subfile_list)
    length_of_subfile_list = len(copy_of_subfile_list)
    length_of_subset = length_of_subfile_list // num_clients
    counter = 0
    global subset_for_clients
    subset_for_clients = {}
    for i in range(num_clients):
        subset_for_clients[i + 1] = []
        while counter < length_of_subset:
            subset_for_clients[i + 1].append(copy_of_subfile_list[0])
            copy_of_subfile_list.pop(0)
            counter += 1
        counter = 0
    if copy_of_subfile_list != 0:
        subset_for_clients[num_clients - 1] = subset_for_clients[num_clients - 1] + copy_of_subfile_list
    return subset_for_clients


def preprocess(file_name, file_path):
    print("file_name: ", file_name)
    print("file_path: ", file_path)
    if os.access(file_path, os.R_OK):
        split_file(file_name)
        subfile_list = get_subfile_list(file_name)
        global subset_for_clients
        subset_for_clients = split_subfile_list(subfile_list, num_clients)
    else:
        print("File Unavailable")


class Handler(BaseRequestHandler):
    def handle(self):
        client_address, client_port = self.client_address[0], self.client_address[1]
        cur_thread = threading.current_thread()
        global threads
        if cur_thread not in threads.keys():
            threads[cur_thread] = False
        print("%s %d connected!" % (client_address, client_port))
        print(cur_thread)

        while True:
            if not threads[cur_thread]:
                print("Waiting for client logging in...")
                self.send_ctrl_response("SERVER: please login to use")
                pre_login_cmd = str(self.request.recv(1024), "utf-8")
                if not pre_login_cmd.endswith("\r\n"):
                    print("checkpoint 1")
                    self.send_ctrl_response("500 Syntax error, command unrecognized.")
                    continue
                else:
                    pre_login_cmd = pre_login_cmd.rstrip("\r\n")

                pre_login_cmd = pre_login_cmd.lower().split(" ")

                if pre_login_cmd[0] == 'login':
                    self.login(pre_login_cmd)
                elif pre_login_cmd[0] == 'quit':
                    self.quit(pre_login_cmd)
                else:
                    print("checkpoint: login error")
                    self.send_ctrl_response("SERVER: You must log into the server before using this command.")

            else:
                # wait for commands
                cmd = str(self.request.recv(1024), "utf-8")
                if cmd:
                    if not cmd.endswith("\r\n"):
                        print("checkpoint 2")
                        self.send_ctrl_response("500 Syntax error, command unrecognized.")
                        continue
                    else:
                        cmd = cmd.rstrip("\r\n")
                    # cmd = cmd.rstrip("\n")
                    # cmd = cmd.rstrip("\r")

                    split = cmd.lower().split(" ")
                    print("cmd: ", split[0])
                    print("input: ", split)

                    try:
                        # # Dynamically call the command passing along the entire command array
                        getattr(self, split[0])(split)

                    except Exception as e:
                        if split[0] == "getlist":
                            self.getlist(split)
                        print("checkpoint 3")
                        print(str(e))
                        self.send_ctrl_response("500 Syntax error, command unrecognized.")

            global finished_running

            if finished_running:
                return

    def login(self, client_info):
        if len(client_info) != 3:
            print('client_info: ', client_info)
            self.send_parameter_error_response()
            return
        try:
            global username, password
            user_name = client_info[1]
            password = client_info[2]
            print("client_info:", user_name, password)

            if user_name not in clients.keys():
                print("user_name is not found")
                self.send_ctrl_response("451 user_name is not found")
            elif password != str(clients[user_name]):
                print("Wrong password, please try again")
                self.send_ctrl_response("451 Wrong password, please try again")
            else:
                global threads
                cur_thread = threading.current_thread()
                threads[cur_thread] = user_name
                print(user_name + " has successful logged in!")
                self.send_ctrl_response("Welcome " + user_name + "!")
        except:
            self.send_ctrl_response('451 Requested action aborted: local error in processing.')

    def dir(self, commands):
        if len(commands) > 2:
            print('commands: ', commands)
            self.send_parameter_error_response()
            return

        # If there is a path given, use this, otherwise default
        # to the current directory
        dir = commands[1] if len(commands) == 2 else current_dir

        data_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        try:
            files_in_dir = os.listdir(dir)
            files_in_dir.sort()
            file_string = ""
            for file in files_in_dir:
                file_string = file_string + file + "\n"

            global data_thread_status
            try:
                data_socket.connect(("127.0.0.1", 6548))
                data_socket.sendall(bytearray(file_string, "utf-8"))
                data_socket.close()
                data_thread_status = "226 Closing data connection"
            except:
                data_thread_status = "425 Can't open data connection"
            self.send_ctrl_response(data_thread_status)
        except:
            self.send_ctrl_response('451 Requested action aborted: local error in processing.')

    def getlist(self, commands):
        print ("check point 4")
        data_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        cur_thread = threading.current_thread()
        global subset_for_clients, threads
        data = pickle.dumps(subset_for_clients)

        try:
            global data_thread_status
            try:
                data_socket.connect(("127.0.0.1", 6548))
                data_socket.sendall(bytearray(data))
                data_socket.close()
                data_thread_status = "226 Closing data connection"
            except Exception as e:
                print(e)
                data_thread_status = "425 Can't open data connection"

            if data_thread_status == "":
                self.send_ctrl_response("226 Closing data connection, requested file action successful")
            else:
                self.send_ctrl_response(data_thread_status)
        except Exception as e:
            print(e)
            self.send_ctrl_response("450 File Unavailable")

    def getchunks(self, commands):

        if len(commands) is not 2:
            self.send_parameter_error_response()
            print("G error: No filename.")
            return

        filename = commands[1]
        print("server received get cmd filename: " + filename)
        filename = os.path.join(current_dir, filename)
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
                    data_socket.connect(("127.0.0.1", 6548))
                    data_socket.sendall(bytearray(file_data))
                    data_socket.close()
                    data_thread_status = "226 Closing data connection"
                except:
                    data_thread_status = "425 Can't open data connection"
                file.close()

                if data_thread_status == "":
                    self.send_ctrl_response("226 Closing data connection, requested file action successful")
                else:
                    self.send_ctrl_response(data_thread_status)
            except:
                self.send_ctrl_response("450 File Unavailable")
        else:
            self.send_ctrl_response("550 File Unavailable")
            return

    def upload(self, commands):

        if len(commands) is not 2:
            self.send_parameter_error_response()
            print("UPLOAD error: No filename.")
            return

        filename = commands[1]
        filename = os.path.join(current_dir, filename)

        # check for OS permissions or if the file does not exist we'll create it
        if os.access(filename, os.R_OK) or not os.path.isfile(filename):
            data_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            try:
                global data_thread_status
                try:
                    data_socket.connect(("127.0.0.1", 6548))
                except:
                    data_thread_status = "425 Can't open data connection"
                # try:
                try:
                    data = data_socket.recv(1024)
                    if data:
                        file = open(filename, "wb")
                        print(filename)

                        while True:
                            if not data:
                                break
                            print(data)
                            file.write(data)
                            data = data_socket.recv(1024)

                        file.close()
                        data_thread_status = "226 Closing data connection, UPLOAD Sucsesful!"
                except:
                    data_thread_status = "SERVER: problem receiving data. Please check your file name."

                data_socket.close()

                self.send_ctrl_response('150 About to open data connection.')
                if data_thread_status == "226 Closing data connection, UPLOAD Sucsesful!":
                    self.send_ctrl_response("226 Closing data connection, file transaction successful")
                else:
                    self.send_ctrl_response("450 File Unavailable. Please check your file name.")
            except:
                self.send_ctrl_response("450 File Unavailable")
        else:
            self.send_ctrl_response("550 File Unavailable")
            return

    def logout(self, commands):
        global threads
        cur_thread = threading.current_thread()
        threads[cur_thread] = False
        print("SERVER: You have successfully logged out")
        self.send_ctrl_response("SERVER: You have successfully logged out")

    def quit(self, commands):
        global threads
        cur_thread = threading.current_thread()
        threads[cur_thread] = False
        print("You have successfully logged out")
        # Set finished_running so that the main loop will
        # finish running
        global finished_running
        self.send_ctrl_response("SERVER: You have successfully logged out\nsession ended!\nBye bye!")

    def send_ctrl_response(self, message, encoding="utf-8"):
        print("Sending CTRL response: " + message)
        self.request.sendall(bytearray(message + "\r\n", encoding))

    def send_parameter_error_response(self):
        self.send_ctrl_response("501 Syntax error in parameters or arguments.")


if __name__ == '__main__':
    print("Start pre-processing the file by splitting it into chunks and assigning chunks to peers.")
    preprocess(file_name, file_path)
    print("subset_for_clients: ", subset_for_clients)
    print("Done")

    HOST = 'localhost'
    PORT = int(input("please input port number:  "))

    print("Starting socket")
    ADDR = (HOST, PORT)
    server = ThreadingTCPServer(ADDR, Handler)  # Handler: the Handler class whose connection has been established.
    print("waiting for connection on " + HOST + ": " + str(PORT))
    server.serve_forever()
    # Listen -> Create new socket and thread when TCP connection established -> data processed by methods in handler.
    print(server)
