from .core import Source, Handle, FileResource, ShareableCookie

from os import stat
import os.path
from urllib.parse import quote, unquote, urlsplit, urlunsplit
from pathlib import Path
from datetime import datetime
from contextlib import contextmanager


class FilesystemSource(Source):
    type_label = "file"

    def __init__(self, path):
        if not os.path.isabs(path):
            raise ValueError("Path {0} is not absolute".format(path))
        self._path = path

    @property
    def path(self):
        return self._path

    def handles(self, sm):
        pathlib_path = Path(self.path)
        for d in pathlib_path.glob("**"):
            for f in d.iterdir():
                if f.is_file():
                    yield FilesystemHandle(self,
                            str(f.relative_to(pathlib_path)))

    def __str__(self):
        return "FilesystemSource({0})".format(self.path)

    def _generate_state(self, sm):
        yield ShareableCookie(self.path)

    def to_url(self):
        return urlunsplit(('file', '', quote(str(self.path)), None, None))

    @staticmethod
    @Source.url_handler("file")
    def from_url(url):
        scheme, netloc, path, _, _ = urlsplit(url)
        assert not netloc
        return FilesystemSource(unquote(path) if path else None)

    def to_json_object(self):
        return dict(**super().to_json_object(), **{
            "path": self.path
        })

    @staticmethod
    @Source.json_handler(type_label)
    def from_json_object(obj):
        return FilesystemSource(path=obj["path"])


@Handle.stock_json_handler("file")
class FilesystemHandle(Handle):
    type_label = "file"

    @property
    def presentation(self):
        return str(Path(self.source.path).joinpath(self.relative_path))

    def follow(self, sm):
        return FilesystemResource(self, sm)


class FilesystemResource(FileResource):
    def __init__(self, handle, sm):
        super().__init__(handle, sm)
        self._full_path = os.path.join(
                self._get_cookie(), self.handle.relative_path)
        self._stat = None

    def get_stat(self):
        if not self._stat:
            self._stat = os.stat(self._full_path)
        return self._stat

    def get_size(self):
        return self.get_stat().st_size

    def get_last_modified(self):
        return datetime.fromtimestamp(self.get_stat().st_mtime)

    @contextmanager
    def make_path(self):
        yield self._full_path

    @contextmanager
    def make_stream(self):
        with open(self._full_path, "rb") as s:
            yield s
