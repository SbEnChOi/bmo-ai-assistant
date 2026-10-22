"""Read-only model metadata check. Does not create sessions or send media."""
import json
from .audio import api_request
from .config import api_key


def main():
    key = api_key('OPENAI_API_KEY')
    results = []
    for model in ('gpt-realtime-2.1', 'gpt-live-1'):
        try:
            data = api_request('https://api.openai.com/v1/models/' + model, key, None)
            results.append({'model': model, 'metadata_accessible': data.get('id') == model})
        except (ValueError, RuntimeError) as exc:
            results.append({'model': model, 'metadata_accessible': False, 'error': str(exc)})
    print(json.dumps({'checks': results, 'session_access_tested': False, 'media_sent': False}, ensure_ascii=False))


if __name__ == '__main__':
    main()
