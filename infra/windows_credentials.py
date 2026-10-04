"""Credenciales genéricas del usuario Windows; nunca serializa contraseñas a disco."""
import ctypes
from ctypes import wintypes
import os

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
