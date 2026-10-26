import ctypes
import os
from ctypes import wintypes

class Windows:
    def __init__(self,dry_run=True):
        if os.name!='nt': raise RuntimeError('실시간 캡처/입력은 Windows 10/11에서 실행하세요.')
        self.u=ctypes.windll.user32; self.dry=dry_run
        self.u.SetProcessDPIAware()
        self.u.GetForegroundWindow.restype=wintypes.HWND
        self.u.GetClientRect.argtypes=[wintypes.HWND,ctypes.POINTER(wintypes.RECT)]
        self.u.ClientToScreen.argtypes=[wintypes.HWND,ctypes.POINTER(wintypes.POINT)]
        self.u.IsWindowVisible.argtypes=[wintypes.HWND]
        self.u.GetWindowTextW.argtypes=[wintypes.HWND,wintypes.LPWSTR,ctypes.c_int]
        self.u.GetAsyncKeyState.argtypes=[ctypes.c_int]
        self.u.GetAsyncKeyState.restype=ctypes.c_short
        self.u.SendInput.argtypes=[wintypes.UINT,ctypes.c_void_p,ctypes.c_int]
        self.u.SendInput.restype=wintypes.UINT
    def windows(self):
        found=[]
        callback=ctypes.WINFUNCTYPE(ctypes.c_bool,wintypes.HWND,wintypes.LPARAM)
        def visit(hwnd,_):
            if self.u.IsWindowVisible(hwnd):
                buf=ctypes.create_unicode_buffer(512); self.u.GetWindowTextW(hwnd,buf,512)
                if buf.value: found.append((hwnd,buf.value))
            return True
        self.u.EnumWindows(callback(visit),0)
        return found
    def region(self,hwnd):
        rect=wintypes.RECT(); point=wintypes.POINT(0,0)
        if not self.u.GetClientRect(hwnd,ctypes.byref(rect)) or not self.u.ClientToScreen(hwnd,ctypes.byref(point)):
            raise RuntimeError('게임 창을 찾을 수 없습니다.')
        if rect.right<100 or rect.bottom<100: raise RuntimeError('게임 창이 최소화되었거나 너무 작습니다.')
        return dict(left=point.x,top=point.y,width=rect.right,height=rect.bottom)
    def focused(self,hwnd): return self.u.GetForegroundWindow()==hwnd
    def emergency(self): return bool(self.u.GetAsyncKeyState(0x77)&0x8000) # F8
    def key(self,key,down):
        if self.dry: return
        vk={'capslock':0x14,'enter':0x0D,'space':0x20}.get(key)
        if vk is None: raise ValueError('지원 키: capslock, enter, space')
        class KEY(ctypes.Structure):
            _fields_=[('vk',wintypes.WORD),('scan',wintypes.WORD),('flags',wintypes.DWORD),('time',wintypes.DWORD),('extra',ctypes.c_size_t)]
        class MOUSE(ctypes.Structure):
            _fields_=[('dx',wintypes.LONG),('dy',wintypes.LONG),('data',wintypes.DWORD),('flags',wintypes.DWORD),('time',wintypes.DWORD),('extra',ctypes.c_size_t)]
        class UNION(ctypes.Union): _fields_=[('ki',KEY),('mi',MOUSE)]
        class INPUT(ctypes.Structure): _fields_=[('type',wintypes.DWORD),('value',UNION)]
        scan=self.u.MapVirtualKeyW(vk,0)
        event=INPUT(type=1,value=UNION(ki=KEY(0,scan,8|(0 if down else 2),0,0)))
        if self.u.SendInput(1,ctypes.byref(event),ctypes.sizeof(event))!=1: raise RuntimeError('SendInput 실패: 게임과 프로그램의 권한 수준을 확인하세요.')
    def click(self,x,y):
        if not self.dry:
            self.u.SetCursorPos(int(x),int(y)); self.u.mouse_event(2,0,0,0,0); self.u.mouse_event(4,0,0,0,0)
