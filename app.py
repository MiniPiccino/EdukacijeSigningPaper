from __future__ import annotations

import uuid
from datetime import datetime, timezone
import os
from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st
from PIL import Image
from streamlit_drawable_canvas import st_canvas


BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
SIGNATURE_DIR = DATA_DIR / "signatures"
ATTENDEE_FILE = DATA_DIR / "attendees.csv"
SIGNIN_FILE = DATA_DIR / "signins.csv"

ATTENDEE_COLUMNS = ["attendee_id", "name", "company", "email"]
SIGNIN_COLUMNS = [
    "record_id",
    "attendee_id",
    "name",
    "company",
    "email",
    "signed_at",
    "signature_file",
]

ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "step")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "step")


def filter_attendees(attendees: pd.DataFrame, query: str) -> pd.DataFrame:
    """Return attendees whose name, company, or email contains the query string."""
    cleaned_query = (query or "").strip().lower()
    if not cleaned_query:
        return attendees
    searchable = (
        attendees[["name", "company", "email"]]
        .astype(str)
        .agg(" ".join, axis=1)
        .str.lower()
    )
    mask = searchable.str.contains(cleaned_query, regex=False)
    return attendees[mask]


def ensure_storage() -> None:
    """Create required data folders/files if they do not yet exist."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    SIGNATURE_DIR.mkdir(parents=True, exist_ok=True)
    if not ATTENDEE_FILE.exists():
        pd.DataFrame(columns=ATTENDEE_COLUMNS).to_csv(ATTENDEE_FILE, index=False)
    if not SIGNIN_FILE.exists():
        pd.DataFrame(columns=SIGNIN_COLUMNS).to_csv(SIGNIN_FILE, index=False)


@st.cache_data(show_spinner=False)
def load_attendees() -> pd.DataFrame:
    if not ATTENDEE_FILE.exists():
        return pd.DataFrame(columns=ATTENDEE_COLUMNS)
    df = pd.read_csv(ATTENDEE_FILE, dtype=str).fillna("")
    missing = [col for col in ATTENDEE_COLUMNS if col not in df.columns]
    if missing:
        raise ValueError(
            f"Attendee CSV missing required columns: {', '.join(missing)}"
        )
    return df[ATTENDEE_COLUMNS]


@st.cache_data(show_spinner=False)
def load_signins() -> pd.DataFrame:
    if not SIGNIN_FILE.exists():
        return pd.DataFrame(columns=SIGNIN_COLUMNS)
    df = pd.read_csv(SIGNIN_FILE, dtype=str).fillna("")
    missing = [col for col in SIGNIN_COLUMNS if col not in df.columns]
    if missing:
        raise ValueError(f"Sign-in CSV missing required columns: {', '.join(missing)}")
    return df[SIGNIN_COLUMNS]


def append_signin(entry: dict[str, str]) -> None:
    df = load_signins()
    df = pd.concat([df, pd.DataFrame([entry])], ignore_index=True)
    df.to_csv(SIGNIN_FILE, index=False)
    load_signins.clear()


def replace_attendees(new_df: pd.DataFrame) -> None:
    new_df = new_df.astype(str).fillna("")
    missing = [col for col in ATTENDEE_COLUMNS if col not in new_df.columns]
    if missing:
        raise ValueError(
            f"Uploaded attendee list missing required columns: {', '.join(missing)}"
        )
    new_df.to_csv(ATTENDEE_FILE, index=False)
    load_attendees.clear()


def save_signature_image(image_data: np.ndarray) -> str:
    """Persist the signature image and return its relative path."""
    if image_data is None:
        raise ValueError("No signature data to save.")
    image = Image.fromarray((image_data).astype("uint8"))
    # Convert transparent pixels to white background for readability.
    background = Image.new("RGBA", image.size, "WHITE")
    composed = Image.alpha_composite(background, image).convert("RGB")

    file_id = uuid.uuid4().hex
    file_path = SIGNATURE_DIR / f"{file_id}.png"
    composed.save(file_path, format="PNG")
    relative_path = file_path.relative_to(BASE_DIR)
    return relative_path.as_posix()


def is_signature_blank(image_data: np.ndarray | None) -> bool:
    if image_data is None:
        return True
    # Check if all RGB pixels are white (255). If so, no stroke was drawn.
    rgb_pixels = image_data[:, :, :3]
    return np.all(rgb_pixels == 255)


def sign_in_page() -> None:
    st.header("Education Sign-In")
    attendees = load_attendees()

    if attendees.empty:
        st.warning(
            "No attendee list available. Please contact the admin to upload one."
        )
        return

    use_existing = st.toggle(
        "I'm on the attendee list", value=True, help="Disable if you are a walk-in."
    )

    selected_attendee = None
    attendee_id = ""
    name = ""
    company = ""
    email = ""

    if use_existing:
        selected_attendee = st.session_state.get("selected_attendee")
        search_query = st.text_input(
            "Search for your name, company, or email",
            key="attendee_search",
            placeholder="Start typing to filter the list...",
        )

        filtered_attendees = filter_attendees(attendees, search_query)
        filtered_records = filtered_attendees.to_dict("records")

        if selected_attendee:

            def matches_selected(record: dict[str, str]) -> bool:
                record_id = (record.get("attendee_id") or "").strip()
                selected_id = (selected_attendee.get("attendee_id") or "").strip()
                if record_id and selected_id:
                    return record_id == selected_id
                return (
                    record.get("name") == selected_attendee.get("name")
                    and record.get("email") == selected_attendee.get("email")
                )

            if not any(matches_selected(record) for record in filtered_records):
                selected_attendee = None
                st.session_state.pop("selected_attendee", None)

        max_results = 12
        if len(filtered_records) > max_results:
            st.info(
                f"Showing first {max_results} matches. Refine your search for more precise results."
            )
            filtered_records = filtered_records[:max_results]

        if not filtered_records:
            st.warning(
                "No attendees match that search. Try a different name or switch off the toggle if you are a walk-in."
            )
        else:
            st.caption("Tap your name to fill in the form automatically.")
            columns_per_row = 2
            for start in range(0, len(filtered_records), columns_per_row):
                row_records = filtered_records[start : start + columns_per_row]
                row_cols = st.columns(len(row_records))
                for idx, (col, record) in enumerate(zip(row_cols, row_records)):
                    name_line = record.get("name") or "Unnamed attendee"
                    extra_lines = [
                        value for value in (record.get("company"), record.get("email")) if value
                    ]
                    button_label = "\n".join([name_line] + extra_lines)
                    unique_fragment = (
                        record.get("attendee_id")
                        or record.get("email")
                        or record.get("name")
                        or f"{start}_{idx}"
                    )
                    button_key = f"attendee_btn_{unique_fragment}_{start}_{idx}"
                    if col.button(button_label, key=button_key, use_container_width=True):
                        st.session_state["selected_attendee"] = record
                        selected_attendee = record

        selected_attendee = st.session_state.get("selected_attendee")
        if selected_attendee:
            company_suffix = (
                f" ({selected_attendee['company']})"
                if selected_attendee.get("company")
                else ""
            )
            st.success(
                f"Selected: {selected_attendee.get('name', 'Unknown attendee')}{company_suffix}"
            )
            attendee_id = selected_attendee.get("attendee_id", "")
            name = selected_attendee.get("name", "")
            company = selected_attendee.get("company", "")
            email = selected_attendee.get("email", "")
    else:
        st.session_state.pop("selected_attendee", None)
        if "attendee_search" in st.session_state:
            st.session_state["attendee_search"] = ""

    name = st.text_input("Full name*", value=name)
    company = st.text_input("Company", value=company)
    email = st.text_input("Email", value=email)

    st.markdown("#### Signature")
    st.caption("Please sign inside the box below.")

    canvas_result = st_canvas(
        fill_color="#FFFFFF",
        stroke_width=2,
        stroke_color="#000000",
        background_color="#FFFFFF",
        height=200,
        width=600,
        drawing_mode="freedraw",
        key="signature_canvas",
    )

    submitted = st.button("Submit sign-in", type="primary")

    if submitted:
        errors = []
        if not name.strip():
            errors.append("Name is required.")
        if is_signature_blank(getattr(canvas_result, "image_data", None)):
            errors.append("Signature is required.")

        if errors:
            for err in errors:
                st.error(err)
            return

        try:
            signature_path = save_signature_image(canvas_result.image_data)
        except ValueError as exc:
            st.error(str(exc))
            return

        entry = {
            "record_id": uuid.uuid4().hex,
            "attendee_id": attendee_id,
            "name": name.strip(),
            "company": company.strip(),
            "email": email.strip(),
            "signed_at": datetime.now(timezone.utc).isoformat(),
            "signature_file": signature_path,
        }
        append_signin(entry)

        st.success("Thank you! Your sign-in has been recorded.")
        st.session_state.pop("signature_canvas", None)


def admin_login_page() -> None:
    st.header("Admin Login")
    st.caption(
        "Enter the admin credentials. You can override them with the "
        "`ADMIN_USERNAME` and `ADMIN_PASSWORD` environment variables."
    )

    with st.form("admin_login"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Log in")

    if submitted:
        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            st.session_state["admin_authenticated"] = True
            st.success("Logged in successfully.")
            st.rerun()
        else:
            st.error("Invalid credentials. Please try again.")


def admin_page() -> None:
    st.header("Admin Panel")
    st.caption(
        "Upload attendee lists, monitor sign-ins, and export data for certificates."
    )

    attendees = load_attendees()
    signins = load_signins()

    col1, col2 = st.columns(2)
    col1.metric("Registered attendees", len(attendees))
    col2.metric("Sign-ins collected", len(signins))

    with st.expander("Current attendee list", expanded=False):
        st.dataframe(attendees)

    with st.expander("Sign-in records", expanded=False):
        st.dataframe(signins)

    st.subheader("Replace attendee list")
    uploaded_file = st.file_uploader(
        "Upload CSV with columns: attendee_id, name, company, email", type=["csv"]
    )
    if uploaded_file is not None:
        try:
            new_df = pd.read_csv(uploaded_file, dtype=str).fillna("")
            replace_attendees(new_df)
            st.success("Attendee list updated successfully.")
            st.rerun()
        except Exception as exc:  # noqa: BLE001 (streamlit feedback)
            st.error(f"Could not import attendee list: {exc}")

    st.subheader("Downloads")
    signins_csv = signins.to_csv(index=False).encode("utf-8")
    st.download_button(
        "Download sign-ins as CSV",
        data=signins_csv,
        file_name=f"signins-{datetime.now().strftime('%Y%m%d-%H%M%S')}.csv",
        mime="text/csv",
    )

    if st.button(
        "Clear sign-in records",
        help="Use at the start of a new education session.",
    ):
        pd.DataFrame(columns=SIGNIN_COLUMNS).to_csv(SIGNIN_FILE, index=False)
        load_signins.clear()
        st.success("Sign-in records cleared.")
        st.rerun()

    if st.button("Log out"):
        st.session_state["admin_authenticated"] = False
        st.success("You have been logged out.")
        st.rerun()


def main() -> None:
    ensure_storage()
    st.set_page_config(
        page_title="Education Sign-In", page_icon=":memo:", layout="wide"
    )

    if "admin_authenticated" not in st.session_state:
        st.session_state["admin_authenticated"] = False

    page = st.sidebar.radio("Navigation", ["Sign In", "Admin"])
    if page == "Admin":
        if st.session_state.get("admin_authenticated", False):
            admin_page()
        else:
            admin_login_page()
    else:
        sign_in_page()


if __name__ == "__main__":
    main()
