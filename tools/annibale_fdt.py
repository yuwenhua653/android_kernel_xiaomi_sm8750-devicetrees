# SPDX-License-Identifier: BSD-3-Clause
"""Small reader for locally compiled trusted FDT validation fixtures."""
import struct,re,json
from pathlib import Path
class Fdt:
 def __init__(self,data):
  h=struct.unpack_from('>10I',data);assert h[0]==0xd00dfeed
  self.nodes={};off=h[2];strings=data[h[3]:h[3]+h[8]];stack=[]
  while True:
   token,=struct.unpack_from('>I',data,off);off+=4
   if token==1:
    end=data.index(0,off);name=data[off:end].decode();off=(end+4)&~3;stack.append(name);self.nodes['/'+ '/'.join(stack[1:])]={}
   elif token==2:stack.pop()
   elif token==3:
    size,idx=struct.unpack_from('>2I',data,off);off+=8;key=strings[idx:strings.index(0,idx)].decode();self.nodes['/'+'/'.join(stack[1:])][key]=data[off:off+size];off=(off+size+3)&~3
   elif token==4:continue
   elif token==9:break
   else:raise ValueError(token)
 def children(self,path):return [p for p in self.nodes if p.rsplit('/',1)[0]==path]
 def symbol(self,name):return self.nodes['/__symbols__'][name].rstrip(b'\0').decode()
 def refs(self):
  r={}
  for label,v in self.nodes['/__fixups__'].items():
   for s in v.rstrip(b'\0').decode().split('\0'):
    p,k,o=s.rsplit(':',2);r[p,k,int(o)]=label
  return r

def cells(b):return list(struct.unpack('>'+str(len(b)//4)+'I',b))
