# RPA Simulate Process

API server để nhận request simulate và thực thi Robot Framework với real-time tracking qua WebSocket.

## 🏗️ Architecture

```
┌─────────────┐     POST /robot/run      ┌──────────────────────┐
│   Frontend  │ ────────────────────────>│   FastAPI Server     │
│             │                          │   (main.py)          │
└─────────────┘                          └──────────┬───────────┘
       ▲                                            │
       │                                            │ Create robot.json
       │                                            │ Execute robot command
       │                                            ▼
       │                                 ┌──────────────────────┐
       │ WebSocket                       │   Robot Framework    │
       │ (robotEvent)                    │   + ProbeListener    │
       │                                 └──────────┬───────────┘
       │                                            │
       │                                            │ Socket.IO emit
       │          ┌──────────────────────┐          │
       └──────────│   WebSocket Server   │<─────────┘
                  │   (NestJS Backend)   │
                  └──────────────────────┘
```

## � Project Structure

```
rpa-simulate-process/
├── main.py                 # FastAPI server - API endpoints
├── robot_executor.py       # Robot Framework executor module
├── dependency_manager.py   # Dependency management module
├── probe_listener.py       # Robot Framework listener - Socket.IO
├── requirements.txt        # Python dependencies
├── Dockerfile              # Docker image
├── docker-compose.yml      # Docker Compose config
├── .env.example            # Environment variables template
└── README.md               # Documentation
```

## �📋 Features

- **FastAPI Server**: Nhận request chạy robot từ Frontend
- **Robot Framework Execution**: Thực thi robot code với listener
- **Real-time Tracking**: WebSocket events qua `probe_listener.py`
- **Step-by-Step Mode**: Chờ signal từ FE trước khi chạy step tiếp theo
- **Run-All Mode**: Chạy tất cả steps liên tục
- **Dependency Management**: Tự động cài đặt packages dựa trên robot code

## 🚀 Quick Start

### Ubuntu Setup

```bash
# Clone repository
git clone <repo_url>
cd rpa-simulate-process

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Start server
python main.py
```

### Docker Setup

```bash
# Build and run
docker-compose up -d

# Check logs
docker-compose logs -f
```

## 📖 API Endpoints

### `POST /robot/run`

Chạy robot simulation.

**Request Body:**
```json
{
  "user_id": "123",
  "process_id": "Process_F8fZ8GC",
  "version": 1,
  "trigger_type": "manual",
  "robot_code": "{...robot JSON...}",
  "is_simulate": true,
  "run_type": "step-by-step"
}
```

**Response:**
```json
{
  "success": true,
  "message": "Robot execution started in step-by-step mode",
  "execution_id": "uuid...",
  "process_id": "Process_F8fZ8GC",
  "robot_file": "/tmp/robot_workspace/robot_Process_F8fZ8GC.json"
}
```

### `GET /robot/status/{process_id}`

Lấy trạng thái của robot process.

### `POST /robot/stop/{process_id}`

Dừng robot process đang chạy.

### `GET /robot/list`

Liệt kê tất cả robot processes đang chạy.

### `POST /dependencies/install`

Cài đặt dependencies dựa trên robot code.

## 🔧 Configuration

| Environment Variable | Default | Description |
|---------------------|---------|-------------|
| `PROBE_WS_URL` | `http://54.252.181.103:8080` | WebSocket server URL |
| `ROBOT_WORKSPACE` | `/tmp/robot_workspace` | Directory for robot files |
| `LOG_DIR` | `/var/log/robot` | Directory for log files |

## 📦 Dependencies

### Core
- `robotframework>=6.1.1`
- `rpaframework`
- `python-socketio`

### Server
- `fastapi>=0.109.0`
- `uvicorn[standard]`

### Additional (auto-installed based on robot code)
```python
DEPENDENCY_MAP = {
    "RPA.Cloud.Google": "rpaframework-google",
    "RPA.Cloud.AWS": "rpaframework-aws",
    "EduRPA.Document": "edurpa-document",
    "EduRPA.Google": "edurpa-cloud",
    "EduRPA.Storage": "edurpa-cloud",
    "PDF": "rpaframework-pdf",
    "RPA.MOCK_SAP": "rpa-sap-mock-bk",
    "RPA.Moodle": "rpa-moodle",
    "RPA.ERPNext": "rpa-erpnext",
}
```

## 🔄 Run Modes

### Run-All Mode

Robot chạy tất cả steps liên tục không chờ.

```json
{
  "run_type": "run-all"
}
```

### Step-by-Step Mode

Robot chờ signal `continueStep` từ Frontend sau mỗi step.

```json
{
  "run_type": "step-by-step"
}
```

Frontend gửi signal qua WebSocket:
```javascript
socket.emit('continueStep', { processId: 'Process_F8fZ8GC' });
```

## 📝 Robot Execution Command

```bash
python3 -m robot \
    --listener probe_listener.ProbeListener \
    --output NONE \
    --log NONE \
    --report NONE \
    robot.json
```

## 🧪 Testing

```bash
# Health check
curl http://localhost:8000/health

# Run robot
curl -X POST http://localhost:8000/robot/run \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "1",
    "process_id": "test_process",
    "version": 1,
    "robot_code": "{}",
    "is_simulate": true,
    "run_type": "run-all"
  }'
```

## 📄 License

MIT License
