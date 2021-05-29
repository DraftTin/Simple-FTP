import threading
import subprocess
import socket
from User import User
from select import select
import shlex
import os

class FTPServer:
    """FTP server"""
    def __init__(self):
        self.controlPort = 21
        self.commandList = ['ls', 'cd', 'pwd', 'get', 'close']
        self.userList = dict()      # id: User
        self.homePath = '/home/flyingbutton/桌面/code/task4/serverspace'
        self.HOST = '127.0.0.1'
        self.CONTROL_PORT = 12002   # controller port
        self.DATA_PORT = 13002      # data port based on the PORT pattern
        self.MAXSIZE = 1024
        self.pieceSize = 500
        self.dataSocketList = []

    def runServer(self):
        self.controlSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.controlSocket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.controlSocket.bind((self.HOST, self.CONTROL_PORT))
        self.controlSocket.listen(10)
        readfds = [self.controlSocket, ]
        print('server starts successfully....')
        while True:
            # 设置超时时间为1sec
            rlist, wlist, xlist = select(readfds, [], readfds, 1)
            for r in rlist:
                # 有连接请求
                if self.controlSocket == r:
                    conn, addr = r.accept()
                    # create the map of socket.fd to User
                    user = User()
                    user.ip = addr[0]
                    user.port = addr[1]
                    user.curPath = self.homePath
                    # socket.fileno can sign a socket uniquely
                    self.userList[conn.fileno()] = user
                    readfds.append(conn)
                    conn.send(bytes('Connect Successfully.\n', 'utf-8'))
                    print(addr, ' connects successfully')
                # 有数据发送
                else:
                    msg = r.recv(self.MAXSIZE)
                    addr = r.getpeername();
                    if msg:
                        msg = msg.decode('utf-8').strip()
                        print(addr, ": ", msg)
                        self.handleCommand(r, msg)                    
                    else:
                        readfds.remove(r)
                        print(addr, " has disconnected.....")

    def isValidPath(self, filePath):
        """return the valid or not valid and kind"""
        import re
        regex = r'/?(.+/)*(.*)/?'
        return re.match(regex, filePath).span()[1] == len(filePath)
    
    def getFullPath(self, curPath, filePath):
        if filePath[0] == '/':
            return os.path.join(self.homePath, filePath[1:])
        return os.path.join(curPath, filePath)

    def getRealPath(self, curPath, filePath):
        # shortcut for path getting
        fullpath = self.getFullPath(curPath, filePath)
        realpath = os.path.realpath(fullpath)
        if realpath.find(self.homePath) != 0:
            realpath = self.homePath
        return realpath

    def handleCommand(self, controlSock, command):
        """forward the command to the specific function"""
        # controlSock.recv(self.MAXSIZE)
        command_spl = shlex.split(command)
        if command_spl[0] == "ls":
            self.LS(controlSock, command_spl)
        elif command_spl[0] == 'pwd':
            self.PWD(controlSock)
        elif command_spl[0] == 'cd':
            self.CD(controlSock, command_spl)
        elif command_spl[0] == 'get':
            self.GET(controlSock, command_spl)
        elif command_spl[0] == 'close':
            self.CLOSE(controlSock)
        elif command_spl[0] == 'quote':
            self.QUOTE(controlSock, command_spl)
        else:
            controlSock.send(bytes("Command '{}' not Found.".format(command_spl[0]), 'utf-8'))

    def LS(self, controlSock, command_spl):
        """list the files among the fullpath"""
        user = self.userList[controlSock.fileno()]
        # invalid format
        if len(command_spl) > 2:
            controlSock.send(bytes('too much parameters: ls <filepath> or ls'))
            return 
        else:
            # ls
            if len(command_spl) == 1:
                rootpath = user.curPath
            # ls <dir> or ls file
            else:
                rootpath = self.getRealPath(user.curPath, command_spl[1])
            # travel the file among the rootpath
            msg = ''
            if os.path.isdir(rootpath):
                files_or_dirs = os.listdir(rootpath)
                for file_or_dir in files_or_dirs:
                    if os.path.isfile(os.path.join(rootpath, file_or_dir)):
                        msg += '{}\t<file>\n'.format(file_or_dir)
                    else:
                        msg += '{}\t<dir>\n'.format(file_or_dir)
            else:
                msg += '{}\t<file>'.format(os.path.basename(rootpath))
            controlSock.send(bytes(msg, 'utf-8'))

    def CD(self, controlSock, command_spl):
        """cd command"""
        # invalid format
        if len(command_spl) > 2:
            controlSock.send(bytes('too much parameters: cd <filepath> or ls'))
            return 
        # config fullPath
        fullPath = ''
        user = self.userList[controlSock.fileno()]
        # cd 
        if len(command_spl) == 1:
            fullPath = self.homePath
        # cd <dir> or cd <file>
        else:
            fullPath = self.getRealPath(user.curPath, command_spl[1])
        if os.path.exists(fullPath):
            # Client can't change directionary out of the home path         
            if os.path.isdir(fullPath):
                realPath = os.path.realpath(fullPath)
                user.curPath = realPath
                controlSock.send(bytes(user.curPath, 'utf-8'))
            else:
                controlSock.send(bytes('cd: {} is not a directionary'.format(command_spl[1]), 'utf-8'))
        else:
            controlSock.send(bytes('cd: {}: there is not such a directionary'.format(command_spl[1]), 'utf-8'))

    def QUOTE(self, controlSock, command_spl):
        """switch the user's file transfer pattern"""
        if len(command_spl) != 2:
            controlSock.send(b'quote: quote PASV or quote PORT')
            return 
        elif command_spl[1] != "PASV" and command_spl[1] != 'PORT':
            controlSock.send(bytes("quote: can't recognize {} pattern".format(command_spl[1]), 'utf-8'))
            return 
        self.userList[controlSock.fileno()].pasv = command_spl[1] == 'PASV'
        controlSock.send(bytes("switch the pattern to {}".format(command_spl[1]), 'utf-8'))

    def PWD(self, controlSock):
        """pwd command"""
        user = self.userList[controlSock.fileno()]
        controlSock.send(bytes(user.curPath, 'utf-8'))

    def GET(self, controlSock, command_spl):
        """get command: file transfer"""
        user = self.userList[controlSock.fileno()]
        fullpath = self.getRealPath(user.curPath, command_spl[1])
        print(fullpath)
        if os.path.isfile(fullpath):
            # send the rcode back and pattern then get the data transfer channel
            if user.pasv:
                controlSock.send(bytes('0PASV', 'utf-8'))
                conn, addr = self.PASV(controlSock)
            else:
                controlSock.send(bytes('0PORT', 'utf-8'))
                conn, addr = self.PORT(controlSock)
            self.fileTransfer(conn, fullpath)
            # '#' represents the end of transfer
            conn.send(bytes('#', 'utf-8'))
            conn.close()
        else:
            controlSock.send(bytes("1" + "Can't access {}: No such file".format(command_spl[1]), 'utf-8'))

    def PASV(self, controlSock):
        """passive pattern: return the dataSock connection"""
        dataSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        dataSocket.bind((self.HOST, 0))     # bind a random port
        self.dataSocketList.append(dataSocket)
        addr, port = dataSocket.getsockname()
        print('server open data sock ({0}, {1})'.format(addr, port))
        msg = bytes(addr + ',' + str(port), 'utf-8')
        controlSock.send(msg)
        dataSocket.listen(10)
        conn, addr = dataSocket.accept()
        print('client ({0}, {1}) has connect data sock'.format(addr[0], addr[1]))
        return (conn, addr)


    def PORT(self, controlSock):
        """port pattern: return the dataSock connection"""
        host, port = controlSock.recv(self.pieceSize).decode('utf-8').split(',')
        port = (int)(port)
        print('client has open the data sock ({0}, {1})'.format(host, port))
        dataSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        dataSocket.connect((host, port))
        return dataSocket, dataSocket.getpeername()

    def CLOSE(self, controlSock):
        """close the connection between the client and server"""
        host, addr = controlSock.getpeername()
        print('({0}, {1}) has closed the connection'.format(host, addr))
        fd = controlSock.fileno()
        self.userList.pop(fd)
        controlSock.send(b'bye')
    
    def fileTransfer(self, dataSock, filepath):
        """only transfer file"""
        f = open(filepath, 'rb+')
        piece = f.read(self.pieceSize)
        while piece:
            dataSock.send(piece)
            piece = f.read(self.pieceSize)
        f.close()

if __name__ == "__main__":
    ftpserver = FTPServer()
    ftpserver.runServer()