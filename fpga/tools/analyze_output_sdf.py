"""Report combinational FF-clock-to-pad paths from public post-route SDF.

Structural extrema are not sensitized timing paths or measured pad delays.
No sequential D->Q arcs, false paths, or synthesized values are introduced.
"""
import argparse
import hashlib
import json
import re
from collections import defaultdict
from pathlib import Path


def analyze(path, start_contains=None):
    source = path.read_text(encoding="utf-8")
    assert "(TIMESCALE 1 ns)" in source
    reverse = defaultdict(list)
    sequential = {}
    def norm(s):
        return s.replace("\\/", "/").replace("\\[", "[").replace("\\]", "]")
    def delay(s):
        values = [float(v) for v in s.split(":")]
        return values[0], values[-1]
    for part in re.split(r"\(CELL\s*\n", source)[1:]:
        celltype = re.search(r'\(CELLTYPE "([^"]+)"\)', part)
        inst = re.search(r"\(INSTANCE\s+([^\s)]+)\)", part)
        if not inst or not celltype:
            continue
        inst = norm(inst.group(1))
        typ = celltype.group(1)
        for a,b,d in re.findall(r"\(IOPATH\s+(\w+)\s+(\w+)\s+\(([\d.:+-]+)\)", part):
            lo,hi = delay(d)
            if typ.startswith("DFF"):
                if a == "CLK" and b == "Q":
                    sequential[inst+"/Q"] = (lo,hi,inst+"/CLK")
            elif typ not in ("DPB", "SP", "SPB", "SDPB", "PLL", "rPLL"):
                reverse[inst+"/"+b].append((inst+"/"+a,lo,hi))
    for a,b,d in re.findall(r"\(INTERCONNECT\s+(\S+)\s+(\S+)\s+\(([\d.:+-]+)\)", source):
        lo,hi = delay(d)
        reverse[norm(b)].append((norm(a),lo,hi))
    memo = {}
    active = set()
    def walk(node):
        if node in memo:
            return memo[node]
        if node in sequential:
            lo,hi,start = sequential[node]
            return (lo,[start,node],hi,[start,node]) if not start_contains or start_contains in node else None
        if node in active:
            raise ValueError("combinational loop: "+node)
        active.add(node)
        candidates=[]
        for prev,lo,hi in reverse[node]:
            item=walk(prev)
            if item:
                candidates.append((item[0]+lo,item[1]+[node],item[2]+hi,item[3]+[node]))
        active.remove(node)
        if not candidates:
            answer=None
        else:
            low=min(candidates,key=lambda x:x[0]); high=max(candidates,key=lambda x:x[2])
            answer=(low[0],low[1],high[2],high[3])
        memo[node]=answer
        return answer
    rows=[]
    for bit in range(8):
        node=f"data_{bit}_iobuf/IO"
        result=walk(node)
        assert result, node
        rows.append(dict(bit=bit,min_ns=result[0],min_path=result[1],max_ns=result[2],max_path=result[3]))
    return dict(sdf_sha256=hashlib.sha256(path.read_bytes()).hexdigest(), start_contains=start_contains, timescale="ns", scope="structural combinational extrema from registered CLK->Q to IOBUF.IO; not sensitized or measured", bits=rows)


if __name__ == "__main__":
    p=argparse.ArgumentParser(); p.add_argument("sdf",type=Path); p.add_argument("--output",type=Path,required=True)
    p.add_argument("--start-contains")
    a=p.parse_args(); result=analyze(a.sdf,a.start_contains); a.output.write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8")
    for row in result["bits"]:
        print(row["bit"],round(row["min_ns"],3),round(row["max_ns"],3),row["max_path"][0])
