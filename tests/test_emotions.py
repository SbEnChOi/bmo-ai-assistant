import json
import unittest
from unittest.mock import patch
from bmo.emotions import EMOTIONS, EmotionalReply, normalize_emotion, parse_reply
from bmo.conversation import Conversation
from tests.test_bmo import engine


def response(text):
    return {'status':'completed','output':[{'type':'message','content':[{'type':'output_text','text':text}]}]}


class EmotionTests(unittest.TestCase):
    def test_one_word_enum_is_separate_from_spoken_text(self):
        r=parse_reply('{"emotion":"기쁨","reply":"성공했어! 축하해!"}')
        self.assertEqual(str(r),'성공했어! 축하해!');self.assertEqual(r.emotion,'기쁨')
        self.assertEqual(normalize_emotion('기쁨,슬픔'),'평온')
        with self.assertRaises(RuntimeError):parse_reply('{"emotion":"기쁨"}')
        with self.assertRaises(RuntimeError):parse_reply('{"emotion":"기쁨", malformed')
        self.assertEqual(parse_reply('```json\n{"emotion":"기쁨","reply":"축하해!"}\n```'),'축하해!')

    def test_engine_shares_emotion_but_synthesizes_only_reply(self):
        e=engine(True)
        try:
            e.llm.reply.return_value=EmotionalReply('축하해!','기쁨')
            result=e.turn(question='성공했어')
            self.assertEqual(result['emotion'],'기쁨')
            self.assertEqual(e.snapshot()['replies'][0]['emotion'],'기쁨')
            e.speech.synthesize.assert_called_once_with('축하해!')
            self.assertEqual(e.history[-1]['content'],'축하해!')
            self.assertEqual(e.total_calls,2)
        finally:e.close()

    @patch('bmo.conversation.api_key',return_value='test-key')
    def test_reply_uses_one_structured_request_with_fixed_emotion_enum(self,_):
        with patch('bmo.conversation.api_request',return_value=response('{"emotion":"장난","reply":"히히, 농담이야!"}')) as request:
            result=Conversation('openai','test-model').reply('농담해줘',[])
        self.assertEqual(result.emotion,'장난');request.assert_called_once()
        payload=json.loads(request.call_args.args[2]);schema=payload['text']['format']['schema']
        self.assertEqual(schema['properties']['emotion']['enum'],list(EMOTIONS))
        self.assertFalse(payload['store'])

    @patch('bmo.conversation.api_key',return_value='test-key')
    def test_realtime_classifier_has_short_timeout_and_sends_only_bmo_text(self,_):
        with patch('bmo.conversation.api_request',return_value=response('{"emotion":"걱정"}')) as request:
            self.assertEqual(Conversation('openai','test-model').classify_emotion('조심해서 확인해 보자.'),'걱정')
        self.assertEqual(request.call_args.kwargs['timeout'],6)
        payload=json.loads(request.call_args.args[2]);self.assertEqual(len(payload['input']),1)
        self.assertFalse(payload['store'])
