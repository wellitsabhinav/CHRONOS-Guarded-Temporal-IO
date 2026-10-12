"""Optional small evidence plot (Matplotlib 3.9.2); no experiment is rerun."""
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

plt.rcParams['svg.hashsalt']='eventless-CS-gate'

ROOT=Path(__file__).resolve().parents[1]


def main():
    result=json.loads((ROOT/'docs/results/eventless_gate.json').read_text())
    fig,axes=plt.subplots(1,2,figsize=(10,3.4),layout='constrained')
    phase_labels={0:'0',1:'1 ps',5000:'0.5 T',9999:'T - 1 ps'}
    for row in result['points']:
        if row['group']!='alignment' or row['frames'][0]['value']!=0:continue
        f=row['frames'][0];x=(f['cs']-f['start'])/10000;y=list(phase_labels).index(f['phase'])
        for ax,key in zip(axes,('payload_success','strict_success')):
            passed=row['eventless'][key]
            ax.scatter(x,y,color='#087f5b' if passed else '#ba303b',marker='o' if passed else 'x',s=45)
    for ax,title in zip(axes,('Selected samples: data, OE, setup','Strict raw-CS framing')):
        ax.set(title=title,xlabel='CS assertion - host START (internal clocks)',yticks=range(4),
               yticklabels=list(phase_labels.values()),ylim=(-.5,3.5),xticks=(-8,-6,-4,-2,0,2,4,6,8))
        ax.grid(alpha=.15)
    axes[0].set_ylabel('Raw SCK phase')
    fig.suptitle('Eventless = edge-reactive; known-schedule WAIT has the same alignment results',fontsize=10)
    fig.legend(handles=[Line2D([],[],color='#087f5b',marker='o',linestyle='',label='Pass'),
                        Line2D([],[],color='#ba303b',marker='x',linestyle='',label='Fail')],
               loc='outside lower center',ncol=2,frameon=False)
    fig.savefig(ROOT/'docs/results/eventless_alignment.svg',metadata={'Date':None})
    plt.close(fig)


if __name__=='__main__':main()
