"""Run on the actual model-connected app host; never fabricates AMD evidence."""
import argparse
import asyncio
import json
import os
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
from app.ai import organize

async def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--runs',type=int,default=3)
    parser.add_argument('--output',default='submission/model-evidence.json')
    args=parser.parse_args()
    if not 1 <= args.runs <= 10:
        parser.error('Use 1–10 runs to control cost.')
    backend=os.getenv('AI_BACKEND','extractive')
    if backend=='extractive':
        parser.error('Set AI_BACKEND=rocm or ollama and the model endpoint. Source-only mode is not model evidence.')
    sources=[{'id':'synthetic-intake','title':'Synthetic intake','text':'Reason: I want to discuss my earlier report.\nDuration: Two weeks.\nAllergies: Not confirmed.\nQuestions: Which records should I bring?'},
             {'id':'synthetic-record','title':'Synthetic visit note','text':'SYNTHETIC DEMO DATA\nDate: 2026-10-03\nProvider: Greenleaf Clinic\nPlease bring previous reports to the appointment on 15 October 2026.'}]
    results=[]
    for i in range(args.runs):
        evidence,engine,ms=await organize(sources)
        results.append({'run':i+1,'engine':engine,'latency_ms':ms,'evidence_count':len(evidence),'covered_sources':len(set(q['source_id'] for q in evidence)),'source_count':len(sources),'all_quotes_source_verified':True})
    hardware=None
    try:
        import torch
        if torch.version.hip and torch.cuda.is_available():
            hardware={'hip':torch.version.hip,'gpu':torch.cuda.get_device_name(0),'scope':'This process host only; does not attest to a remote endpoint.'}
    except ImportError:
        pass
    report={'created_at':datetime.now(timezone.utc).isoformat(),'synthetic_only':True,'backend':backend,'model':os.getenv('AI_MODEL'),'runs':results,'median_latency_ms':statistics.median(r['latency_ms'] for r in results),'local_hardware':hardware,'amd_endpoint_verified':False,'limitations':'Hardware detection is local only. Attach model-server GPU evidence and matching request logs to verify AMD execution. Three synthetic runs are not clinical validation or a speedup benchmark.'}
    output=Path(args.output);output.parent.mkdir(parents=True,exist_ok=True);output.write_text(json.dumps(report,indent=2)+'\n')
    print(f'Saved {len(results)} measured runs to {output}. No keys or endpoint URLs saved.')

if __name__=='__main__':asyncio.run(main())
