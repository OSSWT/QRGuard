"""Registration must never fit a payload's altered data modules."""
import cv2
import numpy as np
import pytest
import qrcode
from PIL import ImageDraw
from structural.attendance_grid import check_attendance_grid
from structural.registered_sampling import sample_registered_grid
from test_attendance_grid import attendance_image


@pytest.mark.parametrize('row,col', [(20, 20), (57, 60), (58, 58), (58, 60), (60, 58)])
def test_registered_sampling_preserves_changed_modules(row, col, monkeypatch):
    monkeypatch.setenv('QRGUARD_ATTENDANCE_REGISTERED_SAMPLING', '1')
    payload, image = attendance_image()
    x, y = (col + 4) * 8, (row + 4) * 8
    colour = 'white' if image.getpixel((x + 4, y + 4))[0] < 128 else 'black'
    ImageDraw.Draw(image).rectangle((x, y, x + 7, y + 7), fill=colour)
    assert not check_attendance_grid(image, payload).passed


@pytest.mark.parametrize('identity,mask', [(0, 0), (1, 3), (2, 7)])
def test_registration_recovers_clean_grid_without_payload_input(identity, mask):
    payload, image = attendance_image(identity, mask=mask)
    gray = cv2.cvtColor(np.asarray(image), cv2.COLOR_RGB2GRAY)
    _, points, straight = cv2.QRCodeDetector().detectAndDecode(gray)
    sampled = sample_registered_grid(gray, points, len(straight))
    assert sampled is not None
    qr = qrcode.QRCode(version=11, error_correction=qrcode.constants.ERROR_CORRECT_H,
                       border=0, mask_pattern=mask)
    qr.add_data(payload, optimize=0)
    qr.make(fit=False)
    diff = sampled != np.asarray(qr.get_matrix(), dtype=bool)
    diff[21:40, 21:40] = False
    assert not diff.any()


def test_registration_experiment_is_off_by_default(monkeypatch):
    monkeypatch.delenv('QRGUARD_ATTENDANCE_REGISTERED_SAMPLING', raising=False)
    payload, image = attendance_image()
    def forbidden(*args):
        raise AssertionError('Production must not invoke preview registration')
    monkeypatch.setattr('structural.registered_sampling.sample_registered_grid', forbidden)
    ImageDraw.Draw(image).rectangle((192, 192, 199, 199), fill='white')
    check_attendance_grid(image, payload)
