"""Relay one frame from the local Pi service to a trusted SSH client."""
import argparse
import json
import sys
import urllib.request


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=8765)
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error('Invalid Pi service port')
    base = f'http://127.0.0.1:{args.port}'
    try:
        with urllib.request.urlopen(base + '/api/state', timeout=10) as response:
            state = json.load(response)
        request = urllib.request.Request(base + '/api/admin/capture', data=b'{}',
            headers={'Content-Type': 'application/json', 'X-BMO-Token': state['token'], 'Origin': base})
        with urllib.request.urlopen(request, timeout=32) as response:
            if response.headers.get_content_type() != 'image/jpeg':
                raise ValueError('Unexpected frame format')
            jpeg = response.read(20 * 1024 * 1024 + 1)
        if not 0 < len(jpeg) <= 20 * 1024 * 1024:
            raise ValueError('Unexpected frame size')
        sys.stdout.buffer.write(jpeg)
        sys.stdout.buffer.flush()
    except Exception:
        # Do not relay server tokens, SSH diagnostics or configuration to clients.
        raise SystemExit('Pi camera capture failed. Check the local BMO service.') from None


if __name__ == '__main__':
    main()
