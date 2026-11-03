"""Stateful triangle diagnostic oracle using the independent G0 CPU model."""
from reference.link_protocol import crc_valid, crc16, respond, seal
from reference.game_gpu_reference import Frame, Vertex

INFO, CLEAR, DRAW, READ_COLOR, READ_DEPTH = 0x20, 0x2b, 0x2c, 0x2d, 0x2e
ROW = 0x2f
FRACTAL_INFO, FRACTAL_DRAW = 0x30, 0x38


def fractal_sample(params, x, y):
    def signed(v): return v if v<32768 else v-65536
    px=signed(params[0])+x*params[2]
    py=signed(params[1])+y*params[3]
    limit, julia=params[6]&255, params[6]>>8
    zx,zy=(px,py) if julia else (0,0)
    cx,cy=(signed(params[4]),signed(params[5])) if julia else (px,py)
    iterations=0
    while zx*zx+zy*zy<4*4096*4096 and iterations<limit:
        zx,zy=((zx*zx-zy*zy)//4096+cx, (2*zx*zy)//4096+cy)
        iterations+=1
    if iterations==limit: return 0x0042,iterations
    n=iterations*3
    r,g,b=32+(n*9%224),60+(n*5%196),100+(n*3%156)
    return ((r&248)<<8)|((g&252)<<3)|(b>>3),iterations


def fractal_pixel(params,x,y):
    return fractal_sample(params,x,y)[0]



class TriangleTile:
    def __init__(self):
        self.abort()

    def abort(self):
        self.params = {}
        self.fractal_params = {}
        self.fractal_cycles = 0
        self.frame = None

    def exchange(self, frame):
        frame = bytes(frame)
        if len(frame) != 8:
            raise ValueError('eight-byte frame required')
        if not crc_valid(frame) or frame[0] != 0xa5 or frame[3] != 2 or frame[1] < INFO:
            return respond(frame)
        op, a, b = frame[1], frame[4], frame[5]
        status, value = 0, a | b << 8
        if op == INFO:
            value = 0x2020
        elif 0x21 <= op <= 0x2a:
            self.params[op - 0x21] = value
        elif op == CLEAR:
            self.frame = Frame(32, 32)
            self.frame.clear(value, 0)
            value = 0
        elif op == FRACTAL_INFO:
            value=0x0107
        elif 0x31 <= op <= 0x36:
            self.fractal_params[op-0x31]=value
        elif op == 0x37:
            if not 1<=a<=128 or b>1: status,value=3,0
            else: self.fractal_params[6]=value
        elif op in (0x39,0x3a):
            value=0
            if a or b: status=3
            elif not self.fractal_cycles: status=5
            else: value=(self.fractal_cycles>>(16*(op-0x39)))&65535
        elif op == FRACTAL_DRAW:
            value=0
            if a or b: status=3
            elif len(self.fractal_params)!=7: status=5
            else:
                params=self.fractal_params
                def signed(v): return v if v<32768 else v-65536
                if not (1<=params[2]<=32767 and 1<=params[3]<=32767 and
                        signed(params[0])+31*params[2]<=32767 and
                        signed(params[1])+31*params[3]<=32767): status=3
                else:
                    self.frame=Frame(32,32)
                    samples=[fractal_sample(params,x,y) for y in range(32) for x in range(32)]
                    self.frame.color[:]=[color for color,_ in samples]
                    self.fractal_cycles=sum(iterations for _,iterations in samples)+2049
                    value=1024
        elif op == DRAW:
            value = 0
            if a or b:
                status = 3
            elif self.frame is None or len(self.params) != 10:
                status = 5
            else:
                def signed(v): return v if v < 32768 else v - 65536
                vertices = [Vertex(signed(self.params[2*i]), signed(self.params[2*i+1]), self.params[6+i])
                            for i in range(3)]
                old = self.frame.depth[:]
                self.frame.triangle(*vertices, self.params[9])
                value = sum(x != y for x, y in zip(old, self.frame.depth))
        elif op == 0x3c:
            status,value=(3,0) if a or b else (0,0x0103)
        elif op == 0x3b:
            if a or b>1: status,value=3,0
            elif self.frame is None: status,value=5,0
            else:
                prefix=bytes([0x5a,0,frame[2],2,0,b])
                plane=self.frame.color if b==0 else self.frame.depth
                payload=b''.join(v.to_bytes(2,'little') for v in plane)
                return seal(prefix)+payload+crc16(prefix+payload).to_bytes(2,'little')
        elif op == ROW:
            if a >= 32 or b >= 2:
                status, value = 3, 0
            elif self.frame is None:
                status, value = 5, 0
            else:
                prefix = bytes([0x5a, 0, frame[2], 2, a, b])
                plane = self.frame.color if b == 0 else self.frame.depth
                payload = b''.join(v.to_bytes(2, 'little') for v in plane[a*32:a*32+32])
                return seal(prefix) + payload + crc16(prefix+payload).to_bytes(2, 'little')
        elif op in (READ_COLOR, READ_DEPTH):
            value = 0
            if a >= 32 or b >= 32:
                status = 3
            elif self.frame is None:
                status = 5
            else:
                value = (self.frame.color if op == READ_COLOR else self.frame.depth)[b * 32 + a]
        else:
            status, value = 2, 0
        return seal(bytes([0x5a, status, frame[2], 2, value & 255, value >> 8]))
