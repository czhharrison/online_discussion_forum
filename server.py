#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import os
import socket
import threading

# ============= 全局常量及工具函数 =============
CREDENTIALS_FILE = "credentials.txt"

def load_credentials():
    """加载凭据文件到一个字典中：{username: password, ...}"""
    creds = {}
    if os.path.exists(CREDENTIALS_FILE):
        with open(CREDENTIALS_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                # 假设一行: username password
                parts = line.split(" ", 1)  # 只分割一次
                if len(parts) == 2:
                    uname, pwd = parts
                    creds[uname] = pwd
    return creds

def save_credentials(creds):
    """将当前用户凭据字典写回到 credentials.txt 文件。"""
    with open(CREDENTIALS_FILE, "w", encoding="utf-8") as f:
        for uname, pwd in creds.items():
            f.write(f"{uname} {pwd}\n")

# ============= 服务器核心类（一次只和一个客户端交互） =============
class ForumServer:
    def __init__(self, server_port):
        self.server_port = server_port
        self.udp_sock = None
        self.tcp_sock = None

        # 加载用户凭据
        self.credentials = load_credentials()  # {username: password}
        # 当前已登录用户：在第一种配置下，实际只会有 0~1 个
        self.active_users = set()

    def start(self):
        """启动服务器：同时启动 UDP 监听和 TCP 监听。"""
        # 1) 启动 UDP
        self.udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.udp_sock.bind(("127.0.0.1", self.server_port))
        print(f"[Server] UDP 端口 {self.server_port} 已打开，等待客户端消息...")

        # 2) 启动 TCP
        self.tcp_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.tcp_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.tcp_sock.bind(("127.0.0.1", self.server_port))
        self.tcp_sock.listen(5)
        print(f"[Server] TCP 端口 {self.server_port} 已打开，用于文件上传/下载...")

        # 3) 进入循环，不断等待新的客户端进行“身份验证+命令交互”
        while True:
            print("\n[Server] 等待新的客户端登录...\n")
            self.handle_single_client()

    def handle_single_client(self):
        """
        实现“第一种配置”：一次只与一个客户端交互。
        包含身份验证过程 + 命令处理过程，直到客户端发 XIT 或意外断开。
        """
        client_addr = None
        current_user = None

        # ========== 身份验证阶段 ==========
        while True:
            # 等待 UDP 收到用户名
            data, addr = self.udp_sock.recvfrom(4096)
            msg = data.decode("utf-8", errors="ignore").strip()
            parts = msg.split()
            if len(parts) < 2:
                # 消息格式不对。理想情况不会发生，简单处理。
                continue

            cmd, username = parts[0], parts[1]
            if cmd != "LOGIN":
                # 不是登录请求，忽略
                continue

            # 如果已经有用户在此服务器上交互(本配置只允许一个)，则阻止
            if len(self.active_users) > 0 and username in self.active_users:
                # 说明有人正在用该用户名登录
                send_msg = "USER_IN_USE"
                self.udp_sock.sendto(send_msg.encode("utf-8"), addr)
                continue

            # 判断用户名是否存在
            if username in self.credentials:
                # 告诉客户端：此用户存在，请输入密码
                send_msg = "EXISTING_USER"
                self.udp_sock.sendto(send_msg.encode("utf-8"), addr)

                # 等待密码
                data, addr = self.udp_sock.recvfrom(4096)
                pwd_msg = data.decode("utf-8", errors="ignore").strip().split()
                if len(pwd_msg) < 2:
                    # 格式错误直接继续
                    continue
                pwd_cmd, password = pwd_msg[0], pwd_msg[1]
                if pwd_cmd != "PWD":
                    continue

                # 验证密码
                if self.credentials[username] == password:
                    # 验证成功
                    send_msg = "LOGIN_SUCCESS"
                    self.udp_sock.sendto(send_msg.encode("utf-8"), addr)
                    print(f"[Server] 用户 {username} 登录成功。")
                    self.active_users.add(username)
                    client_addr = addr
                    current_user = username
                    break
                else:
                    # 密码错误
                    send_msg = "WRONG_PASSWORD"
                    self.udp_sock.sendto(send_msg.encode("utf-8"), addr)
                    # 继续让客户端再发用户名
                    continue
            else:
                # 用户名不存在，创建新用户
                send_msg = "NEW_USER"
                self.udp_sock.sendto(send_msg.encode("utf-8"), addr)

                # 等待新密码
                data, addr = self.udp_sock.recvfrom(4096)
                pwd_msg = data.decode("utf-8", errors="ignore").strip().split()
                if len(pwd_msg) < 2:
                    continue
                pwd_cmd, newpwd = pwd_msg[0], pwd_msg[1]
                if pwd_cmd != "PWD":
                    continue

                # 把新用户写入 credentials
                self.credentials[username] = newpwd
                save_credentials(self.credentials)

                # 登录成功
                send_msg = "LOGIN_SUCCESS"
                self.udp_sock.sendto(send_msg.encode("utf-8"), addr)
                print(f"[Server] 新用户 {username} 已创建并登录成功。")
                self.active_users.add(username)
                client_addr = addr
                current_user = username
                break

        # ========== 命令处理阶段 ==========
        #   直到该客户端发 XIT，或出现异常
        while True:
            try:
                data, addr = self.udp_sock.recvfrom(8192)
            except:
                print("[Server] 接收命令出错，断开。")
                # 主动移除已登录用户
                if current_user in self.active_users:
                    self.active_users.remove(current_user)
                break

            if addr != client_addr:
                # 不接受别的地址的命令(第一种配置不考虑并发)
                continue

            msg = data.decode("utf-8", errors="ignore").rstrip()
            if not msg:
                continue

            # 解析命令
            response = self.process_command(msg, current_user)
            # 通过UDP发送响应
            self.udp_sock.sendto(response.encode("utf-8"), client_addr)

            # 如果是 XIT，则退出命令循环
            if msg.strip().startswith("XIT"):
                # 客户端正常退出
                break

        # 命令循环结束，说明客户端断开或XIT
        if current_user in self.active_users:
            self.active_users.remove(current_user)
        print(f"[Server] 用户 {current_user} 已退出。")

    def process_command(self, msg, username):
        """
        根据客户端发来的指令进行处理。
        msg 示例:
          CRT threadtitle <username>
          MSG threadtitle <message> <username>
          ...
        """
        parts = msg.split()
        cmd = parts[0]

        # ============ 处理各种命令 ============

        # ---------------- 退出 ----------------
        if cmd == "XIT":
            # 通知客户端可以结束
            return "XIT_OK"

        # ---------------- 创建线程 ----------------
        if cmd == "CRT":
            if len(parts) != 3:
                return "ERROR: 用法 CRT <threadtitle>"
            threadtitle = parts[1]
            # 第 3 个是 username，本题里客户端会拼在一起(或者也可只发2个参数，然后服务端带上 username)
            # 这里直接忽视 parts[2]，因为我们自己已经有 username 变量
            thread_file = threadtitle
            if os.path.exists(thread_file):
                return "ERROR: 该线程已存在"
            else:
                # 创建线程文件, 第一行写创建者
                with open(thread_file, "w", encoding="utf-8") as f:
                    f.write(username + "\n")  # 第一行保存创建者
                return f"线程 {threadtitle} 创建成功"

        # ---------------- 发布消息 ----------------
        if cmd == "MSG":
            # MSG threadtitle message... username(最后)
            # 因为消息可能包含空格，所以不能单纯用split()切固定下标
            if len(parts) < 3:
                return "ERROR: 用法 MSG <threadtitle> <message>"
            threadtitle = parts[1]
            # 去掉CMD, threadtitle, 最后的username，共3个位置
            # 中间所有内容作为 message
            # 注意：本示例假设客户端传的最后一个就是username
            message_text = " ".join(parts[2:-1])  # 2到倒数第2
            # 检查文件是否存在
            if not os.path.exists(threadtitle):
                return "ERROR: 线程不存在"
            # 找到目前已有多少条消息编号
            lines = []
            with open(threadtitle, "r", encoding="utf-8") as f:
                lines = f.readlines()

            # 统计已有消息数(不含第一行:创建者, 不含上传记录)
            msg_count = 0
            for line in lines[1:]:
                # 判断这一行是否是 "n username: msg"
                # 或者 "username uploaded filename"
                if " uploaded " not in line:
                    msg_count += 1

            new_num = msg_count + 1
            # 将新消息写入末尾
            with open(threadtitle, "a", encoding="utf-8") as f:
                f.write(f"{new_num} {username}: {message_text}\n")
            return f"在 {threadtitle} 中发布消息成功"

        # ---------------- 删除消息 ----------------
        if cmd == "DLT":
            if len(parts) != 4:
                return "ERROR: 用法 DLT <threadtitle> <messagenumber>"
            threadtitle = parts[1]
            try:
                msg_num = int(parts[2])
            except:
                return "ERROR: 消息编号应为整数"
            # 检查文件是否存在
            if not os.path.exists(threadtitle):
                return "ERROR: 线程不存在"

            # 读取所有行
            with open(threadtitle, "r", encoding="utf-8") as f:
                lines = f.readlines()

            # 检查 msg_num 是否有效、是否是当前用户发的
            # lines[0] 是创建者
            found_line_index = -1
            found_line_content = None
            message_count = 0

            # 把不含上传记录的行(消息行)编号计数，用于判断 msg_num 对应哪行
            for i in range(1, len(lines)):
                if " uploaded " in lines[i]:
                    # 跳过上传记录
                    continue
                message_count += 1
                if message_count == msg_num:
                    found_line_index = i
                    found_line_content = lines[i]
                    break

            if found_line_index == -1:
                return "ERROR: 消息编号不存在"

            # 检查是不是该用户发的
            # found_line_content 形如 "1 yoda: text..."
            # 拿到 "yoda" 跟 username 比较
            # 先去掉编号
            tmp = found_line_content.strip().split(" ", 1)  # ["1", "yoda: blabla"]
            if len(tmp) < 2:
                return "ERROR: 消息格式不对"
            user_part = tmp[1]  # "yoda: blabla"
            poster = user_part.split(":", 1)[0]  # "yoda"
            if poster != username:
                return "ERROR: 只能删除自己发布的消息"

            # 删除此行
            del lines[found_line_index]

            # 重新写入文件
            with open(threadtitle, "w", encoding="utf-8") as f:
                for line_i, line_content in enumerate(lines):
                    f.write(line_content)

            # 重新编号
            # 需要再次读出来进行编号修正
            with open(threadtitle, "r", encoding="utf-8") as f:
                lines = f.readlines()

            new_lines = [lines[0]]  # 第一行保留
            real_msg_index = 0
            for i in range(1, len(lines)):
                if " uploaded " in lines[i]:
                    # 上传记录不动
                    new_lines.append(lines[i])
                else:
                    # 消息
                    real_msg_index += 1
                    # 行可能类似 "2 yoda: hi there"
                    # 去掉原先编号，换成新的 real_msg_index
                    parts_line = lines[i].strip().split(" ", 2)
                    if len(parts_line) >= 3:
                        # parts_line[0]是旧编号
                        # parts_line[1]是 username:
                        # parts_line[2]是 消息正文
                        # 重新拼
                        new_lines.append(f"{real_msg_index} {parts_line[1]} {parts_line[2]}\n")
                    else:
                        # 格式不明，理论不会出现
                        new_lines.append(lines[i])

            # 覆盖写回
            with open(threadtitle, "w", encoding="utf-8") as f:
                for l in new_lines:
                    f.write(l)

            return f"删除 {threadtitle} 中的第 {msg_num} 号消息成功"

        # ---------------- 编辑消息 ----------------
        if cmd == "EDT":
            # EDT threadtitle msg_num new_message... username
            if len(parts) < 4:
                return "ERROR: 用法 EDT <threadtitle> <messagenumber> <new_message>"
            threadtitle = parts[1]
            try:
                msg_num = int(parts[2])
            except:
                return "ERROR: 消息编号应为整数"
            # new message 在 3:-1 之间
            new_msg = " ".join(parts[3:-1])
            if not os.path.exists(threadtitle):
                return "ERROR: 线程不存在"

            with open(threadtitle, "r", encoding="utf-8") as f:
                lines = f.readlines()

            # 寻找对应消息
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
                return "ERROR: 消息编号不存在"

            # 检查是不是该用户发的
            tmp = found_line_content.strip().split(" ", 2)  # ["1", "yoda:", "blabla..."]
            if len(tmp) < 3:
                return "ERROR: 消息格式不对"
            # tmp[1] = "yoda:"
            poster = tmp[1].replace(":", "")
            if poster != username:
                return "ERROR: 只能编辑自己发布的消息"

            # 修改消息
            # 保留编号和 "username:"
            new_line = f"{tmp[0]} {tmp[1]} {new_msg}\n"
            lines[found_line_index] = new_line

            # 写回
            with open(threadtitle, "w", encoding="utf-8") as f:
                for l in lines:
                    f.write(l)

            return f"编辑 {threadtitle} 中的第 {msg_num} 号消息成功"

        # ---------------- 列出线程 ----------------
        if cmd == "LST":
            # 列举当前目录下所有文件名，看哪些是线程文件
            # 线程文件要求：文件存在且第一行是创建者(只要不是 threadtitle-filename，就算是一个线程)
            files = os.listdir(".")
            thread_titles = []
            for filename in files:
                if os.path.isfile(filename):
                    # 简单判断一下，这里假设：上传的文件都是 "threadtitle-filename"
                    # 只要文件名中没有 '-' 或者不是 threadtitle-filename，就认为可能是线程文件
                    # 更严格可以去看第一行
                    # 这里为了简单，若首行是用户就认为是线程文件
                    try:
                        with open(filename, "r", encoding="utf-8") as f:
                            first_line = f.readline().strip()
                            if first_line in self.credentials.keys():
                                thread_titles.append(filename)
                    except:
                        pass
            if len(thread_titles) == 0:
                return "没有任何线程"
            else:
                return "\n".join(thread_titles)

        # ---------------- 读取线程 ----------------
        if cmd == "RDT":
            if len(parts) != 2 and len(parts) != 3:
                # 有些同学会把username附在后面，也可以处理
                # 假设客户端发送 "RDT threadtitle username"
                threadtitle = parts[1] if len(parts) >= 2 else None
            else:
                threadtitle = parts[1]
            if not os.path.exists(threadtitle):
                return "ERROR: 线程不存在"

            with open(threadtitle, "r", encoding="utf-8") as f:
                lines = f.readlines()
            # 第一行是创建者，不显示
            if len(lines) <= 1:
                return "（线程无内容）"
            else:
                content = "".join(lines[1:])
                return content

        # ---------------- 上传文件（先通过UDP握手，再TCP传） ----------------
        if cmd == "UPD":
            # UPD threadtitle filename username
            if len(parts) != 4:
                return "ERROR: 用法 UPD <threadtitle> <filename>"
            threadtitle = parts[1]
            filename = parts[2]

            if not os.path.exists(threadtitle):
                return "ERROR: 线程不存在"

            # 检查该线程下是否已存在同名文件
            # 同名文件命名规则：threadtitle-filename
            server_side_file = f"{threadtitle}-{filename}"
            if os.path.exists(server_side_file):
                return "ERROR: 该文件名已上传到该线程"

            # 如果可以开始上传，则返回 "UPD_OK"
            return "UPD_OK"

        # ---------------- 下载文件（先通过UDP握手，再TCP发） ----------------
        if cmd == "DWN":
            # DWN threadtitle filename username
            if len(parts) != 4:
                return "ERROR: 用法 DWN <threadtitle> <filename>"
            threadtitle = parts[1]
            filename = parts[2]

            if not os.path.exists(threadtitle):
                return "ERROR: 线程不存在"
            server_side_file = f"{threadtitle}-{filename}"
            if not os.path.exists(server_side_file):
                return "ERROR: 线程中不存在该文件"

            # 可以下载
            return "DWN_OK"

        # ---------------- 删除线程 ----------------
        if cmd == "RMV":
            if len(parts) != 3:
                return "ERROR: 用法 RMV <threadtitle>"
            threadtitle = parts[1]
            if not os.path.exists(threadtitle):
                return "ERROR: 线程不存在"
            # 检查是否是创建者
            with open(threadtitle, "r", encoding="utf-8") as f:
                creator = f.readline().strip()
            if creator != username:
                return "ERROR: 只有线程创建者才可删除该线程"

            # 删除所有与此线程相关的文件
            files = os.listdir(".")
            for f in files:
                if f == threadtitle or f.startswith(threadtitle + "-"):
                    os.remove(f)
            return f"线程 {threadtitle} 已被删除"

        # 如果都不匹配
        return "ERROR: 无效命令"

    # ============= 处理 TCP 文件传输 =============
    # 在本题第一种配置中，一个时刻只处理一个客户端，流程上可以简单一些。
    # 客户端先通过 UDP 告知要 UPD/DWN，然后发起 TCP connect，服务器只 accept 一次即可。

    def accept_single_tcp_connection(self):
        """
        等待一次 TCP 连接。返回 (conn, addr)
        在 handle_single_client() 中如果发现客户端发来 UPD/DWN_OK 就调用此函数
        """
        conn, addr = self.tcp_sock.accept()
        return conn, addr

# ============= 主程序 =============
if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("用法: python server.py <server_port>")
        sys.exit(1)

    port = int(sys.argv[1])
    server = ForumServer(port)
    server.start()
