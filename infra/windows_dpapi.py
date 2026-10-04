"""DPAPI de usuario Windows. Referencia: Microsoft CryptProtectData/UnprotectData."""
import ctypes
from ctypes import wintypes
import os

MAGIC=b'SEBACKUP1\0'


class Blob(ctypes.Structure):
    _fields_=[('cbData',wintypes.DWORD),('pbData',ctypes.POINTER(ctypes.c_ubyte))]


def _crypt(value,protect):
    if os.name!='nt': raise RuntimeError('WINDOWS_DPAPI_REQUIRED')
    if not isinstance(value,bytes) or not value or len(value)>512*1024*1024:
        raise RuntimeError('DPAPI_INPUT_INVALID')
    crypt=ctypes.WinDLL('crypt32',use_last_error=True)
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    buffer=(ctypes.c_ubyte*len(value)).from_buffer_copy(value)
    source=Blob(len(value),buffer)
    output=Blob()
    function=crypt.CryptProtectData if protect else crypt.CryptUnprotectData
    function.argtypes=[ctypes.POINTER(Blob),wintypes.LPCWSTR if protect else ctypes.c_void_p,
        ctypes.c_void_p,ctypes.c_void_p,ctypes.c_void_p,wintypes.DWORD,ctypes.POINTER(Blob)]
    function.restype=wintypes.BOOL
    kernel.LocalFree.argtypes=[ctypes.c_void_p]
    kernel.LocalFree.restype=ctypes.c_void_p
    # UI_FORBIDDEN; no LOCAL_MACHINE: identidad del usuario, no todos los usuarios.
    success=function(ctypes.byref(source),'Seguimiento Escolar S6' if protect else None,
        None,None,None,1,ctypes.byref(output))
    if not success: raise RuntimeError('DPAPI_PROTECT_FAILED' if protect else 'DPAPI_INTEGRITY_OR_IDENTITY_FAILED')
    try: return ctypes.string_at(output.pbData,output.cbData)
    finally: kernel.LocalFree(output.pbData)


def protect(value):
    return MAGIC+_crypt(value,True)


def unprotect(value):
    if not value.startswith(MAGIC): raise RuntimeError('BACKUP_FORMAT_INVALID')
    return _crypt(value[len(MAGIC):],False)
