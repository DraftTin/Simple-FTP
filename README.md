# Simple FTP

A basic FTP protocol implementation in Python, enabling GET and PUT commands for file transfer between the user and the server, along with commands like ls, pwd, cd, close, and quote, as well as some local user commands. It supports both PORT and PASV modes for file transfer.

## Features

- **Server-Side Implementation** (`ftpserver.py`)
  - Handles client connections using control and data ports.
  - Maintains a directory for storing server files (`serverspace`).
  - Supports multiple clients with threading.

- **Client-Side Implementation** (`ftpclient.py`)
  - Connects to the FTP server over specified control and data ports.
  - Allows users to upload and download files to/from the server.
  - Includes local commands for managing the client's local directory (`clientspace`).

- **User Management** (`User.py`)
  - Tracks user-specific attributes such as current path and mode of operation.

## File Structure

- **ftpserver.py**: The server-side script for managing FTP operations.
- **ftpclient.py**: The client-side script for interacting with the server.
- **User.py**: A helper module for managing user-specific properties.
- **clientspace/**: Directory for storing client-side files.
- **serverspace/**: Directory for storing server-side files.

## Usage

### Starting the Server

Run the server-side script to start the FTP server:

```bash
python ftpserver.py
```

### Running the Client

Run the client-side script to connect to the FTP server:

```bash
python ftpclient.py
```

### Supported Commands

##### Client Commands:

* **sethome**: Set the home directory for the client.
* **showhome**: Display the current home directory.

* **listhome**: List files in the client’s home directory.
* **help**: Display help information.

##### FTP Operations:

* **PUT**: Upload a file to the server.
* **GET**: Download a file from the server.
* **LIST**: List files on the server.
* **QUIT**: Disconnect from the server.

