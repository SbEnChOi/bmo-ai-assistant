from pathlib import Path
import tempfile
import unittest

from tools.configure_pi_display import BLOCK, BEGIN, END, configured_text, save_config


class DisplayConfigTests(unittest.TestCase):
    def test_preserves_working_pi5_hdmi_camera_and_other_spi_controller(self):
        original = ('#dtparam=spi=on\ndtparam=audio=on\ncamera_auto_detect=0\n'
                    'dtoverlay=vc4-kms-v3d\n[pi5]\ndtoverlay=nospi10\n'
                    '[all]\ndtoverlay=imx219,cam0\n')
        updated = configured_text(original)
        self.assertTrue(updated.startswith(original))
        self.assertTrue(updated.endswith(BLOCK))
        self.assertEqual(configured_text(updated), updated)

    def test_rejects_custom_touch_and_spi0_conflicts(self):
        for line in ('dtoverlay=ads7846,penirq=24', 'dtoverlay=piscreen',
                     'dtoverlay=spi0-1cs', 'dtparam=spi=off', 'dtparam=audio=on,spi=0',
                     'include custom.txt'):
            with self.subTest(line=line), self.assertRaises(ValueError):
                configured_text('[all]\n' + line + '\n')

    def test_rejects_changed_duplicate_or_incomplete_managed_block(self):
        for original in (BLOCK.replace('penirq=25', 'penirq=24'), BLOCK + BLOCK,
                         BEGIN + '\n', END + '\n', BLOCK + '\ndtparam=spi=off\n'):
            with self.subTest(original=original), self.assertRaises(ValueError):
                configured_text(original)

    def test_normalizes_missing_final_newline_and_does_not_enable_commented_settings(self):
        updated = configured_text('# dtoverlay=ads7846\n[pi5]')
        self.assertIn('[pi5]\n\n' + BEGIN + '\n[all]\n', updated)
        self.assertEqual(configured_text(updated), updated)

    def test_backup_retains_original_before_replacement(self):
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / 'config.txt'
            original = 'camera_auto_detect=0\ndtoverlay=imx219,cam0\n'
            config.write_text(original)
            updated = configured_text(original)
            backup = save_config(config, updated)
            self.assertEqual(backup.read_text(), original)
            self.assertEqual(config.read_text(), updated)
            self.assertNotEqual(backup, config)
            self.assertEqual(len(list(config.parent.glob('.bmo-touch-*'))), 0)


if __name__ == '__main__':
    unittest.main()
