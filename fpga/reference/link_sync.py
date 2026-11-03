"""Independent optional LINK prefix wrapper; underlying device semantics unchanged."""
from reference.link_protocol import crc_valid, request, seal
PREFIX=bytes([0xc3])*8

class SyncPrefixDevice:
    def __init__(self, device):
        self.device=device
    def exchange(self, frame):
        frame=bytes(frame)
        if len(frame)!=8: raise ValueError('eight-byte request required')
        valid=frame[0]==0xa5 and frame[3]==2 and crc_valid(frame)
        tagged=bool(frame[1]&128) and valid
        logical=request(frame[1]&127,frame[2],frame[4],frame[5]) if tagged else frame
        if valid and (frame[1]&127)==4:
            reply=seal(bytes([0x5a,0,frame[2],2,8,1]))
        else: reply=self.device.exchange(logical)
        return (PREFIX if tagged else b'')+reply
