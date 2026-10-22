import copy,unittest
from pathlib import Path
from test_rules import sample

class LayerInterfaces(unittest.TestCase):
    def config(self):
        c=sample();m=copy.deepcopy(c['materials'][0]);m['id']='LOWER';m['properties']['cref']=40
        c['materials'].append(m);c['layer_materials']['L2']='LOWER'
        c['geology']['boreholes'][1]['bottoms'][0]=-9
        for w in c['walls']:w['interface_material']='AUTO'
        return c
    def test_schema_accepts_auto_and_keeps_custom_override(self):
        from pitbuilder.schema import validate_config
        c=validate_config(self.config(),Path('.'))
        self.assertEqual(c['walls'][0]['interface_material'],'AUTO')
        c['walls'][0]['interface_material']='WALL'
        with self.assertRaises(ValueError):validate_config(c,Path('.'))
    def test_sloping_contacts_differ_at_two_walls(self):
        from pitbuilder.interfaces import wall_segments,segment_layer
        c=self.config();left=wall_segments(c,c['walls'][0]);right=wall_segments(c,c['walls'][1])
        self.assertEqual([s['material_id'] for s in left],['SOIL','LOWER'])
        self.assertAlmostEqual(left[0]['bottom'],-6)
        self.assertAlmostEqual(right[0]['bottom'],-8)
        self.assertEqual(segment_layer(left,-12,-6)['layer_id'],'L2')
        with self.assertRaises(ValueError):segment_layer(left,-7,-5)
    def test_zero_thickness_skipped_without_inventing_layer(self):
        from pitbuilder.interfaces import wall_segments
        c=self.config()
        for h in c['geology']['boreholes']:h['bottoms'][0]=h['ground']
        segments=wall_segments(c,c['walls'][0])
        self.assertEqual(len(segments),1)
        self.assertEqual(segments[0]['layer_id'],'L2')
    def test_explicit_material_preserved_but_cut_positions_follow_geology(self):
        from pitbuilder.interfaces import wall_segments
        c=self.config();c['walls'][0]['interface_material']='SOIL'
        segments=wall_segments(c,c['walls'][0])
        self.assertEqual([s['material_id'] for s in segments],['SOIL','SOIL'])
        self.assertAlmostEqual(segments[0]['bottom'],-6)
    def test_horizontal_slab_resolves_both_sides_and_rejects_cross_layer(self):
        from pitbuilder.interfaces import horizontal_adjacent_layer
        c=self.config()
        self.assertEqual(horizontal_adjacent_layer(c,10,30,-10,True),'L2')
        with self.assertRaises(ValueError):horizontal_adjacent_layer(c,10,30,-7,True)

if __name__=='__main__':unittest.main()
