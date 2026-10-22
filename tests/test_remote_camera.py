import io
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from PIL import Image
from bmo.camera import RemotePiCamera


class RemoteCameraTests(unittest.TestCase):
    def make_camera(self, folder):
        key = Path(folder) / 'test-key'
        key.write_text('dummy fixture, not a private key')
        return RemotePiCamera('192.168.1.50', 'pi-user', str(key), '/home/pi-user/bmo-project')

    def test_each_capture_fetches_a_new_image_over_strict_ssh(self):
        images = []
        for color in ('red', 'blue'):
            image = io.BytesIO()
            Image.new('RGB', (40, 30), color).save(image, format='JPEG')
            images.append(image.getvalue())
        with tempfile.TemporaryDirectory() as folder:
            camera = self.make_camera(folder)
            with patch('bmo.camera.subprocess.run', side_effect=[subprocess.CompletedProcess([], 0, image, b'') for image in images]) as run:
                first, second = camera.capture(), camera.capture()
            self.assertNotEqual(first, second)
            self.assertEqual(run.call_count, 2)
            self.assertIn('StrictHostKeyChecking=yes', run.call_args.args[0])
            self.assertIn('BatchMode=yes', run.call_args.args[0])
            self.assertIn('bmo.remote_capture', run.call_args.args[0][-1])

    def test_failures_never_return_a_stale_image_or_remote_diagnostics(self):
        with tempfile.TemporaryDirectory() as folder:
            camera = self.make_camera(folder)
            failures = [subprocess.CompletedProcess([], 1, b'', b'private diagnostics'),
                        subprocess.CompletedProcess([], 0, b'not-an-image', b''),
                        subprocess.TimeoutExpired('ssh', 40)]
            for failure in failures:
                with patch('bmo.camera.subprocess.run', side_effect=failure if isinstance(failure, Exception) else None, return_value=failure):
                    with self.assertRaises(RuntimeError) as caught:
                        camera.capture()
                    self.assertNotIn('private diagnostics', str(caught.exception))


if __name__ == '__main__':
    unittest.main()
