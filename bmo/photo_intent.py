"""Small, conservative matcher for an explicitly requested new camera exposure."""
import re


def requests_photo(text):
    text = re.sub(r'\s+', '', str(text)).lower()
    # Do not turn a refusal or a question about an old photograph into a capture.
    if re.search(r'(찍|촬영).{0,6}(지마|지말|지않|말고|필요없)|촬영취소|사진취소', text):
        return False
    if re.search(r"(don't|donot|never)(take|capture|retake)", text):
        return False
    if (re.search(r'(아까|이전|예전|지난|전에).{0,30}(찍었|촬영했|보였|말했|했지)', text)
            and not re.search(r'(다시|새로|지금).{0,12}(찍|촬영)', text)):
        return False
    return bool(re.search(
        r'(사진|카메라).{0,14}(찍어(줘|주|줄|봐|볼|서|요|라|$)|찍자|찍을래|찍고|촬영해|촬영하|촬영좀)|'
        r'(다시|새로|지금).{0,5}(찍어|촬영해)|'
        r'(take|capture)(a|another|anew)?(photo|picture)|retake', text))


FRESH_PHOTO_NOTE = ('이 요청을 받은 뒤 새로 촬영한 사진만 첨부했다. 현재 장면은 이 사진으로만 판단한다. '
                    '이전 사진의 설명이나 과거 관찰 요약을 반복하지 않는다. 보이지 않거나 흐리면 그대로 알린다. '
                    '사진은 메모리에서 갱신했으며 파일로 저장했다고 말하지 않는다.')
