#!/usr/bin/env python3
"""SMF Swarm — Hardware environment logger for reproducibility.

Records CPU, RAM, GPU, OS, Python version, and installed package versions
to a JSON file so benchmark runs can be exactly reproduced.
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


def cpu_info() -> dict:
    info = {
        "processor": platform.processor() or "",
        "machine": platform.machine(),
        "arch": platform.architecture()[0],
        "cpu_count": os.cpu_count(),
    }
    try:
        if sys.platform.startswith("linux"):
            with open("/proc/cpuinfo", encoding="utf-8") as f:
                for line in f:
                    if line.lower().startswith("model name"):
                        info["model_name"] = line.split(":", 1)[1].strip()
                        break
    except Exception:
        pass
    return info


def mem_info() -> dict:
    try:
        if sys.platform.startswith("linux"):
            with open("/proc/meminfo", encoding="utf-8") as f:
                memlines = f.read().splitlines()
            memtotal = [l for l in memlines if l.startswith("MemTotal")]
            if memtotal:
                kb = int(memtotal[0].split()[1])
                return {"total_gb": round(kb / 1024 / 1024, 2)}
        elif sys.platform == "darwin":
            out = subprocess.check_output(["sysctl", "-n", "hw.memsize"], text=True)
            b = int(out.strip())
            return {"total_gb": round(b / (1024 ** 3), 2)}
    except Exception:
        pass
    return {}


def gpu_info() -> list[dict]:
    gpus = []
    try:
        out = subprocess.check_output(
            ["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader"],
            text=True,
            stderr=subprocess.DEVNULL,
            timeout=10,
        )
        for line in out.strip().splitlines():
            parts = [p.strip() for p in line.split(",")]
            if len(parts) >= 2:
                gpus.append({"name": parts[0], "memory_str": parts[1]})
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
        json.dump(data, f, indent=2)

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
