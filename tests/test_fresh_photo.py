"""Requested photographs must be new exposures, not observation cache hits."""
import threading
import time
import unittest
from unittest.mock import Mock

from bmo.camera import Camera
from bmo.photo_intent import requests_photo
from tests.test_bmo import engine
from tests import test_live as live_tests
from tests.test_observation import scene


class PhotoTests(unittest.TestCase):
    def test_korean_requests_and_refusals(self):
        for text in ('사진 찍어줘', '사진 한 장 좀 찍어줄래?', '카메라로 촬영해 줘', '다시 찍어 줘',
                     '새로 촬영해줘', '사진을 찍어서 뭐가 보이는지 알려줘', 'take a photo'):
            self.assertTrue(requests_photo(text), text)
        for text in ('사진 찍지 마', '다시 찍지 말고 설명해 줘', '사진 촬영 취소',
                     '예전 사진에 뭐가 있었지?', '사진 찍는 방법이 뭐야?', '사진 찍어본 적 있어?',
                     '아까 사진 찍어서 뭐가 보였다고 했지?', "don't take a photo", 'do not take a picture', '안녕'):
            self.assertFalse(requests_photo(text), text)

    def test_picamera_discards_queued_frame_and_releases_request(self):
        from PIL import Image
        c = Camera('pi')
        c.device = Mock()
        request = c.device.capture_request.return_value
        request.make_image.return_value = Image.new('RGB', (40, 30), 'red')
        self.assertTrue(c.capture().startswith(b'\xff\xd8'))
        c.device.capture_request.assert_called_once_with(flush=True)
        request.release.assert_called_once()
        request.make_image.side_effect = RuntimeError('bad frame')
        with self.assertRaises(RuntimeError):
            c.capture()
        self.assertEqual(request.release.call_count, 2)

    def setup_engine(self):
        e = engine(True)
        self.addCleanup(e.close)
        e.args.source = 'pi'
        e.camera = Mock()
        e.observation.enabled = True
        e.observation.ingest(scene(0))
        e.observation.memory.append({'received':e.observation.clock(), 'timestamp':'old', 'summary':'예전 빨간 우산'})
        e.history = [{'role':'assistant', 'content':'예전 빨간 우산이 보여.'}]
        return e

    def test_ptt_request_captures_even_when_scene_toggle_off_and_replaces_cache(self):
        e = self.setup_engine()
        e.camera.capture.side_effect = [scene(1), scene(2)]
        old = e.observation.latest.jpeg
        self.assertEqual(e.scene_mode, 'off')
        for i in range(2):
            e.turn(question='사진 다시 찍어줘', use_camera=False)
            call = e.llm.reply.call_args
            frames = call.kwargs['frames']
            self.assertEqual(len(frames), 1)
            self.assertNotEqual(frames[0].jpeg, old)
            self.assertEqual(call.args[1], [])
            self.assertNotIn('빨간 우산', call.kwargs['observation'])
            self.assertEqual(e.photo_serial, i+1)
            self.assertEqual(e.observation.latest.jpeg, frames[0].jpeg)
            self.assertFalse(e.observation.memory)
            old = frames[0].jpeg
        self.assertEqual(e.camera.capture.call_count, 2)

    def test_capture_failure_does_not_analyze_previous_frame(self):
        e = self.setup_engine()
        e.camera.capture.side_effect = RuntimeError('disconnected')
        with self.assertRaises(RuntimeError):
            e.turn(question='사진 찍어줘')
        e.llm.reply.assert_not_called()
        self.assertIsNone(e.last_photo)

    def test_single_request_does_not_enable_background_observation(self):
        e = self.setup_engine()
        e.observation.enabled = False
        e.camera.capture.return_value = scene(1)
        e.turn(question='사진 찍어줘')
        self.assertFalse(e.observation.enabled)
        self.assertFalse(e.observation.frames())
        self.assertTrue(e.last_photo)

    def test_cancelled_capture_cannot_publish_or_replace_memory(self):
        e = self.setup_engine()
        old = e.observation.latest
        entered, release = threading.Event(), threading.Event()
        self.addCleanup(release.set)
        def capture():
            entered.set(); release.wait(2); return scene(1)
        e.camera.capture.side_effect = capture
        result = []
        t = threading.Thread(target=lambda: result.append(e.turn(question='사진 찍어줘')))
        t.start(); self.assertTrue(entered.wait(1))
        e.cancel(); release.set(); t.join(2)
        self.assertEqual(result, [{'cancelled':True}])
        self.assertIs(e.observation.latest, old)
        self.assertIsNone(e.last_photo)
        e.llm.reply.assert_not_called()


class FreshLiveTests(unittest.TestCase):
    # Share only the trusted sideband fixture, not its test cases.
    setUp = live_tests.LiveTests.setUp
    start = live_tests.LiveTests.start
    emit = live_tests.LiveTests.emit
    user = live_tests.LiveTests.user
    delegate = live_tests.LiveTests.delegate
    wait_backend = live_tests.LiveTests.wait_backend
    results = live_tests.LiveTests.results

    def camera(self):
        self.e.args.source = 'pi'
        self.e.camera = Mock()
        self.e.camera.capture.return_value = scene(1)
        self.e.observation.enabled = True
        self.e.observation.ingest(scene(0))

    def test_live_request_uses_only_new_photo_not_manual_upload_or_cached_scene(self):
        _, a = self.start(); self.camera()
        self.e.scene_mode, self.e.admin_image = 'upload', b'past upload'
        self.e.live.heartbeat({'session_id':a['id'], 'manual':True})
        self.e.observation.context = Mock(return_value='예전 빨간 우산')
        self.user(a, '사진 찍어줘'); self.delegate(a); self.wait_backend()
        call = self.e.llm.reply.call_args
        self.e.camera.capture.assert_called_once()
        self.assertEqual(call.args[1:3], ([], None))
        self.assertEqual([f.jpeg for f in call.kwargs['frames']], [self.e.last_photo.jpeg])
        self.assertNotIn('빨간 우산', call.kwargs['observation'])
        self.assertIn('새 사진 #1', self.results(a)[0]['content'])
        self.user(a, '다시 찍어줘'); self.delegate(a, 'next'); self.wait_backend()
        self.assertEqual(self.e.camera.capture.call_count, 2)
        self.assertIn('새 사진 #2', self.results(a)[1]['content'])

    def test_trusted_transcript_triggers_capture_without_model_delegation(self):
        _, a = self.start(); self.camera()
        self.user(a, '사진 찍어줘')
        self.e.live._photo_fallback(a, a['transcript_version'])
        self.wait_backend()
        self.e.camera.capture.assert_called_once()
        self.assertIsNone(self.results(a)[0]['delegation_id'])
        self.delegate(a, 'late-delegation'); self.wait_backend()
        self.assertEqual(self.e.camera.capture.call_count, 1)
        self.assertEqual(len(self.results(a)), 1)

    def test_partial_transcript_after_delegation_does_not_lose_photo_request(self):
        _, a = self.start(); self.camera()
        self.user(a, '사진 찍어'); self.delegate(a)
        self.user(a, '줘. 지금 뭐가 보이는지 알려줘')
        self.e.live._photo_fallback(a, a['transcript_version']); self.wait_backend()
        self.assertEqual(self.e.camera.capture.call_count, 1)
        self.assertIn('지금 뭐가', self.e.llm.reply.call_args.args[0])
        self.assertEqual(len(self.results(a)), 1)

    def test_live_failed_new_photo_never_uses_old_photo(self):
        _, a = self.start(); self.camera()
        self.e.camera.capture.side_effect = RuntimeError('disconnected')
        self.user(a, '사진 찍어줘'); self.delegate(a); self.wait_backend()
        self.e.llm.reply.assert_not_called()
        self.assertIn('이전 사진으로 대신 답하지', self.results(a)[0]['content'])

    def test_microphone_heartbeat_does_not_invalidate_trusted_photo_request(self):
        _, a = self.start(); self.camera()
        self.user(a, '사진 찍어줘')
        version = a['transcript_version']
        self.e.live.heartbeat({'session_id':a['id'], 'input_active':True})
        self.e.live.heartbeat({'session_id':a['id'], 'input_active':False})
        self.assertNotEqual(a['input_serial'], version)
        self.e.live._photo_fallback(a, version); self.wait_backend()
        self.e.camera.capture.assert_called_once()
        self.assertEqual(len(self.results(a)), 1)

    def test_new_input_during_capture_discards_older_photo(self):
        _, a = self.start(); self.camera()
        entered, release = threading.Event(), threading.Event()
        self.addCleanup(release.set)
        def capture():
            entered.set(); release.wait(2); return scene(1)
        self.e.camera.capture.side_effect = capture
        self.user(a, '사진 찍어줘'); self.delegate(a); self.assertTrue(entered.wait(1))
        self.user(a, ' 아니 사진 찍지 마')
        release.set(); self.wait_backend()
        self.assertFalse(self.results(a))
        self.assertIsNone(self.e.last_photo)
        self.e.llm.reply.assert_not_called()

    def test_two_delegations_for_one_utterance_share_the_new_exposure(self):
        _, a = self.start(); self.camera()
        entered, release = threading.Event(), threading.Event()
        self.addCleanup(release.set)
        def reply(*args, **kwargs):
            entered.set(); release.wait(2); return '새로 촬영한 컵이 보여.'
        self.e.llm.reply.side_effect = reply
        self.user(a, '사진 찍어줘'); self.delegate(a, 'first')
        self.assertTrue(entered.wait(1))
        self.delegate(a, 'second'); release.set(); self.wait_backend()
        self.e.camera.capture.assert_called_once()
        self.assertEqual(len(self.results(a)), 1)
        self.assertTrue(any(ev['delegation_id'] == 'second' and ev['type'] == 'session.thinking.append'
                            for ev in a['sideband'].sent))


if __name__ == '__main__':
    unittest.main()
