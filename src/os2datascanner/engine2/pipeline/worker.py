from os import getpid

from prometheus_client import start_http_server

from ..model.core import SourceManager
from .utilities import (notify_ready, PikaPipelineRunner, notify_stopping,
        prometheus_summary, make_common_argument_parser,
        make_sourcemanager_configuration_block)
from .explorer import message_received_raw as explorer_handler
from .processor import message_received_raw as processor_handler
from .matcher import message_received_raw as matcher_handler
from .tagger import message_received_raw as tagger_handler

def explore(sm, msg):
    for channel, message in explorer_handler(msg, "ss", sm, "co", "pr"):
        if channel == "co":
            yield from process(sm, message)
        elif channel in ('pr',):
            yield channel, message


def process(sm, msg):
    for channel, message in processor_handler(msg, "co", sm, "re", "ss", "pr"):
        if channel == "re":
            yield from match(sm, message)
        elif channel == "ss":
            yield from explore(sm, message)
        elif channel in ('pr',):
            yield channel, message


def match(sm, msg):
    for channel, message in matcher_handler(msg, "re", "ma", "me", "co"):
        if channel == "me":
            yield from tag(sm, message)
        elif channel == "co":
            yield from process(sm, message)
        elif channel in ('ma',):
            yield channel, message


def tag(sm, msg):
    yield from tagger_handler(msg, "ha", sm, "me", "pr")


def message_received_raw(body,
        channel, source_manager, matches_q, metadata_q, problems_q):
    for channel, message in process(source_manager, body):
        if channel == "ma":
            yield (matches_q, message)
        elif channel == "me":
            yield (metadata_q, message)
        elif channel == "pr":
            yield (problems_q, message)


def main():
    parser = make_common_argument_parser()
    parser.description = (
            "Consume and fully execute conversions, and generate matches and"
            " metadata messages.")

    inputs = parser.add_argument_group("inputs")
    inputs.add_argument(
            "--conversions",
            metavar="NAME",
            help="the name of the AMQP queue from which conversions"
                    + " should be read",
            default="os2ds_conversions")

    make_sourcemanager_configuration_block(parser)

    outputs = parser.add_argument_group("outputs")
    outputs.add_argument(
            "--matches",
            metavar="NAME",
            help="the name of the AMQP queue to which matches should be"
                    " written",
            default="os2ds_matches")
    outputs.add_argument(
            "--problems",
            metavar="NAME",
            help="the name of the AMQP queue to which problems should be"
                    " written",
            default="os2ds_problems")
    outputs.add_argument(
            "--metadata",
            metavar="NAME",
            help="the name of the AMQP queue to which metadata should be"
                    " written",
            default="os2ds_metadata")

    args = parser.parse_args()

    if args.enable_metrics:
        start_http_server(args.prometheus_port)

    class ProcessorRunner(PikaPipelineRunner):
        @prometheus_summary("os2datascanner_pipeline_worker",
                "Objects handled")
        def handle_message(self, body, *, channel=None):
            if args.debug:
                print(channel, body)
            return message_received_raw(body, channel, source_manager,
                    args.matches, args.metadata, args.problems)

    with SourceManager(width=args.width) as source_manager:
        with ProcessorRunner(
                read=[args.conversions],
                write=[args.matches, args.problems, args.metadata],
                heartbeat=6000) as runner:
            try:
                print("Start")
                notify_ready()
                runner.run_consumer()
            finally:
                print("Stop")
                notify_stopping()

if __name__ == "__main__":
    main()
