#!/usr/bin/env python
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
# OS2datascanner was developed by Magenta in collaboration with OS2 the
# Danish community of open source municipalities (https://os2.eu/).
#
# The code is currently governed by OS2 the Danish community of open
# source municipalities ( https://os2.eu/ )
import structlog
from django.core.management.base import BaseCommand

from os2datascanner.utils.system_utilities import json_utf8_decode
from os2datascanner.utils.amqp_connection_manager import start_amqp, \
    set_callback, start_consuming, ack_message

from ...utils import hash_handle
from ...models.documentreport_model import DocumentReport

logger = structlog.get_logger()


def consume_results(channel, method, properties, body):
    print('Message recieved {} :'.format(body))
    ack_message(method)

    _restructure_and_save_result(body)


def _restructure_and_save_result(result):
    """Method for restructuring and storing result body.

    The agreed structure is as follows:
    {'scan_tag', '2019-11-28T14:56:58', 'matches': null, 'metadata': null,
    'problem': []}
    """
    updated_fields = _format_results(json_utf8_decode(result))
    if updated_fields:
        handle = result.get('handle')

        DocumentReport.objects.update_or_create(
            path=hash_handle(handle), data=updated_fields)


def _format_results(result):
    """Method for restructuring result body"""

    updated_fields = {}
    origin = result.get('origin')

    # TODO: Problem messages do not have a well enough
    # defined structure to be used in the system yet.
    # Therefore they are just logged for now.
    if origin == 'os2ds_problems':
        logger.info('Problem message recieved: {}'.format(result))
    elif origin == 'os2ds_metadata':
        updated_fields['scan_tag'] = result.get('scan_tag')
        updated_fields['metadata'] = result
    elif origin == 'os2ds_matches':
        if result.get('matched'):
            updated_fields['scan_tag'] = result.get('scan_spec').get('scan_tag')
            updated_fields['matches'] = result
        else:
            logger.info('Object processed with no matches: {}'.format(result))

    return updated_fields



class Command(BaseCommand):
    """Command for starting a pipeline collector process."""
    help = __doc__

    def add_arguments(self, parser):
        parser.add_argument(
            "--results",
            type=str,
            help="the name of the AMQP queue from which filtered result objects"
                 + " should be read",
            default="os2ds_results")

    def handle(self, results, *args, **options):

        # Start listning on matches queue
        start_amqp(results)
        set_callback(consume_results, results)
        start_consuming()
