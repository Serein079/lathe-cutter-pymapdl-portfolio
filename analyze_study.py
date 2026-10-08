"""Plot real study CSV data and export adjacent-case differences.

Example: python analyze_study.py results/studies/mesh_.../study_results.csv
         --x tip_size_in --group element
No solver runs or assumptions of convergence are made by this script.
"""
import argparse
import csv
import os
import tempfile
from pathlib import Path
ROOT = Path(__file__).resolve().parent
os.environ.setdefault('MPLCONFIGDIR',str(Path(tempfile.gettempdir())/'lathe_cutter_mpl'))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('csv_path',type=Path)
    parser.add_argument('--x',default='tip_size_in')
    parser.add_argument('--group',default='element')
    parser.add_argument('--output-dir',type=Path,default=ROOT/'results'/'analysis')
    args=parser.parse_args()
    rows=list(csv.DictReader(args.csv_path.open(encoding='utf-8-sig')))
    if not rows:
        raise ValueError('No rows in study CSV')
    for row in rows:
        if row.get('status')!='solved' or row.get('converged') not in ('True','true'):
            raise ValueError('Only verified solved rows should be analyzed')
    groups={}
    for row in rows:
        groups.setdefault(row[args.group],[]).append(row)
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    output=args.output_dir
    output.mkdir(parents=True,exist_ok=True)
    fig,axes=plt.subplots(1,2,figsize=(12,4.6),layout='constrained')
    records=[]
    metrics=('max_u_in','max_s1_psi','max_seqv_psi')
    for name,group in groups.items():
        group.sort(key=lambda r:float(r[args.x]),reverse=args.x in ('tip_size_in','global_size_in'))
        x=[float(r[args.x]) for r in group]
        axes[0].plot(x,[float(r['max_u_in']) for r in group],'-o',label=name)
        axes[1].plot(x,[float(r['max_s1_psi']) for r in group],'-o',label=f'{name} S1')
        axes[1].plot(x,[float(r['max_seqv_psi']) for r in group],'--s',label=f'{name} VM')
        for coarse,fine in zip(group,group[1:]):
            record={'group':name,'from_case':coarse['case'],'to_case':fine['case']}
            for metric in metrics:
                old,new=float(coarse[metric]),float(fine[metric])
                record[metric+'_relative_change']=abs(new-old)/max(abs(new),1e-12)
            records.append(record)
    axes[0].set_ylabel('Maximum displacement (in)')
    axes[1].set_ylabel('Nodal averaged stress (psi)')
    for axis in axes:
        axis.set_xlabel(args.x)
        axis.grid(alpha=0.25)
        axis.legend(fontsize=8)
        axis.ticklabel_format(axis='y',style='sci',scilimits=(-3,4))
    fig.suptitle('Actual study results - convergence must be assessed separately')
    fig.savefig(output/'response_curves.png',dpi=200)
    plt.close(fig)
    if records:
        with (output/'adjacent_changes.csv').open('w',newline='',encoding='utf-8-sig') as stream:
            writer=csv.DictWriter(stream,fieldnames=list(records[0]))
            writer.writeheader();writer.writerows(records)
    print(f'Analysis saved: {output}')
    print('Adjacent differences alone do not certify mesh convergence.')


if __name__=='__main__':
    main()
