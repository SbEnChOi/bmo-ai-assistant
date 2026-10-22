from io import BytesIO
import json
import threading
import time
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from unittest.mock import Mock, patch
from PIL import Image, ImageDraw
from bmo.app import handler_for, parse_args
from bmo.conversation import Conversation
from bmo.observation import Observation
from tests.test_bmo import engine
from tests.test_emotions import response


def scene(number=0, brightness=0):
    picture = Image.new('RGB', (160, 120), (180+brightness,)*3)
    draw = ImageDraw.Draw(picture)
    x = (number % 3) * 45
    draw.rectangle((x, 15, x+40, 105), fill=(40+brightness,)*3)
    out = BytesIO(); picture.save(out, 'JPEG')
    return out.getvalue()


def result(summary='책상에 컵이 있음.', speak=False, notice='컵을 가져왔네! 뭐 마시고 있어?'):
    return {'summary': summary, 'speak': speak, 'notice': notice, 'emotion': '기쁨'}


class ObservationTests(unittest.TestCase):
    def setUp(self):
        self.e = engine(True)
        self.e.args.source = 'pi'
        self.now = [1000]
        self.o = self.e.observation = Observation(self.e, clock=lambda: self.now[0])
        self.o.enabled = True
        self.e.camera = Mock(); self.e.camera.capture.return_value = scene()
        self.e.llm.observe.return_value = result()
        self.e.mark_presence('phone'); self.e.activity('idle')
        self.addCleanup(self.e.close)

    def changed(self, number=1, seconds=31):
        self.now[0] += seconds
        self.o.ingest(scene(number)); self.now[0] += 1; self.o.ingest(scene(number))

    def baseline(self):
        self.o.ingest(scene()); self.o.analyze_once()

    def test_idle_captures_do_not_call_ai_and_first_summary_never_speaks(self):
        self.o.capture_once()
        self.e.llm.observe.assert_not_called()
        self.e.llm.observe.return_value = result(speak=True)
        self.o.analyze_once()
        self.assertEqual(len(self.o.memory), 1)
        self.assertEqual(len(self.e.reply_records), 0)
        self.assertEqual(self.e.total_calls, 1)

    def test_stable_frames_and_brightness_do_not_repeatedly_analyze_or_speak(self):
        self.baseline()
        version = self.o.scene
        self.now[0] += 31
        self.o.ingest(scene(brightness=10)); self.o.ingest(scene(brightness=10))
        self.o.analyze_once()
        self.assertEqual(self.o.scene, version)
        self.assertEqual(self.e.llm.observe.call_count, 1)
        self.now[0] += 90; self.o.ingest(scene(brightness=10))
        self.e.llm.observe.return_value = result(speak=True)
        self.o.analyze_once()
        self.assertEqual(self.e.llm.observe.call_count, 2)
        self.assertFalse(self.e.reply_records)

    def test_change_requires_two_samples_then_notice_uses_existing_audio_and_emotion(self):
        self.baseline(); version = self.o.scene
        self.now[0] += 31; self.o.ingest(scene(1)); self.o.analyze_once()
        self.assertEqual(self.o.scene, version)
        self.e.llm.observe.return_value = result(speak=True)
        self.o.ingest(scene(1)); self.o.analyze_once()
        record = self.e.snapshot()['replies'][-1]
        self.assertEqual(record['kind'], 'proactive')
        self.assertEqual(record['emotion'], '기쁨')
        self.e.speech.synthesize.assert_called_once_with(result()['notice'])
        self.assertEqual(len(self.o.notices), 1)
        self.assertEqual(self.e.total_calls, 3)

    def test_notice_cooldown_and_duplicate_suppression(self):
        self.baseline(); self.e.llm.observe.return_value = result(speak=True)
        self.changed(1); self.o.analyze_once()
        self.changed(2); self.e.llm.observe.return_value = result(speak=True, notice='책도 가져왔네.')
        self.o.analyze_once(); self.assertEqual(len(self.e.reply_records), 1)
        self.changed(0, 181); self.e.llm.observe.return_value = result(speak=True)
        self.o.analyze_once(); self.assertEqual(len(self.e.reply_records), 1)

    def test_hourly_notice_cap(self):
        self.baseline()
        self.o.notices.extend(self.now[0]-300-i for i in range(6))
        self.changed(); self.e.llm.observe.return_value = result(speak=True)
        self.o.analyze_once(); self.assertFalse(self.e.reply_records)

    def test_observer_respects_global_budget_and_leaves_voice_headroom(self):
        self.e.args.max_calls = 23
        self.e.calls.extend([time.monotonic()]*3)
        self.o.ingest(scene()); self.o.analyze_once()
        self.e.llm.observe.assert_not_called()
        self.assertFalse(self.o.analyses)

    def test_background_hourly_cap_does_not_stop_capturing(self):
        self.o.analyses.extend([self.now[0]]*30)
        self.o.capture_once(); self.o.analyze_once()
        self.assertTrue(self.o.frames()); self.e.llm.observe.assert_not_called()

    def test_pause_discards_inflight_result_and_closes_camera(self):
        self.o.ingest(scene())
        self.e.llm.observe.side_effect = lambda *args: (self.o.configure(False, True), result())[1]
        self.o.analyze_once()
        self.assertFalse(self.o.memory); self.assertFalse(self.o.frames())
        self.e.camera.close.assert_called_once()

    def test_reset_discards_inflight_summary(self):
        self.o.ingest(scene())
        self.e.llm.observe.side_effect = lambda *args: (self.e.cancel(clear=True), result())[1]
        self.o.analyze_once(); self.assertFalse(self.o.memory)

    def test_capture_finishing_after_reset_cannot_repopulate_old_generation(self):
        self.e.camera.capture.side_effect = lambda: (self.o.clear(), scene())[1]
        self.o.capture_once(); self.assertFalse(self.o.frames())

    def test_recording_started_during_analysis_discards_notice_even_if_finished(self):
        self.baseline(); self.changed()
        def analyze(*args):
            self.e.activity('listening'); self.e.activity('idle')
            return result(speak=True)
        self.e.llm.observe.side_effect = analyze
        self.o.analyze_once(); self.assertFalse(self.e.reply_records)
        self.assertEqual(len(self.o.memory), 2)

    def test_user_starts_during_tts_discards_notice(self):
        self.baseline(); self.changed(); self.e.llm.observe.return_value = result(speak=True)
        self.e.speech.synthesize.side_effect = lambda _: (self.e.activity('permission'), b'mp3')[1]
        self.o.analyze_once(); self.assertFalse(self.e.reply_records)

    def test_tts_finishing_after_scene_changed_or_expired_drops_notice(self):
        for cause in ('changed', 'expired'):
            self.o.clear(); self.o.last_analysis = float('-inf')
            self.baseline(); self.changed(); self.e.llm.observe.return_value = result(speak=True)
            def synthesize(_):
                if cause == 'changed': self.changed(2, seconds=1)
                else: self.now[0] += 21
                return b'mp3'
            self.e.speech.synthesize.side_effect = synthesize
            self.o.analyze_once(); self.assertFalse(self.e.reply_records)

    def test_no_first_speech_when_phone_absent_hidden_or_proactive_disabled(self):
        for setting in ('absent', 'hidden', 'disabled'):
            with self.subTest(setting=setting):
                self.o.clear(); self.o.last_analysis = float('-inf'); self.baseline(); self.changed()
                self.e.llm.observe.return_value = result(speak=True)
                self.e.mark_presence('phone'); self.e.activity('idle'); self.o.proactive = True
                if setting == 'absent': self.e.presence['phone'] = 0
                if setting == 'hidden': self.e.activity('hidden')
                if setting == 'disabled': self.o.proactive = False
                self.o.analyze_once(); self.assertFalse(self.e.reply_records)

    def test_busy_voice_defers_but_realtime_still_updates_scene_memory(self):
        self.o.ingest(scene()); self.e.busy = True
        self.o.analyze_once(); self.e.llm.observe.assert_not_called()
        self.e.busy = False
        session = self.e.realtime.start(mock=True)
        self.o.analyze_once(); self.e.llm.observe.assert_called_once()
        self.assertTrue(self.o.memory)
        self.assertFalse(self.e.reply_records)
        self.e.realtime.stop(session['session_id'])

    def test_stale_images_not_attached_but_past_summary_has_age_and_expires(self):
        self.baseline(); self.now[0] += 6
        self.assertFalse(self.o.frames()); self.assertIn('6초 전', self.o.context())
        self.now[0] += 901; self.assertEqual(self.o.context(), '')

    def test_realtime_notice_waits_for_quiet_and_uses_same_session_without_tts(self):
        self.baseline();session=self.e.realtime.start(mock=True);a=self.e.realtime.active
        self.changed();self.e.llm.observe.return_value=result(speak=True);self.o.analyze_once()
        self.assertTrue(self.o.pending_notice);self.assertFalse(self.e.reply_records)
        a.update(quiet_ms=3999,input_active=False)
        self.assertIsNone(self.o.take_notice(a));a['quiet_ms']=4000
        notice=self.o.take_notice(a);self.assertEqual(notice['text'],result()['notice'])
        self.assertEqual(len(self.o.notices),1);self.e.speech.synthesize.assert_not_called()
        self.assertIsNone(self.o.take_notice(a));self.e.realtime.stop(session['session_id'])

    def test_pending_notice_drops_on_new_input_pause_scene_or_session(self):
        for cause in ('input','pause','scene','session'):
            with self.subTest(cause=cause):
                self.o.clear();self.o.last_analysis=float('-inf');self.baseline()
                session=self.e.realtime.start(mock=True);a=self.e.realtime.active
                self.changed();self.e.llm.observe.return_value=result(speak=True);self.o.analyze_once()
                self.assertTrue(self.o.pending_notice);a.update(quiet_ms=5000)
                if cause=='input':a['input_serial']=1
                elif cause=='pause':self.o.configure(False,True);self.o.enabled=True
                elif cause=='scene':self.changed(2,seconds=1)
                else:a={**a,'id':'other'}
                self.assertIsNone(self.o.take_notice(a));self.e.realtime.stop(session['session_id'])

    def test_pi_camera_defaults_to_observing_with_explicit_opt_out(self):
        self.assertTrue(parse_args(['--source','pi']).auto_observe)
        self.assertFalse(parse_args(['--source','pi','--no-auto-observe']).auto_observe)

    def test_short_utterance_between_heartbeats_invalidates_older_notice(self):
        self.baseline();session=self.e.realtime.start(mock=True);a=self.e.realtime.active
        self.changed();self.e.llm.observe.return_value=result(speak=True);self.o.analyze_once()
        self.assertTrue(self.o.pending_notice)
        self.e.realtime.heartbeat({'session_id':a['id'],'quiet_ms':5000,'input_active':False,'turn_serial':1})
        self.assertIsNone(self.o.take_notice(a));self.e.realtime.stop(session['session_id'])

    def test_question_automatically_uses_latest_frames_and_memory_without_toggle(self):
        self.baseline(); self.e.turn(question='주변에 뭐 있어?')
        kwargs = self.e.llm.reply.call_args.kwargs
        self.assertIn('과거 요약', kwargs['observation'])
        self.assertIn('파이 카메라', kwargs['frames'][-1].caption())
        self.assertNotIn('image_url', json.dumps(self.e.history))

    def test_camera_failure_expires_visual_input_without_stopping_voice(self):
        self.baseline(); self.now[0] += 6
        self.e.camera.capture.side_effect = RuntimeError('unplugged')
        self.o.capture_once(); self.assertFalse(self.o.snapshot()['fresh'])
        self.assertTrue(self.o.snapshot()['error'])
        self.e.turn(question='안녕'); self.assertNotIn('frames', self.e.llm.reply.call_args.kwargs)

    def test_failed_analysis_is_throttled_and_does_not_speak(self):
        self.o.ingest(scene()); self.e.llm.observe.side_effect = RuntimeError('offline')
        self.o.analyze_once(); self.o.analyze_once()
        self.assertEqual(self.e.llm.observe.call_count, 1); self.assertFalse(self.e.reply_records)

    @patch('bmo.conversation.api_key', return_value='test-key')
    def test_vision_payload_is_bounded_structured_and_not_stored(self, _):
        self.o.ingest(scene())
        with patch('bmo.conversation.api_request', return_value=response(json.dumps(result()))) as request:
            out = Conversation('openai', 'test-model').observe(self.o.frames(), '이전 장면', ['앞서 건넨 말'])
        self.assertEqual(out['emotion'], '기쁨')
        payload = json.loads(request.call_args.args[2])
        self.assertFalse(payload['store']); self.assertEqual(request.call_args.kwargs['timeout'], 8)
        self.assertEqual(payload['text']['format']['schema']['additionalProperties'], False)
        self.assertEqual(payload['input'][0]['content'][-1]['type'], 'input_image')
        with patch('bmo.conversation.api_request', return_value=response('{"summary":123}')):
            with self.assertRaises(RuntimeError): Conversation('openai', 'test-model').observe(self.o.frames())

    def test_invalid_start_flags_are_rejected(self):
        with patch('sys.stderr', new=__import__('io').StringIO()):
            with self.assertRaises(SystemExit): parse_args(['--auto-observe'])


class ObservationHttpTests(unittest.TestCase):
    def setUp(self):
        self.e = engine(); self.e.args.source = 'pi'
        self.o = self.e.observation = Observation(self.e)
        self.e.camera = Mock(); self.o.start = Mock()
        self.server = ThreadingHTTPServer(('127.0.0.1', 0), handler_for(self.e))
        self.thread = threading.Thread(target=self.server.serve_forever); self.thread.start()
        self.url = f'http://127.0.0.1:{self.server.server_port}'

    def tearDown(self):
        self.e.close(); self.server.shutdown(); self.server.server_close(); self.thread.join()

    def post(self, path, data, token=True):
        headers = {'Content-Type': 'application/json'}
        if token: headers['X-BMO-Token'] = self.e.token
        request = urllib.request.Request(self.url + '/api/' + path, json.dumps(data).encode(), headers)
        with urllib.request.urlopen(request) as response: return json.load(response)

    def test_settings_require_token_validate_types_and_pause_clears_memory(self):
        with self.assertRaises(urllib.error.HTTPError) as caught:
            self.post('observation', {'enabled': True, 'proactive': True}, token=False)
        self.assertEqual(caught.exception.code, 403)
        with self.assertRaises(urllib.error.HTTPError):
            self.post('observation', {'enabled': 'true', 'proactive': True})
        out = self.post('observation', {'enabled': True, 'proactive': True})
        self.assertTrue(out['enabled']); self.o.ingest(scene())
        out = self.post('observation', {'enabled': False, 'proactive': True})
        self.assertFalse(out['fresh']); self.assertFalse(self.o.frames())

    def test_auto_realtime_frames_are_owned_throttled_bounded_and_removed_on_pause(self):
        self.o.enabled = True; self.o.ingest(scene())
        session = self.e.realtime.start(mock=True)
        data = {'session_id': session['session_id'], 'manual': False}
        first = self.post('realtime/frames', data)
        self.assertTrue(first['automatic']); self.assertEqual(len(first['frames']), 1)
        self.assertTrue(self.post('realtime/frames', data)['unchanged'])
        with self.assertRaises(urllib.error.HTTPError): self.post('realtime/frames', {**data, 'session_id': 'not-owner'})
        self.e.realtime.active.update(visual_count=240, visual_sent_at=0)
        self.assertTrue(self.post('realtime/frames', {**data, 'force': True})['limited'])
        self.o.configure(False, True)
        self.assertEqual(self.post('realtime/frames', data)['frames'], [])

    def test_activity_and_new_asset_route(self):
        self.post('phone/activity', {'phase': 'listening'})
        self.assertEqual(self.e.phone_activity['phase'], 'listening')
        with self.assertRaises(urllib.error.HTTPError): self.post('phone/activity', {'phase': 'invalid'})
        with urllib.request.urlopen(self.url + '/observation.js') as response: self.assertEqual(response.status, 200)
