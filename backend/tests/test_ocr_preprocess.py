import pytest

np = pytest.importorskip("numpy")
pytest.importorskip("cv2")
Image = pytest.importorskip("PIL.Image")

from app.tools.ingest import ocr  # noqa: E402


def test_preprocess_returns_binary_grayscale():
    rng = np.zeros((60, 240, 3), dtype=np.uint8)
    rng[:] = 255
    rng[20:40, 30:210] = 20  # a dark "text" band
    out = ocr._preprocess(Image.fromarray(rng))
    arr = np.array(out)
    assert arr.ndim == 2  # grayscale
    assert set(np.unique(arr).tolist()) <= {0, 255}  # Otsu binarized


def test_photo_mode_upscales_small_images():
    small = np.full((300, 400, 3), 255, dtype=np.uint8)
    small[120:180, 40:360] = 20
    plain = np.array(ocr._preprocess(Image.fromarray(small), photo=False))
    photo = np.array(ocr._preprocess(Image.fromarray(small), photo=True))
    assert max(photo.shape) > max(plain.shape)  # photo mode upscaled the low-res image


def test_extract_ocr_from_image_bytes_runs():
    import io

    if not ocr.ocr_status().get("ocr"):
        pytest.skip("tesseract not available")
    buf = io.BytesIO()
    Image.new("RGB", (1200, 800), "white").save(buf, format="JPEG")
    res = ocr.extract_ocr_from_image_bytes(buf.getvalue())
    assert isinstance(res, ocr.OcrResult)
    assert res.page_images  # photo pipeline produced a processed page


def test_image_to_text_reflows_and_flags_low_conf():
    data = {
        "text": ["Hello", "", "World"],
        "conf": [95, -1, 40],
        "block_num": [1, 1, 1],
        "par_num": [1, 1, 1],
        "line_num": [1, 1, 2],
        "left": [10, 0, 10],
        "width": [80, 0, 80],
    }
    text = ocr._image_to_text(data, width=1000)
    assert "Hello" in text and "World" in text

    low: set[str] = set()
    confs: list[float] = []
    ocr._collect_confidence(data, low, confs, threshold=0.6)
    assert "world" in low  # conf 0.40 < 0.60
    assert "hello" not in low  # conf 0.95 stays trusted


def test_two_column_header_deinterleaved():
    # supplier (right) beside recipient (left) on the same OCR lines must be split into
    # column-major order, not interleaved across the gutter.
    W = 1000
    data = {"text": [], "conf": [], "block_num": [], "par_num": [], "line_num": [],
            "left": [], "width": []}
    rows = [
        ("Получател", 60), ("Доставчик", 600),
        ("Алфа", 60), ("Бета", 600),
        ("BG111111111", 60), ("BG222222222", 600),
    ]
    for idx, (word, x) in enumerate(rows):
        data["text"].append(word); data["conf"].append(95)
        data["block_num"].append(1); data["par_num"].append(1)
        data["line_num"].append(idx // 2)  # two words per line
        data["left"].append(x); data["width"].append(120)
    text = ocr._image_to_text(data, width=W)
    # left column (recipient) should be contiguous, then the right column (supplier)
    assert text.index("Получател") < text.index("Алфа") < text.index("Доставчик")
    assert text.index("Доставчик") < text.index("Бета") < text.index("BG222222222")
    assert "Получател Доставчик" not in text  # not interleaved
