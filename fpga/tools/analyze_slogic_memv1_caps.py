"""Read-only offline short CAPS request/reply analysis; no repaired bytes/edges.
Fixed probes: CLK7, DIR5, READY6; D0..7=CH15..8. Whole-edge sampling only.
At 50MS/s a 20MHz half-cycle has only 1.25 samples; no internal P4 phase claim.
"""
import argparse,json,re,zipfile
from pathlib import Path
import numpy as np
from analyze_slogic_memv1 import regions,blocks,data_bytes,sha,histogram,MAPPING
from map_slogic_memv1 import crc16,request,response


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('folder',type=Path);ap.add_argument('--output',type=Path)
    ap.add_argument('--tx-hz',type=float,help='Expected TX clock; defaults to host tx_hz')
    ap.add_argument('--tx-preamble',type=int,choices=range(5),help='Explicit physical zero-byte preamble; defaults to recorded host option, otherwise zero')
    ap.add_argument('--bus-hz',type=float,help='Expected RX clock for comparison only; defaults to host requested rx_hz; never rescales samples')
    a=ap.parse_args();p=a.folder
    run=json.loads((p/'run.json').read_text());host=json.loads((p/'caps.json').read_text())
    rate,total,short=regions(p/'capture.sr');sample_ns=1e9/rate
    bus_hz=a.bus_hz or host.get('rx_hz')
    tx_hz=a.tx_hz or host.get('tx_hz',2000000)
    tx_preamble=a.tx_preamble if a.tx_preamble is not None else host.get('dma_options',{}).get('tx_preamble',0)
    if tx_hz<=0:raise ValueError('tx-hz must be positive')
    if tx_preamble not in range(5):raise ValueError('recorded tx preamble must be 0..4')
    tx_wire_length=8+tx_preamble
    if bus_hz is not None and bus_hz<=0:raise ValueError('bus-hz must be positive')
    windows=[(max(0,span[0]-int(rate*.002)),span[1]+64) for span,_,_ in short]
    buf=[[] for _ in windows]
    with zipfile.ZipFile(p/'capture.sr') as archive:
        names=sorted([n for n in archive.namelist() if re.fullmatch(r'logic-1-\d+',n)],key=lambda n:int(n.rsplit('-',1)[1]))
        for offset,values in blocks(archive,names):
            end=offset+len(values)
            for i,(lo,hi) in enumerate(windows):
                if lo<end and hi>offset:buf[i].append(values[max(0,lo-offset):min(len(values),hi-offset)].copy())
    result={'scope':'offline short frame analysis; host FAIL remains FAIL; no bit/byte/edge repair',
            'ready_count_policy':'informational only; phase3 intentionally delays READY; no PASS/FAIL based on count',
            'timebase_policy':'nominal metadata time only; compare TX period to expected; common-factor mismatch has no assigned cause',
            'script_sha256':sha(__file__),'helper_sha256':sha(Path(__file__).with_name('analyze_slogic_memv1.py')),
            'capture_sha256':sha(p/'capture.sr'),'run_sha256':sha(p/'run.json'),'host_sha256':sha(p/'caps.json'),
            'expected_tx_bus_hz':tx_hz,'tx_preamble_bytes':tx_preamble,'expected_rx_bus_hz':bus_hz,'expected_rx_period_samples':rate/bus_hz if bus_hz else None,'sample_rate':rate,'sample_ns':sample_ns,'stored_samples':total,'requested_samples':run.get('samples'),
            'capture_exit_code':run.get('capture_exit_code'),'host_result':host.get('result'),'mapping':MAPPING,
            'limits':[f'{sample_ns:g}ns digitizer resolution cannot prove internal setup/hold or analog edges','Probe edges are not internal P4 sampling events','Each phase samples one whole frame; no per-byte choice or deleted edges'], 'frames':[]}
    for i,((span,_,_),window,parts) in enumerate(zip(short,windows,buf)):
        if i>=9:raise ValueError('more than 9 DIR intervals: refuse CAPS sequence assumption')
        lo,hi=window;v=np.concatenate(parts);values=data_bytes(v);clk=(v&128)!=0
        rises=np.flatnonzero(clk[1:]&~clk[:-1])+1;falls=np.flatnonzero(~clk[1:]&clk[:-1])+1
        txr=rises[rises<span[0]-lo];txperiod=rate/tx_hz
        cuts=np.flatnonzero(np.abs(np.diff(txr)-txperiod)>max(1.1,txperiod*.15))+1
        groups=[g for g in np.split(txr,cuts) if len(g)==tx_wire_length]
        tx=bytes(values[groups[-1]-1]) if groups else b''
        observed_period=float(np.median(np.diff(txr))) if len(txr)>=tx_wire_length else None
        observed_cuts=np.flatnonzero(np.abs(np.diff(txr)-observed_period)>1.1)+1 if observed_period else []
        observed_groups=[g for g in np.split(txr,observed_cuts) if len(g)==tx_wire_length]
        observed_tx=bytes(values[observed_groups[-1]-1]) if observed_groups else b''
        rxrise=rises[(rises>=span[0]-lo)&(rises<span[1]-lo)];rxfall=falls[(falls>=span[0]-lo)&(falls<span[1]-lo)]
        expected=response(i);expected_tx=bytes(tx_preamble)+request(i);row={'index':i,'seq':0x41+i,'request_hex':tx.hex(),'expected_request_hex':expected_tx.hex(),'physical_request_length':tx_wire_length,'request_preamble_valid':tx[:tx_preamble]==bytes(tx_preamble),'request_crc_valid':len(tx)==tx_wire_length and crc16(tx[tx_preamble:tx_preamble+6])==int.from_bytes(tx[tx_preamble+6:],'little'),
             'observed_period_request_hex':observed_tx.hex(),'observed_period_request_exact':observed_tx==expected_tx,'observed_tx_period_samples':observed_period,'nominal_tx_period_samples':txperiod,'timebase_ratio_observed_to_nominal':observed_period/txperiod if observed_period else None,'request_exact_match':tx==expected_tx,'pre_dir_tx_rising_period_samples':histogram(np.diff(txr[-20:])), 'pre_dir_tx_last_group_lengths':[len(g) for g in np.split(txr,cuts)][-5:],'expected_reply_hex':expected[8:].hex(),'expected_status':expected[9],
             'raw_rising_edges':len(rxrise),'raw_falling_edges':len(rxfall),'rising_period_samples':histogram(np.diff(rxrise)),
             'dir_start_sample':span[0],'dir_end_sample':span[1],'phases':[]}
        row['tx_primary_sampling']='physical rising edge minus one acquired sample; not FPGA internal capture'
        row['tx_high_width_samples']=histogram([falls[np.searchsorted(falls,t,side='right')]-t for t in (observed_groups[-1] if observed_groups else []) if np.searchsorted(falls,t,side='right')<len(falls)])
        row['tx_whole_frame_phases']=[]
        for txedge,txpositions in [('rising',txr),('falling',falls[falls<span[0]-lo])]:
            if len(txpositions)<tx_wire_length:continue
            txcuts=np.flatnonzero(np.abs(np.diff(txpositions)-observed_period)>1.1)+1
            txgroups=[g for g in np.split(txpositions,txcuts) if len(g)==tx_wire_length]
            if not txgroups:continue
            for shift in [-2,-1,0,1,2]:
                frame=bytes(values[txgroups[-1]+shift])
                row['tx_whole_frame_phases'].append({'physical_edge':txedge,'offset_ns':shift*sample_ns,'hex':frame.hex(),'exact_expected':frame==expected_tx})
        for edge,positions in [('rising',rxrise),('falling',rxfall)]:
            for shift in [-2,-1,0,1,2]:
                stream=bytes(values[positions+shift]);heads=[]
                for at in range(min(32,max(0,len(stream)-7))):
                    h=stream[at:at+8]
                    if h[0]!=0x5a or h[2]!=0x41+i or h[3]!=2:continue
                    heads.append({'header_offset':at,'hex':h.hex(),'status':h[1],
                                  'crc_calculated':f'{crc16(h[:6]):04x}','crc_received':f'{int.from_bytes(h[6:8],"little"):04x}',
                                  'crc_valid':crc16(h[:6])==int.from_bytes(h[6:8],'little'),
                                  'exact_expected':h==expected[8:], 'prefix8_valid':at>=8 and stream[at-8:at]==b'\xc3'*8})
                row['phases'].append({'physical_edge':edge,'offset_ns':shift*sample_ns,'first24_hex':stream[:24].hex(),'header_candidates':heads,
                                      'unique_valid_header':sum(h['crc_valid'] and h['prefix8_valid'] for h in heads)==1})
        ready=((v>>6)&1)!=0;change=np.flatnonzero(ready[1:]!=ready[:-1])+1
        row['ready_falls']=[{'sample':lo+int(t),'rises_before':int(np.searchsorted(rxrise,t))} for t in change if not ready[t] and span[0]-lo<=t<span[1]-lo]
        changes=np.flatnonzero(values[1:]!=values[:-1])+1
        row['first24_clock_detail']=[{'ordinal':j,'rise_sample':lo+int(t),'byte_at_rise':int(values[t]),
            'period_to_next_rise_ns':float((rxrise[j+1]-t)*sample_ns) if j+1<len(rxrise) else None,'high_width_ns':float((rxfall[np.searchsorted(rxfall,t,side='right')]-t)*sample_ns) if np.searchsorted(rxfall,t,side='right')<len(rxfall) else None,
            'data_changes_until_next_rise':[{'after_rise_ns':float((c-t)*sample_ns),'byte':int(values[c])} for c in changes[(changes>=t)&(changes<(rxrise[j+1] if j+1<len(rxrise) else t+8))]],
            'ready_at_rise':bool(ready[t])} for j,t in enumerate(rxrise[:24])]
        result['frames'].append(row)
    raw=bytes.fromhex(host.get('error',{}).get('capture_head_hex',''));heads=[]
    failed_index=len(result['frames'])-1 if host.get('result')=='FAIL' else None
    expected_failed=response(failed_index)[8:] if failed_index is not None and 0<=failed_index<=8 else None
    for at in range(max(0,len(raw)-7)):
        h=raw[at:at+8]
        # Keep a corrupted seq/status: this is a diagnostic of the failed raw
        # capture, not an attempt to qualify it as a matching response.
        if h[0]!=0x5a or h[3]!=2:continue
        heads.append({'offset':at,'hex':h.hex(),'status':h[1],'sequence':h[2],
                      'crc_valid':crc16(h[:6])==int.from_bytes(h[6:8],'little'),
                      'crc_calculated':f'{crc16(h[:6]):04x}','crc_received':f'{int.from_bytes(h[6:8],"little"):04x}',
                      'xor_to_expected':bytes(x^y for x,y in zip(h,expected_failed)).hex() if expected_failed else None})
    result['p4_failed_capture']={'raw_hex':raw.hex(),'headers':heads,'expected_failed_index':failed_index,
                                  'expected_header_for_failed_request':expected_failed.hex() if expected_failed else None}
    output=a.output or p/'short-caps-analysis.json';output.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'output':str(output),'host_result':result['host_result'],'capture_exit_code':result['capture_exit_code'],
                      'request_exact_matches':sum(f['request_exact_match'] for f in result['frames']),
                      'frames':len(result['frames']),'last_phases':result['frames'][-1]['phases']},indent=2))

if __name__=='__main__':main()
