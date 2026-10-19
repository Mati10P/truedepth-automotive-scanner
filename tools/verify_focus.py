"""Reject capture sets without a consistent, confirmed v4 focus lock."""
import argparse
import json
from fractions import Fraction
from pathlib import Path

def time_value(stamp):
    return Fraction(stamp['value'],stamp['timescale'])

def verify(headers):
    if not headers:raise ValueError('No frames')
    profiles=set();positions=[]
    for h in headers:
        focus=h.get('capture_settings',{}).get('focus',{})
        if focus.get('state')!='locked' or focus.get('lock_confirmed') is not True or focus.get('is_adjusting') is not False or focus.get('mode_raw')!=0:
            raise ValueError('Focus not confirmed locked and stable')
        profile=focus.get('profile_id')
        if not profile:raise ValueError('Missing focus profile')
        profiles.add(profile)
        boundary=focus.get('sample_clock_boundary')
        if not boundary:raise ValueError('Missing focus boundary')
        if min(time_value(h['timestamp']),time_value(h['rgb']['timestamp']))<=time_value(boundary):
            raise ValueError('Frame precedes focus boundary')
        positions.append(float(focus['lens_position']))
    if len(profiles)!=1:raise ValueError('Multiple focus profiles')
    if not all(0<=p<=1 for p in positions) or max(positions)-min(positions)>=.0001:
        raise ValueError('Lens changed or invalid')
    return {'frames':len(headers),'focus_profile_id':next(iter(profiles)),
            'lens_min':min(positions),'lens_max':max(positions),'focus_lock_verified':True,
            'limitation':'Device-state check, not optical sharpness or dimensional validation'}

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('sequence',type=Path)
    a=p.parse_args()
    print(json.dumps(verify([json.loads(f.read_text()) for f in sorted(a.sequence.glob('frame-*/metadata.json'))]),indent=2))
