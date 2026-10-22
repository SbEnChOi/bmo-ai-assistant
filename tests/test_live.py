"""Offline contracts: no microphone, device, or paid OpenAI requests."""
import json
import threading
import time
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from unittest.mock import Mock, patch

from tests.test_bmo import engine
from bmo.live import Live, short_content
from bmo.app import handler_for


class FakeSideband:
    instances = []

    def __init__(self, session_id, key, on_event, on_error):
        self.session_id, self.on_event, self.on_error = session_id, on_event, on_error
        self.sent, self.closed = [], False
        self.instances.append(self)

    def start(self):
        pass

    def send(self, event):
        self.sent.append(event)
        if event['type'] == 'session.close':
            self.on_event({'type': 'session.closed', 'usage': {'seconds': 9.5}})

    def close(self):
        self.closed = True


class LiveTests(unittest.TestCase):
    def setUp(self):
        self.e = engine(True)
        self.addCleanup(self.e.close)
        self.stack = []
        for target, value in [('bmo.live.LiveSideband', FakeSideband),
                              ('bmo.live.ensure_transport', Mock()),
                              ('bmo.live.api_key', Mock(return_value='test-key'))]:
            p = patch(target, value)
            p.start()
            self.addCleanup(p.stop)
        self.request = patch('bmo.live.api_request', return_value={
            'session': {'id': 'sess_opaque_1'}, 'transport': {'type': 'webrtc', 'sdp': 'v=0\r\nanswer'}}).start()
        self.addCleanup(patch.stopall)

    def start(self):
        result = self.e.live.start('v=0\r\noffer')
        return result, self.e.live.active

    def test_json_handshake_voice_and_no_key_to_browser(self):
        result, a = self.start()
        args, kwargs = self.request.call_args
        self.assertEqual(args[0], 'https://api.openai.com/v1/live/sessions')
        payload = json.loads(args[2])
        self.assertEqual(payload['session']['model'], 'gpt-live-1')
        self.assertEqual(payload['session']['audio']['output']['voice'], 'noeul')
        self.assertEqual(payload['session']['delegation'], {'type': 'client'})
        self.assertEqual(payload['transport']['sdp'], 'v=0\r\noffer')
        self.assertNotIn('test-key', json.dumps(result))
        self.assertEqual(a['sideband'].session_id, 'sess_opaque_1')
        self.assertEqual(a['sideband'].sent, [])  # no duplicate session.start

    def test_one_voice_session_across_versions(self):
        result, _ = self.start()
        with self.assertRaises(ValueError):
            self.e.realtime.start(mock=True)
        with self.assertRaises(ValueError):
            self.e.turn(question='중복 대화')
        self.assertEqual(self.e.snapshot()['realtime']['kind'], 'live')
        self.e.live.stop(result['session_id'])
        self.e.realtime.start(mock=True)
        with self.assertRaises(ValueError):
            self.e.live.start(mock=True)

    def test_mock_has_no_paid_calls(self):
        self.e.live.start(mock=True)
        self.request.assert_not_called()
        self.assertEqual(self.e.total_calls, 0)

    def test_close_waits_for_server_confirmation(self):
        result, a = self.start()
        self.e.live.stop(result['session_id'])
        self.assertEqual(a['sideband'].sent[-1]['type'], 'session.close')
        self.assertIsNone(self.e.live.ending)
        self.assertEqual(self.e.live.snapshot()['usage_seconds'], 9.5)

    def test_content_is_bounded_utf8(self):
        text = short_content('한글 ' * 500)
        self.assertLessEqual(len(text.encode('utf-8')), 480)
        self.assertNotIn('\ufffd', text)

    def emit(self, a, kind, **extra):
        self.e.live._event(a, {'type': kind, **extra})

    def user(self, a, text='무엇이 보여?'):
        self.user_serial = getattr(self, 'user_serial', 0) + 1
        self.emit(a, 'session.input_transcript.delta', event_id='u'+str(self.user_serial), delta=text,
                  start_ms=0, end_ms=1000)

    def delegate(self, a, did='deleg_1'):
        self.emit(a, 'session.delegation.created', delegation={'id': did, 'target': 'client'})

    def wait_backend(self):
        until = time.monotonic() + 2
        while self.e.live.backend_running and time.monotonic() < until:
            time.sleep(.005)
        self.assertFalse(self.e.live.backend_running)

    def results(self, a):
        return [e for e in a['sideband'].sent if e['type'] == 'session.commentary.append']

    def test_exact_transcripts_use_server_once_and_preserve_overlap(self):
        _, a = self.start()
        self.emit(a, 'session.input_transcript.delta', event_id='u1', delta='안녕 ', start_ms=0, end_ms=100)
        self.emit(a, 'session.output_transcript.delta', event_id='a1', delta='반가워 ', start_ms=100, end_ms=200)
        for _ in range(2):
            self.emit(a, 'session.input_transcript.delta', event_id='u2', delta='안녕', start_ms=100, end_ms=300)
        self.assertEqual(self.e.history[0]['content'], '안녕 안녕')
        self.assertEqual(self.e.history[1]['content'], '반가워 ')
        with self.assertRaises(ValueError):
            self.e.live.heartbeat({'session_id': a['id'], 'events': [{'role':'user','id':'forged','text':'forged'}]})

    def test_backend_receives_images_but_live_only_gets_bounded_text(self):
        from tests.test_observation import scene
        _, a = self.start()
        self.e.scene_mode = 'frames'
        self.e.frames.add(scene(0), 'prepared')
        self.e.frames.add(scene(1), 'prepared')
        self.e.live.heartbeat({'session_id': a['id'], 'manual': True})
        self.user(a)
        self.e.llm.reply.return_value = '책상 위에 컵이 보여. ' * 100
        self.delegate(a)
        self.wait_backend()
        self.assertEqual(len(self.e.llm.reply.call_args.kwargs['frames']), 2)
        answer = self.results(a)[0]
        self.assertEqual(answer['delegation_id'], 'deleg_1')
        self.assertLessEqual(len(answer['content'].encode()), 480)
        self.assertNotIn('image', json.dumps(answer))
        self.assertEqual(self.e.total_calls, 2)  # one session + one backend

    def test_usage_is_cumulative_and_finalized(self):
        _, a = self.start()
        self.emit(a, 'session.usage.updated', usage={'seconds': 12})
        self.emit(a, 'session.usage.updated', usage={'seconds': 15})
        self.assertEqual(self.e.live.snapshot()['usage_seconds'], 15)

    def test_late_backend_after_stop_is_discarded(self):
        result, a = self.start()
        entered, release = threading.Event(), threading.Event()
        self.addCleanup(release.set)
        def reply(*args, **kwargs):
            entered.set(); release.wait(2); return '늦은 답변'
        self.e.llm.reply.side_effect = reply
        self.user(a); self.delegate(a)
        self.assertTrue(entered.wait(1))
        self.e.live.stop(result['session_id']); release.set(); self.wait_backend()
        self.assertEqual(self.results(a), [])

    def test_new_question_or_paused_observation_discards_old_result(self):
        for change in ('question','pause'):
            with self.subTest(change=change):
                result, a = self.start()
                entered, release = threading.Event(), threading.Event()
                self.addCleanup(release.set)
                def reply(*args, **kwargs):
                    entered.set(); release.wait(2); return '오래된 답변'
                self.e.llm.reply.side_effect = reply
                self.user(a); self.delegate(a)
                self.assertTrue(entered.wait(1))
                if change == 'question':
                    self.user(a, '아니야 다른 질문이야')
                else:
                    self.e.observation.generation += 1
                release.set(); self.wait_backend()
                self.assertEqual(self.results(a), [])
                self.e.live.stop(result['session_id'])

    def test_new_delegation_wins_and_duplicate_does_not_repeat_backend(self):
        _, a = self.start()
        entered, release = threading.Event(), threading.Event()
        self.addCleanup(release.set)
        def reply(*args, **kwargs):
            entered.set(); release.wait(2); return '최신 답변'
        self.e.llm.reply.side_effect = reply
        self.user(a); self.delegate(a, 'old')
        self.assertTrue(entered.wait(1))
        self.delegate(a, 'new'); self.delegate(a, 'new')
        release.set(); self.wait_backend()
        self.assertEqual([e['delegation_id'] for e in self.results(a)], ['new'])
        self.assertEqual(self.e.llm.reply.call_count, 2)

    def test_live_backend_budget_is_bounded(self):
        _, a = self.start(); self.user(a)
        a['backend_calls'] = 24
        self.delegate(a); self.wait_backend()
        self.e.llm.reply.assert_not_called()
        self.assertIn('분석 한도', self.results(a)[0]['content'])

    def test_broken_sideband_uses_http_hangup_and_404_keeps_lease_blocked(self):
        result, a = self.start()
        a['sideband'].send = Mock(side_effect=RuntimeError('broken'))
        self.request.side_effect = RuntimeError('API HTTP 404: missing')
        self.e.live.stop(result['session_id'])
        self.assertTrue(self.request.call_args.args[0].endswith('/sess_opaque_1/hangup'))
        self.assertIs(self.e.live.ending, a)
        self.assertTrue(self.e.live.warning)
        with self.assertRaises(ValueError):
            self.e.realtime.start(mock=True)
        self.request.side_effect = None
        self.e.live._hangup(a)
        self.assertIsNone(self.e.live.ending)

    def test_heartbeat_ownership_and_frame_consent(self):
        _, a = self.start()
        with self.assertRaises(ValueError):
            self.e.live.heartbeat({'session_id': 'other'})
        with self.assertRaises(ValueError):
            self.e.live.heartbeat({'session_id': a['id'], 'manual': 'yes'})
        self.e.live.heartbeat({'session_id': a['id'], 'manual': True})
        self.assertTrue(a['manual'])

    def test_new_webcam_frame_does_not_cancel_analysis_but_clear_does(self):
        from tests.test_observation import scene
        for clear in (False, True):
            with self.subTest(clear=clear):
                result, a = self.start()
                self.e.scene_mode = 'frames'
                self.e.frames.add(scene(0), 'webcam')
                self.e.live.heartbeat({'session_id': a['id'], 'manual': True})
                entered, release = threading.Event(), threading.Event()
                self.addCleanup(release.set)
                def reply(*args, **kwargs):
                    entered.set(); release.wait(2); return '촬영 당시 컵이 보였어.'
                self.e.llm.reply.side_effect = reply
                self.user(a); self.delegate(a); self.assertTrue(entered.wait(1))
                if clear:
                    self.e.frames.clear()
                else:
                    self.e.frames.add(scene(1), 'webcam')
                release.set(); self.wait_backend()
                self.assertEqual(len(self.results(a)), 0 if clear else 1)
                self.e.live.stop(result['session_id'])

    def test_latest_observation_fits_live_context_budget(self):
        _, a = self.start()
        self.e.observation.context = Mock(return_value='과거 기록 안내\n오래된 장면 ' + '책상' * 200 + '\n방금: 빨간 우산')
        self.e.live.heartbeat({'session_id': a['id']})
        context = a['sideband'].sent[-1]
        self.assertIn('빨간 우산', context['content'])
        self.assertLessEqual(len(context['content'].encode()), 480)
        self.assertIsNone(context['delegation_id'])

    def test_uploaded_jpeg_is_labeled_as_past_photo_for_backend_and_live(self):
        _, a = self.start()
        self.e.scene_mode, self.e.admin_image = 'upload', b'fake jpeg'
        self.e.live.heartbeat({'session_id': a['id'], 'manual': True})
        self.user(a); self.delegate(a); self.wait_backend()
        call = self.e.llm.reply.call_args
        self.assertEqual(call.args[2], b'fake jpeg')
        self.assertIn('과거 업로드', call.kwargs['observation'])
        self.assertIn('촬영 시각 미확인', self.results(a)[0]['content'])

    def test_live_quiet_notice_uses_existing_voice_and_never_overlaps_speaking(self):
        _, a = self.start()
        o = self.e.observation
        o.enabled = o.proactive = True
        o.pending_notice = {'session_id':a['id'],'input_serial':0,'generation':o.generation,
                            'scene':o.scene,'received':o.clock(),'text':'새 책을 가져왔네!','emotion':'호기심'}
        self.e.live.heartbeat({'session_id':a['id'],'phase':'speaking','quiet_ms':5000})
        self.assertFalse(self.results(a))
        self.e.live.heartbeat({'session_id':a['id'],'phase':'listening','quiet_ms':3999})
        self.assertFalse(self.results(a))
        self.e.live.heartbeat({'session_id':a['id'],'phase':'listening','quiet_ms':5000})
        self.assertEqual(len(self.results(a)),1)
        self.assertIsNone(self.results(a)[0]['delegation_id'])
        self.assertIn('새 책',self.results(a)[0]['content'])
        self.e.speech.synthesize.assert_not_called()


class LiveHttpTests(unittest.TestCase):
    def setUp(self):
        self.e = engine()
        self.e.args.dialogue_mode = 'live'
        self.server = ThreadingHTTPServer(('127.0.0.1', 0), handler_for(self.e))
        self.thread = threading.Thread(target=self.server.serve_forever)
        self.thread.start()
        self.url = 'http://127.0.0.1:' + str(self.server.server_port)

    def tearDown(self):
        self.e.close(); self.server.shutdown(); self.server.server_close(); self.thread.join()

    def post(self, path, body, token=True):
        return urllib.request.urlopen(urllib.request.Request(self.url+path,
            data=json.dumps(body).encode(), headers={'Content-Type':'application/json',
            **({'X-BMO-Token': self.e.token} if token else {})}))

    def test_live_routes_require_csrf_and_owned_lease(self):
        with self.assertRaises(urllib.error.HTTPError) as err:
            self.post('/api/live/start', {'mock':True}, token=False)
        self.assertEqual(err.exception.code, 403)
        with self.post('/api/live/start', {'mock': True}) as response:
            result = json.load(response)
        with self.assertRaises(urllib.error.HTTPError):
            self.post('/api/live/stop', {'session_id':'other'})
        with self.post('/api/live/stop', {'session_id':result['session_id']}) as response:
            self.assertTrue(json.load(response)['ok'])

    def test_phone_mode_is_server_selected_and_legacy_remains_default(self):
        with urllib.request.urlopen(self.url+'/phone') as response:
            self.assertIn(b'content="live" data-dialogue-mode', response.read())
        self.e.args.dialogue_mode = 'realtime'
        with urllib.request.urlopen(self.url+'/phone') as response:
            self.assertIn(b'content="realtime" data-dialogue-mode', response.read())
        with self.assertRaises(urllib.error.HTTPError):
            self.post('/api/live/start', {'mock':True})


if __name__ == '__main__':
    unittest.main()
