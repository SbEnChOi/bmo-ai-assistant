import subprocess
import unittest
from unittest.mock import Mock, patch
from bmo.audio_controls import AudioControls


class AudioControlTests(unittest.TestCase):
    def controls(self):
        c = AudioControls()
        c.command = '/usr/bin/wpctl'
        return c

    def test_read_percent_mute_and_missing_device(self):
        c = self.controls()
        c.run = Mock(side_effect=['node.name = "usb"', 'Volume: 0.39 [MUTED]', RuntimeError('gone')])
        state = c.snapshot()
        self.assertEqual(state['speaker'], {'available': True, 'volume': 39, 'muted': True})
        self.assertFalse(state['microphone']['available'])

    def test_no_control_on_unsupported_system_or_dummy_output(self):
        c = self.controls(); c.command = None
        self.assertFalse(c.snapshot()['speaker']['available'])
        c.command = '/usr/bin/wpctl'; c.run = Mock(return_value='node.name = "auto_null"')
        self.assertFalse(c.snapshot()['speaker']['available'])

    def test_untrusted_devices_and_out_of_range_values_never_run_commands(self):
        c = self.controls(); c.run = Mock()
        for device, value in [('speaker', -1), ('microphone', 101), ('speaker', True), ('speaker', 42.5), ('speaker;reboot', 50), ([], 50)]:
            with self.subTest(device=device, value=value), self.assertRaises(ValueError):
                c.set_volume(device, value)
        c.run.assert_not_called()

    def test_microphone_setting_is_read_back_and_unmuted_without_recording(self):
        c = self.controls()
        c.run = Mock(side_effect=['node.name = "usb"', 'Volume: 0.39', '', '', 'node.name = "usb"', 'Volume: 0.44'])
        self.assertEqual(c.set_volume('microphone', 44)['microphone']['volume'], 44)
        self.assertIn(('set-volume', '@DEFAULT_AUDIO_SOURCE@', '0.44'), [call.args for call in c.run.call_args_list])
        self.assertIn(('set-mute', '@DEFAULT_AUDIO_SOURCE@', '0'), [call.args for call in c.run.call_args_list])

    def test_subprocess_timeout_is_reported_without_command_output(self):
        c = self.controls()
        with patch('bmo.audio_controls.subprocess.run', side_effect=subprocess.TimeoutExpired('wpctl', 3)):
            with self.assertRaisesRegex(RuntimeError, 'USB'):
                c.run('get-volume', '@DEFAULT_AUDIO_SOURCE@')

    def test_unplugged_device_cannot_be_changed(self):
        c = self.controls(); c.read = Mock(return_value={'available': False}); c.run = Mock()
        with self.assertRaises(ValueError): c.set_volume('speaker', 50)
        c.run.assert_not_called()
