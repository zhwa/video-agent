import os
import tempfile
from agent.storage.dummy_storage import DummyStorageAdapter


def test_dummy_storage_upload_download(tmp_path):
    adapter = DummyStorageAdapter(base_dir=str(tmp_path / "store"))
    # create a temp file
    src = tmp_path / "hello.txt"
    src.write_text("hello world", encoding="utf-8")
    url = adapter.upload_file(str(src), dest_path="folder/hello.txt")
    assert url.startswith("file://")
    dest = tmp_path / "download.txt"
    downloaded = adapter.download_file(url, str(dest))
    assert os.path.exists(downloaded)
    assert open(downloaded, "r", encoding="utf-8").read() == "hello world"
