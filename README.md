# UDP/TCP-Based Online Forum Application

本项目实现了一个基于 **客户端-服务器模型** 的简易在线论坛应用程序。不同于常规基于 HTTP 的论坛系统，本项目设计并实现了一个自定义通信协议，客户端和服务器通过 UDP 和 TCP 进行交互：

- **UDP**：用于处理主要论坛功能（登录、发帖、编辑、删除等）
- **TCP**：用于上传和下载文件

---

## 📁 项目结构

```
.
├── client.py           # 客户端主程序（UDP + TCP 文件交互）
├── server.py           # 多线程服务器（支持并发 UDP/TCP 通信）
├── credentials.txt     # 存储用户登录信息的文件（用户名 密码）
├── test.exe            # 任意可测试传输的二进制文件
```

---

## 🚀 启动说明

### 1️⃣ 启动服务器

```bash
python server.py <server_port>
```

- 服务端会监听指定端口上的 **UDP 和 TCP 请求**
- 支持多客户端并发连接

### 2️⃣ 启动客户端

```bash
python client.py <server_port>
```

- 客户端默认连接 `127.0.0.1:<server_port>`
- 首次登录将自动注册新用户

---

## ✅ 支持功能列表

客户端支持以下命令（全部基于自定义协议）：

| 命令 | 描述 |
|------|------|
| `CRT <threadtitle>` | 创建新主题 |
| `MSG <threadtitle> <message>` | 向主题发布消息 |
| `DLT <threadtitle> <messagenumber>` | 删除某条消息（只能删除自己发布的） |
| `EDT <threadtitle> <messagenumber> <new_message>` | 编辑自己的消息内容 |
| `LST` | 查看当前所有主题 |
| `RDT <threadtitle>` | 阅读某个主题下的所有消息 |
| `UPD <threadtitle> <filename>` | 上传文件到某主题（TCP传输） |
| `DWN <threadtitle> <filename>` | 从某主题下载文件（TCP传输） |
| `RMV <threadtitle>` | 删除主题（仅限创建者） |
| `XIT` | 注销并退出客户端 |

---

## 💡 技术要点

- 使用 `socket` 编程实现 UDP + TCP 网络通信
- 使用 `threading` 模块支持服务器端并发多用户处理
- 支持断点容错（UDP重传机制）
- 文件传输采用 TCP 保证可靠性
- 服务器维护以下状态：
  - 已注册用户（存储于 `credentials.txt`）
  - 当前在线用户
  - 每个主题及其消息（文件持久化）
  - 每个主题的上传文件（命名规则：`<threadtitle>-<filename>`）

---

## 📦 示例运行

### 启动服务器

```bash
python server.py 12345
```

### 启动两个客户端（分别执行）

```bash
python client.py 12345
```

输入用户名，如：

```text
Enter username: alice
Set a password for new user: 123456
```

然后执行命令：

```text
> CRT topic1
> MSG topic1 Hello, this is Alice!
> UPD topic1 test.exe
```

---

## 🔒 登录机制说明

- **首次登录新用户名** ➜ 系统将自动注册
- **再次登录已有用户** ➜ 需输入密码验证
- **同一用户不可同时登录多个客户端**

---

## 📎 注意事项

- 上传/下载文件保存在当前工作目录，文件命名为 `<threadtitle>-<filename>`
- 所有线程和消息记录均保存在以线程名命名的文件中
- 不支持中文路径或文件名（推荐使用英文）

---

## 🧠 项目灵感与价值

该项目是一个基于 **套接字编程 + 多线程并发处理** 的网络编程实践项目，结合了：

- **UDP 的高效但不可靠特性**
- **TCP 的稳定传输机制**
- **客户端身份验证**
- **自定义指令集协议解析**
- **服务端多线程模型**

---

```bash
Python 3.10+ 推荐
```

# UDP/TCP-Based Online Forum Application

This project implements an **online forum system** based on a **custom application protocol** using both **UDP and TCP**. Unlike traditional HTTP-based forums, this system communicates over a client-server architecture where:

- **UDP** is used for most forum operations (e.g., authentication, creating and editing threads and messages)
- **TCP** is used exclusively for **file uploads and downloads**

---

## 📁 Project Structure

```
.
├── client.py           # Client application (UDP + TCP communication)
├── server.py           # Multithreaded server (handles both UDP and TCP)
├── credentials.txt     # Stores registered usernames and passwords
├── test.exe            # Example binary file for upload/download
```

---

## 🚀 Getting Started

### 1️⃣ Start the Server

```bash
python server.py <server_port>
```

- Listens on both **UDP and TCP** at the same port
- Supports multiple concurrent clients using threads

### 2️⃣ Start the Client

```bash
python client.py <server_port>
```

- Connects to `127.0.0.1:<server_port>`
- New usernames are registered automatically on first login

---

## ✅ Supported Commands (Client)

| Command | Description |
|---------|-------------|
| `CRT <threadtitle>` | Create a new thread |
| `MSG <threadtitle> <message>` | Post a message in a thread |
| `DLT <threadtitle> <messagenumber>` | Delete a message (must be author) |
| `EDT <threadtitle> <messagenumber> <message>` | Edit a message (must be author) |
| `LST` | List all thread titles |
| `RDT <threadtitle>` | Read all messages in a thread |
| `UPD <threadtitle> <filename>` | Upload file to a thread (**TCP**) |
| `DWN <threadtitle> <filename>` | Download file from a thread (**TCP**) |
| `RMV <threadtitle>` | Remove thread (only by creator) |
| `XIT` | Exit and logout |

---

## ⚙️ Technical Features

- UDP with **retry mechanism** for robust command handling
- TCP used for **reliable file transfer**
- Multithreaded server (`threading.Thread`) for concurrent client processing
- Credential management stored in `credentials.txt`
- File and thread data stored as plain text for persistence

---

## 🧪 Sample Usage

### Start server:

```bash
python server.py 12345
```

### Start client:

```bash
python client.py 12345
```

On first login:

```text
Enter username: alice
Set a password for new user: 123456
```

Then try:

```text
> CRT topic1
> MSG topic1 Hello, this is Alice!
> UPD topic1 test.exe
```

---

## 🔐 Authentication Rules

- New usernames are automatically registered on first login
- Existing usernames require password verification
- The same user **cannot login from multiple clients simultaneously**

---

## 📌 Notes

- Uploaded files are stored as `<threadtitle>-<filename>`
- Each thread is saved as a text file named after the thread title
- Only ASCII filenames and thread titles are recommended (no Unicode)

---

## 🎓 Educational Value

This project demonstrates practical implementation of:

- **UDP (unreliable datagram protocol)** + timeout/retry logic
- **TCP file transfer**
- **Thread-based server concurrency**
- **Simple text-based command protocol**
- **User authentication + persistent state**

---

```bash
Recommended: Python 3.10+
```

