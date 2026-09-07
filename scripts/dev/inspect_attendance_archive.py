"""Replay a private diagnostic ZIP without extracting or printing QR payloads.

Set QRGUARD_ATTENDANCE_REGISTERED_SAMPLING=1 for the preview verifier.
No network requests, archive modifications or automatic image persistence.
"""
import argparse
from dataclasses import asdict
import hashlib
import io
import json
from pathlib import Path
import sys
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'backend'))
from PIL import Image
from structural.attendance_grid import check_attendance_grid
from structural.qr_decoder import decode_qr


def inspect(path):
    with zipfile.ZipFile(path) as archive:
        metadata = json.loads(archive.read('diagnostics.json'))
        for record in metadata['files']:
            entry = archive.getinfo(record['file'])
            if entry.file_size > 25 * 1024 * 1024:
                raise ValueError('Image exceeds diagnostic replay limit')
            data = archive.read(entry)
            if hashlib.sha256(data).hexdigest() != record['sha256']:
                raise ValueError('Image checksum mismatch')
            image = Image.open(io.BytesIO(data)).convert('RGB')
            payload = decode_qr(image)
            if not payload:
                print(json.dumps({'file': record['file'], 'decoded': False}))
                continue
            print(json.dumps({'file': record['file'], 'hash_verified': True,
                'payload_hash_matches': hashlib.sha256(payload.encode()).hexdigest() == metadata['payload_sha256'],
                'check': asdict(check_attendance_grid(image, payload))}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('archive', type=Path)
    inspect(parser.parse_args().archive)
