import base64
from io import BytesIO
import json
import threading
import unittest
from unittest.mock import patch
from PIL import Image
from bmo.app import Engine, parse_args
from bmo.frames import FrameBuffer
from bmo.conversation import Conversation


def picture(color):
    out = BytesIO()
    Image.new('RGB', (100, 60), color).save(out, 'PNG')
    return out.getvalue()


class FrameTests(unittest.TestCase):
    def test_bounded_order_selection_and_timestamps(self):
        clock = [0]
        frames = FrameBuffer(clock=lambda: clock[0])
        for i in range(15):
            frames.add(picture((i * 10, 30, 40)), label=str(i))
            clock[0] += 1
        self.assertEqual(len(frames.frames), 10)
        self.assertEqual([f.seq for f in frames.select()], [6, 9, 12, 15])
        self.assertIn('촬영 시각 미확인', frames.select()[0].caption())
        self.assertEqual(frames.snapshot()['selected'], 4)

    def test_live_expiry_and_static_refresh(self):
        clock = [0]
        frames = FrameBuffer(clock=lambda: clock[0])
        img = picture('green')
        self.assertTrue(frames.add(img, 'webcam'))
        clock[0] = 1
        self.assertFalse(frames.add(img, 'webcam'))
        clock[0] = 5
        self.assertTrue(frames.add(img, 'webcam'))
        clock[0] = 16
        self.assertEqual(frames.select(), [])
        self.assertTrue(frames.snapshot()['stale'])
        frames.add(picture('red'), 'prepared')
        self.assertEqual(len(frames.frames), 1)
        self.assertFalse(frames.snapshot()['stale'])

    def test_compact_images_fit_data_channel(self):
        out = BytesIO()
        Image.effect_noise((1280, 960), 100).convert('RGB').save(out, 'JPEG')
        frames = FrameBuffer()
        frames.add(out.getvalue())
        data = frames.select()[0].public(compact=True)
        self.assertLessEqual(len(base64.b64decode(data['image_url'].split(',')[1])), 32000)

    def test_webcam_noise_is_suppressed_and_old_capture_rejected(self):
        frames = FrameBuffer()
        frames.add(picture((100, 100, 100)), 'webcam')
        self.assertFalse(frames.add(picture((102, 101, 100)), 'webcam'))
        with patch('bmo.frames.time.time', return_value=100):
            with self.assertRaises(ValueError):
                frames.add(picture('blue'), 'webcam', captured_at=80)
            frames.add(picture('red'), 'webcam', captured_at=99)
        self.assertIn('1970-', frames.select()[-1].captured)

    def test_responses_multiple_images_are_interleaved_with_timing(self):
        frames = FrameBuffer()
        frames.add(picture('red'), label='1')
        frames.add(picture('blue'), label='2')
        result = {'status':'completed','output':[{'type':'message','content':[{'type':'output_text','text':'색이 바뀌었어.'}]}]}
        with patch('bmo.conversation.api_key', return_value='test-key'), patch('bmo.conversation.api_request', return_value=result) as request:
            Conversation('openai','test-model').reply('변화?', [], frames=frames.select())
        content = json.loads(request.call_args.args[2])['input'][-1]['content']
        self.assertEqual([c['type'] for c in content], ['input_text','input_text','input_image','input_text','input_image'])
        self.assertIn('#1', content[1]['text'])
        self.assertIn('#2', content[3]['text'])


class RealtimeTests(unittest.TestCase):
    def setUp(self):
        api_patch = patch('bmo.realtime.api_request', side_effect=AssertionError('Unmocked API call'))
        api_patch.start()
        self.addCleanup(api_patch.stop)
        self.e = Engine(parse_args(['--min-turn-seconds','0']))
        self.addCleanup(self.e.close)

    def test_mock_no_api_and_exclusive_and_private_id(self):
        with patch('bmo.realtime.api_request') as request:
            result = self.e.realtime.start(mock=True)
            request.assert_not_called()
        self.assertTrue(result['mock'])
        self.assertNotIn(result['session_id'], json.dumps(self.e.snapshot()))
        with self.assertRaises(ValueError):
            self.e.turn(question='안녕')
        with self.assertRaises(ValueError):
            self.e.realtime.start(mock=True)
        self.e.realtime.stop(result['session_id'])
        self.assertTrue(self.e.turn(question='안녕')['mock'])

    def test_transcript_dedup_and_ownership(self):
        result = self.e.realtime.start(mock=True)
        data = {'session_id':result['session_id'],'phase':'speaking','events':[{'id':'u1','role':'user','text':'안녕'}], 'frames_sent':4}
        self.e.realtime.heartbeat(data)
        self.e.realtime.heartbeat(data)
        self.assertEqual(len(self.e.events), 1)
        self.assertEqual(self.e.snapshot()['realtime']['frames_sent'], 4)
        with self.assertRaises(ValueError):
            self.e.realtime.stop('other-device')
        self.assertTrue(self.e.realtime.active)

    def test_emotion_classification_is_owned_deduplicated_and_counted(self):
        from unittest.mock import Mock
        result=self.e.realtime.start(mock=True)
        self.e.realtime.active['mock']=False
        self.e.llm=Mock();self.e.llm.classify_emotion.return_value='기쁨'
        data={'session_id':result['session_id'],'response_id':'resp_1','text':'성공해서 신나!'}
        self.e.realtime.heartbeat({'session_id':result['session_id'],'events':[{'id':'a1','role':'assistant','text':data['text'],'response_id':'resp_1'}]})
        self.assertEqual(self.e.realtime.emotion(data)['emotion'],'기쁨')
        self.assertEqual(self.e.events[-1]['emotion'],'기쁨')
        self.assertEqual(self.e.realtime.emotion(data)['emotion'],'기쁨')
        self.e.llm.classify_emotion.assert_called_once_with('성공해서 신나!')
        self.assertEqual(self.e.total_calls,1)
        with self.assertRaises(ValueError):self.e.realtime.emotion({**data,'session_id':'other'})

    def test_failed_emotion_is_nonfatal_and_bounded(self):
        from unittest.mock import Mock
        result=self.e.realtime.start(mock=True);self.e.realtime.active['mock']=False
        self.e.llm=Mock();self.e.llm.classify_emotion.side_effect=RuntimeError('offline')
        data={'session_id':result['session_id'],'response_id':'resp_1','text':'안녕!'}
        self.assertEqual(self.e.realtime.emotion(data)['emotion'],'평온')
        self.assertTrue(self.e.realtime.active)
        self.e.realtime.active['emotion_count']=48
        self.assertEqual(self.e.realtime.emotion({**data,'response_id':'resp_2'})['emotion'],'평온')
        self.e.llm.classify_emotion.assert_called_once()

    def test_emotion_finishing_after_session_stopped_cannot_affect_another_session(self):
        from unittest.mock import Mock
        result=self.e.realtime.start(mock=True);self.e.realtime.active['mock']=False
        self.e.llm=Mock()
        def classify(text):
            self.e.realtime.stop(result['session_id']);self.e.realtime.start(mock=True);return '기쁨'
        self.e.llm.classify_emotion.side_effect=classify
        out=self.e.realtime.emotion({'session_id':result['session_id'],'response_id':'resp_1','text':'축하해!'})
        self.assertTrue(out['cancelled']);self.assertEqual(out['emotion'],'평온')

    def test_handshake_configuration_key_stays_server_side_and_hangup(self):
        self.e.args.provider = 'openai'
        replies = [(b'v=0\r\nanswer', {'Location':'/v1/realtime/calls/rtc_test'}), b'']
        with patch('bmo.realtime.api_key', return_value='test-key'), patch('bmo.realtime.api_request', side_effect=replies) as request:
            result = self.e.realtime.start('v=0\r\noffer')
            self.assertEqual(result['sdp'],'v=0\r\nanswer')
            self.assertNotIn('test-key', json.dumps(result))
            body = request.call_args.args[2].decode()
            self.assertIn('gpt-realtime-2.1',body)
            self.assertIn('"interrupt_response": false',body)
            self.assertIn('"create_response": false',body)
            self.assertIn('"noise_reduction": {"type": "near_field"}',body)
            self.assertIn('"threshold": 0.7',body)
            self.assertIn('"language": "ko"',body)
            self.e.realtime.stop(result['session_id'])
            self.assertTrue(request.call_args.args[0].endswith('/rtc_test/hangup'))

    def test_handshake_error_releases_slot(self):
        self.e.args.provider = 'openai'
        with patch('bmo.realtime.api_key', return_value='test-key'), patch('bmo.realtime.api_request', side_effect=RuntimeError('API unavailable')):
            with self.assertRaises(RuntimeError):
                self.e.realtime.start('v=0\r\noffer')
        self.assertFalse(self.e.realtime.active)

    def test_failed_hangup_blocks_restart_and_can_be_retried(self):
        self.e.args.provider = 'openai'
        replies = [(b'v=0\r\nanswer', {'Location':'/v1/realtime/calls/rtc_test'}), RuntimeError('offline'), b'']
        with patch('bmo.realtime.api_key', return_value='test-key'), patch('bmo.realtime.api_request', side_effect=replies):
            result = self.e.realtime.start('v=0\r\noffer')
            self.e.realtime.stop(result['session_id'])
            self.assertEqual(self.e.snapshot()['realtime']['phase'], 'closing')
            with self.assertRaises(ValueError):
                self.e.realtime.start(mock=True)
            self.e.realtime.stop(force=True)
            self.assertFalse(self.e.snapshot()['realtime']['active'])

    def test_cancel_while_handshake_pending_hangs_up_late_call(self):
        self.e.args.provider = 'openai'
        entered, release = threading.Event(), threading.Event()
        errors = []
        def request(url, *args, **kwargs):
            if url.endswith('/hangup'):
                return b''
            entered.set()
            release.wait(3)
            return b'v=0\r\nanswer', {'Location':'/v1/realtime/calls/rtc_test'}
        def start():
            try:
                self.e.realtime.start('v=0\r\noffer')
            except ValueError as exc:
                errors.append(str(exc))
        with patch('bmo.realtime.api_key', return_value='test-key'), patch('bmo.realtime.api_request', side_effect=request) as call:
            thread = threading.Thread(target=start)
            thread.start()
            self.assertTrue(entered.wait(2))
            self.e.realtime.stop(force=True)
            release.set()
            thread.join(4)
            self.assertTrue(errors)
            self.assertTrue(call.call_args.args[0].endswith('/hangup'))
        self.assertFalse(self.e.realtime.active)
