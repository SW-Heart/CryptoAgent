# 服务器服务查询速查表

您可以使用以下命令来全面排查服务器上正在运行的服务和资源占用情况。

### 1. 查看所有 Docker 容器
查看服务器上是否跑了其他项目的 Docker 容器（不仅仅是当前目录下的）：
```bash
sudo docker ps
```

### 2. 查看系统进程与资源占用 (最直观)
使用 `top` 命令查看是谁在吃 CPU 和 内存：
```bash
top
```
*   **按 `M` 键**：按 **内存** 占用排序（这是您最需要关注的，构建时容易 OOM）。
*   **按 `P` 键**：按 **CPU** 占用排序。
*   **按 `q` 键**：退出。
*(如果安装了 `htop`，界面会更友好)*

### 3. 查看端口占用情况
查看哪些服务正在监听端口（这能发现那些在后台默默运行的非 Docker 服务，比如 Nginx, MySQL 原生服务等）：
```bash
sudo netstat -tulnp
# 或者
sudo ss -tulnp
```

### 4. 检查已启动的系统服务
查看系统层面（Systemd）正在运行的服务：
```bash
systemctl list-units --type=service --state=running
```

### 5. 检查僵尸进程
查看系统中是否存在僵尸进程（状态为 Z）：
```bash
ps -A -o stat,ppid,pid,cmd | grep -e '^[Zz]'
```
*   **stat**: 状态（Z 代表僵尸）
*   **ppid**: 父进程ID（如果要杀僵尸，得杀父进程）
*   **pid**: 进程ID
*   **cmd**: 进程名

**建议**：在执行 `docker build` 之前，重点关注 `top` 里的内存（Res/Mem）剩余量。如果剩余内存少于 1GB，建议先停止大内存应用。
