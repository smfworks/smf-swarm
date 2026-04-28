"""Hardware detection module.

Cross-platform RAM, GPU, and CPU detection with graceful fallbacks.
Zero heavy dependencies — prefers stdlib, falls back to psutil.
"""

from __future__ import annotations

import os
import re
import sys
import subprocess
from dataclasses import dataclass
from typing import Optional


def _try_import_psutil():
    try:
        import psutil
        return psutil
    except Exception:
        return None


@dataclass
class HardwareProfile:
    """Snapshot of available hardware."""
    total_ram_gb: float
    available_ram_gb: float
    cpu_cores: int
    cpu_threads: int
    vram_gb: Optional[float] = None
    gpu_name: Optional[str] = None
    os_name: str = ""
    os_version: str = ""

    @property
    def has_gpu(self) -> bool:
        return self.vram_gb is not None and self.vram_gb > 0


def detect_hardware() -> HardwareProfile:
    """Return hardware profile of the current machine."""
    return HardwareProfile(
        total_ram_gb=_detect_ram_total(),
        available_ram_gb=_detect_ram_available(),
        cpu_cores=_detect_cpu_cores(),
        cpu_threads=_detect_cpu_threads(),
        vram_gb=_detect_vram(),
        gpu_name=_detect_gpu_name(),
        os_name=_detect_os_name(),
        os_version=_detect_os_version(),
    )


# ── RAM ──────────────────────────────────────────

def _detect_ram_total() -> float:
    """Total system RAM in GB."""
    psutil = _try_import_psutil()
    if psutil:
        try:
            return psutil.virtual_memory().total / (1024 ** 3)
        except Exception:
            pass
    if sys.platform == "win32":
        return _win32_mem() or 8.0
    return _get_meminfo("MemTotal") or _sysctl_mem() or 8.0


def _detect_ram_available() -> float:
    """Currently available RAM in GB."""
    psutil = _try_import_psutil()
    if psutil:
        try:
            return psutil.virtual_memory().available / (1024 ** 3)
        except Exception:
            pass
    if sys.platform == "win32":
        return _win32_mem() or (_detect_ram_total() * 0.5)
    return _get_meminfo("MemAvailable") or (_detect_ram_total() * 0.5)


def _win32_mem() -> Optional[float]:
    """Windows RAM via ctypes (no external deps)."""
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
        return mem.ullTotalPhys / (1024 ** 3)
    except Exception:
        pass
    return None


def _get_meminfo(key: str) -> Optional[float]:
    try:
        with open("/proc/meminfo", "r") as f:
            for line in f:
                if line.startswith(key):
                    kb = int(line.split()[1])
                    return kb / (1024 ** 2)  # Convert to GB
    except (OSError, ValueError):
        pass
    return None


def _sysctl_mem() -> Optional[float]:
    try:
        import ctypes
        libc = ctypes.CDLL("")
        total = ctypes.c_uint64(0)
        size = ctypes.c_size_t(ctypes.sizeof(total))
        libc.sysctlbyname(b"hw.memsize", ctypes.byref(total), ctypes.byref(size), None, 0)
        return total.value / (1024 ** 3)
    except Exception:
        pass
    return None


# ── CPU ──────────────────────────────────────────

def _detect_cpu_cores() -> int:
    return os.cpu_count() or 4


def _detect_cpu_threads() -> int:
    psutil = _try_import_psutil()
    if psutil:
        try:
            return psutil.cpu_count(logical=True) or _detect_cpu_cores()
        except Exception:
            pass
    return _detect_cpu_cores()


# ── GPU / VRAM ───────────────────────────────────

def _detect_vram() -> Optional[float]:
    return _nvidia_vram() or _amd_vram() or _apple_vram() or _win32_vram()


def _detect_gpu_name() -> Optional[str]:
    for func in (_nvidia_name, _amd_name, _apple_name, _win32_gpu_name):
        name = func()
        if name:
            return name
    return None


def _win32_vram() -> Optional[float]:
    """Windows GPU VRAM via wmic."""
    if sys.platform != "win32":
        return None
    try:
        result = subprocess.run(
            ["wmic", "path", "Win32_VideoController", "get", "AdapterRAM", "/value"],
            capture_output=True, text=True, timeout=5, shell=True,
        )
        if result.returncode == 0:
            match = re.search(r"AdapterRAM=(\d+)", result.stdout)
            if match:
                bytes_val = int(match.group(1))
                # Handle signed int32 wrap-around for >2GB (wmic quirk)
                if bytes_val < 0:
                    bytes_val += 2 ** 32
                return bytes_val / (1024 ** 3)
    except (FileNotFoundError, subprocess.TimeoutExpired, ValueError):
        pass
    return None


def _win32_gpu_name() -> Optional[str]:
    """Windows GPU name via wmic."""
    if sys.platform != "win32":
        return None
    try:
        result = subprocess.run(
            ["wmic", "path", "Win32_VideoController", "get", "Name", "/value"],
            capture_output=True, text=True, timeout=5, shell=True,
        )
        if result.returncode == 0:
            match = re.search(r"Name=(.+)", result.stdout)
            if match:
                return match.group(1).strip()
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return None


def _nvidia_vram() -> Optional[float]:
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.total", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip():
            max_vram = max(float(line.strip()) for line in result.stdout.strip().splitlines())
            return max_vram / 1024  # Convert MB → GB
    except (FileNotFoundError, subprocess.TimeoutExpired, ValueError):
        pass
    return None


def _nvidia_name() -> Optional[str]:
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip().splitlines()[0].strip()
    except (FileNotFoundError, subprocess.TimeoutExpired, ValueError):
        pass
    return None


def _amd_vram() -> Optional[float]:
    try:
        result = subprocess.run(
            ["radeontop", "-d", "-"],
            capture_output=True, text=True, timeout=3,
        )
        # radeontop output not easily machine-parseable; skip
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    # Try rocm-smi
    try:
        result = subprocess.run(
            ["rocm-smi", "--showmeminfo", "VRAM"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            match = re.search(r"(\d+)\s*MB", result.stdout)
            if match:
                return float(match.group(1)) / 1024
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return None


def _amd_name() -> Optional[str]:
    try:
        result = subprocess.run(
            ["rocm-smi", "--showproductname"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip().splitlines()[0].strip()
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return None


def _apple_vram() -> Optional[float]:
    """Apple Silicon unified memory — share with system RAM."""
    if sys.platform == "darwin":
        try:
            result = subprocess.run(
                ["system_profiler", "SPDisplaysDataType"],
                capture_output=True, text=True, timeout=5,
            )
            if result.returncode == 0:
                # On Apple Silicon, VRAM = shared system memory
                # Return a fraction of total RAM as usable for GPU
                ram = _detect_ram_total()
                return ram * 0.7  # Unified memory: ~70% of total available to GPU
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass
    return None


def _apple_name() -> Optional[str]:
    if sys.platform == "darwin":
        try:
            result = subprocess.run(
                ["system_profiler", "SPDisplaysDataType"],
                capture_output=True, text=True, timeout=5,
            )
            if result.returncode == 0:
                match = re.search(r"Chipset Model:\s*(.+)", result.stdout)
                if match:
                    return match.group(1).strip()
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass
    return None


# ── OS ───────────────────────────────────────────

def _detect_os_name() -> str:
    if sys.platform == "linux":
        try:
            with open("/etc/os-release", "r") as f:
                for line in f:
                    if line.startswith("PRETTY_NAME="):
                        return line.split("=", 1)[1].strip().strip('"')
        except OSError:
            pass
        return "Linux"
    elif sys.platform == "darwin":
        return "macOS"
    elif sys.platform == "win32":
        return "Windows"
    return "Unknown"


def _detect_os_version() -> str:
    try:
        import platform
        return platform.release()
    except Exception:
        return ""
