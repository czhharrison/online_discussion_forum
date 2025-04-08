import sys
import socket
import os

TIMEOUT = 3.0
RETRY_TIMES = 3

# UDP向服务器发送消息并接收响应
def udp_msg_process(udp_sock, server_addr, send_msg):

    udp_sock.settimeout(TIMEOUT)
    for _ in range(RETRY_TIMES):
        try:
            udp_sock.sendto(send_msg.encode("utf-8"), server_addr)
            data, _ = udp_sock.recvfrom(8192)
            return data.decode("utf-8", errors="ignore")
        
        except socket.timeout:
            print("[Client] UDP timeout, retry...")
            continue
        
    # 超出设定的重试次数
    print("[Client] Communication with the server failed.")
    return ""

# TCP上传文件
def tcp_upload(server_ip, server_port, local_filename, remote_threadtitle, remote_filename, username):

    # 连接
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.connect((server_ip, server_port))
        print(f"[Client] Connected to server. Uploading {local_filename} now...")

        try:
            with open(local_filename, "rb") as f:
                while True:
                    chunk = f.read(4096)
                    if not chunk:
                        break
                    s.sendall(chunk)
        except Exception as e:
            print(f"[Client] Failed to open the file to be uploaded: {e}")
            return

        print(f"[Client] File {local_filename} upload completed.")

# TCP下载文件
def tcp_download(server_ip, server_port, local_filename, remote_threadtitle, remote_filename, username):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.connect((server_ip, server_port))
        print(f"[Client] Connected to the server. Starting download {remote_filename} ...")

        try:
            with open(local_filename, "wb") as f:
                while True:
                    chunk = s.recv(4096)
                    if not chunk:
                        break
                    f.write(chunk)
        except Exception as e:
            print(f"[Client] Unable to write to local file {local_filename}: {e}")
            return

        print(f"[Client] File {local_filename} download completed.")

def main():
    if len(sys.argv) != 2:
        print("correct usage: python client.py <server_port>")
        sys.exit(1)

    server_port = int(sys.argv[1])
    server_ip = "127.0.0.1"

    # 创建UDP socket
    udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    server_addr = (server_ip, server_port)

    # 身份验证
    username = None
    while True:
        user_input = input("Enter username:").strip()
        if not user_input:
            continue

        # 发送消息到服务器
        response = udp_msg_process(udp_sock, server_addr, f"LOGIN {user_input}")
        if not response:
            continue        # 说明UDP重传3次都没成功

        if response == "USER_IN_USE":
            print("[Client] This user is already logged in elsewhere, please change your username.")
            continue

        elif response == "EXISTING_USER":               # 用户存在，输入密码
            pwd = input("Enter password: ").strip()
            resp2 = udp_msg_process(udp_sock, server_addr, f"PWD {pwd}")
            if resp2 == "LOGIN_SUCCESS":
                print(f"[Client] Welcome back, {user_input}!")
                username = user_input
                break

            elif resp2 == "WRONG_PASSWORD":
                print("[Client] Incorrect password, please log in again.")
                continue

            else:
                print("[Client] Unknown response, re-login.")
                continue

        elif response == "NEW_USER":                # 创建新用户
            pwd = input("Set a password for new user:").strip()
            resp2 = udp_msg_process(udp_sock, server_addr, f"PWD {pwd}")

            if resp2 == "LOGIN_SUCCESS":
                print(f"[Client] New user {user_input} created successfully, logged in!")
                username = user_input
                break
            else:
                print("[Client] Failed to create a new user, please try again.")
                continue
        else:
            print("[Client] Unknown response, retry.")

    # 处理命令
    print("[Client] Available commands:")
    print("  CRT <threadtitle>")
    print("  MSG <threadtitle> <message>")
    print("  DLT <threadtitle> <messagenumber>")
    print("  EDT <threadtitle> <messagenumber> <message>")
    print("  LST")
    print("  RDT <threadtitle>")
    print("  UPD <threadtitle> <filename>")
    print("  DWN <threadtitle> <filename>")
    print("  RMV <threadtitle>")
    print("  XIT")
    print("************************************************\n")

    while True:
        cmd_line = input("Enter a command: ").rstrip()
        if not cmd_line:
            continue

        parts = cmd_line.split()
        cmd = parts[0].upper()

        # XIT
        if cmd == "XIT":
            resp = udp_msg_process(udp_sock, server_addr, "XIT")
            if resp == "XIT_OK":
                print("[Client] Exit successful.")
            else:
                print("[Client] Exit anomaly.")
            break
        
        # CRT
        elif cmd == "CRT":
            if len(parts) != 2:
                print("correct usage:CRT <threadtitle>")
                continue
            threadtitle = parts[1]
            to_send = f"CRT {threadtitle} {username}"
            resp = udp_msg_process(udp_sock, server_addr, to_send)
            print(resp)

        # MSG
        elif cmd == "MSG":
            if len(parts) < 3:
                print("correct usage: MSG <threadtitle> <message>")
                continue
            threadtitle = parts[1]
            message_text = " ".join(parts[2:])                      # 后面的全都是消息内容
            to_send = f"MSG {threadtitle} {message_text} {username}"
            resp = udp_msg_process(udp_sock, server_addr, to_send)
            print(resp)

        # DLT
        elif cmd == "DLT":
            if len(parts) != 3:
                print("correct usage: DLT <threadtitle> <messagenumber>")
                continue
            threadtitle = parts[1]
            messagenumber = parts[2]
            to_send = f"DLT {threadtitle} {messagenumber} {username}"
            resp = udp_msg_process(udp_sock, server_addr, to_send)
            print(resp)

        # EDT
        elif cmd == "EDT":
            if len(parts) < 4:
                print("correct usage: EDT <threadtitle> <messagenumber> <new_message>")
                continue
            threadtitle = parts[1]
            messagenumber = parts[2]
            new_msg = " ".join(parts[3:])
            to_send = f"EDT {threadtitle} {messagenumber} {new_msg} {username}"
            resp = udp_msg_process(udp_sock, server_addr, to_send)
            print(resp)

        # LST
        elif cmd == "LST":
            if len(parts) != 1:
                print("Error: LST No parameters.")
                continue
            to_send = f"LST {username}"
            resp = udp_msg_process(udp_sock, server_addr, to_send)
            print(resp)

        # RDT
        elif cmd == "RDT":
            if len(parts) != 2:
                print("correct usage: RDT <threadtitle>")
                continue
            threadtitle = parts[1]
            to_send = f"RDT {threadtitle} {username}"
            resp = udp_msg_process(udp_sock, server_addr, to_send)
            print(resp)

        # UPD
        elif cmd == "UPD":
            # UPD threadtitle filename
            if len(parts) != 3:
                print("correct usage: UPD <threadtitle> <filename>")
                continue
            threadtitle = parts[1]
            filename = parts[2]

            # 检查文件是否存在
            if not os.path.exists(filename):
                print(f"File {filename} does not exist.")
                continue

            to_send = f"UPD {threadtitle} {filename} {username}"
            resp = udp_msg_process(udp_sock, server_addr, to_send)

            # 开始上传
            if resp == "UPD_OK":
                print("[Client] Ready to connect to TCP to transfer files...")
                tcp_upload(server_ip, server_port, filename, threadtitle, filename, username)
                record_cmd = f"{username} uploaded {filename}"
                to_send = f"MSG_UPLOAD {threadtitle} {record_cmd} {username}"

                print("[Client] The file is uploaded.")
            else:
                print(resp)

        # DWN
        elif cmd == "DWN":
            if len(parts) != 3:
                print("correct usage: DWN <threadtitle> <filename>")
                continue
            threadtitle = parts[1]
            filename = parts[2]

            # 发请求
            to_send = f"DWN {threadtitle} {filename} {username}"
            resp = udp_msg_process(udp_sock, server_addr, to_send)

            if resp == "DWN_OK":
                print("[Client] Preparing TCP to receive files...")         # 开始TCP下载
                local_filename = filename
                tcp_download(server_ip, server_port, local_filename, threadtitle, filename, username)
            else:
                print(resp)

        # RMV
        elif cmd == "RMV":
            # RMV threadtitle
            if len(parts) != 2:
                print("correct usage: RMV <threadtitle>")
                continue
            threadtitle = parts[1]
            to_send = f"RMV {threadtitle} {username}"
            resp = udp_msg_process(udp_sock, server_addr, to_send)
            print(resp)

        else:
            print("ERROR: Invalid command, please enter again.")

    udp_sock.close()

if __name__ == "__main__":
    main()
