"""List DXGI adapters using the same EnumAdapters ordering as ORT DirectML."""
from __future__ import annotations

import ctypes
import json
import sys
from collections.abc import Callable
from ctypes import wintypes
from typing import Any, TypedDict


class GUID(ctypes.Structure):
    _fields_ = [("data1", wintypes.DWORD), ("data2", wintypes.WORD), ("data3", wintypes.WORD), ("data4", ctypes.c_ubyte * 8)]


class LUID(ctypes.Structure):
    _fields_ = [("low", wintypes.DWORD), ("high", wintypes.LONG)]


class AdapterDesc(ctypes.Structure):
    _fields_ = [("description", wintypes.WCHAR * 128), ("vendor", wintypes.UINT), ("device", wintypes.UINT), ("subsystem", wintypes.UINT), ("revision", wintypes.UINT), ("dedicated_video", ctypes.c_size_t), ("dedicated_system", ctypes.c_size_t), ("shared_system", ctypes.c_size_t), ("luid", LUID)]


def method(obj: ctypes.c_void_p, index: int, result: Any, *args: Any) -> Callable[..., int]:
    table = ctypes.cast(obj, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents
    function: Callable[..., int] = ctypes.WINFUNCTYPE(result, ctypes.c_void_p, *args)(table[index])
    return function


class VideoMemoryInfo(ctypes.Structure):
    _fields_ = [("budget", ctypes.c_uint64), ("usage", ctypes.c_uint64),
                ("reservation", ctypes.c_uint64), ("available_reservation", ctypes.c_uint64)]


def available_video_memory(adapter: ctypes.c_void_p) -> int | None:
    iid = GUID(0x645967A4, 0x1392, 0x4310, (ctypes.c_ubyte * 8)(0xA7, 0x98, 0x80, 0x53, 0xCE, 0x3E, 0x93, 0xFD))
    adapter3 = ctypes.c_void_p()
    query = method(adapter, 0, ctypes.c_long, ctypes.POINTER(GUID), ctypes.POINTER(ctypes.c_void_p))
    if query(adapter, ctypes.byref(iid), ctypes.byref(adapter3)) < 0:
        return None
    try:
        info = VideoMemoryInfo()
        check = method(adapter3, 14, ctypes.c_long, wintypes.UINT, ctypes.c_int, ctypes.POINTER(VideoMemoryInfo))
        if check(adapter3, 0, 0, ctypes.byref(info)) < 0:
            return None
        return max(0, int(info.budget) - int(info.usage))
    finally:
        method(adapter3, 2, wintypes.ULONG)(adapter3)


class Adapter(TypedDict):
    index: int
    name: str
    vendor_id: str
    device_id: str
    dedicated_bytes: int
    directx12: bool
    available_bytes: int | None


def supports_directx12(adapter: ctypes.c_void_p) -> bool:
    d3d12 = ctypes.WinDLL("d3d12.dll")
    d3d12.D3D12CreateDevice.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.POINTER(GUID), ctypes.c_void_p]
    d3d12.D3D12CreateDevice.restype = ctypes.c_long
    iid = GUID(0x189819F1, 0x1DB6, 0x4B57, (ctypes.c_ubyte * 8)(0xBE, 0x54, 0x18, 0x21, 0x33, 0x9B, 0x85, 0xF7))
    return bool(d3d12.D3D12CreateDevice(adapter, 0xB000, ctypes.byref(iid), None) >= 0)


def enumerate_adapters() -> list[Adapter]:
    if sys.platform != "win32":
        raise RuntimeError("DXGI is available only on Windows")
    iid = GUID(0x7B7166EC, 0x21C7, 0x44AE, (ctypes.c_ubyte * 8)(0xB2, 0x1A, 0xC9, 0xAE, 0x32, 0x1A, 0xE3, 0x69))
    factory = ctypes.c_void_p()
    dxgi = ctypes.WinDLL("dxgi.dll")
    dxgi.CreateDXGIFactory.argtypes = [ctypes.POINTER(GUID), ctypes.POINTER(ctypes.c_void_p)]
    dxgi.CreateDXGIFactory.restype = ctypes.c_long
    hr = dxgi.CreateDXGIFactory(ctypes.byref(iid), ctypes.byref(factory))
    if hr < 0:
        raise OSError(f"CreateDXGIFactory failed: 0x{hr & 0xffffffff:08x}")
    adapters: list[Adapter] = []
    try:
        enum = method(factory, 7, ctypes.c_long, wintypes.UINT, ctypes.POINTER(ctypes.c_void_p))
        for index in range(128):
            adapter = ctypes.c_void_p()
            hr = enum(factory, index, ctypes.byref(adapter))
            if (hr & 0xffffffff) == 0x887A0002:
                break
            if hr < 0:
                raise OSError(f"EnumAdapters({index}) failed: 0x{hr & 0xffffffff:08x}")
            try:
                desc = AdapterDesc()
                hr = method(adapter, 8, ctypes.c_long, ctypes.POINTER(AdapterDesc))(adapter, ctypes.byref(desc))
                if hr < 0:
                    raise OSError(f"GetDesc failed: 0x{hr & 0xffffffff:08x}")
                adapters.append({"index": index, "name": desc.description, "vendor_id": f"{desc.vendor:04x}", "device_id": f"{desc.device:04x}", "dedicated_bytes": desc.dedicated_video, "directx12": supports_directx12(adapter) if desc.vendor == 0x1002 else False, "available_bytes": available_video_memory(adapter) if desc.vendor == 0x1002 else None})
            finally:
                method(adapter, 2, wintypes.ULONG)(adapter)
    finally:
        method(factory, 2, wintypes.ULONG)(factory)
    return adapters


def compatible_adapters(adapters: list[Adapter]) -> list[Adapter]:
    return [a for a in adapters if a['vendor_id'].lower() == '1002' and a['directx12']]


def select_adapter(adapters: list[Adapter], index: int | None = None) -> Adapter:
    candidates = compatible_adapters(adapters)
    if index is not None:
        candidates = [a for a in candidates if a['index'] == index]
    if not candidates:
        raise ValueError('No selected AMD adapter passed the DirectX 12 device check. Check the GPU selection and driver.')
    return max(candidates, key=lambda a: (a['dedicated_bytes'] > 0, a['available_bytes'] or 0, a['dedicated_bytes']))


def default_worker_limit(dedicated_bytes: int, available_bytes: int | None = None) -> int:
    # Capacity is not free memory. Restrict simultaneous sessions on smaller or unknown GPUs.
    gib = 1024 ** 3
    if available_bytes is None:
        return 1
    if available_bytes < 4 * gib:
        return 1
    if available_bytes < 6 * gib:
        return 1 if dedicated_bytes < 10 * gib else 2
    if dedicated_bytes < 10 * gib:
        return 1
    if dedicated_bytes < 15 * gib:
        return 2
    return 3


if __name__ == "__main__":
    print(json.dumps(enumerate_adapters()))
