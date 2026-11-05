"""Offline TX packet/edge inspection; 10ns sampled logic is not an analog eye."""
import argparse
import hashlib
import json
import re
from pathlib import Path
import sys
import zipfile
import numpy as np

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'fpga'))
from reference.link_protocol import crc16


def histogram(a):
    u,n=np.unique(a,return_counts=True)
    return {str(int(x)):int(y) for x,y in zip(u,n)}


def decode(words):
    a=np.asarray(words,dtype=np.uint16)
    b=np.zeros(a.size,dtype=np.uint8)
    for bit in range(8):b|=(((a>>(15-bit))&1)<<bit).astype(np.uint8)
    return bytes(b)


def analyze(folder):
    cap=folder/'capture.sr'
    with zipfile.ZipFile(cap)as z:
        names=sorted([n for n in z.namelist()if n.startswith('logic-1-')],key=lambda n:int(n.rsplit('-',1)[1]))
        assert [int(n.rsplit('-',1)[1])for n in names]==list(range(1,len(names)+1))
        raw=b''.join(z.read(n)for n in names)
        metadata=z.read('metadata').decode()
        rate_match=re.search(r'samplerate\s*=\s*([\d.]+)\s*([kMG]?)Hz',metadata)
        if not rate_match:raise ValueError('Unknown samplerate')
        rate=float(rate_match[1])*{'':1,'k':1000,'M':1000000,'G':1000000000}[rate_match[2]]
        period_ns=1e9/rate
        offsets=range(-round(30/period_ns),round(30/period_ns)+1)
    samples=np.frombuffer(raw,dtype='<u2')
    clock=(samples>>7)&1;direction=(samples>>6)&1
    rises=np.flatnonzero(clock[1:]>clock[:-1])+1
    falls=np.flatnonzero(clock[1:]<clock[:-1])+1
    changes=np.flatnonzero(((samples[1:]^samples[:-1])&0xff00)!=0)+1
    boundaries=np.r_[0,np.flatnonzero(direction[1:]!=direction[:-1])+1,len(samples)]
    bursts=[]
    for start,end in zip(boundaries[:-1],boundaries[1:]):
        if direction[start]:continue
        r=rises[(rises>=start)&(rises<end)]
        if not len(r):continue
        packet={}
        for offset in offsets:
            at=r+offset
            if at[0]<start or at[-1]>=end:continue
            data=decode(samples[at]);found=[]
            for n in range(max(0,len(data)-7)):
                q=data[n:n+8]
                if q[0]!=0xa5 or q[3]!=2 or crc16(q[:6])!=int.from_bytes(q[6:8],'little'):continue
                op=q[1]&127;length=8
                if op in (0x41,0x5f,0x6e) and 1<=q[4]<=64 and q[5]==1:length=10+q[4]*20
                complete=len(data)-n>=length
                body_ok=None
                if complete and length>8:
                    frame=data[n:n+length]
                    body_ok=crc16(frame[:6]+frame[8:-2])==int.from_bytes(frame[-2:],'little')
                found.append(dict(edge_offset=n,header_hex=q.hex(),opcode=op,sequence=q[2],length=length,
                                  complete=complete,body_crc_pass=body_ok,leading_edges=n,trailing_edges=len(data)-n-length))
            packet[str(offset)]=found
        periods=np.diff(r)
        fast=len(r)>8 and len(periods) and np.median(periods)*period_ns<200
        record=dict(start_sample=int(start),end_sample=int(end),rising_edges=len(r),
                    last_rise_to_dir_change_samples=int(end-r[-1]),fast=bool(fast),decoded_fixed_offset=packet)
        if fast:
            f=falls[(falls>=r[0])&(falls<end)]
            after=np.searchsorted(f,r,side='right');valid=after<len(f)
            high=f[after[valid]]-r[valid]
            low=r[1:]-f[np.searchsorted(f,r[1:],side='left')-1]
            dc_context=changes[(changes>start)&(changes<end)]
            dc=changes[(changes>r[0])&(changes<r[-1])]
            before=np.searchsorted(dc_context,r,side='right')-1
            nxt=np.searchsorted(dc_context,r,side='left')
            su=r[before>=0]-dc_context[before[before>=0]]
            ho=dc_context[nxt[nxt<len(dc_context)]]-r[nxt<len(dc_context)]
            k=np.searchsorted(r,dc)
            left=np.clip(k-1,0,len(r)-1);right=np.clip(k,0,len(r)-1)
            nearest=np.where(dc-r[left]<=r[right]-dc,left,right)
            record.update(first_clock_setup_samples=int(r[0]-dc_context[before[0]])if before[0]>=0 else None,
                          last_clock_hold_samples=int(dc_context[nxt[-1]]-r[-1])if nxt[-1]<len(dc_context)else None,
                          high_complete_edges=int(valid.sum()),
                          data_setup_hist_samples=histogram(su[su<=2*np.median(periods)]),
                          data_hold_hist_samples=histogram(ho[ho<=2*np.median(periods)]),
                          period_hist_samples=histogram(periods),high_hist_samples=histogram(high),low_hist_samples=histogram(low),
                          setup_min_samples=int(su.min())if len(su)else None,hold_min_samples=int(ho.min())if len(ho)else None,
                          coincident_data_clock_samples=int(np.isin(r,dc).sum()),
                          nearest_rise_data_change_offset_hist_samples=histogram(dc-r[nearest]))
        bursts.append(record)
    comp=folder/'completeness.json';complete=json.loads(comp.read_text())if comp.exists()else None
    result=folder/'result.json';device=json.loads(result.read_text())if result.exists()else{}
    log=(folder/'capture.log').read_text() if (folder/'capture.log').exists() else ''
    transport=re.search(r'slogic-report[^\n]*?mbps=([\d.]+)\s+exp_mbps=([\d.]+)',log)
    transport_note=None
    if transport:
        actual,expected=map(float,transport.groups())
        transport_note=dict(actual_mbps=actual,expected_mbps=expected,ratio=actual/expected,
                            warning='transport ratio alone is not sampling-clock calibration; check independent CLK periods',
                            suspicious_ratio=actual/expected<0.8 or actual/expected>1.2)
    merged={name:{}for name in ['period_hist_samples','high_hist_samples','low_hist_samples','nearest_rise_data_change_offset_hist_samples','data_setup_hist_samples','data_hold_hist_samples']}
    fast=[b for b in bursts if b['fast']]
    for b in fast:
        for name,d in merged.items():
            for k,n in b[name].items():d[k]=d.get(k,0)+n
    summary={str(offset):dict(complete_long_packets=sum(1 for b in fast for p in b['decoded_fixed_offset'].get(str(offset),[])if p['complete']),
                             valid_body_crc=sum(1 for b in fast for p in b['decoded_fixed_offset'].get(str(offset),[])if p['complete']and p['body_crc_pass']))
             for offset in offsets}
    return dict(scope='offline sampled digital inspection; no per-byte phase repair; sampling from metadata; no analog setup/hold/MTBF proof',
                capture=str(cap.resolve()),capture_sha256=hashlib.sha256(cap.read_bytes()).hexdigest(),samples=len(samples),sample_rate_hz=rate,sample_period_ns=period_ns,
                original_completeness=complete,timebase_transport_note=transport_note,configured_tx_hz=device.get('tx_hz'),configured_rx_hz=device.get('rx_hz'),
                device_last_step_error=device.get('after',{}).get('last_step_error'),device_link_error=device.get('after',{}).get('link_error'),
                dma_bursts=len(fast),decoded_summary=summary,merged_histograms=merged,bursts=bursts)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('folder',type=Path);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    r=analyze(a.folder);a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(r,indent=2),encoding='utf-8')
    print(json.dumps({k:r[k]for k in ['samples','sample_period_ns','configured_tx_hz','device_last_step_error','device_link_error','dma_bursts','decoded_summary','merged_histograms']}))


if __name__=='__main__':main()
