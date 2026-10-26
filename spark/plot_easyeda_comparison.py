from pathlib import Path
import json,numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
H=Path(__file__).resolve().parent;W=H/'simulation/easyeda-wasm';name='spark-12V-nominal'
d=json.loads((W/'results'/(name+'.json')).read_text());r=json.loads(d['raw']) if 'raw' in d else json.loads(Path(d['rawPath']).read_text());p=next(x for x in r['plots'] if x['name'].startswith('tran'));v={x['name']:np.array(x['real']) for x in p['vectors']};b=np.load('D:/tmp/carrier-power-transient/'+name+'.npz')
fig,axs=plt.subplots(2,1,figsize=(9,5.5),layout='constrained')
for ax,limits in zip(axs,[(0,45),(19.8,21)]):
 ax.plot(v['time']*1e3,v['vcore'],color='#1778b5',lw=1.8,label='EasyEDA API / official NGspice46 WASM')
 ax.plot(b['time']*1e3,b['v(vcore)'],color='#e37c22',ls='--',lw=1,label='Previous external NGspice')
 ax.set_xlim(*limits);ax.set_ylabel('Core supply (V)');ax.grid(alpha=.25)
axs[0].set_title('Spark carrier: independent rerun of the same 12 V averaged-power model');axs[0].legend(loc='lower right',fontsize=8)
axs[1].set_ylim(4.84,5.03);axs[1].set_xlabel('Time (ms)');axs[1].set_title('0.05 A to 0.5 A load step: the two traces overlap',fontsize=10)
fig.savefig(W/'power-waveform-comparison.png',dpi=160);plt.close(fig)
print('Power overlay plotted from independently computed traces')
