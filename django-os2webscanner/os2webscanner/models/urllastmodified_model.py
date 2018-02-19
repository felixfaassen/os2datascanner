from django.db import models

from webscanner_model import WebScanner


class UrlLastModified(models.Model):

    """A representation of a URL, its last-modifed date, and its links."""

    url = models.CharField(max_length=2048, verbose_name='Url')
    last_modified = models.DateTimeField(blank=True, null=True,
                                         verbose_name='Last-modified')
    links = models.ManyToManyField("self", symmetrical=False,
                                   verbose_name='Links')
    scanner = models.ForeignKey(WebScanner, null=False, verbose_name='WebScanner')

    def __unicode__(self):
        """Return the URL and last modified date."""
        return "<%s %s>" % (self.url, self.last_modified)
