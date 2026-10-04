"""Credenciales genéricas del usuario Windows; nunca serializa contraseñas a disco."""
import ctypes
from ctypes import wintypes
import os
import json
import re
from contextlib import contextmanager
import hashlib

OPERATOR_PREFIX = 'SeguimientoEscolar/Operadores/'
_created_operator_profiles = {}

PREFIX = 'SeguimientoEscolar/S2.2/'
ROLES = ('ADMIN', 'TUTOR', 'DIRECTOR', 'RESEARCHER')

class Credential(ctypes.Structure):
    _fields_ = [('Flags', wintypes.DWORD), ('Type', wintypes.DWORD),
        ('TargetName', wintypes.LPWSTR), ('Comment', wintypes.LPWSTR),
        ('LastWritten', wintypes.FILETIME), ('CredentialBlobSize', wintypes.DWORD),
        ('CredentialBlob', ctypes.POINTER(ctypes.c_ubyte)), ('Persist', wintypes.DWORD),
        ('AttributeCount', wintypes.DWORD), ('Attributes', ctypes.c_void_p),
        ('TargetAlias', wintypes.LPWSTR), ('UserName', wintypes.LPWSTR)]

def api():
    if os.name != 'nt':
        raise RuntimeError('Esta herramienta requiere el almacén de credenciales de Windows.')
    dll = ctypes.WinDLL('Advapi32.dll', use_last_error=True)
    dll.CredWriteW.argtypes = [ctypes.POINTER(Credential), wintypes.DWORD]
    dll.CredWriteW.restype = wintypes.BOOL
    dll.CredReadW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, ctypes.POINTER(ctypes.POINTER(Credential))]
    dll.CredReadW.restype = wintypes.BOOL
    dll.CredFree.argtypes = [ctypes.c_void_p]
    dll.CredDeleteW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD]
    dll.CredDeleteW.restype = wintypes.BOOL
    return dll

def target(role):
    if role not in ROLES:
        raise ValueError('Rol no admitido.')
    return PREFIX + role

def read(role):
    dll = api()
    pointer = ctypes.POINTER(Credential)()
    if not dll.CredReadW(target(role), 1, 0, ctypes.byref(pointer)):
        error = ctypes.get_last_error()
        if error == 1168:
            return None
        raise OSError(error, 'No se pudo leer la entrada privada de Windows.')
    try:
        entry = pointer.contents
        password = ctypes.string_at(entry.CredentialBlob, entry.CredentialBlobSize).decode('utf-16-le')
        return {'email': entry.UserName, 'password': password}
    finally:
        dll.CredFree(pointer)

def write_new(role, email, password):
    if read(role) is not None:
        raise RuntimeError('La entrada privada ya existe; no se sobrescribe.')
    raw = password.encode('utf-16-le')
    buffer = (ctypes.c_ubyte * len(raw)).from_buffer_copy(raw)
    entry = Credential(Type=1, TargetName=target(role), Comment='Acceso local autorizado para revisión S2.2',
        CredentialBlobSize=len(raw), CredentialBlob=buffer, Persist=2, UserName=email)
    if not api().CredWriteW(ctypes.byref(entry), 0):
        raise OSError(ctypes.get_last_error(), 'No se pudo guardar la entrada privada de Windows.')
    assert read(role) == {'email': email, 'password': password}


def operator_target(name):
    """Namespace distinto de las cuatro entradas históricas; nombre explícito."""
    if not isinstance(name, str) or re.fullmatch(r'[a-z][a-z0-9_-]{2,79}', name) is None:
        raise RuntimeError('OPERATOR_PROFILE_NAME_INVALID')
    return OPERATOR_PREFIX + name


def read_operator_profile(name):
    pointer = ctypes.POINTER(Credential)()
    dll = api()
    if not dll.CredReadW(operator_target(name), 1, 0, ctypes.byref(pointer)):
        error = ctypes.get_last_error()
        if error == 1168:
            return None
        raise RuntimeError('OPERATOR_PROFILE_READ_FAILED')
    try:
        entry = pointer.contents
        metadata = json.loads(entry.Comment or '')
        if (not isinstance(metadata, dict) or metadata.get('schema') != 'operator-profile-v1'
            or not isinstance(metadata.get('target_binding'), str)
            or re.fullmatch(r'[0-9a-f]{64}', metadata['target_binding']) is None):
            raise RuntimeError('OPERATOR_PROFILE_INCOMPATIBLE')
        return {'email': entry.UserName,
            'password': ctypes.string_at(entry.CredentialBlob, entry.CredentialBlobSize).decode('utf-16-le'),
            'target_binding': metadata['target_binding']}
    except (ValueError, UnicodeError, TypeError):
        raise RuntimeError('OPERATOR_PROFILE_INCOMPATIBLE') from None
    finally:
        dll.CredFree(pointer)


@contextmanager
def _operator_lock(name):
    if os.name != 'nt':
        raise RuntimeError('OPERATOR_WINDOWS_REQUIRED')
    kernel = ctypes.WinDLL('Kernel32.dll', use_last_error=True)
    kernel.CreateMutexW.argtypes = [ctypes.c_void_p, wintypes.BOOL, wintypes.LPCWSTR]
    kernel.CreateMutexW.restype = wintypes.HANDLE
    kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    kernel.WaitForSingleObject.restype = wintypes.DWORD
    kernel.ReleaseMutex.argtypes = [wintypes.HANDLE]
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    suffix = hashlib.sha256(operator_target(name).encode()).hexdigest()
    handle = kernel.CreateMutexW(None, False, 'Local\\SeguimientoEscolar-operator-' + suffix)
    if not handle:
        raise RuntimeError('OPERATOR_PROFILE_LOCK_FAILED')
    acquired = False
    try:
        acquired = kernel.WaitForSingleObject(handle, 10000) in (0, 128)
        if not acquired:
            raise RuntimeError('OPERATOR_PROFILE_LOCK_FAILED')
        yield
    finally:
        if acquired:
            kernel.ReleaseMutex(handle)
        kernel.CloseHandle(handle)


def write_new_operator_profile(name, email, password, target_binding):
    """Serializa las altas de este launcher y rechaza una entrada existente."""
    with _operator_lock(name):
        _write_new_operator_profile(name, email, password, target_binding)


def _write_new_operator_profile(name, email, password, target_binding):
    destination = operator_target(name)
    if re.fullmatch(r'[0-9a-f]{64}', target_binding) is None:
        raise RuntimeError('OPERATOR_PROFILE_BINDING_INVALID')
    if read_operator_profile(name) is not None:
        raise RuntimeError('OPERATOR_PROFILE_EXISTS')
    raw = password.encode('utf-16-le')
    buffer = (ctypes.c_ubyte * len(raw)).from_buffer_copy(raw)
    metadata = json.dumps({'schema': 'operator-profile-v1', 'target_binding': target_binding}, separators=(',', ':'))
    entry = Credential(Type=1, TargetName=destination, Comment=metadata,
        CredentialBlobSize=len(raw), CredentialBlob=buffer, Persist=2, UserName=email)
    if not api().CredWriteW(ctypes.byref(entry), 0):
        raise RuntimeError('OPERATOR_PROFILE_WRITE_FAILED')
    expected = {'email': email, 'password': password, 'target_binding': target_binding}
    _created_operator_profiles[name] = expected
    if read_operator_profile(name) != expected:
        raise RuntimeError('OPERATOR_PROFILE_ROUNDTRIP_FAILED')


def delete_operator_profile_created_here(name):
    """Limpieza de pruebas: solo una entrada creada por este proceso y sin cambios."""
    with _operator_lock(name):
        _delete_operator_profile_created_here(name)


def _delete_operator_profile_created_here(name):
    destination = operator_target(name)
    expected = _created_operator_profiles.get(name)
    if expected is None:
        raise RuntimeError('OPERATOR_PROFILE_NOT_CREATED_HERE')
    if read_operator_profile(name) != expected:
        raise RuntimeError('OPERATOR_PROFILE_CHANGED_KEEP_ENTRY')
    if not api().CredDeleteW(destination, 1, 0):
        raise RuntimeError('OPERATOR_PROFILE_DELETE_FAILED')
    del _created_operator_profiles[name]
    if read_operator_profile(name) is not None:
        raise RuntimeError('OPERATOR_PROFILE_DELETE_FAILED')

def show(role):
    """Solo el operador abre una ventana local; no salida de contraseña en consola."""
    import tkinter as tk
    from tkinter import ttk
    entry = read(role)
    if entry is None:
        raise SystemExit('No existe una entrada para ese rol en esta cuenta Windows.')
    window = tk.Tk()
    window.title('Credencial privada — Seguimiento Escolar')
    frame = ttk.Frame(window, padding=24)
    frame.pack()
    ttk.Label(frame, text=target(role)).pack(anchor='w')
    ttk.Label(frame, text=entry['email']).pack(anchor='w', pady=10)
    field = ttk.Entry(frame, width=48, show='●')
    field.insert(0, entry['password'])
    field.configure(state='readonly')
    field.pack()
    visible = tk.BooleanVar(value=False)
    ttk.Checkbutton(frame, text='Mostrar contraseña en esta ventana', variable=visible,
        command=lambda: field.configure(show='' if visible.get() else '●')).pack(anchor='w', pady=12)
    ttk.Button(frame, text='Cerrar', command=window.destroy).pack(anchor='e')
    window.mainloop()

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Consultar una credencial privada en ventana local, sin imprimirla.')
    parser.add_argument('role', choices=ROLES)
    show(parser.parse_args().role)
