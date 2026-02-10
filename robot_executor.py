"""
Robot Executor
==============

Module thực thi Robot Framework với listener.
"""
import os
import subprocess
import asyncio
from datetime import datetime
from typing import Dict, Any, Optional
from pathlib import Path

# Get project directory
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))


class RobotExecutor:
    """Quản lý việc thực thi Robot Framework"""
    
    def __init__(
        self,
        workspace: str = None,  # Default to project directory
        ws_url: str = "http://54.252.181.103:8080"
    ):
        # Use project directory as default workspace
        self.workspace = workspace if workspace else PROJECT_DIR
        self.ws_url = ws_url
        self.running_processes: Dict[str, Dict[str, Any]] = {}
        
        print(f"[EXECUTOR] Initialized with workspace: {self.workspace}")
        
        # Ensure workspace exists
        Path(self.workspace).mkdir(parents=True, exist_ok=True)
    
    def create_robot_file(self, process_id: str, robot_code: str) -> str:
        """
        Tạo file robot từ robot_code.
        
        Args:
            process_id: Process ID
            robot_code: Robot code content (JSON or .robot format)
        
        Returns:
            Path đến robot file
        """
        import json
        
        robot_file_path = os.path.join(self.workspace, f"robot_{process_id}.json")
        
        try:
            # Parse nếu là JSON string
            if isinstance(robot_code, str):
                robot_data = json.loads(robot_code)
                with open(robot_file_path, 'w', encoding='utf-8') as f:
                    json.dump(robot_data, f, ensure_ascii=False, indent=2)
            else:
                with open(robot_file_path, 'w', encoding='utf-8') as f:
                    json.dump(robot_code, f, ensure_ascii=False, indent=2)
        except json.JSONDecodeError:
            # Nếu không phải JSON, write as text
            with open(robot_file_path, 'w', encoding='utf-8') as f:
                f.write(robot_code)
        
        return robot_file_path
    
    def run_robot(
        self,
        robot_file: str,
        process_id: str,
        step_mode: str = "all",
        execution_id: str = None
    ) -> int:
        """
        Chạy Robot Framework với listener.
        
        Args:
            robot_file: Path đến robot file
            process_id: Process ID
            step_mode: "all" hoặc "step"
            execution_id: Execution ID
        
        Returns:
            Return code của process
        """
        print(f"\n[EXECUTOR] Starting robot execution...")
        print(f"[EXECUTOR] execution_id: {execution_id}")
        print(f"[EXECUTOR] process_id: {process_id}")
        print(f"[EXECUTOR] robot_file: {robot_file}")
        print(f"[EXECUTOR] step_mode: {step_mode}")
        print(f"[EXECUTOR] ws_url: {self.ws_url}")
        
        # Get project directory (where probe_listener.py is located)
        project_dir = os.path.dirname(os.path.abspath(__file__))
        print(f"[EXECUTOR] project_dir: {project_dir}")
        
        # Environment variables cho listener
        env = os.environ.copy()
        env["PROBE_WS_URL"] = self.ws_url
        env["STEP_MODE"] = step_mode
        env["PROCESS_ID"] = process_id
        
        # Add project directory to PYTHONPATH so robot can find probe_listener
        existing_pythonpath = env.get("PYTHONPATH", "")
        env["PYTHONPATH"] = f"{project_dir}:{existing_pythonpath}" if existing_pythonpath else project_dir
        print(f"[EXECUTOR] PYTHONPATH: {env['PYTHONPATH']}")
        
        # Robot command
        cmd = [
            "rpa-runner",
            robot_file,
            f"--listener={step_mode}"
        ]
        
        print(f"[EXECUTOR] Command: {' '.join(cmd)}")
        print(f"[EXECUTOR] Starting subprocess...")
        
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            env=env,
            cwd=self.workspace,
            text=True
        )
        
        print(f"[EXECUTOR] Process started with PID: {process.pid}")
        
        # Track process
        self.running_processes[process_id] = {
            "execution_id": execution_id,
            "process": process,
            "pid": process.pid,
            "started_at": datetime.utcnow().isoformat(),
            "robot_file": robot_file,
            "step_mode": step_mode
        }
        
        # Stream output in real-time
        print(f"[EXECUTOR] --- Robot Output Start ---")
        for line in process.stdout:
            print(f"[ROBOT] {line.rstrip()}")
        
        # Wait for completion
        return_code = process.wait()
        print(f"[EXECUTOR] --- Robot Output End ---")
        print(f"[EXECUTOR] Process finished with return code: {return_code}")
        
        # Remove from tracking
        if process_id in self.running_processes:
            del self.running_processes[process_id]
        
        return return_code
    
    async def run_robot_async(
        self,
        robot_file: str,
        process_id: str,
        step_mode: str,
        execution_id: str
    ) -> int:
        """
        Async wrapper để chạy robot.
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            self.run_robot,
            robot_file,
            process_id,
            step_mode,
            execution_id
        )
    
    def stop_robot(self, process_id: str) -> bool:
        """
        Dừng robot process đang chạy.
        
        Args:
            process_id: Process ID
        
        Returns:
            True nếu dừng thành công
        """
        if process_id not in self.running_processes:
            return False
        
        proc_info = self.running_processes[process_id]
        process = proc_info["process"]
        
        try:
            process.terminate()
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
        
        if process_id in self.running_processes:
            del self.running_processes[process_id]
        
        return True
    
    def get_status(self, process_id: str) -> Optional[Dict[str, Any]]:
        """
        Lấy trạng thái của robot process.
        
        Args:
            process_id: Process ID
        
        Returns:
            Dict thông tin process hoặc None
        """
        if process_id not in self.running_processes:
            return None
        
        proc_info = self.running_processes[process_id]
        process = proc_info["process"]
        poll_result = process.poll()
        
        if poll_result is None:
            status = "running"
        elif poll_result == 0:
            status = "completed"
        else:
            status = "failed"
        
        return {
            "process_id": process_id,
            "execution_id": proc_info["execution_id"],
            "status": status,
            "pid": proc_info["pid"],
            "started_at": proc_info["started_at"],
            "step_mode": proc_info["step_mode"],
            "return_code": poll_result
        }
    
    def list_running(self) -> list:
        """
        Liệt kê tất cả processes đang chạy.
        """
        result = []
        for process_id in list(self.running_processes.keys()):
            status = self.get_status(process_id)
            if status:
                result.append(status)
        return result
