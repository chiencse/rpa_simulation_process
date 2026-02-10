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
        
        # Prepare local devdata path for replacement
        # Normalize to forward slashes for JSON string compatibility if needed, 
        # but Windows accepts forward slashes in python mostly. 
        # Robot Framework might need escaped backslashes in JSON string.
        local_devdata = os.path.join(self.workspace, "devdata").replace("\\", "/")
        linux_path_prefix = "/home/ec2-user/robot/devdata/"
        
        try:
            # Helper to replace path in string
            def replace_path(text):
                return text.replace(linux_path_prefix, f"{local_devdata}/")

            # Parse nếu là JSON string
            if isinstance(robot_code, str):
                # Replace paths in the string directly before parsing
                # This covers "token_file=..." inside the JSON string
                robot_code_patched = replace_path(robot_code)
                try:
                    robot_data = json.loads(robot_code_patched)
                    with open(robot_file_path, 'w', encoding='utf-8') as f:
                        json.dump(robot_data, f, ensure_ascii=False, indent=2)
                except json.JSONDecodeError:
                    # Not JSON, write as text (patched)
                    with open(robot_file_path, 'w', encoding='utf-8') as f:
                        f.write(robot_code_patched)
            else:
                # If it's already a dict/list object
                # We should dump to string, patch, then parse back or just write
                json_str = json.dumps(robot_code, ensure_ascii=False)
                json_str_patched = replace_path(json_str)
                robot_data = json.loads(json_str_patched)
                
                with open(robot_file_path, 'w', encoding='utf-8') as f:
                    json.dump(robot_data, f, ensure_ascii=False, indent=2)
                    
        except Exception as e:
            print(f"[EXECUTOR] Error creating robot file: {e}")
            # Fallback to original write if something breaks
            if isinstance(robot_code, str):
                with open(robot_file_path, 'w', encoding='utf-8') as f:
                    f.write(robot_code)
            else:
                with open(robot_file_path, 'w', encoding='utf-8') as f:
                    json.dump(robot_code, f, ensure_ascii=False, indent=2)
        
        return robot_file_path
    
    
    def setup_connections(
        self,
        connection_keys: list[str]
    ):
        """
        Fetch connection credentials from BE and save to files in devdata folder.
        
        Args:
            connection_keys: List of connection keys
        """
        import json
        import requests
        
        if not connection_keys:
            print("[EXECUTOR] No connection keys provided. Skipping credential fetch.")
            return

        print(f"[EXECUTOR] Fetching credentials for keys: {connection_keys}")
        
        try:
            # Use ws_url as base url (remove trailing slash if any)
            base_url = self.ws_url.rstrip('/')
            url = f"{base_url}/connection/for-simulation"
            
            # Header
            headers = {
                "Service-Key": "e238e535-decb-4e18-9ef2-5094cf4b9a08",
                "Content-Type": "application/json"
            }
            
            # Body
            payload = {
                "connectionKeys": connection_keys
            }
            
            print(f"[EXECUTOR] Calling {url}")
            
            response = requests.get(url, json=payload, headers=headers, timeout=30)
            
            if response.status_code != 200:
                print(f"[EXECUTOR] Method GET failed. Status: {response.status_code}. Response: {response.text}")
                print(f"[EXECUTOR] Retrying with POST...")
                response = requests.post(url, json=payload, headers=headers, timeout=30)
            
            if response.status_code != 200:
                print(f"[EXECUTOR] Failed to fetch credentials. Status: {response.status_code}, Response: {response.text}")
                response.raise_for_status()
                
            connections_data = response.json()
            print(f"[EXECUTOR] Received {len(connections_data)} credential files")
            
            # Ensure devdata directory exists
            devdata_dir = os.path.join(self.workspace, "devdata")
            Path(devdata_dir).mkdir(parents=True, exist_ok=True)
            
            for item in connections_data:
                file_name = item.get("fileName")
                data = item.get("data")
                
                if file_name and data:
                    # Force save into devdata directory
                    # Only take basename to avoid directory traversal
                    safe_filename = os.path.basename(file_name)
                    file_path = os.path.join(devdata_dir, safe_filename)
                    
                    with open(file_path, 'w', encoding='utf-8') as f:
                        if isinstance(data, (dict, list)):
                            json.dump(data, f, ensure_ascii=False, indent=2)
                        else:
                            f.write(str(data))
                            
                    print(f"[EXECUTOR] Saved credential: devdata/{safe_filename}")
            
            print(f"[EXECUTOR] All credentials setup successfully")
            
        except Exception as e:
            print(f"[EXECUTOR] Error in setup_connections: {str(e)}")
            raise e
    
    
    def run_robot(
        self,
        robot_file: str,
        process_id: str,
        step_mode: str = "all",
        execution_id: str = None,
        connection_keys: list[str] = None
    ) -> int:
        """
        Chạy Robot Framework với listener.
        
        Args:
            robot_file: Path đến robot file
            process_id: Process ID
            step_mode: "all" hoặc "step"
            execution_id: Execution ID
            connection_keys: List of connection keys to fetch credentials for
        
        Returns:
            Return code của process
        """
        print(f"\n[EXECUTOR] Starting robot execution...")
        print(f"[EXECUTOR] execution_id: {execution_id}")
        print(f"[EXECUTOR] process_id: {process_id}")
        
        # Setup connections if keys are provided
        if connection_keys:
            try:
                self.setup_connections(connection_keys)
            except Exception as e:
                print(f"[EXECUTOR] WARNING: Failed to setup connections: {e}")
                pass
        
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
        execution_id: str,
        connection_keys: list[str] = None
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
            execution_id,
            connection_keys
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
