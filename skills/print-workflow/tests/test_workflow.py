"""Isolated synthetic state tests. Quotes below are fixtures, never real approvals."""
import json
import tempfile
import sys
import zipfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import trimesh
import workflow as w
from mesh_check import check_stl
from bambu import inspect_3mf




class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name)
        self.sliced = self.base / 'synthetic.3mf'
        # This is a parser fixture, not printable geometry or an approved print job.
        with zipfile.ZipFile(self.sliced, 'w') as z:
            z.writestr('Metadata/plate_1.gcode', '; HEADER_BLOCK_START\n; total layer number: 50\n; HEADER_BLOCK_END\nM109 S220\n')
            z.writestr('Metadata/project_settings.config', json.dumps({'printer_model': 'Bambu Lab H2S'}))
            z.writestr('Metadata/slice_info.config', '<config><plate><metadata key="prediction" value="562"/></plate></config>')
        self.project = Path(w.initialize('测试项目', 'blender', self.base)['project'])
        self.req = self.project / '01-方案/需求与方案.md'
        self.image = self.project / '01-方案/fixture.png'
        self.image.write_bytes(b'SYNTHETIC image fixture; not a real preview')

    def tearDown(self):
        self.temp.cleanup()

    def design(self):
        w.submit(self.project, 'design', [self.req, self.image])
        w.confirm(self.project, 'design', 'SYNTHETIC TEST ONLY')

    def model(self):
        self.design()
        self.source = self.project / '02-源文件/fixture.blend'
        self.source.write_bytes(b'SYNTHETIC source fixture; not a model')
        self.stl = self.project / '03-打印文件/cube.stl'
        trimesh.creation.box(extents=[10, 10, 10]).export(self.stl)
        self.report = self.project / '05-检查/mesh.json'
        w.save(self.report, check_stl(self.stl))
        w.submit(self.project, 'model', [self.source, self.stl, self.image, self.report])
        w.confirm(self.project, 'model', 'SYNTHETIC TEST ONLY')

    def test_new_project_and_unapproved_import(self):
        self.assertEqual(w.status(self.project)['stages']['design'], 'pending_or_changed')
        with patch('workflow.subprocess.Popen') as launch:
            with self.assertRaises(ValueError): w.open_bambu(self.project, self.image)
            launch.assert_not_called()

    def test_missing_preview_rejected(self):
        with self.assertRaises(ValueError): w.submit(self.project, 'design', [self.req])

    def test_change_after_submission_cannot_be_confirmed(self):
        w.submit(self.project, 'design', [self.req, self.image])
        self.image.write_bytes(b'new version')
        with self.assertRaises(ValueError): w.confirm(self.project, 'design', 'SYNTHETIC TEST ONLY')

    def test_upstream_change_invalidates_model_and_import(self):
        self.model()
        self.req.write_text('changed dimensions', encoding='utf-8')
        self.assertEqual(w.status(self.project)['stages']['model'], 'pending_or_changed')
        with patch('workflow.subprocess.Popen') as launch:
            with self.assertRaises(ValueError): w.open_bambu(self.project, self.stl)
            launch.assert_not_called()

    def test_resubmission_removes_downstream_approval(self):
        self.model()
        w.submit(self.project, 'design', [self.req, self.image])
        self.assertNotIn('model', w.read_project(self.project)[1]['stages'])

    def test_missing_current_mesh_report_rejected(self):
        self.model()
        self.stl.write_bytes(self.stl.read_bytes() + b'changed')
        with self.assertRaises(ValueError):
            w.submit(self.project, 'model', [self.source, self.stl, self.image, self.report])

    def test_mesh_open_surface_fails_and_cube_dimensions(self):
        mesh = trimesh.creation.box(extents=[10, 20, 30])
        closed = self.base / 'closed.stl'; mesh.export(closed)
        report = check_stl(closed)
        self.assertTrue(report['basic_mesh_checks_passed'])
        self.assertEqual(report['dimensions_mm'], [10, 20, 30])
        mesh.update_faces(list(range(len(mesh.faces) - 1)))
        opened = self.base / 'opened.stl'; mesh.export(opened)
        self.assertFalse(check_stl(opened)['basic_mesh_checks_passed'])

    def test_reserved_name_and_existing_folder(self):
        for name in ['../escape', 'CON', 'bad.', 'a:b']:
            with self.assertRaises(ValueError): w.initialize(name, 'fusion', self.base)
        with self.assertRaises(ValueError): w.initialize('测试项目', 'fusion', self.base)

    def test_package_requires_slice_then_contains_only_confirmed_evidence(self):
        self.model()
        with self.assertRaises(ValueError): w.package(self.project)
        review = self.project / '05-检查/切片审查.md'
        review.write_text('SYNTHETIC review fixture; not print approval', encoding='utf-8')
        w.submit(self.project, 'slice', [self.sliced, review])
        w.confirm(self.project, 'slice', 'SYNTHETIC TEST ONLY')
        package = w.package(self.project)
        self.assertTrue(Path(package['package']).is_file())
        self.assertEqual(package['physical_validation'], 'not_verified')

    def test_synthetic_bambu_parser_fixture(self):
        report = inspect_3mf(self.sliced)
        self.assertTrue(report['sliced'])
        self.assertEqual(report['gcode'][0]['metadata']['total layer number'], '50')
        self.assertEqual(report['settings']['printer_model'], 'Bambu Lab H2S')
        self.assertEqual(report['plates'][0]['metadata']['prediction'], '562')


if __name__ == '__main__':
    unittest.main(verbosity=2)
