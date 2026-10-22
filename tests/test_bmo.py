import base64
from io import BytesIO
import json
import threading
import time
from types import ModuleType
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from unittest.mock import Mock, patch

from bmo.app import Engine, handler_for, parse_args
from bmo.audio import MAX_AUDIO, OpenAISpeech, validate_audio, validate_api_key
from bmo.conversation import Conversation
from bmo.config import api_key


def engine(real=False):
    e = Engine(parse_args(["--min-turn-seconds", "0"]))
    if real:
        e.args.provider = "openai"
        e.llm = Mock()
        e.llm.reply.return_value = "안녕! 무엇을 도와줄까?"
        e.speech = Mock()
        e.speech.transcribe.return_value = "안녕 비모"
        e.speech.synthesize.return_value = b"mock-mp3"
    return e


class EngineTests(unittest.TestCase):
    def test_demo_honest_and_no_api(self):
        e = engine()
        result = e.turn(question="안녕")
        self.assertTrue(result["mock"])
        self.assertIn("모의", result["reply"])
        self.assertIsNone(result["audio"])
        self.assertEqual(e.total_calls, 0)
        self.assertFalse(e.snapshot()["voice_ready"])

    def test_voice_pipeline_and_history(self):
        e = engine(True)
        r = e.turn(audio=b"x" * 100, mime="audio/mp4")
        self.assertEqual(r["question"], "안녕 비모")
        self.assertEqual(base64.b64decode(r["audio"]), b"mock-mp3")
        self.assertEqual(e.total_calls, 3)
        e.turn(question="내가 뭐라고 했지?")
        history = e.llm.reply.call_args.args[1]
        self.assertEqual(history[0]["content"], "안녕 비모")
        self.assertFalse(e.busy)

    def test_history_is_bounded(self):
        e = engine()
        for i in range(15):
            e.turn(question=str(i))
        self.assertEqual(len(e.history), 12)
        self.assertEqual(len(e.events), 24)
        self.assertEqual(e.history[0]["content"], "9")

    def test_camera_is_opt_in_and_not_in_history(self):
        e = engine(True)
        e.camera = Mock()
        e.camera.capture.return_value = b"jpeg"
        e.args.source = "pi"
        e.turn(question="안녕")
        e.camera.capture.assert_not_called()
        e.set_scene_mode("camera")
        e.turn(question="뭐가 보여?", use_camera=True)
        self.assertEqual(e.llm.reply.call_args.args[2], b"jpeg")
        self.assertNotIn("jpeg", json.dumps(e.history))
        self.assertIn("사진", e.history[-2]["content"])

    def test_no_camera_does_not_pretend(self):
        with self.assertRaises(ValueError):
            engine().set_scene_mode("camera")

    def test_cancel_during_transcription_stops_later_stages(self):
        e = engine(True)
        entered, released = threading.Event(), threading.Event()
        def transcribe(*args):
            entered.set()
            released.wait(3)
            return "안녕"
        e.speech.transcribe.side_effect = transcribe
        result = []
        t = threading.Thread(target=lambda: result.append(e.turn(audio=b"x"*100, mime="audio/mp4")))
        t.start()
        self.assertTrue(entered.wait(2))
        e.cancel(clear=True)
        released.set()
        t.join(3)
        self.assertEqual(result, [{"cancelled": True}])
        e.llm.reply.assert_not_called()
        e.speech.synthesize.assert_not_called()
        self.assertEqual(e.history, [])

    def test_cancel_during_tts_discards_result(self):
        e = engine(True)
        e.speech.synthesize.side_effect = lambda text: (e.cancel(), b"mp3")[1]
        self.assertEqual(e.turn(question="안녕"), {"cancelled": True})
        self.assertEqual(e.history, [])

    def test_tts_failure_keeps_text(self):
        e = engine(True)
        e.speech.synthesize.side_effect = RuntimeError("offline")
        r = e.turn(question="안녕")
        self.assertTrue(r["reply"])
        self.assertIn("음성", r["warning"])
        self.assertIsNone(r["audio"])
        self.assertEqual(len(e.history), 2)

    def test_stt_failure_no_dialogue(self):
        e = engine(True)
        e.speech.transcribe.side_effect = RuntimeError("offline")
        with self.assertRaises(RuntimeError):
            e.turn(audio=b"x"*100, mime="audio/webm")
        e.llm.reply.assert_not_called()
        self.assertFalse(e.busy)

    def test_budget_counts_each_stage_and_rolling_expiry(self):
        e = engine(True)
        e.args.max_calls = 1
        r = e.turn(question="안녕")
        self.assertEqual(e.total_calls, 1)
        self.assertTrue(r["warning"])
        with self.assertRaises(ValueError):
            e.turn(question="또 안녕")
        e.calls[0] -= 3601
        e.turn(question="다시 안녕")
        self.assertEqual(e.total_calls, 2)

    def test_phone_and_pc_share_ordered_conversation(self):
        e = engine(True)
        entered, release = threading.Event(), threading.Event()
        def reply(question, history, jpeg):
            if question == "전화 질문":
                entered.set()
                release.wait(3)
            return question + " 답변"
        e.llm.reply.side_effect = reply
        results = []
        phone = threading.Thread(target=lambda: results.append(e.turn(question="전화 질문", origin="phone")))
        pc = threading.Thread(target=lambda: results.append(e.turn(question="PC 질문", origin="pc")))
        phone.start()
        self.assertTrue(entered.wait(2))
        pc.start()
        time.sleep(.05)
        self.assertTrue(e.snapshot()["busy"])
        self.assertEqual(e.snapshot()["queued"], 1)
        release.set()
        phone.join(4)
        pc.join(4)
        self.assertEqual(len(results), 2)
        self.assertEqual([event["text"] for event in e.events if event["role"] == "user"], ["전화 질문", "PC 질문"])
        self.assertEqual(e.events[0]["origin"], "phone")
        self.assertEqual(e.events[2]["origin"], "pc")
        self.assertEqual(e.snapshot()["reply_id"], 2)

    def test_phone_cancel_keeps_queued_pc_message(self):
        e = engine(True)
        entered, release = threading.Event(), threading.Event()
        def reply(question, history, jpeg):
            if question == "전화 질문":
                entered.set()
                release.wait(3)
            return question + " 답변"
        e.llm.reply.side_effect = reply
        results = {}
        phone = threading.Thread(target=lambda: results.update(phone=e.turn(question="전화 질문", origin="phone")))
        pc = threading.Thread(target=lambda: results.update(pc=e.turn(question="PC 질문", origin="pc")))
        phone.start()
        self.assertTrue(entered.wait(2))
        pc.start()
        time.sleep(.05)
        e.cancel(origin="phone")
        release.set()
        phone.join(4)
        pc.join(4)
        self.assertEqual(results["phone"], {"cancelled": True})
        self.assertEqual(results["pc"]["reply"], "PC 질문 답변")

    def test_invalid_inputs_and_clear(self):
        e = engine()
        for q in (None, "", "x"*3001, 123):
            with self.assertRaises(ValueError):
                e.turn(question=q)
        e.turn(question="안녕")
        e.cancel(clear=True)
        self.assertEqual(e.history, [])
        self.assertEqual(list(e.events), [])


class ProviderTests(unittest.TestCase):
    def setUp(self):
        # Provider tests must not depend on the operator's real local keys.
        self.private_config = ModuleType("bmo.private_config")
        self.private_config.OPENAI_API_KEY = self.private_config.ANTHROPIC_API_KEY = ""
        key_patch = patch.dict("sys.modules", {"bmo.private_config": self.private_config})
        key_patch.start()
        self.addCleanup(key_patch.stop)

    def test_local_config_is_used_when_environment_has_no_key(self):
        private_config = self.private_config
        with patch.dict("os.environ", {}, clear=True), patch.object(private_config, "OPENAI_API_KEY", "local-test-key"):
            self.assertEqual(api_key("OPENAI_API_KEY"), "local-test-key")
            self.assertEqual(OpenAISpeech().key, "local-test-key")
        with patch.dict("os.environ", {"OPENAI_API_KEY":"env-test-key"}), patch.object(private_config, "OPENAI_API_KEY", "local-test-key"):
            self.assertEqual(api_key("OPENAI_API_KEY"), "local-test-key")

    def test_non_ascii_key_rejected_without_echo(self):
        for value in ("sk-한글", "sk-abc def", "sk-abc\nmore", ""):
            with self.assertRaises(ValueError) as caught:
                validate_api_key(value, "OpenAI")
            if value:
                self.assertNotIn(value, str(caught.exception))
        with patch.dict("os.environ", {"OPENAI_API_KEY": "sk-한글"}):
            with self.assertRaises(ValueError):
                OpenAISpeech()
            with self.assertRaises(ValueError):
                Conversation("openai", "gpt-4.1-mini")

    @patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"})
    def test_safari_mp4_and_chrome_webm_multipart(self):
        for mime, ext in (("audio/mp4", "mp4"), ("audio/webm;codecs=opus", "webm")):
            with patch("bmo.audio.api_request", return_value={"text": "안녕"}) as call:
                self.assertEqual(OpenAISpeech().transcribe(b"x"*100, mime), "안녕")
            body = call.call_args.args[2]
            self.assertIn(f'filename="speech.{ext}"'.encode(), body)
            self.assertIn(b'name="language"\r\n\r\nko', body)
            self.assertNotIn(b"test-key", body)

    def test_audio_bounds_and_mime(self):
        for data, mime in ((b"", "audio/mp4"), (b"x"*100, "text/plain"), (b"x"*(MAX_AUDIO+1), "audio/mp4")):
            with self.assertRaises(ValueError):
                validate_audio(data, mime)

    @patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"})
    def test_empty_transcription(self):
        with patch("bmo.audio.api_request", return_value={"text": " "}):
            with self.assertRaises(ValueError):
                OpenAISpeech().transcribe(b"x"*100, "audio/mp4")

    @patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"})
    def test_tts_payload(self):
        with patch("bmo.audio.api_request", return_value=b"mp3") as call:
            self.assertEqual(OpenAISpeech().synthesize("안녕"), b"mp3")
        payload = json.loads(call.call_args.args[2])
        self.assertEqual(payload["response_format"], "mp3")
        self.assertEqual(payload["input"], "안녕")

    @patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"})
    def test_claude_history_and_current_image(self):
        result = {"stop_reason": "end_turn", "content": [{"type": "text", "text": "부품이 보여."}]}
        history = [{"role": "user", "content": "안녕"}, {"role": "assistant", "content": "반가워"}]
        with patch("bmo.conversation.api_request", return_value=result) as call:
            self.assertEqual(Conversation("claude", "model").reply("뭐야?", history, b"jpeg"), "부품이 보여.")
        payload = json.loads(call.call_args.args[2])
        self.assertEqual(payload["messages"][:2], history)
        self.assertEqual(payload["messages"][-1]["content"][0]["type"], "image")

    @patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"})
    def test_openai_responses_and_no_remote_storage(self):
        result = {"status": "completed", "output": [{"type": "message", "content": [{"type": "output_text", "text": "안녕"}]}]}
        with patch("bmo.conversation.api_request", return_value=result) as call:
            self.assertEqual(Conversation("openai", "model").reply("안녕", []), "안녕")
        self.assertFalse(json.loads(call.call_args.args[2])["store"])

    @patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"})
    def test_incomplete_response_rejected(self):
        with patch("bmo.conversation.api_request", return_value={"status": "incomplete"}):
            with self.assertRaises(RuntimeError):
                Conversation("openai", "model").reply("안녕", [])

    def test_http_error_is_sanitized(self):
        from bmo.audio import api_request
        error = urllib.error.HTTPError("https://api.openai.com", 401, "secret-detail", {}, BytesIO(b"secret"))
        with patch("urllib.request.urlopen", side_effect=error):
            with self.assertRaisesRegex(RuntimeError, "401") as cm:
                api_request("https://api.openai.com", "private-key", b"{}")
        self.assertNotIn("secret", str(cm.exception))
        self.assertNotIn("private-key", str(cm.exception))

    def test_http_429_explains_known_cause_without_remote_text(self):
        from bmo.audio import api_request
        cases = (
            ("credit_balance_exhausted", "선불 크레딧"),
            ("project_spend_limit_exceeded", "프로젝트의 API 지출 한도"),
            ("rate_limit_exceeded", "요청 속도 제한"),
        )
        for code, expected in cases:
            body = json.dumps({"error": {"code": code, "message": "private-detail"}}).encode()
            error = urllib.error.HTTPError("https://api.openai.com", 429, "private-detail", {}, BytesIO(body))
            with patch("urllib.request.urlopen", side_effect=error):
                with self.assertRaises(RuntimeError) as caught:
                    api_request("https://api.openai.com", "private-key", b"{}")
            self.assertIn(expected, str(caught.exception))
            self.assertNotIn("private-detail", str(caught.exception))
            self.assertNotIn("private-key", str(caught.exception))


class HttpTests(unittest.TestCase):
    def setUp(self):
        self.e = engine()
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), handler_for(self.e))
        self.thread = threading.Thread(target=self.server.serve_forever)
        self.thread.start()
        self.url = f"http://127.0.0.1:{self.server.server_port}"

    def tearDown(self):
        self.e.close()
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()

    def post(self, path, data=None, headers=None):
        request = urllib.request.Request(self.url+path, data=json.dumps(data or {}).encode(),
            headers={"Content-Type": "application/json", "X-BMO-Token": self.e.token, **(headers or {})})
        return urllib.request.urlopen(request)

    def test_assets_and_chat(self):
        for path in ("/", "/admin", "/phone", "/app.js", "/style.css", "/phone.js", "/face.js", "/phone.css", "/audio-controls.js", "/api/state"):
            with urllib.request.urlopen(self.url+path) as r:
                self.assertEqual(r.status, 200)
        with self.post("/api/chat", {"question": "안녕"}) as r:
            self.assertIn("모의", json.load(r)["reply"])
        with self.post("/api/reset") as r:
            self.assertEqual(r.status, 200)
        self.assertEqual(self.e.history, [])

    def test_audio_controls_share_current_device_level_and_require_request_token(self):
        self.e.audio_controls = Mock()
        self.e.audio_controls.snapshot.return_value = {'microphone': {'available': True, 'volume': 39}}
        self.e.audio_controls.set_volume.return_value = {'microphone': {'available': True, 'volume': 44}}
        with urllib.request.urlopen(self.url+'/api/audio-levels') as response:
            self.assertEqual(json.load(response)['microphone']['volume'], 39)
        with self.post('/api/audio-levels', {'device': 'microphone', 'volume': 44}) as response:
            self.assertEqual(json.load(response)['microphone']['volume'], 44)
        with self.assertRaises(urllib.error.HTTPError) as denied:
            self.post('/api/audio-levels', {'device': 'microphone', 'volume': 100}, {'X-BMO-Token': 'wrong'})
        self.assertEqual(denied.exception.code, 403)
        self.e.audio_controls.set_volume.assert_called_once_with('microphone', 44)

    def test_face_images_are_served_from_a_fixed_allowlist(self):
        for number in (1, 15, 30):
            with urllib.request.urlopen(self.url + f"/faces/Rosto-{number:02}.jpg") as response:
                self.assertEqual(response.headers.get_content_type(), "image/jpeg")
                self.assertTrue(response.read().startswith(b"\xff\xd8"))
        for path in ("/faces/Rosto-00.jpg", "/faces/Rosto-31.jpg", "/faces/../private_config.py"):
            with self.assertRaises(urllib.error.HTTPError) as caught:
                urllib.request.urlopen(self.url + path)
            self.assertEqual(caught.exception.code, 404)

    def test_admin_image_and_phone_share_reply_audio(self):
        from PIL import Image
        picture = BytesIO()
        Image.new("RGB", (40, 30), (30, 160, 120)).save(picture, format="PNG")
        request = urllib.request.Request(self.url + "/api/admin/image", data=picture.getvalue(),
            headers={"Content-Type":"image/png", "X-BMO-Token":self.e.token})
        with urllib.request.urlopen(request) as response:
            self.assertEqual(response.status, 200)
        with urllib.request.urlopen(self.url + "/api/admin/image") as response:
            self.assertEqual(response.headers.get_content_type(), "image/jpeg")
            self.assertTrue(response.read().startswith(b"\xff\xd8"))
        with urllib.request.urlopen(self.url + "/api/state?role=phone") as response:
            self.assertTrue(json.load(response)["phone_online"])
        self.e.args.provider = "openai"
        self.e.llm = Mock()
        self.e.llm.reply.return_value = "사진이 보여."
        self.e.speech = Mock()
        self.e.speech.synthesize.return_value = b"mp3-data"
        with self.post("/api/chat", {"question":"뭐가 보여?", "camera":True}) as response:
            result = json.load(response)
        self.assertNotIn("audio", result)
        self.assertTrue(self.e.llm.reply.call_args.args[2].startswith(b"\xff\xd8"))
        with urllib.request.urlopen(self.url + f"/api/audio/{result['reply_id']}") as response:
            self.assertEqual(response.read(), b"mp3-data")
        with self.post("/api/chat", {"question":"또 물어볼게", "camera":False}) as response:
            second = json.load(response)
        self.assertGreater(second["reply_id"], result["reply_id"])
        with urllib.request.urlopen(self.url + f"/api/audio/{result['reply_id']}") as response:
            self.assertEqual(response.read(), b"mp3-data")
        with urllib.request.urlopen(self.url + "/api/state?role=pc") as response:
            state = json.load(response)
        self.assertTrue(state["phone_online"])
        self.assertTrue(state["pc_online"])
        self.assertEqual(state["scene_mode"], "upload")
        self.assertEqual(len(state["replies"]), 2)
        with self.post("/api/admin/image/clear") as response:
            self.assertEqual(response.status, 200)
        self.assertEqual(self.e.snapshot()["scene_mode"], "off")

    def test_iphone_root_opens_phone_view(self):
        request = urllib.request.Request(self.url + "/", headers={"User-Agent":"iPhone Safari"})
        with urllib.request.urlopen(request) as response:
            self.assertIn("BMO · 음성 화면", response.read().decode())

    def test_camera_preview_captures_fresh_without_ai_or_scene_changes(self):
        from PIL import Image
        picture = BytesIO()
        Image.new('RGB', (40, 30), (30, 160, 120)).save(picture, format='JPEG')
        self.e.args.source = 'pi'
        self.e.camera = Mock()
        self.e.camera.capture.return_value = picture.getvalue()
        for _ in range(2):
            with self.post('/api/admin/capture') as response:
                self.assertEqual(response.headers.get_content_type(), 'image/jpeg')
                self.assertEqual(response.read(), picture.getvalue())
        self.assertEqual(self.e.camera.capture.call_count, 2)
        self.assertEqual(self.e.total_calls, 0)
        self.assertEqual(self.e.history, [])
        self.assertEqual(self.e.scene_mode, 'off')
        self.assertFalse(self.e.busy)
        with self.assertRaises(urllib.error.HTTPError) as failure:
            self.post('/api/admin/capture', headers={'X-BMO-Token':'wrong'})
        self.assertEqual(failure.exception.code, 403)
        self.e.camera.capture.side_effect = RuntimeError('촬영 실패')
        with self.assertRaises(urllib.error.HTTPError) as failure:
            self.post('/api/admin/capture')
        self.assertEqual(failure.exception.code, 502)
        self.assertFalse(self.e.busy)
        self.assertEqual(self.e.total_calls, 0)

    def test_host_origin_csrf_rejected(self):
        for headers in ({"Host": "attacker.example"}, {"Origin": "https://attacker.example"}, {"X-BMO-Token": "wrong"}):
            with self.assertRaises(urllib.error.HTTPError) as cm:
                self.post("/api/chat", {"question": "안녕"}, headers)
            self.assertEqual(cm.exception.code, 403)

    def test_explicit_pc_tunnel_port_accepts_matching_origin(self):
        self.e.args.allowed_host.append("127.0.0.1:8775")
        with self.post("/api/chat", {"question": "안녕"},
                       {"Host": "127.0.0.1:8775", "Origin": "http://127.0.0.1:8775"}) as response:
            self.assertEqual(response.status, 200)

    def test_pair_auth_cookie_and_expiry(self):
        self.e.args.tls_cert = "test-mode"  # Exercise auth policy; actual TLS tested separately.
        with self.assertRaises(urllib.error.HTTPError) as cm:
            urllib.request.urlopen(self.url+"/api/state")
        self.assertEqual(cm.exception.code, 401)
        with self.post("/api/pair", {"code": self.e.pair_code}) as r:
            cookie = r.headers["Set-Cookie"]
        self.assertIn("Secure", cookie)
        self.assertIn("HttpOnly", cookie)
        request = urllib.request.Request(self.url+"/api/state", headers={"Cookie": cookie.split(";",1)[0]})
        with urllib.request.urlopen(request) as r:
            self.assertIn("token", json.load(r))
        for key in self.e.sessions:
            self.e.sessions[key] = 0
        with self.assertRaises(urllib.error.HTTPError) as cm:
            urllib.request.urlopen(request)
        self.assertEqual(cm.exception.code, 401)

    def test_pair_rate_limit(self):
        self.e.args.tls_cert = "test-mode"
        for i in range(6):
            with self.assertRaises(urllib.error.HTTPError) as cm:
                self.post("/api/pair", {"code": "bad"})
            self.assertEqual(cm.exception.code, 403 if i<5 else 429)

    def test_mock_voice_rejected_not_fake_transcribed(self):
        request=urllib.request.Request(self.url+"/api/voice",data=b"x"*100,headers={"Content-Type":"audio/mp4","X-BMO-Token":self.e.token})
        with self.assertRaises(urllib.error.HTTPError) as cm:
            urllib.request.urlopen(request)
        self.assertEqual(cm.exception.code, 400)

    def test_proactive_endpoint_removed(self):
        with self.assertRaises(urllib.error.HTTPError) as cm:
            self.post("/api/start")
        self.assertEqual(cm.exception.code, 404)

    def test_frames_http_versioned_upload_and_mock_transfer(self):
        from PIL import Image
        def upload(color, generation, activate=False):
            image = BytesIO()
            Image.new('RGB', (60, 40), color).save(image, 'PNG')
            request = urllib.request.Request(self.url+'/api/admin/frames',data=image.getvalue(),headers={
                'Content-Type':'image/png','X-BMO-Token':self.e.token,'X-BMO-Frame-Generation':str(generation),
                'X-BMO-Activate':'1' if activate else '0'})
            return urllib.request.urlopen(request)
        with self.post('/api/admin/frames/clear') as response:
            generation = json.load(response)['generation']
        with upload('red', generation, True):
            pass
        with self.post('/api/admin/scene',{'mode':'off'}):
            pass
        with upload('blue', generation):
            pass
        self.assertEqual(self.e.scene_mode, 'off')
        with self.post('/api/admin/scene',{'mode':'frames'}):
            pass
        with self.post('/api/realtime/start',{'mock':True}) as response:
            session = json.load(response)['session_id']
        with self.post('/api/realtime/frames',{'session_id':session}) as response:
            frames = json.load(response)['frames']
        self.assertEqual([f['seq'] for f in frames], [1,2])
        self.assertTrue(all(f['image_url'].startswith('data:image/jpeg;base64,') for f in frames))
        with self.assertRaises(urllib.error.HTTPError) as denied:
            self.post('/api/realtime/frames',{'session_id':'other'})
        self.assertEqual(denied.exception.code, 400)
        with self.post('/api/admin/frames/clear'):
            pass
        with self.assertRaises(urllib.error.HTTPError) as stale:
            upload('green', generation)
        self.assertEqual(stale.exception.code, 400)
        with self.post('/api/realtime/stop',{'session_id':session}):
            pass
        self.assertEqual(self.e.total_calls, 0)

    def test_realtime_endpoints_need_auth_token_and_reset_waits(self):
        with self.assertRaises(urllib.error.HTTPError) as denied:
            self.post('/api/realtime/start', {'mock':True}, {'X-BMO-Token':'wrong'})
        self.assertEqual(denied.exception.code, 403)
        with self.post('/api/realtime/start', {'mock':True}):
            pass
        with self.assertRaises(urllib.error.HTTPError):
            self.post('/api/reset')
        with self.post('/api/admin/realtime/stop'):
            pass
        self.assertFalse(self.e.snapshot()['realtime']['active'])

    def test_unsafe_lan_start_rejected(self):
        with patch("sys.stderr"):
            with self.assertRaises(SystemExit):
                parse_args(["--host", "0.0.0.0"])


if __name__ == "__main__":
    unittest.main()
