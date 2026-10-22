import unittest

from tools.configure_pi_camera import configured_text


class CameraConfigTests(unittest.TestCase):
    def test_move_existing_camera_to_port_zero_preserves_other_settings(self):
        original = ('camera_auto_detect=0\ndtparam=audio=on\n[pi5]\n'
                    'dtoverlay=nospi10\n[all]\n'
                    '# BMO: Camera Module v1 OV5647 on CAM/DISP 1\ndtoverlay=ov5647\n')
        updated = configured_text(original, 0)
        self.assertEqual(updated, original.replace('CAM/DISP 1', 'CAM/DISP 0').replace(
            'dtoverlay=ov5647\n', 'dtoverlay=ov5647,cam0\n'))
        self.assertEqual(configured_text(updated, 0), updated)
        self.assertEqual(configured_text(updated, 1), original)

    def test_initial_manual_config_disables_detection_and_adds_one_overlay(self):
        original = 'camera_auto_detect=1\n[all]\ndtparam=audio=on\n'
        updated = configured_text(original, 0)
        self.assertIn('camera_auto_detect=0\n', updated)
        self.assertIn('[all]\n# BMO: Camera Module v1 OV5647 on CAM/DISP 0\ndtoverlay=ov5647,cam0\n', updated)
        self.assertEqual(updated.count('dtoverlay=ov5647'), 1)

    def test_ambiguous_or_other_camera_configuration_is_rejected(self):
        for extra in ('dtoverlay=imx708\n', 'dtoverlay=ov5647,rotation=180\n',
                      'dtoverlay=ov5647\ndtoverlay=ov5647,cam0\n',
                      'camera_auto_detect=1\n', 'camera_auto_detect=2\n'):
            with self.subTest(extra=extra), self.assertRaises(ValueError):
                configured_text('camera_auto_detect=0\n' + extra, 0)
        with self.assertRaises(ValueError):
            configured_text('[all]\n', 0)

    def test_replace_v1_with_v2_on_existing_port_without_duplicate_overlay(self):
        original = ('camera_auto_detect=0\ndtparam=audio=on\n[all]\n'
                    '# BMO: Camera Module v1 OV5647 on CAM/DISP 0\ndtoverlay=ov5647,cam0\n')
        updated = configured_text(original, 0, 'imx219')
        self.assertEqual(updated, original.replace('v1 OV5647', 'v2 IMX219').replace('ov5647', 'imx219'))
        self.assertEqual(configured_text(updated, 0, 'imx219'), updated)
        self.assertEqual(configured_text(updated, 0, 'ov5647'), original)
        self.assertIn('dtoverlay=imx219\n', configured_text(updated, 1, 'imx219'))
        self.assertNotIn(',cam0', configured_text(updated, 1, 'imx219'))

    def test_unsupported_sensor_is_rejected(self):
        with self.assertRaises(ValueError):
            configured_text('camera_auto_detect=1\n', 0, 'imx708')


if __name__ == '__main__':
    unittest.main()
