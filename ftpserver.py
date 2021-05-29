import threading
import subprocess
import socket
import shlex
import os
import time
from select import select
from User import User

class FTPServer:
    """FTP server"""
    def __init__(self):
        self.controlPort = 21
        self.userList = dict()      # id: User
        # self.homePath = '/home/flyingbutton/桌面/code/task4/serverspace'
        self.homePath = None
        self.HOST = '127.0.0.1'
        self.CONTROL_PORT = 12002   # controller port
        self.DATA_PORT = 13002      # data port based on the PORT pattern
        self.pieceSize = 500
        self.controlSocket = None
        self.dataSocket = None

    def runServer(self):
        self.homePath = os.path.abspath('./serverspace')
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
                    msg = r.recv(self.pieceSize)
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
        """basedir: self.homePath + filePath"""
        if filePath[0] == '/':
            return os.path.join(self.homePath, filePath[1:])
        return os.path.join(curPath, filePath)

    def getRealPath(self, curPath, filePath):
        """remove the '..' from the fullpath"""
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
        elif command_spl[0] == 'put':
            self.PUT(controlSock, command_spl)
        else:
            controlSock.send(bytes("Command '{}' not Found.".format(command_spl[0]), 'utf-8'))

    def LS(self, controlSock, command_spl):
        """list the files among the fullpath"""
        user = self.userList[controlSock.fileno()]
        # invalid format
        if len(command_spl) > 2:
            controlSock.send(bytes('too much parameters: ls <filepath> or ls', 'utf-8'))
            return 
        else:
            # ls
            fullpath = ''
            if len(command_spl) == 1:
                fullpath = user.curPath
            # ls <dir> or ls file
            else:
                fullpath = self.getRealPath(user.curPath, command_spl[1])
            # travel the file among the fullpath
            msg = ''
            if not os.path.exists(fullpath):
                controlSock.send(bytes("ls: {} doesn't exist".format(command_spl[1]), 'utf-8'))
                return 
            if os.path.isdir(fullpath):
                files_or_dirs = os.listdir(fullpath)
                for file_or_dir in files_or_dirs:
                    # print(os.path.join(fullpath, file_or_dir))
                    if os.path.isfile(os.path.join(fullpath, file_or_dir)):
                        msg += '{}\t<file>\n'.format(file_or_dir)
                    else:
                        msg += '{}\t<dir>\n'.format(file_or_dir)
            else:
                msg += '{}\t<file>'.format(os.path.basename(fullpath))
            controlSock.send(bytes(msg, 'utf-8'))

    def CD(self, controlSock, command_spl):
        """cd command"""
        # invalid format
        if len(command_spl) > 2:
            controlSock.send(bytes('too much parameters: cd <filepath> or cd', 'utf-8'))
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
        if len(command_spl) != 2:
            controlSock.send(b'1get: get <filepath>')
            return 
        user = self.userList[controlSock.fileno()]
        fullpath = self.getRealPath(user.curPath, command_spl[1])
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

    def PUT(self, controlSock, command_spl):
        """put command: put the file from client to ftp server"""
        if len(command_spl) != 3:
            controlSock.send(b'1put: put <upload path> <local filename>')
        user = self.userList[controlSock.fileno()]
        fullpath = self.getRealPath(user.curPath, command_spl[1])
        if os.path.isdir(fullpath):
            # default pasv
            controlSock.send(b'0PASV')
            conn, addr = self.PASV(controlSock)
            self.fileRecv(conn, fullpath, command_spl[2])
            conn.close()
            print('file {} uploaded'.format(command_spl[2]))
        else:
            controlSock.send(bytes("1put: '{}' is not a valid path".format(command_spl[1]), 'utf-8'))
        

    def PASV(self, controlSock):
        """passive pattern: return the dataSock connection"""
        print('pasv')
        dataSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        dataSocket.bind((self.HOST, 0))     # bind a random port
        addr, port = dataSocket.getsockname()
        print('server open data sock ({0}, {1})'.format(addr, port))
        msg = bytes(addr + ',' + str(port), 'utf-8')
        # delay
        time.sleep(0.5)
        controlSock.send(msg)
        dataSocket.listen(10)
        conn, addr = dataSocket.accept()
        print('client ({0}, {1}) has connect data sock'.format(addr[0], addr[1]))
        return (conn, addr)


    def PORT(self, controlSock):
        """port pattern: return the dataSock connection"""
        print('port')
        host, port = controlSock.recv(self.pieceSize).decode('utf-8').split(',')
        port = (int)(port)
        print('client has open the data sock ({0}, {1})'.format(host, port))
        # use dataport as 21 -> 13002 port
        self.dataSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.dataSocket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.dataSocket.bind((self.HOST, self.DATA_PORT))
        self.dataSocket.connect((host, port))
        return self.dataSocket, self.dataSocket.getpeername()

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
    
    def fileRecv(self, dataSock, uploadPath, filename):
        """upload file"""
        f = open(os.path.join(uploadPath, filename), 'wb+')
        while True:
            msg = dataSock.recv(self.pieceSize)
            if msg[len(msg) - 1] == ord('#'):
                f.write(msg[:len(msg) - 1])
                break
            f.write(msg)
        f.close()

if __name__ == "__main__":
    ftpserver = FTPServer()
    ftpserver.runServer()