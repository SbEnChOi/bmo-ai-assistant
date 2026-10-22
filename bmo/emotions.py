"""One bounded emotion label describing BMO's wording, not the user's mind."""
import json

EMOTIONS = ('평온', '기쁨', '애정', '장난', '감동', '슬픔', '걱정', '화남', '불만', '놀람', '혼란', '지침')
GUIDANCE = '''BMO가 말하는 문장 자체의 주된 감정/말투를 다음 목록의 한 단어로 분류한다.
평온: 인사·차분한 설명, 기쁨: 축하·즐거움, 애정: 다정함·고마움, 장난: 농담·귀여운 장난,
감동: 뭉클함·감격, 슬픔: 위로·아쉬움, 걱정: 염려·조심스러움, 화남: 부당함에 대한 분노,
불만: 못마땅함·투덜거림, 놀람: 신기함·감탄, 혼란: 당황·이해하기 어려움, 지침: 피곤함·녹초.
주제에 등장하는 감정과 화자의 말투를 구별한다. 사용자의 실제 감정이나 성격을 추정하지 않는다.
감정이 뚜렷하지 않으면 평온을 선택한다. 다양한 표정을 보여주려고 부적절한 감정을 고르거나 답변 내용을 바꾸지 않는다.'''


def normalize_emotion(value):
    return value if isinstance(value, str) and value in EMOTIONS else '평온'


def fallback_emotion(text):
    """Offline/mock fallback only; real replies carry the model's label."""
    for label, words in (
        ('장난', ('농담', '장난', '히히', 'ㅋㅋ')), ('감동', ('뭉클', '감동', '감격')),
        ('애정', ('고마워', '사랑', '소중', '다정')), ('슬픔', ('슬프', '속상', '아쉽', '위로')),
        ('화남', ('화가 나', '화나', '분노', '부당')), ('걱정', ('걱정', '염려', '조심')),
        ('지침', ('지쳤', '피곤', '녹초')), ('혼란', ('헷갈', '혼란', '어리둥절')),
        ('불만', ('못마땅', '불만', '투덜')), ('놀람', ('놀랍', '신기', '깜짝')),
        ('기쁨', ('축하', '기뻐', '신나', '즐거', '성공', '좋아!'))):
        if any(word in text for word in words):
            return label
    return '평온'


def output_format(reply=False):
    properties = {'emotion': {'type': 'string', 'enum': list(EMOTIONS)}}
    if reply:
        properties['reply'] = {'type': 'string'}
    return {'type': 'json_schema', 'name': 'bmo_reply' if reply else 'bmo_emotion', 'strict': True,
            'schema': {'type': 'object', 'properties': properties,
                       'required': list(properties), 'additionalProperties': False}}


class EmotionalReply(str):
    def __new__(cls, text, emotion='평온'):
        result = super().__new__(cls, text)
        result.emotion = normalize_emotion(emotion)
        return result


def parse_reply(text):
    text = text.strip()
    if text.startswith('```') and text.endswith('```'):
        text = '\n'.join(text.splitlines()[1:-1]).strip()
    try:
        data = json.loads(text)
    except (ValueError, TypeError):
        if text.startswith('{') and '"emotion"' in text:
            raise RuntimeError('AI 답변 형식을 확인하지 못했습니다. 다시 질문해 주세요.') from None
        return EmotionalReply(text.strip()[:2000], fallback_emotion(text))
    if not isinstance(data, dict) or not isinstance(data.get('reply'), str) or not data['reply'].strip():
        raise RuntimeError('AI 답변 형식을 확인하지 못했습니다. 다시 질문해 주세요.')
    return EmotionalReply(data['reply'].strip()[:2000], data.get('emotion'))
