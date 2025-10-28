from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from PIL import Image

import app


@pytest.fixture(autouse=True)
def isolated_storage(tmp_path, monkeypatch):
    base_dir = tmp_path / "app_root"
    data_dir = base_dir / "data"
    events_dir = data_dir / "events"
    base_dir.mkdir()

    monkeypatch.setattr(app, "BASE_DIR", base_dir)
    monkeypatch.setattr(app, "DATA_DIR", data_dir)
    monkeypatch.setattr(app, "EVENTS_DIR", events_dir)
    monkeypatch.setattr(app, "EVENTS_FILE", data_dir / "events.csv")
    monkeypatch.setattr(app, "LEGACY_ATTENDEE_FILE", data_dir / "attendees.csv")
    monkeypatch.setattr(app, "LEGACY_SIGNIN_FILE", data_dir / "signins.csv")
    monkeypatch.setattr(app, "LEGACY_SIGNATURE_DIR", data_dir / "signatures")

    for cached in (app.load_events, app.load_attendees, app.load_signins):
        try:
            cached.clear()
        except Exception:  # pragma: no cover - streamlit runtime mismatch
            pass

    app.ensure_storage()
    yield

    for cached in (app.load_events, app.load_attendees, app.load_signins):
        try:
            cached.clear()
        except Exception:  # pragma: no cover
            pass


def read_csv(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, dtype=str).fillna("")


def test_ensure_storage_creates_default_event():
    assert app.DATA_DIR.exists()
    assert app.EVENTS_DIR.exists()
    assert app.EVENTS_FILE.exists()

    events = read_csv(app.EVENTS_FILE)
    assert list(events.columns) == app.EVENT_COLUMNS
    assert app.DEFAULT_EVENT_ID in events["event_id"].values

    default_attendees = read_csv(app.attendee_file(app.DEFAULT_EVENT_ID))
    default_signins = read_csv(app.signin_file(app.DEFAULT_EVENT_ID))
    assert list(default_attendees.columns) == app.ATTENDEE_COLUMNS
    assert list(default_signins.columns) == app.SIGNIN_COLUMNS


def test_replace_attendees_validates_required_columns():
    invalid = pd.DataFrame(
        [
            {"attendee_id": "1", "name": "Jane", "company": "ACME"},
        ]
    )
    with pytest.raises(ValueError):
        app.replace_attendees(app.DEFAULT_EVENT_ID, invalid)


def test_replace_attendees_overwrites_existing_data():
    initial = pd.DataFrame(
        [
            {
                "attendee_id": "1",
                "name": "Jane Doe",
                "company": "ACME",
                "email": "jane@acme.com",
            }
        ]
    )
    app.replace_attendees(app.DEFAULT_EVENT_ID, initial)

    updated = pd.DataFrame(
        [
            {
                "attendee_id": "2",
                "name": "John Smith",
                "company": "Widgets",
                "email": "john@widgets.com",
            }
        ]
    )
    app.replace_attendees(app.DEFAULT_EVENT_ID, updated)

    stored = read_csv(app.attendee_file(app.DEFAULT_EVENT_ID))
    assert len(stored) == 1
    assert stored.iloc[0]["attendee_id"] == "2"


def test_create_event_generates_unique_directory():
    record = app.create_event("Advanced Session", "Hands-on workshop")
    event_id = record["event_id"]
    assert (app.EVENTS_DIR / event_id).exists()
    assert read_csv(app.EVENTS_FILE).shape[0] == 2


def test_filter_attendees_matches_by_partial_text():
    df = pd.DataFrame(
        [
            {
                "attendee_id": "1",
                "name": "Alice Example",
                "company": "Example Co",
                "email": "alice@example.com",
            },
            {
                "attendee_id": "2",
                "name": "Bob Builder",
                "company": "Construction Ltd",
                "email": "bob@build.com",
            },
        ]
    )

    result_name = app.filter_attendees(df, "alice")
    assert list(result_name["attendee_id"]) == ["1"]

    result_company = app.filter_attendees(df, "construction")
    assert list(result_company["attendee_id"]) == ["2"]

    result_email = app.filter_attendees(df, "@example.com")
    assert list(result_email["attendee_id"]) == ["1"]

    result_empty_query = app.filter_attendees(df, "")
    pd.testing.assert_frame_equal(result_empty_query.reset_index(drop=True), df)


def test_is_signature_blank_detects_drawn_pixels():
    blank = np.full((5, 5, 4), 255, dtype=np.uint8)
    assert app.is_signature_blank(blank)

    drawn = blank.copy()
    drawn[2, 2, :3] = 0
    assert not app.is_signature_blank(drawn)


def test_save_signature_image_persists_file():
    event_id = app.DEFAULT_EVENT_ID
    pixels = np.full((10, 10, 4), 255, dtype=np.uint8)
    pixels[3, 4, :3] = 0  # simulate a stroke

    relative_path = app.save_signature_image(event_id, pixels)
    stored_path = app.BASE_DIR / relative_path

    assert relative_path.startswith(f"data/events/{event_id}/signatures/")
    assert stored_path.exists()

    with Image.open(stored_path) as img:
        assert img.mode == "RGB"
        assert img.size == (10, 10)


def test_append_signin_appends_to_event_csv():
    event_id = app.DEFAULT_EVENT_ID
    entry = {
        "record_id": "abc123",
        "attendee_id": "1",
        "name": "Alice Example",
        "company": "Example Co",
        "email": "alice@example.com",
        "signed_at": "2024-01-01T12:00:00Z",
        "signature_file": f"data/events/{event_id}/signatures/test.png",
    }

    app.append_signin(event_id, entry)

    stored = read_csv(app.signin_file(event_id))
    assert len(stored) == 1
    assert stored.iloc[0]["record_id"] == "abc123"
