# Báo cáo U1: Kiểm tra môi trường máy

## 1. Mục tiêu
- Kiểm tra các công cụ môi trường cần thiết trên máy phục vụ dự án ABEST WMS ở chế độ chỉ đọc:
  - `git --version`
  - `docker --version` và `docker info`
  - `python --version` (yêu cầu từ 3.11 trở lên)
  - `gh --version`
  - `gh auth status`
- Đánh giá trạng thái sẵn sàng của môi trường theo từng công cụ.

## 2. Đã làm
- Chạy lại các lệnh kiểm tra phiên bản và trạng thái của Git, Docker, Python, GitHub CLI (`gh`) sau khi người dùng bật Docker Desktop và cài đặt / đăng nhập GitHub CLI.
- Xác nhận các thông tin trả về từ terminal thực tế.
- Lập bảng tổng hợp kết quả đánh giá trạng thái ĐẠT / KHÔNG ĐẠT.

## 3. Lệnh đã chạy và kết quả thật

### 3.1. Lệnh: `git --version`
- **Kết quả thật:**
  ```text
  git version 2.51.2.windows.1
  ```
- **Đánh giá:** ĐẠT.

### 3.2. Lệnh: `docker --version`
- **Kết quả thật:**
  ```text
  Docker version 29.4.3, build 055a478
  ```
- **Đánh giá:** ĐẠT.

### 3.3. Lệnh: `docker info`
- **Kết quả thật:**
  ```text
  Client:
   Version:    29.4.3
   Context:    desktop-linux
   Debug Mode: false
   Plugins:
    agent: Docker AI Agent Runner (Docker Inc.)
      Version:  v1.54.0
    ai: Docker AI Agent - Ask Gordon (Docker Inc.)
      Version:  v1.20.2
    buildx: Docker Buildx (Docker Inc.)
      Version:  v0.33.0-desktop.1
    compose: Docker Compose (Docker Inc.)
      Version:  v5.1.3
    debug: Get a shell into any image or container (Docker Inc.)
      Version:  0.0.47
    desktop: Docker Desktop commands (Docker Inc.)
      Version:  v0.3.0
    dhi: CLI for managing Docker Hardened Images (Docker Inc.)
      Version:  v0.0.3
    extension: Manages Docker extensions (Docker Inc.)
      Version:  v0.2.31
    init: Creates Docker-related starter files for your project (Docker Inc.)
      Version:  v1.4.0
    mcp: Docker MCP Plugin (Docker Inc.)
      Version:  v0.42.0
    model: Docker Model Runner (Docker Inc.)
      Version:  v1.1.37
    offload: Docker Offload (Docker Inc.)
      Version:  v0.5.85
    pass: Docker Pass Secrets Manager Plugin (beta) (Docker Inc.)
      Version:  v0.0.25
    sandbox: Docker Sandbox (Docker Inc.)
      Version:  v0.12.0
    sbom: View the packaged-based Software Bill Of Materials (SBOM) for an image (Anchore Inc.)
      Version:  0.6.0
    scout: Docker Scout (Docker Inc.)
      Version:  v1.20.4

  Server:
   Containers: 0
    Running: 0
    Paused: 0
    Stopped: 0
   Images: 1
   Server Version: 29.4.3
   Storage Driver: overlayfs
    driver-type: io.containerd.snapshotter.v1
   Logging Driver: json-file
   Cgroup Driver: cgroupfs
   Cgroup Version: 2
   Plugins:
    Volume: local
    Network: bridge host ipvlan macvlan null overlay
    Log: awslogs fluentd gcplogs gelf journald json-file local splunk syslog
   Kernel Version: 6.6.114.1-microsoft-standard-WSL2
   Operating System: Docker Desktop
   OSType: linux
   Architecture: x86_64
   CPUs: 12
   Total Memory: 7.628GiB
   Name: docker-desktop
  ```
- **Đánh giá:** ĐẠT (Docker Desktop daemon đã chạy, kết nối thành công).

### 3.4. Lệnh: `python --version`
- **Kết quả thật:**
  ```text
  Python 3.12.8
  ```
- **Đánh giá:** ĐẠT (3.12.8 >= 3.11).

### 3.5. Lệnh: `gh --version`
- **Kết quả thật:**
  ```text
  gh version 2.104.0 (2026-11-12)
  https://github.com/cli/cli/releases/tag/v2.104.0
  ```
- **Đánh giá:** ĐẠT.

### 3.6. Lệnh: `gh auth status`
- **Kết quả thật:**
  ```text
  github.com
    ✓ Logged in to github.com account binhdoan0201 (keyring)
    - Active account: true
    - Git operations protocol: https
    - Token: gho_************************************
    - Token scopes: 'gist', 'read:org', 'repo', 'workflow'
  ```
- **Đánh giá:** ĐẠT (Tài khoản binhdoan0201 đã đăng nhập thành công).

---

## 4. Bảng tổng hợp công cụ

| Công cụ | Phiên bản / Trạng thái | Yêu cầu | Kết luận |
| :--- | :--- | :--- | :--- |
| **Git** | `2.51.2.windows.1` | Có sẵn trong hệ thống | **ĐẠT** |
| **Docker (Client)** | `29.4.3` | Có sẵn trong hệ thống | **ĐẠT** |
| **Docker (Daemon / Server)** | Server Version `29.4.3` (Docker Desktop đang chạy) | Docker daemon phải đang chạy | **ĐẠT** |
| **Python** | `3.12.8` | >= 3.11 | **ĐẠT** |
| **GitHub CLI (`gh`)** | `2.104.0` | Đã cài đặt | **ĐẠT** |
| **GitHub Auth Status** | Đã đăng nhập tài khoản `binhdoan0201` | Đã đăng nhập (`gh auth login`) | **ĐẠT** |

---

## 5. Kết luận
- **Kết luận:** **ĐẠT**.
- Tất cả các yêu cầu kiểm tra môi trường máy ở U1 đều đã thỏa mãn.

---

## 6. Việc tôi cần làm tiếp
- Chuyển sang thực hiện **U2. Ghi nhận quyết định công nghệ**:
  - Đọc tài liệu công nghệ tại `./_inbox/` (mục 1: Công nghệ chốt).
  - Tạo `docs/adr/0001-cong-nghe.md`.
  - Xuất báo cáo `docs/reports/u2-tech-decision.md`.
