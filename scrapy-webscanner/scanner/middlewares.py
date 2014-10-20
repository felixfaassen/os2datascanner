# The contents of this file are subject to the Mozilla Public License
# Version 2.0 (the "License"); you may not use this file except in
# compliance with the License. You may obtain a copy of the License at
#    http://www.mozilla.org/MPL/
#
# Software distributed under the License is distributed on an "AS IS"basis,
# WITHOUT WARRANTY OF ANY KIND, either express or implied. See the License
# for the specific language governing rights and limitations under the
# License.
#
# OS2Webscanner was developed by Magenta n collaboration with OS2 the
# Danish community of open source municipalities (http://www.os2web.dk/).
#
# The code is currently governed by OS2 the Danish community of open
# source municipalities ( http://www.os2web.dk/ )
"""Middleware for the scanner."""

import datetime
import pytz

from scrapy import Request
from scrapy import log, signals
from scrapy.contrib.downloadermiddleware.redirect import RedirectMiddleware
from scrapy.contrib.spidermiddleware.offsite import OffsiteMiddleware
from scrapy.exceptions import IgnoreRequest
from scrapy.utils.httpobj import urlparse_cached
from scrapy.utils.url import canonicalize_url

from email.utils import parsedate_tz, mktime_tz
from os2webscanner.models import UrlLastModified


class ExclusionRuleMiddleware(object):

    """A Spider Middleware which excludes certain URLs from being followed.

    If the spider has an exclusion_rules attribute, this is used to determine
    whether to visit the URLs.
    The exclusion_rules is a list which can be either strings or compiled
    regular expressions.
    """

    def process_spider_output(self, response, result, spider):
        """Process the output of a spider."""
        for x in result:
            if isinstance(x, Request):
                if self.should_follow(x, spider):
                    yield x
                else:
                    # TODO: Log excluded URLs somewhere?
                    log.msg("Excluding %s" % x.url)
            else:
                yield x

    def should_follow(self, request, spider):
        """Return whether the URL should be followed."""
        return not spider.is_excluded(request)


class NoSubdomainOffsiteMiddleware(OffsiteMiddleware):

    """Offsite middleware which doesn't allow subdomains of allowed_domains."""

    def get_host_regex(self, spider):
        """Disallow subdomains of the allowed domains.

        Overrides OffsiteMiddleware.
        """
        return spider.get_host_regex()


class OffsiteDownloaderMiddleware(object):

    """Offsite middleware which doesn't allow subdomains of allowed_domains."""

    @classmethod
    def from_crawler(cls, crawler):
        """Connect spider open signal."""
        o = cls()
        crawler.signals.connect(o.spider_opened, signal=signals.spider_opened)
        return o

    def process_request(self, request, spider):
        """Process a spider request."""
        if request.dont_filter or self.should_follow(request, spider):
            return None
        else:
            domain = urlparse_cached(request).hostname
            log.msg(format="Filtered offsite request to " +
                    "%(domain)r: %(request)s",
                    level=log.DEBUG, spider=spider, domain=domain,
                    request=request)
            raise IgnoreRequest

    def should_follow(self, request, spider):
        """Return whether the request should be followed."""
        regex = self.host_regex
        # hostname can be None for wrong urls (like javascript links)
        host = urlparse_cached(request).hostname or ''
        return bool(regex.search(host))

    def get_host_regex(self, spider):
        """Return the regex which hosts should be matched against."""
        return spider.get_host_regex()

    def spider_opened(self, spider):
        """Store the spider's host regex."""
        self.host_regex = self.get_host_regex(spider)


class ExclusionRuleDownloaderMiddleware(object):

    """Exclusion rule downloader middleware."""

    def process_request(self, request, spider):
        """Process a spider request."""
        if request.dont_filter or self.should_follow(request, spider):
            return None
        else:
            raise IgnoreRequest

    def should_follow(self, request, spider):
        """Return whether the request should be followed (not excluded)."""
        return not spider.is_excluded(request)


class OffsiteRedirectMiddleware(RedirectMiddleware,
                                NoSubdomainOffsiteMiddleware,
                                ExclusionRuleMiddleware):

    """Handle redirects, ensuring they are not offsite or excluded URLs."""

    def process_response(self, request, response, spider):
        """Process a spider response."""
        if not hasattr(self, 'host_regex'):
            self.host_regex = self.get_host_regex(spider)
        result = RedirectMiddleware.process_response(
            self, request, response, spider
        )
        if isinstance(result, Request):
            # Check that the redirect request is not offsite
            if NoSubdomainOffsiteMiddleware.should_follow(self, result,
                                                          spider):
                if ExclusionRuleMiddleware.should_follow(self, result,
                                                         spider):
                    return result
                else:
                    log.msg("Excluding redirect due to exclusion rule %s" %
                            result.url)
                    raise IgnoreRequest
            else:
                log.msg("Excluding redirect due to no offsite domains %s" %
                        result.url)
                raise IgnoreRequest
        else:
            return result


class LastModifiedLinkStorageMiddleware(object):

    """Spider middleware to store links on pages for Last-Modified check."""

    def process_spider_output(self, response, result, spider):
        """Process spider output."""
        if not getattr(spider, "do_last_modified_check", False):
            return result
        last_modified_header = response.headers.get("Last-Modified", None)
        if last_modified_header is None:
            # We don't need to store the links, since the page has no
            # Last-Modified header.
            return result

        source_url = canonicalize_url(response.request.url)
        try:
            url_last_modified = UrlLastModified.objects.get(
                url=source_url,
                scanner=self.get_scanner(spider)
            )
        except UrlLastModified.DoesNotExist:
            # We never stored the URL for the original request: this
            # shouldn't happen.
            return result

        log.msg("Updating links for %s" % url_last_modified, level=log.DEBUG)

        # Clear existing links
        url_last_modified.links.clear()

        # log.msg("Spider result: %s" % result)

        # Update links
        for r in result:
            if isinstance(r, Request):
                if spider.is_offsite(r) or spider.is_excluded(r):
                    continue
                target_url = canonicalize_url(r.url)
                # Get or create a URL last modified object
                try:
                    link = UrlLastModified.objects.get(
                        url=target_url,
                        scanner=self.get_scanner(spider)
                    )
                except UrlLastModified.DoesNotExist:
                    # Create new link
                    link = UrlLastModified(
                        url=target_url,
                        last_modified=None,
                        scanner=self.get_scanner(spider)
                    )
                    link.save()
                # Add the link to the URL last modified object
                url_last_modified.links.add(link)
                log.msg("Added link %s" % link, level=log.DEBUG)
        return result

    def get_scanner(self, spider):
        """Return the spider's scanner object."""
        return spider.scanner.scan_object


class LastModifiedCheckMiddleware(object):

    """Check the Last-Modified header to filter responses.

    Only process a response if the content for the URL has been updated as
    indicated by the Last-Modified header.

    Optionally, change GET requests into HEAD requests (to avoid
    transferring too much data before we know if a URL has been updated),
    then check the Last-Modified header before issuing a new request.

    Last-modified dates are stored in the database.
    """

    def __init__(self, crawler):
        """Initialize the middleware."""
        self.crawler = crawler
        self.stats = crawler.stats

    @classmethod
    def from_crawler(cls, crawler):
        """Instantiate the middleware."""
        return cls(crawler)

    def process_request(self, request, spider):
        """Process a spider request."""
        # Make the request into a HEAD request instead of a GET request,
        # if the spider says we should and if we haven't
        # already checked the last modified date.
        if (getattr(spider, 'do_last_modified_check', False) and
                getattr(spider, 'do_last_modified_check_head_request', True)
                and not request.meta.get('skip_modified_check', False) and
                request.method != "HEAD" and
                self.get_stored_last_modified_date(request.url, spider) is not
                None):
            log.msg("Replacing with HEAD request %s" % request,
                    level=log.DEBUG)
            return request.replace(method='HEAD')
        else:
            return None

    def process_response(self, request, response, spider):
        """Process a spider response."""
        # Don't run the check if it's not specified by the spider
        if request.meta.get('skip_modified_check', False):
            return response
        if not getattr(spider, 'do_last_modified_check', False):
            return response

        # We only handle HTTP status OK responses
        if response.status != 200:
            return response

        # Check the Last-Modified header to see if the content has been
        # updated since the last time we checked it.
        if self.has_been_modified(request, response, spider):
            if request.method == 'HEAD':
                # Issue a new GET request, since the data was updated
                log.msg("Issuing a new GET for %s" % request, level=log.DEBUG)

                # Skip the modified check, since we just did the check
                meta = request.meta
                meta["skip_modified_check"] = True

                # Have to pass dont_filter=True or the request will be
                # filtered by the duplicates filter (since it was originally
                # scheduled as a GET request already).
                return request.replace(method='GET', dont_filter=True)
            else:
                # If it's a GET request, process the response
                return response
        else:
            # Add requests for all the links that we know were on the
            # page the last time we visited it.
            links = self.get_stored_links(response.url, spider)
            for link in links:
                req = Request(link.url,
                              callback=request.callback,
                              errback=request.errback,
                              headers={"referer": response.url})
                log.msg("Adding request %s" % req, level=log.DEBUG)
                self.crawler.engine.crawl(req, spider)
            # Ignore the request, since the content has not been modified
            self.stats.inc_value('last_modified_check/pages_skipped')
            raise IgnoreRequest

    def get_stored_links(self, url, spider):
        """Return the links that have been stored for this URL."""
        url = canonicalize_url(url)
        try:
            url_last_modified = UrlLastModified.objects.get(
                url=url, scanner=self.get_scanner(spider))
            return url_last_modified.links.all()
        except UrlLastModified.DoesNotExist:
            return []

    def get_stored_last_modified_date(self, url, spider):
        """Return the last modified date that has been stored for this URL."""
        url_last_modified_object = self.get_stored_last_modified_object(url,
                                                                        spider)
        if url_last_modified_object is not None:
            return url_last_modified_object.last_modified
        else:
            return None

    def get_stored_last_modified_object(self, url, spider):
        """Return the UrlLastModified object for the given URL."""
        url = canonicalize_url(url)
        try:
            url_last_modified = UrlLastModified.objects.get(
                url=url, scanner=self.get_scanner(spider))
            return url_last_modified
        except UrlLastModified.DoesNotExist:
            return None

    def get_scanner(self, spider):
        """Return the spider's scanner object."""
        return spider.scanner.scan_object

    def has_been_modified(self, request, response, spider):
        """Return whether the response was modified since last seen.

        We check against the database here.
        If the response has been modified, we update the database.
        If there is no stored last modified date, we save one.
        """
        # Check the Last-Modified header to see if the content has been
        # updated since the last time we checked it.
        last_modified_header = response.headers.get("Last-Modified", None)
        last_modified_header_date = datetime.datetime.fromtimestamp(
            mktime_tz(parsedate_tz(last_modified_header)), tz=pytz.utc
        ) if last_modified_header is not None else None

        # lastmod comes from a sitemap.xml file
        sitemap_lastmod_date = request.meta.get("lastmod", None)
        if sitemap_lastmod_date is None:
            last_modified = last_modified_header_date
            log.msg("Using header's last-modified date: %s" % last_modified,
                    level=log.DEBUG)
        else:
            if last_modified_header_date is None:
                # No Last-Modified header, use the lastmod from the sitemap
                last_modified = sitemap_lastmod_date
                log.msg("Using lastmod from sitemap %s" % last_modified,
                        level=log.DEBUG)
            else:
                # Take the most recent of the two
                log.msg("Taking most recent of (header) %s and (sitemap) %s" %
                        (last_modified_header_date, sitemap_lastmod_date),
                        level=log.DEBUG)
                last_modified = max(last_modified_header_date,
                                    sitemap_lastmod_date)
                log.msg("Last modified %s" % last_modified,
                        level=log.DEBUG)

        # log.msg("Last modified header: %s" % last_modified_header)
        if last_modified is not None:
            # Check against the database
            canonical_url = canonicalize_url(response.url)
            try:
                url_last_modified = UrlLastModified.objects.get(
                    url=canonical_url, scanner=self.get_scanner(spider))
                stored_last_modified = url_last_modified.last_modified
                log.msg("Comparing header %s against stored %s" % (
                    last_modified, stored_last_modified), level=log.INFO)
                if (stored_last_modified is not None
                        and last_modified == stored_last_modified):
                    return False
                else:
                    # Update last-modified date in database
                    url_last_modified.last_modified = last_modified
                    url_last_modified.save()
                    return True
            except UrlLastModified.DoesNotExist:
                log.msg("No stored Last-Modified header found.",
                        level=log.DEBUG)
                url_last_modified = UrlLastModified(
                    url=canonical_url,
                    last_modified=last_modified,
                    scanner=self.get_scanner(spider)
                )
                log.msg("Saving new last-modified value %s" %
                        url_last_modified, level=log.DEBUG)
                url_last_modified.save()
                return True
        else:
            # If there is no Last-Modified header, we have to assume it has
            # been modified.
            return True
