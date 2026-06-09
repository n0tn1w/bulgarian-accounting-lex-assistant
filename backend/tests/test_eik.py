from app.tools.ingest.eik import eik_check_digit_9, validate_eik


def test_valid_9_digit():
    assert validate_eik("000694037")  # Bulgarian National Bank


def test_valid_13_digit():
    assert validate_eik("0006940370018")


def test_rejects_bad_check_digit():
    assert not validate_eik("000694038")


def test_rejects_wrong_length_and_nondigit():
    assert not validate_eik("12345")
    assert not validate_eik("BG000694037")
    assert not validate_eik("")
    assert not validate_eik(None)


def test_two_pass_fallback_when_first_pass_is_ten():
    # Find an 8-digit prefix whose first modulo-11 pass yields 10, forcing the
    # second weighting, and confirm the produced check digit validates.
    for n in range(10_000_000, 10_000_200):
        digits = [int(c) for c in f"{n:08d}"]
        first = sum(d * w for d, w in zip(digits, [1, 2, 3, 4, 5, 6, 7, 8])) % 11
        if first == 10:
            cd = eik_check_digit_9(digits)
            assert validate_eik(f"{n:08d}{cd}")
            break
    else:  # pragma: no cover - statistically unreachable
        raise AssertionError("no first-pass==10 case in range")
