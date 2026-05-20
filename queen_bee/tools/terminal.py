def execute(command: str, timeout: int = 30, cwd: str = None) -> str:
    import subprocess, json
    try:
        r = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=timeout, cwd=cwd)
        return json.dumps({"stdout": r.stdout, "stderr": r.stderr, "exit_code": r.returncode, "success": r.returncode == 0})
    except subprocess.TimeoutExpired:
        return json.dumps({"stdout": "", "stderr": f"超时 ({timeout}s)", "exit_code": -1, "success": False})
    except Exception as e:
        return json.dumps({"stdout": "", "stderr": str(e), "exit_code": -1, "success": False})
