import sys
import os
import socket
import threading
from queue import Queue

credentials_file = "credentials.txt"

# 读取credentials文件到一个字典中，格式为：{username: password}
def read_credentials():
    accounts = {}
    if os.path.exists(credentials_file):
        with open(credentials_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                p = line.split(" ", 1)          # 只分割一次
                if len(p) == 2:
                    usrname, pwd = p
                    accounts[usrname] = pwd
    return accounts

# 把用户的名字和密码保存到credentials文件
def save_credentials(accounts):
    with open(credentials_file, "w", encoding="utf-8") as f:
        for usrname, pwd in accounts.items():
            f.write(f"{usrname} {pwd}\n")

# 论坛服务器对象
class ForumServer:
    def __init__(self, server_port):
        self.server_port = server_port
        self.udp_sock = None
        self.tcp_sock = None

        # 加载用户凭据
        self.credentials = read_credentials()  # {username: password}
        # 已登录用户
        self.active_users = set()
        # 记录地址和线程的关系
        self.client_threads = {}
        # 另一个TCP
        self.file_transfer_threads = []
        # 记录client对应的文件信息
        self.pending_transfers = {}

    # 启动server以及TCP、UDP
    def start(self):
        # 启动UDP
        self.udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.udp_sock.bind(("127.0.0.1", self.server_port))
        print(f"[Server] UDP port {self.server_port} is open, waiting for client messages...")

        # 启动TCP
        self.tcp_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.tcp_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.tcp_sock.bind(("127.0.0.1", self.server_port))
        self.tcp_sock.listen(5)
        print(f"[Server] TCP port {self.server_port} is open.")

        # 创建udp线程
        udp_thread = threading.Thread(target=self.udp_msg_process, daemon=True)
        udp_thread.start()

        # 创建tcp线程
        tcp_thread = threading.Thread(target=self.tcp_connect_file, daemon=True)
        tcp_thread.start()

        # 主线程保持存活
        print("[Server] The server is ready to serve multiple clients concurrently.")
        while True:
            threading.Event().wait(1000)

    # 消息处理
    def udp_msg_process(self):
        while True:
            data, addr = self.udp_sock.recvfrom(8192)       # 阻塞等待UDP

            if addr not in self.client_threads:             # 说明是新client，需要创建一个新的线程
                print(f"[Server] New client address detected: {addr}, create thread...")
                client_thread = ProcessClient(self, addr)
                self.client_threads[addr] = client_thread
                client_thread.start()

            self.client_threads[addr].messages.put(data)   # 分配信息给对应的线程

    # 处理连接和文件
    def tcp_connect_file(self):
        while True:
            link, addr = self.tcp_sock.accept()
            print(f"[Server] Receives a TCP file transfer request from {addr}, creates FileTransfer...")
            file_thread = FileTransfer(self, link, addr)
            self.file_transfer_threads.append(file_thread)
            file_thread.start()

    # 移除线程
    def remov_thread(self, addr):
        if addr in self.client_threads:
            del self.client_threads[addr]

    # 命令处理
    def command_process(self, msg, username, addr):
        print(f"[Server] {username} issued the command: {msg}.")
        p = msg.split()
        command = p[0]

        def end(res):
            print(f"[Server] The server respond to {username} with: \n{res}.")
            return res
        
        # XIT退出
        if command == "XIT":
            return end("XIT_OK")

        # CRT创建线程
        if command == "CRT":
            if len(p) != 3:
                return end("ERROR: correct usage: CRT <threadtitle>")
            
            threadtitle = p[1]
            thread_file = threadtitle

            if os.path.exists(thread_file):
                return end("ERROR: The thread already exists.")
            else:
                with open(thread_file, "w", encoding="utf-8") as f:
                    f.write(username + "\n")

                print(f"[Server] Thread {threadtitle} has been created by {username}.")
                return end(f"Thread {threadtitle} was created successfully.")

        # MSG发消息
        if command == "MSG":
            if len(p) < 3:
                return end("ERROR: correct usage: MSG <threadtitle> <message>")
            
            threadtitle = p[1]
            message_text = " ".join(p[2:-1])        # 去掉最后的username
            if not os.path.exists(threadtitle):
                return end("ERROR: Thread does not exist.")

            with open(threadtitle, "r", encoding="utf-8") as f:
                lines = f.readlines()

            msg_count = 0
            for line in lines[1:]:
                if " uploaded " not in line:
                    msg_count += 1
            new_num = msg_count + 1

            with open(threadtitle, "a", encoding="utf-8") as f:
                f.write(f"{new_num} {username}: {message_text}\n")

            print(f"[Server] {username} posted a new message in {threadtitle}.")
            return end(f"Successfully posted a message in {threadtitle}.")

        # DLT删除消息
        if command == "DLT":
            if len(p) != 4:
                return end("ERROR: correct usage: DLT <threadtitle> <messagenumber>")
            threadtitle = p[1]

            try:
                msg_num = int(p[2])
            except:
                return end("ERROR: The message number should be an integer.")
            
            if not os.path.exists(threadtitle):
                return end("ERROR: Thread does not exist.")

            with open(threadtitle, "r", encoding="utf-8") as f:
                lines = f.readlines()

            found_line_index = -1
            found_line_content = None
            message_count = 0

            for i in range(1, len(lines)):
                if " uploaded " in lines[i]:
                    continue
                message_count += 1
                if message_count == msg_num:
                    found_line_index = i
                    found_line_content = lines[i]
                    break

            if found_line_index == -1:
                return end("ERROR: Message number does not exist.")
            
            tmp = found_line_content.strip().split(" ", 2)
            if len(tmp) < 2:
                return end("ERROR: Message number does not exist.")
            

            user_part = tmp[1]
            poster = user_part.split(":", 1)[0]
            if poster != username:
                return end("ERROR: You can only delete your own messages.")

            del lines[found_line_index]
            with open(threadtitle, "w", encoding="utf-8") as f:
                for line_content in lines:
                    f.write(line_content)

            # 重新编号
            with open(threadtitle, "r", encoding="utf-8") as f:
                lines = f.readlines()

            new_lines = [lines[0]]
            real_msg_index = 0
            for i in range(1, len(lines)):
                if " uploaded " in lines[i]:
                    new_lines.append(lines[i])
                else:
                    real_msg_index += 1
                    parts_line = lines[i].strip().split(" ", 2)
                    if len(parts_line) >= 3:
                        new_lines.append(f"{real_msg_index} {parts_line[1]} {parts_line[2]}\n")
                    else:
                        new_lines.append(lines[i])

            with open(threadtitle, "w", encoding="utf-8") as f:
                for l in new_lines:
                    f.write(l)

            print(f"[Server] {username} deleted message {msg_num} in {threadtitle}.")
            return end(f"Message {msg_num} in {threadtitle} has been successfully deleted.")

        # EDT编辑消息
        if command == "EDT":
            if len(p) < 4:
                return end("ERROR: correct usage: EDT <threadtitle> <messagenumber> <new_message>")
            threadtitle = p[1]
            try:
                msg_num = int(p[2])
            except:
                return end("ERROR: The message number should be an integer.")
            
            new_msg = " ".join(p[3:-1])
            if not os.path.exists(threadtitle):
                return end("ERROR: Message number does not exist.")

            with open(threadtitle, "r", encoding="utf-8") as f:
                lines = f.readlines()

            message_count = 0
            found_line_index = -1
            found_line_content = None

            for i in range(1, len(lines)):
                if " uploaded " in lines[i]:
                    continue
                message_count += 1
                if message_count == msg_num:
                    found_line_index = i
                    found_line_content = lines[i]
                    break

            if found_line_index == -1:
                return end("ERROR: Message number does not exist.")
            
            tmp = found_line_content.strip().split(" ", 2)
            if len(tmp) < 3:
                return end("ERROR: Message number does not exist.")

            poster = tmp[1].replace(":", "")
            if poster != username:
                return end("ERROR: You can only delete your own messages.")

            new_line = f"{tmp[0]} {tmp[1]} {new_msg}\n"
            lines[found_line_index] = new_line

            with open(threadtitle, "w", encoding="utf-8") as f:
                for l in lines:
                    f.write(l)

            print(f"[Server] {username} edited message {msg_num} in {threadtitle}.")
            return end(f"Message {msg_num} in {threadtitle} has been successfully edited.")

        # LST列出线程
        if command == "LST":
            files = os.listdir(".")
            thread_titles = []
            
            for filename in files:
                if os.path.isfile(filename):
                    try:
                        with open(filename, "r", encoding="utf-8") as f:
                            first_line = f.readline().strip()
                            if first_line in self.credentials.keys():
                                thread_titles.append(filename)
                    except:
                        pass

            if len(thread_titles) == 0:
                print(f"[Server] {username} requested LST, but there are no threads.")
                return end("There are no threads.")
            else:
                print(f"[Server] {username} request LST, current thread list: {thread_titles}")
                return end("\n".join(thread_titles))

        # RDT读取线程
        if command == "RDT":
            threadtitle = p[1] if len(p) >= 2 else None
            if not os.path.exists(threadtitle):
                return end("ERROR: Message number does not exist.")
            
            with open(threadtitle, "r", encoding="utf-8") as f:
                lines = f.readlines()

            if len(lines) <= 1:
                print(f"[Server] {username} read {threadtitle} but no content.")
                return end("Thread has no content")
            else:
                content = "".join(lines[1:])
                print(f"[Server] {username} read {threadtitle}.")
                return end(content)

        # UPD上传文件
        if command == "UPD":
            if len(p) != 4:
                return end("ERROR: correct usage: UPD <threadtitle> <filename>")
            
            threadtitle = p[1]
            filename = p[2]
            if not os.path.exists(threadtitle):
                return end("ERROR: Message number does not exist.")
            
            server_side_file = f"{threadtitle}-{filename}"
            if os.path.exists(server_side_file):
                return end("ERROR: The filename has been uploaded to the thread.")
            
            # 记录文件信息
            client_ip = addr[0]
            self.pending_transfers[client_ip] = {
                "mode": "upload",
                "threadtitle": threadtitle,
                "filename": filename,
                "username": username
            }

            print(f"[Server] {username} preparing to upload a file to {threadtitle}: {filename}")

            return end("UPD_OK")

        # DWN下载文件
        if command == "DWN":
            if len(p) != 4:
                return end("ERROR: correct usage: DWN <threadtitle> <filename>")
            
            threadtitle = p[1]
            filename = p[2]
            if not os.path.exists(threadtitle):
                return end("ERROR: Message number does not exist.")
            
            server_side_file = f"{threadtitle}-{filename}"
            if not os.path.exists(server_side_file):
                return end("ERROR: The file does not exist in the thread.")
            
            # 记录文件信息
            client_ip = addr[0]
            self.pending_transfers[client_ip] = {
                "mode": "download",
                "threadtitle": threadtitle,
                "filename": filename,
                "username": username
            }

            print(f"[Server] {username}  preparing to download file to {threadtitle}: {filename}")
            return end("DWN_OK")

        # RMV删除线程
        if command == "RMV":
            if len(p) != 3:
                return end("ERROR: correct usage: RMV <threadtitle>")
            
            threadtitle = p[1]
            if not os.path.exists(threadtitle):
                return end("ERROR: Message number does not exist.")
            
            with open(threadtitle, "r", encoding="utf-8") as f:
                creator = f.readline().strip()

            if creator != username:
                return end("ERROR: Only the thread creator can delete the thread.")
            
            files = os.listdir(".")
            for f in files:
                if f == threadtitle or f.startswith(threadtitle + "-"):
                    os.remove(f)

            print(f"[Server] Thread {threadtitle} has been deleted by {username}.")
            return end(f"Thread {threadtitle} has been deleted")

        # 如果都不匹配
        return end("ERROR: Invalid command")

# 处理各个client的UDP消息
class ProcessClient(threading.Thread):
    def __init__(self, server: ForumServer, addr):
        super().__init__()
        self.server = server
        self.addr = addr
        self.active = True
        self.messages = Queue()        # 存放udp_msg_process分配的消息
        self.current_user = None       # 记录现在的用户名

    # 运行线程
    def run(self):
        try:
            self.identity_confirm()             # 首先执行身份验证流程

            while self.active:                  # 一直处理命令
                # 阻塞等待消息
                data = self.messages.get()
                if not data:
                    continue

                msg_str = data.decode("utf-8", errors="ignore").strip()
                if not msg_str:
                    continue

                # 处理命令，返回结果
                response = self.server.command_process(msg_str, self.current_user, self.addr)
                # 用UDP发回给客户端
                self.server.udp_sock.sendto(response.encode("utf-8"), self.addr)

                # 若client发XIT，结束循环
                if msg_str.startswith("XIT"):
                    break

        except Exception as e:
            print(f"[Server] {self.addr} an error occurred: {e}")

        finally:
            if self.current_user in self.server.active_users:
                self.server.active_users.remove(self.current_user)

            self.server.remov_thread(self.addr)
            self.active = False
            print(f"[Server] Client thread {self.addr} has finished.")

    # 身份验证
    def identity_confirm(self):
        while True:
            # 读取用户名
            data = self.messages.get()
            if not data:
                continue

            msg = data.decode("utf-8", errors="ignore").strip()
            p = msg.split()
            if len(p) < 2:
                continue

            command, username = p[0], p[1]
            if command != "LOGIN":
                continue

            # 如果该用户名已经被其他client使用
            if username in self.server.active_users:
                send_msg = "USER_IN_USE"
                self.server.udp_sock.sendto(send_msg.encode("utf-8"), self.addr)
                continue

            # 判断用户名是否存在
            if username in self.server.credentials:
                # 用户已存在，输入密码
                send_msg = "EXISTING_USER"
                self.server.udp_sock.sendto(send_msg.encode("utf-8"), self.addr)

                # 读取密码
                data2 = self.messages.get()
                if not data2:
                    continue

                pwd_msg = data2.decode("utf-8", errors="ignore").strip().split()
                if len(pwd_msg) < 2:
                    continue

                pwd_cmd, password = pwd_msg[0], pwd_msg[1]
                if pwd_cmd != "PWD":
                    continue

                # 验证密码
                if self.server.credentials[username] == password:
                    self.server.active_users.add(username)
                    self.current_user = username
                    send_msg = "LOGIN_SUCCESS"
                    self.server.udp_sock.sendto(send_msg.encode("utf-8"), self.addr)

                    print(f"[Server] User {username} logged in successfully.")
                    return
                
                else:
                    send_msg = "WRONG_PASSWORD"
                    self.server.udp_sock.sendto(send_msg.encode("utf-8"), self.addr)
                    continue

            else:
                # 新用户
                send_msg = "NEW_USER"
                self.server.udp_sock.sendto(send_msg.encode("utf-8"), self.addr)

                # 读取密码
                data2 = self.messages.get()
                if not data2:
                    continue

                pwd_msg = data2.decode("utf-8", errors="ignore").strip().split()
                if len(pwd_msg) < 2:
                    continue

                pwd_cmd, newpwd = pwd_msg[0], pwd_msg[1]
                if pwd_cmd != "PWD":
                    continue

                # 写入credentials文件
                self.server.credentials[username] = newpwd
                save_credentials(self.server.credentials)

                self.server.active_users.add(username)
                self.current_user = username
                send_msg = "LOGIN_SUCCESS"
                self.server.udp_sock.sendto(send_msg.encode("utf-8"), self.addr)

                print(f"[Server] New user {username} has been created and logged in successfully.")
                return

# 文件传输
class FileTransfer(threading.Thread):
    def __init__(self, server: ForumServer, link: socket.socket, addr):
        super().__init__()
        self.server = server
        self.link = link
        self.addr = addr

    def run(self):
        print(f"[FileTransfer] Start processing file transfers from {self.addr}...")

        try:
            # 根据pending_transfers查询模式
            client_ip = self.addr[0]
            transfer_info = self.server.pending_transfers.get(client_ip)
            if not transfer_info:
                print("[FileTransfer] ERROR: No pending transfer information.")
                self.link.close()
                return

            mode = transfer_info["mode"]
            threadtitle = transfer_info["threadtitle"]
            filename = transfer_info["filename"]
            username = transfer_info["username"]

            if mode == "upload":
                # 将数据写入到threadtitle-filename
                server_side_file = f"{threadtitle}-{filename}"
                with open(server_side_file, "wb") as f:
                    while True:
                        chunk = self.link.recv(4096)
                        if not chunk:
                            break
                        f.write(chunk)

                # 上传成功后写入文件
                with open(threadtitle, "a", encoding="utf-8") as f:
                    f.write(f"{username} uploaded {filename}\n")
                    
                print(f"[FileTransfer] {username} has uploaded {server_side_file} successfully.")


            elif mode == "download":
                # 把threadtitle-filename文件发送给client
                server_side_file = f"{threadtitle}-{filename}"
                if not os.path.exists(server_side_file):
                    print(f"[FileTransfer] ERROR: file {server_side_file} not found.")
                    self.link.close()
                    return
                
                with open(server_side_file, "rb") as f:
                    while True:
                        chunk = f.read(4096)
                        if not chunk:
                            break
                        self.link.sendall(chunk)

                with open(threadtitle, "a", encoding="utf-8") as f:
                    f.write(f"{username} downloaded {filename}\n")

                print(f"[FileTransfer] {username} has downloaded {server_side_file} successfully.")

        except Exception as e:
            print(f"[FileTransfer] Error: {e}")

        finally:
            # 清除pending_transfers的对应信息
            if client_ip in self.server.pending_transfers:
                del self.server.pending_transfers[client_ip]
            self.link.close()
            print(f"[FileTransfer] Finish file transfer with {self.addr}.")


if __name__ == "__main__":

    if len(sys.argv) != 2:
        print("correct usage: python server.py <server_port>")
        sys.exit(1)

    port = int(sys.argv[1])
    server = ForumServer(port)
    server.start()
