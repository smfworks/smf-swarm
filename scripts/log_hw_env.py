#!/usr/bin/env python3
"""SMF Swarm — Hardware environment logger for reproducibility.

Records CPU, RAM, GPU, OS, Python version, and installed package versions
to a JSON file so benchmark runs can be exactly reproduced.

Cross-platform: Linux, macOS, Windows.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


def _run_cmd(*cmd: str, timeout: float = 5) -> str:
    """Run a shell command and return stdout as string, or empty on failure."""
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout,
        )
        if result.returncode == 0:
            return result.stdout
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return ""


def _safe_json(data: Any) -> Any:
    """Strip non-serializable objects to keep JSON valid."""
    try:
        json.dumps(data)
        return data
    except (TypeError, ValueError):
        return str(data)


def cpu_info() -> dict:
    info = {
        "processor": platform.processor() or "",
        "machine": platform.machine(),
        "arch": platform.architecture()[0],
        "cpu_count": os.cpu_count(),
    }
    # Linux /proc/cpuinfo
    if sys.platform.startswith("linux"):
        try:
            with open("/proc/cpuinfo", encoding="utf-8") as f:
                for line in f:
                    if line.lower().startswith("model name"):
                        info["model_name"] = line.split(":", 1)[1].strip()
                        break
        except Exception:
            pass
    # macOS sysctl
    elif sys.platform == "darwin":
        try:
            out = _run_cmd("sysctl", "-n", "machdep.cpu.brand_string").strip()
            if out:
                info["model_name"] = out
        except Exception:
            pass
    # Windows wmic
    elif sys.platform == "win32":
        try:
            out = _run_cmd("wmic", "cpu", "get", "Name", "/value")
            match = out.split("Name=")[-1].split("\n")[0].strip() if "Name=" in out else ""
            if match:
                info["model_name"] = match
        except Exception:
            pass
    return info


def mem_info() -> dict:
    # Prefer psutil
    try:
        import psutil
        vm = psutil.virtual_memory()
        return {"total_gb": round(vm.total / (1024 ** 3), 2),
                "available_gb": round(vm.available / (1024 ** 3), 2)}
    except Exception:
        pass

    # Linux
    if sys.platform.startswith("linux"):
        try:
            with open("/proc/meminfo", encoding="utf-8") as f:
                memlines = f.read().splitlines()
            memtotal = [l for l in memlines if l.startswith("MemTotal")]
            if memtotal:
                kb = int(memtotal[0].split()[1])
                return {"total_gb": round(kb / 1024 / 1024, 2)}
        except Exception:
            pass
    # macOS
    elif sys.platform == "darwin":
        try:
            out = subprocess.check_output(["sysctl", "-n", "hw.memsize"], text=True)
            b = int(out.strip())
            return {"total_gb": round(b / (1024 ** 3), 2)}
        except Exception:
            pass
    # Windows
    elif sys.platform == "win32":
        try:
            import ctypes
            kernel32 = ctypes.windll.kernel32
            class MEMORYSTATUSEX(ctypes.Structure):
                _fields_ = [
                    ("dwLength", ctypes.c_ulong),
                    ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong),
                    ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong),
                    ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong),
                    ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
                ]
            mem = MEMORYSTATUSEX()
            mem.dwLength = ctypes.sizeof(mem)
            kernel32.GlobalMemoryStatusEx(ctypes.byref(mem))
            return {"total_gb": round(mem.ullTotalPhys / (1024 ** 3), 2),
                    "available_gb": round(mem.ullAvailPhys / (1024 ** 3), 2)}
        except Exception:
            pass
    return {}


def gpu_info() -> list[dict]:
    gpus = []
    # NVIDIA (all platforms)
    try:
        out = subprocess.check_output(
            ["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader"],
            text=True, stderr=subprocess.DEVNULL, timeout=10,
        )
        for line in out.strip().splitlines():
            parts = [p.strip() for p in line.split(",")]
            if len(parts) >= 2:
                gpus.append({"name": parts[0], "memory_str": parts[1]})
    except Exception:
        pass

    # Windows wmic fallback
    if not gpus and sys.platform == "win32":
        try:
            out = _run_cmd(
                "wmic", "path", "Win32_VideoController",
                "get", "Name,AdapterRAM", "/value"
            )
            names = [l.split("Name=")[-1].strip() for l in out.split("\n") if l.startswith("Name=")]
            rams = [l.split("AdapterRAM=")[-1].strip() for l in out.split("\n") if l.startswith("AdapterRAM=")]
            for n, r in zip(names, rams):
                try:
                    b = int(r)
                    if b < 0:
                        b += 2 ** 32
                    gpus.append({"name": n, "memory_str": f"{round(b / (1024**3), 2)} GB"})
                except ValueError:
                    gpus.append({"name": n, "memory_str": r})
        except Exception:
            pass
    return gpus


def python_env() -> dict:
    env = {
        "version": sys.version,
        "executable": sys.executable,
        "version_info": list(sys.version_info),
    }
    try:
        import pkg_resources
        env["packages"] = {d.project_name: d.version for d in pkg_resources.working_set}
    except Exception:
        env["packages"] = {}
    return env


def gather() -> dict:
    return {
        "timestamp": datetime.now().isoformat(),
        "os": {
            "system": platform.system(),
            "release": platform.release(),
            "version": platform.version(),
            "node": platform.node(),
        },
        "cpu": cpu_info(),
        "memory": mem_info(),
        "gpu": gpu_info(),
        "python": python_env(),
    }


def main():
    parser = argparse.ArgumentParser(description="Log hardware environment for SMF Swarm benchmarks")
    parser.add_argument("--outfile", default="benchmark_hw_env.json", help="Output JSON file")
    args = parser.parse_args()

    print("Gathering hardware environment...")
    data = gather()

    with open(args.outfile, "w", encoding="utf-8") as f:
        json.dump(_safe_json(data), f, indent=2)

    print(f"Wrote environment to {args.outfile}")
    print(f"  CPU: {data['cpu'].get('model_name', data['cpu'].get('processor', 'unknown'))}")
    print(f"  RAM: {data['memory'].get('total_gb', 'unknown')} GB")
    print(f"  GPU: {len(data['gpu'])} found")
    if data["gpu"]:
        for g in data["gpu"]:
            print(f"    - {g['name']}")
    print(f"  Python: {sys.version.split()[0]}")


if __name__ == "__main__":
    main()
