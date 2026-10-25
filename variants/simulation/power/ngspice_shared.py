"""Small ngspice shared-library adapter; no external Python SPICE dependency."""
from pathlib import Path
import ctypes as ct
import os
import numpy as np

class VectorInfo(ct.Structure):
    _fields_=[('name',ct.c_char_p),('type',ct.c_int),('flags',ct.c_short),('realdata',ct.POINTER(ct.c_double)),('complexdata',ct.c_void_p),('length',ct.c_int)]

class Spice:
    def __init__(self, dll='C:/Program Files/KiCad/10.0/bin/ngspice.dll'):
        self.messages=[];self.exits=[]
        self._stream=open(os.environ['NGSPICE_STREAM_LOG'],'w',encoding='utf8',buffering=1) if os.environ.get('NGSPICE_STREAM_LOG') else None
        self._dll_dir=os.add_dll_directory(str(Path(dll).parent)) if os.name=='nt' else None
        self.lib=ct.CDLL(dll)
        CHAR=ct.CFUNCTYPE(ct.c_int,ct.c_char_p,ct.c_int,ct.c_void_p)
        EXIT=ct.CFUNCTYPE(ct.c_int,ct.c_int,ct.c_bool,ct.c_bool,ct.c_int,ct.c_void_p)
        self._send=CHAR(lambda s,ident,user:self._message(s))
        self._exit=EXIT(lambda status,immediate,quitexit,ident,user:self._exit_message(status,immediate,quitexit))
        self.lib.ngSpice_Init.argtypes=[ct.c_void_p]*7
        self.lib.ngSpice_Init.restype=ct.c_int
        self.lib.ngSpice_Command.argtypes=[ct.c_char_p];self.lib.ngSpice_Command.restype=ct.c_int
        self.lib.ngSpice_Circ.argtypes=[ct.POINTER(ct.c_char_p)];self.lib.ngSpice_Circ.restype=ct.c_int
        self.lib.ngGet_Vec_Info.argtypes=[ct.c_char_p];self.lib.ngGet_Vec_Info.restype=ct.POINTER(VectorInfo)
        code=self.lib.ngSpice_Init(self._send,None,self._exit,None,None,None,None)
        if code:raise RuntimeError(('ngSpice_Init',code))
        cm=Path(dll).parent.parent/'lib/ngspice'
        for name in ('analog.cm','digital.cm','spice2poly.cm','table.cm','tlines.cm','xtradev.cm','xtraevt.cm'):
            if (cm/name).exists():
                p=str(cm/name)
                if os.name=='nt':
                    buf=ct.create_unicode_buffer(4096)
                    if ct.windll.kernel32.GetShortPathNameW(p,buf,4096):p=buf.value
                self.command('codemodel '+p.replace('\\','/'))
    def _message(self,s):
        message=s.decode('utf8',errors='replace');self.messages.append(message)
        if self._stream:self._stream.write(message+'\n')
        return 0
    def _exit_message(self,*args):self.exits.append(args);return 0
    def command(self,s):return self.lib.ngSpice_Command(s.encode('utf8'))
    def load(self,lines,pspice=False):
        self.command('destroy all')
        if pspice:self.command('set ngbehavior=ps')
        self._lines=[l.encode('utf8') for l in lines]
        self._array=(ct.c_char_p*(len(self._lines)+1))(*self._lines,None)
        return self.lib.ngSpice_Circ(self._array)
    def vector(self,name):
        p=self.lib.ngGet_Vec_Info(name.encode('utf8'))
        if not p:raise KeyError(name)
        info=p.contents
        if not info.realdata:raise ValueError(('not real',name))
        return np.ctypeslib.as_array(info.realdata,shape=(info.length,)).copy()
    def run(self):return self.command('run')
    def log(self,path):Path(path).write_text('\n'.join(self.messages)+'\n',encoding='utf8')

if __name__=='__main__':
    s=Spice();s.command('version')
    s.load(['RC smoke test','Vin in 0 PULSE(0 1 0 1n 1n 1m 2m)','R1 in out 1k','C1 out 0 1u','.tran 10u 2m','.end'])
    s.run();print('samples',len(s.vector('time')),'Voutmax',s.vector('v(out)').max());print('\n'.join(s.messages[-8:]))
