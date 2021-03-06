from io import BytesIO
import os.path
import email
from contextlib import contextmanager

from ...conversions.utilities.results import SingleResult
from ..core import Source, Handle, FileResource, SourceManager
from ..utilities import NamedTemporaryResource
from .derived import DerivedSource


def _parts_are_text_body(parts):
    return (len(parts) == 2
            and parts[0].get_content_type() == "text/plain"
            and parts[1].get_content_type() == "text/html")


@Source.mime_handler("message/rfc822")
class MailSource(DerivedSource):
    type_label = "mail"

    def _generate_state(self, sm):
        with self.handle.follow(sm).make_stream() as fp:
            yield email.message_from_bytes(fp.read())

    def handles(self, sm):
        def _process_message(path, part):
            ct, st = part.get_content_maintype(), part.get_content_subtype()
            if ct == "multipart":
                parts = part.get_payload()
                # XXX: this is a slightly hacky implementation of multipart/
                # alternative, but we don't know what task we're being asked to
                # perform and so we can't do any better
                if st == "alternative" and _parts_are_text_body(parts):
                    yield from _process_message(path + ["1"], parts[1])
                else:
                    for idx, part in enumerate(parts):
                        yield from _process_message(path + [str(idx)], part)
            else:
                filename = part.get_filename()
                full_path = "/".join(path + [filename or ''])
                yield MailPartHandle(self, full_path, part.get_content_type())
        yield from _process_message([], sm.open(self))


class MailPartResource(FileResource):
    def __init__(self, handle, sm):
        super().__init__(handle, sm)
        self._fragment = None

    def _get_fragment(self):
        if not self._fragment:
            where = self._get_cookie()
            path = self.handle.relative_path.split("/")[:-1]
            while path:
                next_idx, path = int(path[0]), path[1:]
                where = where.get_payload()[next_idx]
            self._fragment = where
        return self._fragment

    def get_last_modified(self):
        return super().get_last_modified()

    def get_size(self):
        with self.make_stream() as s:
            initial = s.seek(0, 1)
            try:
                s.seek(0, 2)
                return SingleResult(None, "size", s.tell())
            finally:
                s.seek(initial, 0)

    @contextmanager
    def make_path(self):
        with NamedTemporaryResource(self.handle.name) as ntr:
            with ntr.open("wb") as res:
                with self.make_stream() as s:
                    res.write(s.read())
            yield ntr.get_path()

    @contextmanager
    def make_stream(self):
        yield BytesIO(self._get_fragment().get_payload(decode=True))


class MailPartHandle(Handle):
    type_label = "mail-part"
    resource_type = MailPartResource

    def __init__(self, source, path, mime):
        super().__init__(source, path)
        self._mime = mime

    @property
    def presentation(self):
        basename = os.path.basename(self.relative_path)
        if not basename:
            return self.source.handle.presentation
        else:
            return "{0} (in {1})".format(basename, self.source.handle)

    def censor(self):
        return MailPartHandle(
                self.source.censor(), self.relative_path, self._mime)

    def guess_type(self):
        return self._mime

    def to_json_object(self):
        return dict(**super().to_json_object(), **{
            "mime": self._mime
        })

    @staticmethod
    @Handle.json_handler(type_label)
    def from_json_object(obj):
        return MailPartHandle(Source.from_json_object(obj["source"]),
                obj["path"], obj["mime"])
