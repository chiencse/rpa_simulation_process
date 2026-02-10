#!/usr/bin/env python3
"""
Robot JSON Runner with Parallel Support

A single command to run Robot Framework JSON files that may contain PARALLEL blocks.
Automatically transforms PARALLEL blocks into Run Parallel keyword calls.

Usage:
    python run_robot_json.py test_parallel.json [robot options...]

Examples:
    python run_robot_json.py test.json
    python run_robot_json.py test.json --listener probe_listener.ProbeListener
    python run_robot_json.py test.json --output NONE --log NONE
"""

import json
import sys
import os
import subprocess
import tempfile
import time
from typing import Dict, List, Any


def has_parallel_blocks(data: Dict) -> bool:
    """Check if JSON contains any PARALLEL blocks."""
    
    def check_body(body: List) -> bool:
        for item in body:
            if item.get("type") == "PARALLEL":
                return True
        return False
    
    for test in data.get("tests", []):
        if check_body(test.get("body", [])):
            return True
    
    return False


def transform_json(input_data: Dict, listener: str = "") -> Dict:
    """Transform JSON with PARALLEL blocks to Robot Framework compatible format."""
    
    suite_name = input_data.get("name", "Main") or "Main"
    
    # Process resource section
    resource = input_data.get("resource", {})
    imports = list(resource.get("imports", []))  # Make a copy
    variables = resource.get("variables", [])
    
    # Filter out invalid variables (like "${}")
    valid_variables = [v for v in variables if v.get("name") and v.get("name") != "${}"]
    
    # Replace RPA.Cloud.Google with local RPA.Google if present
    for imp in imports:
        if imp.get("name") == "RPA.Cloud.Google":
            imp["name"] = "RPA.Google"
    
    # Only add RPA.Parallel library (required for Run Parallel keyword)
    # Other libraries should be defined in the input JSON
    library_names = [imp.get("name") for imp in imports]
    
    if "RPA.Parallel" not in library_names:
        imports.append({"type": "LIBRARY", "name": "RPA.Parallel"})
    
    # Build resource
    suite_resource = {"imports": imports}
    if valid_variables:
        suite_resource["variables"] = valid_variables
    
    tests = []
    
    for test_data in input_data.get("tests", []):
        test_name = test_data.get("name", "Main")
        body = test_data.get("body", [])
        
        # Transform body with listener and imports
        transformed_body = transform_body(body, valid_variables, listener, imports)
        
        tests.append({
            "name": test_name,
            "body": transformed_body
        })
    
    # Use flat structure - name and tests at root, no nested suites
    return {
        "name": suite_name,
        "tests": tests,
        "resource": suite_resource
    }


def transform_body(body: List[Dict], variables: List[Dict], listener: str = "", imports: List[Dict] = None) -> List[Dict]:
    """Transform body items, converting PARALLEL blocks to Run Parallel calls."""
    
    transformed = []
    
    for item in body:
        if item.get("type") == "PARALLEL":
            # Convert PARALLEL block to Run Parallel keyword call
            parallel_keyword = create_run_parallel_keyword(item, variables, listener, imports)
            transformed.append(parallel_keyword)
        else:
            # Regular keyword
            transformed.append({
                "type": "keyword",
                "name": item.get("name", ""),
                "args": item.get("args", [])
            })
    
    return transformed


def create_run_parallel_keyword(parallel_block: Dict, variables: List[Dict], listener: str = "", imports: List[Dict] = None) -> Dict:
    """Create a Run Parallel keyword call from a PARALLEL block."""
    
    branches = parallel_block.get("branches", [])
    
    # Build branches JSON
    branches_data = []
    for i, branch in enumerate(branches):
        branch_data = {
            "name": f"Branch_{i+1}",
            "body": branch.get("body", [])
        }
        branches_data.append(branch_data)
    
    # Build variables JSON
    vars_data = {}
    for var in variables:
        var_name = var.get("name", "")
        var_value = var.get("value", [])
        if var_name:
            if not var_value:
                # Handle empty value
                vars_data[var_name] = []
            else:
                vars_data[var_name] = var_value[0] if len(var_value) == 1 else var_value
    
    # Serialize as JSON strings and ESCAPE Robot variable syntax
    # This prevents Robot from resolving variables in the main suite
    # before passing them to the Run Parallel keyword.
    branches_json = json.dumps(branches_data, ensure_ascii=False).replace("${", "\\${").replace("@{", "\\@{").replace("&{", "\\&{")
    variables_json = json.dumps(vars_data, ensure_ascii=False).replace("${", "\\${").replace("@{", "\\@{").replace("&{", "\\&{")
    imports_json = json.dumps(imports or [], ensure_ascii=False).replace("${", "\\${").replace("@{", "\\@{").replace("&{", "\\&{")
    
    return {
        "type": "keyword",
        "name": "Run Parallel",
        "args": [branches_json, variables_json, listener, imports_json]
    }


def run_robot(json_file: str, robot_args: List[str]) -> int:
    """Run Robot Framework with the given JSON file."""
    
    # Read input JSON
    with open(json_file, "r", encoding="utf-8") as f:
        input_data = json.load(f)
    
    # Extract listener from robot_args if present
    listener = ""
    for i, arg in enumerate(robot_args):
        if arg == "--listener" and i + 1 < len(robot_args):
            listener = robot_args[i + 1]
            break
    
    # Check if transformation is needed
    if has_parallel_blocks(input_data):
        print("[*] Detected PARALLEL blocks, transforming...")
        if listener:
            print(f"    Listener: {listener}")
        transformed_data = transform_json(input_data, listener)
        
        # Create temp file
        temp_file = tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".json",
            delete=False,
            encoding="utf-8"
        )
        json.dump(transformed_data, temp_file, indent=2, ensure_ascii=False)
        temp_file.close()
        
        target_file = temp_file.name
        cleanup_file = True
        print(f"   Temp file: {target_file}")
    else:
        print("[*] No PARALLEL blocks found, running directly...")
        target_file = json_file
        cleanup_file = False
    
    # Build robot command
    cmd = ["python3", "-m", "robot"] + robot_args + [target_file]
    
    # Set PYTHONPATH and ROBOT_LISTENER for parallel branches
    env = os.environ.copy()
    cwd = os.path.dirname(os.path.abspath(json_file)) or os.getcwd()
    env["PYTHONPATH"] = cwd
    if listener:
        env["ROBOT_LISTENER"] = listener
    
    print(f"[>] Running: python3 -m robot {' '.join(robot_args)} {os.path.basename(target_file)}")
    print(f"   Working dir: {cwd}")
    print()
    
    try:
        result = subprocess.run(cmd, cwd=cwd, env=env)
        return result.returncode
    finally:
        # Cleanup temp file
        if cleanup_file and os.path.exists(target_file):
            os.remove(target_file)
            print("\n[*] Cleaned up temp file")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        print("\nAvailable options (passed to robot):")
        print("  --listener NAME    Add listener (e.g. probe_listener.ProbeListener)")
        print("  --output FILE      Output file (use NONE to disable)")
        print("  --log FILE         Log file (use NONE to disable)")
        print("  --report FILE      Report file (use NONE to disable)")
        sys.exit(1)
    
    json_file = sys.argv[1]
    robot_args = sys.argv[2:]
    
    if not os.path.exists(json_file):
        print(f"[ERROR] File not found: {json_file}")
        sys.exit(1)
    
    print(f"{'='*60}")
    print(f"Robot JSON Runner with Parallel Support")
    print(f"{'='*60}")
    print(f"Input: {json_file}")
    
    exit_code = run_robot(json_file, robot_args)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
