import copy
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from verify_focus import verify

def frame():
    return {'timestamp':{'value':21,'timescale':10},'rgb':{'timestamp':{'value':21,'timescale':10}},
        'capture_settings':{'focus':{'state':'locked','lock_confirmed':True,'is_adjusting':False,
            'mode_raw':0,'profile_id':'test','lens_position':.5,'sample_clock_boundary':{'value':2,'timescale':1}}}}

class FocusTests(unittest.TestCase):
    def test_stable_lock(self):self.assertTrue(verify([frame(),frame()])['focus_lock_verified'])
    def test_reject_old_adjusting_or_preboundary(self):
        cases=[{},frame(),frame(),frame()]
        cases[1]['capture_settings']['focus']['is_adjusting']=True
        cases[2]['timestamp']['value']=20
        cases[3]['rgb']['timestamp']['value']=19
        for h in cases:
            with self.assertRaises((ValueError,KeyError)):verify([h])
    def test_changed_profile_or_lens(self):
        for key,val in [('profile_id','other'),('lens_position',.52)]:
            other=copy.deepcopy(frame());other['capture_settings']['focus'][key]=val
            with self.assertRaises(ValueError):verify([frame(),other])

if __name__=='__main__':unittest.main()
