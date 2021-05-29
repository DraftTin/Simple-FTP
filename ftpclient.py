import socket
import shlex
import threading
import os
import subprocess


class FTPClient:
    def __init__(self):
        self.HOST = '127.0.0.1'
        self.SERVER_HOST = '127.0.0.1'
        self.SERVER_CONTROL_PORT = 12002    
        self.SERVER_DATA_PORT = 13002       # server data port based on the PORT pattern
        # self.homePath = './clientspace/'
        self.homePath = None
        self.pieceSize = 500
        self.localCommands = ['sethome', 'showhome', 'listhome', 'help']

    def run(self):
        """main function"""
        self.homePath = os.path.abspath('./clientspace')
        print(self.homePath)
        mkdir = subprocess.run('mkdir -p {}'.format(self.homePath), shell=True, capture_output=True)
        if mkdir.returncode:
            print(mkdir.stderr)
            return
        self.clientSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.clientSocket.connect((self.SERVER_HOST, self.SERVER_CONTROL_PORT))
        recvMsg = self.clientSocket.recv(self.pieceSize).decode().strip()
        print(recvMsg)
        while True:
            print('ftp> ', end='')
            command = input()
            if self.handleInput(command) == 0:
                break

    def handleInput(self, command):
        command_spl = shlex.split(command)
        # check this command whether should be sent
        valid, msg = self.commandCheck(command_spl)
        if not valid: 
            print(msg)
            return
        # empty input
        if len(command_spl) == 0:
            return 1
        # local command
        elif command_spl[0][0] == '!' and command_spl[0] != '!':
            command_spl[0] = command_spl[0][1:]
            self.handleLocalCommand(command_spl)
            return 1
        # remote command
        elif command_spl[0] == 'close' or command_spl[0] == 'bye':
            self.clientSocket.send(bytes('close', 'utf-8'))
            msg = self.clientSocket.recv(self.pieceSize).decode('utf-8')
            print(msg)
            return 0
        thread = threading.Thread(target=self.handleRemoteCommand, args=(self.clientSocket, command_spl,))
        thread.start()
        msg = bytes(command, 'utf-8')
        self.clientSocket.send(msg)
        thread.join()
        return 1

    def commandCheck(self, command_spl):
        if len(command_spl) == 0:
            return True, ''
        # only check get and put command
        if command_spl[0] == 'get':
            if len(command_spl) != 2:
                return False, 'get: get <filepath>'
        elif command_spl[0] == 'put':
            if len(command_spl) != 3:
                return False, 'put: put <upload path> <local filename>'
            filename = command_spl[2]
            # must only filename
            if os.path.dirname(filename) != '':
                return False, "put: file {} not found".format(filename)
            if not os.path.isfile(os.path.join(self.homePath, filename)):
                return False, "put: file {} not found".format(filename)
            return True, ''
        return True, ''

    def handleLocalCommand(self, command_spl):
        """Command which can be handled locally"""
        if command_spl[0] == '':
            return 
        if command_spl[0] == 'sethome':
            self.SET_HOME(command_spl)
        elif command_spl[0] == 'showhome':
            self.SHOW_HOME()
        elif command_spl[0] == 'listhome':
            self.LIST_HOME()
        elif command_spl[0] == 'help':
            self.HELP()
        else:
            print('Local command: {} not found'.format(command_spl[0]))

    def handleRemoteCommand(self, controlSock, command_spl):
        """Command which needs to be sent to server"""
        msg = ''
        if command_spl[0] == 'get':
            msg = self.GET(controlSock, command_spl)
        elif command_spl[0] == 'put':
            msg = self.PUT(controlSock, command_spl)
        else:
            msg = controlSock.recv(self.pieceSize).decode()
        print(msg)

    def SET_HOME(self, command_spl):
        """setup the homePath"""
        if len(command_spl) != 2:
            print('sethome: sethome <filepath>')
            return 
        if os.path.isdir(command_spl[1]):
            self.homePath = command_spl[1]
            print('setup ok')
        else:
            print("sethome: {} does'n exist".format(command_spl[1]))            

    def SHOW_HOME(self):
        """show the homePath"""
        print(self.homePath)

    def LIST_HOME(self):
        """list all files among the homePath"""
        files_or_dirs = os.listdir(self.homePath)
        msg = ''
        for file_or_dir in files_or_dirs:
            if os.path.isdir(os.path.join(self.homePath, file_or_dir)):
                msg += '{}\t<dir>\n'.format(file_or_dir)
            else:
                msg += '{}\t<file>\n'.format(file_or_dir)
        print(msg)

    def HELP(self):
        helpMsg = """
get <filepath>: download file 
put <filepath> <filename>: upload file
ls <filepath> or ls: list file
pwd: check current path
cd <filepath>: change directionary
close: close the ftp connection
quote PASV or PORT: switch the file transfer pattern
!sethome: set the local client space
!showhome: check local client space path
!listhome: list the file among the local client space
!help: check all help information\r\n
                """
        print(helpMsg)

    def GET(self, controlSock, command_spl):
        """retrieve the file from the server"""
        msg = controlSock.recv(self.pieceSize)
        # can't get the file, msg[0] is a flag
        if msg[0] == ord('1'):
            return msg[1:].decode()
        print(msg[1:])
        # judge the transfer pattern
        print('waiting for file transfering')
        if msg[1:] == b'PASV':
            conn, addr = self.PASV(controlSock)
        else:
            conn, addr = self.PORT(controlSock)
        filepath = command_spl[1]
        filename = os.path.basename(filepath)
        self.fileRecv(conn, filename)
        conn.close()
        return 'file transfer successfully'
    
    def PUT(self, controlSock, command_spl):
        """upload file to the server"""
        msg = controlSock.recv(self.pieceSize)
        # can't get the file, msg[0] is a flag
        if msg[0] == ord('1'):
            return msg[1:].decode()
        conn, addr = self.PASV(controlSock)
        print('waiting for file uploading')
        filepath = os.path.join(self.homePath, command_spl[2])
        self.fileSend(conn, filepath)
        conn.send(b'#')
        conn.close()
        return 'file upload successfully'        


    def PASV(self, controlSock):
        """client connects to server"""
        host, port = controlSock.recv(self.pieceSize).decode('utf-8').split(',')
        port = (int)(port)
        print('server has open the data sock ({0}, {1})'.format(host, port))
        dataSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        dataSocket.connect((host, port))
        return dataSocket, dataSocket.getpeername()

    def PORT(self, controlSock):
        """server connects to client"""
        dataSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        dataSocket.bind((self.HOST, 0))     # bind a random port
        addr, port = dataSocket.getsockname()
        print('client open data sock ({0}, {1})'.format(addr, port))
        msg = bytes(addr + ',' + str(port), 'utf-8')
        controlSock.send(msg)
        dataSocket.listen(10)
        conn, addr = dataSocket.accept()
        print('server open data sock ({0}, {1})'.format(addr[0], addr[1]))
        return (conn, addr)

    def fileRecv(self, dataSock, filename):
        f = open(os.path.join(self.homePath, filename), 'wb+')
        while True:
            msg = dataSock.recv(self.pieceSize)
            if msg[len(msg) - 1] == ord('#'):
                f.write(msg[:len(msg) - 1])
                break
            f.write(msg)
        f.close()

    def fileSend(self, dataSock, filepath):
        f = open(filepath, 'rb+')
        piece = f.read(self.pieceSize)
        while piece:
            dataSock.send(piece)
            piece = f.read(self.pieceSize)
        f.close()

if __name__ == '__main__':
    ftpclient = FTPClient()
    ftpclient.run()