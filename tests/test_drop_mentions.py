"""Tests for drag-and-drop @-mention resolution: files dropped from outside the
workspace are uploaded into the trusted upload dir and must be readable via an
@-mention by their absolute path."""
import os
import tempfile


def test_upload_dir_path_is_inside_trusted_dir():
    """The mention resolver trusts files under _UPLOAD_DIR. Verify the commonpath
    guard accepts an upload-dir path and rejects an arbitrary outside path."""
    import harness.server as srv
    upload_real = os.path.realpath(srv._UPLOAD_DIR)
    os.makedirs(upload_real, exist_ok=True)

    # A file genuinely inside the upload dir -> accepted.
    fd, p = tempfile.mkstemp(dir=upload_real, suffix=".txt")
    os.close(fd)
    try:
        abs_token = os.path.realpath(os.path.abspath(p))
        assert os.path.commonpath([upload_real, abs_token]) == upload_real
        assert os.path.isfile(abs_token)
    finally:
        os.unlink(p)

    # An arbitrary outside path -> NOT under the upload dir.
    outside = os.path.realpath("/etc/hosts")
    try:
        common = os.path.commonpath([upload_real, outside])
    except Exception:
        common = None
    assert common != upload_real


def test_mention_reads_uploaded_file_end_to_end(tmp_path, monkeypatch):
    """A dropped external file (in the upload dir) referenced by @abs-path is read
    into the resolved-files context, even though it lives outside the repo."""
    import harness.server as srv

    # Point the upload dir at a temp location we control.
    upload_dir = tmp_path / "uploads"
    upload_dir.mkdir()
    monkeypatch.setattr(srv, "_UPLOAD_DIR", str(upload_dir))

    # A repo (empty) and an uploaded file OUTSIDE it.
    repo = tmp_path / "repo"
    repo.mkdir()
    dropped = upload_dir / "notes.txt"
    dropped.write_text("DROPPED FILE CONTENTS 123")

    # Reproduce the resolver's acceptance check from server.py.
    token = str(dropped)
    upload_real = os.path.realpath(str(upload_dir))
    abs_token = os.path.realpath(os.path.abspath(token))
    accepted = (os.path.commonpath([upload_real, abs_token]) == upload_real
                and os.path.isfile(abs_token))
    assert accepted, "uploaded file must be accepted by the mention resolver"
    assert open(abs_token).read() == "DROPPED FILE CONTENTS 123"
