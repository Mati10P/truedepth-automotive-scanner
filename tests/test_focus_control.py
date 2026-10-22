import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch
spec=importlib.util.spec_from_file_location('control_focus',Path(__file__).resolve().parents[1]/'apps/windows/control_focus.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class FocusControlTests(unittest.TestCase):
 def test_reject_invalid_positions_before_network(self):
  for value in [-1,2,float('nan'),float('inf')]:
   with self.assertRaises(ValueError):m.set_focus('host','token',value)
 def test_waits_for_confirmation(self):
  pending={'state':'locking','lock_confirmed':False}
  ready={'state':'locked','lock_confirmed':True,'is_adjusting':False,'lens_position':.56}
  with patch.object(m,'request',side_effect=[pending,ready]) as request,patch.object(m.time,'sleep'):
   self.assertEqual(m.set_focus('host','token',.56),ready)
   self.assertEqual(request.call_count,2)
 def test_rejects_device_failure(self):
  with patch.object(m,'request',return_value={'state':'failed'}):
   with self.assertRaises(RuntimeError):m.set_focus('host','token',.56)
 def test_stable_actual_position_accepted_without_hiding_difference(self):
  wrong={'state':'locked','lock_confirmed':True,'is_adjusting':False,'lens_position':.42}
  with patch.object(m,'request',return_value=wrong),patch.object(m.time,'monotonic',side_effect=[0,0,9]),patch.object(m.time,'sleep'):
   self.assertEqual(m.set_focus('host','token',.56)['lens_position'], .42)
if __name__=='__main__':unittest.main()
