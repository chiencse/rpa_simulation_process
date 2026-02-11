"""
RPA Simulate Process - FastAPI Server
======================================

Nhận request run-simulate từ Frontend và thực thi Robot Framework.
"""
import os
import uuid
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn

from robot_executor import RobotExecutor

# ===== Configuration =====
PROBE_WS_URL = os.environ.get("PROBE_WS_URL", "http://172.21.112.1:8080")

# ===== Initialize =====
# Workspace defaults to project directory (where robot_executor.py is located)
executor = RobotExecutor(ws_url=PROBE_WS_URL)

# ===== FastAPI App =====
app = FastAPI(
    title="RPA Simulate Process API",
    description="API để nhận request simulate và thực thi Robot Framework",
    version="1.0.0"
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ===== Pydantic Models =====
class RunSimulateRequest(BaseModel):
    user_id: str
    process_id: str
    version: int
    trigger_type: str = "manual"
    robot_code: str  # Robot Framework code (JSON format)
    is_simulate: Optional[bool] = False
    run_type: Optional[str] = "run-all"  # "run-all" | "step-by-step"
    connection_keys: Optional[list[str]] = []


class RunSimulateResponse(BaseModel):
    success: bool
    message: str
    execution_id: str
    process_id: str
    robot_file: str


# ===== API Endpoints =====
@app.get("/")
async def root():
    return {
        "service": "RPA Simulate Process",
        "version": "1.0.0",
        "status": "running"
    }


@app.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}


@app.post("/robot/simulate", response_model=RunSimulateResponse)
async def run_simulate(request: RunSimulateRequest, background_tasks: BackgroundTasks):
    """
    Nhận request run-simulate từ Frontend
    
    - Tạo file robot JSON theo process_id
    - Chạy robot command với listener
    - WebSocket kết nối qua probe_listener.py
    """
    try:
        print(f"\n{'='*60}")
        print(f"[DEBUG] /robot/simulate - Received request")
        print(f"[DEBUG] user_id: {request.user_id}")
        print(f"[DEBUG] process_id: {request.process_id}")
        print(f"[DEBUG] version: {request.version}")
        print(f"[DEBUG] run_type: {request.run_type}")
        print(f"[DEBUG] is_simulate: {request.is_simulate}")
        print(f"[DEBUG] robot_code length: {len(request.robot_code)} chars")
        print(f"[DEBUG] connection_keys: {request.connection_keys}")
        
        execution_id = str(uuid.uuid4())
        print(f"[DEBUG] Generated execution_id: {execution_id}")
        
        # Kiểm tra và terminate process cũ nếu đang chạy
        if request.process_id in executor.running_processes:
            print(f"[DEBUG] Found existing process for {request.process_id}, stopping...")
            executor.stop_robot(request.process_id)
            print(f"[DEBUG] Existing process stopped")
        
        # Tạo robot file
        print(f"[DEBUG] Creating robot file...")
        robot_file = executor.create_robot_file(request.process_id, request.robot_code)
        print(f"[DEBUG] Robot file created: {robot_file}")
        
        # Xác định step mode
        step_mode = "step" if request.run_type == "step-by-step" else "all"
        print(f"[DEBUG] Step mode: {step_mode}")
        
        # Chạy robot trong background
        print(f"[DEBUG] Adding robot execution to background tasks...")
        background_tasks.add_task(
            executor.run_robot_async,
            robot_file,
            request.process_id,
            step_mode,
            execution_id,
            connection_keys=request.connection_keys
        )
        print(f"[DEBUG] Background task added successfully")
        print(f"{'='*60}\n")
        
        return RunSimulateResponse(
            success=True,
            message=f"Robot execution started in {request.run_type} mode",
            execution_id=execution_id,
            process_id=request.process_id,
            robot_file=robot_file
        )
        
    except Exception as e:
        print(f"[ERROR] /robot/simulate failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/robot/status/{process_id}")
async def get_robot_status(process_id: str):
    """
    Lấy trạng thái của robot process
    """
    status = executor.get_status(process_id)
    
    if status is None:
        return {
            "process_id": process_id,
            "status": "not_running",
            "message": "No active process for this process_id"
        }
    
    return status


@app.post("/robot/stop/{process_id}")
async def stop_robot(process_id: str):
    """
    Dừng robot process đang chạy
    """
    print(f"\n[DEBUG] /robot/stop/{process_id} - Received request")
    
    status = executor.get_status(process_id)
    
    if status is None:
        print(f"[DEBUG] Process {process_id} not found in running_processes")
        print(f"[DEBUG] Current running processes: {list(executor.running_processes.keys())}")
        # Return success anyway - process may have already finished
        return {
            "success": True,
            "message": f"Process {process_id} is not running (may have already finished)",
            "process_id": process_id
        }
    
    print(f"[DEBUG] Found process {process_id}, stopping...")
    success = executor.stop_robot(process_id)
    
    if success:
        print(f"[DEBUG] Process {process_id} stopped successfully")
        return {
            "success": True,
            "message": f"Process {process_id} terminated",
            "execution_id": status["execution_id"]
        }
    else:
        print(f"[ERROR] Failed to stop process {process_id}")
        raise HTTPException(status_code=500, detail="Failed to stop process")


@app.get("/robot/list")
async def list_running_robots():
    """
    Liệt kê tất cả robot processes đang chạy
    """
    processes = executor.list_running()
    return {"processes": processes, "total": len(processes)}


# ===== Main Entry Point =====
if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8001,
        reload=True
    )

