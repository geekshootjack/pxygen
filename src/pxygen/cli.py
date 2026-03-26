"""Command-line interface entry point.

Parses arguments and dispatches to :mod:`pxygen.modes`.
Supports both named flags and the legacy positional-argument syntax.
"""
from __future__ import annotations

import logging
import platform
import sys

from .logging_utils import configure_logging
from .modes import process_directory_mode, process_json_mode
from .paths import clean_path_input, is_json_file
from .presenter import ConsolePresenter
from .resolve import ProxyGeneratorError

logger = logging.getLogger(__name__)


def _build_parser():
    import argparse

    class _Formatter(
        argparse.RawDescriptionHelpFormatter,
        argparse.ArgumentDefaultsHelpFormatter,
    ):
        pass

    default_depth = 5 if platform.system() == "Darwin" else 4

    parser = argparse.ArgumentParser(
        prog="pxygen",
        description=(
            "pxygen v1.5.2\n\n"
            "Pass a footage folder or a JSON comparison file to --input;\n"
            "the mode is detected automatically."
        ),
        formatter_class=_Formatter,
        epilog=(
            "Examples:\n"
            "  pxygen -i /Volumes/SSD/Footage -o /Volumes/SSD/Proxy\n"
            "  pxygen -i comparison.json -o /Volumes/SSD/Proxy --group 2\n"
            "  pxygen -i /Volumes/SSD/Footage -o /Proxy --select\n"
            '  pxygen -i /Volumes/SSD/Footage -o /Proxy --filter "Day1,Day2"\n'
            "\nLegacy alias still works: proxy-generator"
        ),
    )

    parser.add_argument("-i", "--input", help="Footage folder or JSON comparison file")
    parser.add_argument("-o", "--output", help="Proxy output folder")
    parser.add_argument(
        "-n", "--in-depth",
        type=int, default=default_depth,
        help="Depth of shooting-day folders",
    )
    parser.add_argument(
        "-d", "--out-depth",
        type=int, default=default_depth,
        help="Depth of camera-reel folders",
    )
    parser.add_argument(
        "-g", "--group",
        type=int, choices=[1, 2], default=1,
        help="JSON mode: which comparison group to use",
    )

    selection_group = parser.add_mutually_exclusive_group()
    selection_group.add_argument(
        "-s", "--select", action="store_true",
        help="Interactively select which folders to process",
    )
    selection_group.add_argument(
        "-f", "--filter", type=str,
        help="Comma-separated folder names to process (e.g. 'Day1,Day2')",
    )

    parser.add_argument(
        "-c", "--clean-image", action="store_true",
        help="Generate proxies without burn-in overlays",
    )
    parser.add_argument(
        "-k", "--codec",
        choices=["auto", "prores", "h265", "hevc", "265"],
        default="auto",
        help="Render codec (h265 for ≤4 audio ch, ProRes otherwise)",
    )
    parser.add_argument(
        "--log-level",
        choices=["debug", "info", "warning", "error"],
        default="info",
        help="Logging verbosity",
    )
    parser.add_argument(
        "--log-file",
        help="Optional file path for detailed runtime logs",
    )
    parser.add_argument(
        "--web", action="store_true",
        help="Launch the WebUI in a browser (no -i/-o required)",
    )
    parser.add_argument(
        "--port", type=int, default=8321,
        help="Port for the WebUI server",
    )

    # Legacy positional arguments kept for backward compatibility
    parser.add_argument("args", nargs="*", help=argparse.SUPPRESS)

    return parser


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()
    configure_logging(args.log_level, args.log_file)
    presenter = ConsolePresenter()

    if args.web:
        from .server import launch_server
        launch_server(args.port)
        return

    filter_mode = "select" if args.select else ("filter" if args.filter else None)
    filter_list = args.filter if filter_mode == "filter" else None

    shared = dict(
        clean_image=args.clean_image,
        filter_mode=filter_mode,
        filter_list=filter_list,
        codec=args.codec,
        input_func=presenter.read_line,
        output=presenter.show,
        confirm_render=lambda: presenter.confirm(
            "\nAll render jobs added. Start rendering now? (y/n)"
        ),
    )

    try:
        if args.input:
            if not args.output:
                parser.error("requires -o/--output")
            input_path = clean_path_input(args.input)
            output_path = clean_path_input(args.output)
            if is_json_file(input_path):
                process_json_mode(
                    input_path, output_path,
                    args.group, args.in_depth, args.out_depth,
                    **shared,
                )
            else:
                process_directory_mode(
                    input_path, output_path,
                    args.in_depth, args.out_depth,
                    **shared,
                )

        elif len(args.args) >= 2:
            # Legacy positional: <footage_or_json> <proxy>
            first = clean_path_input(args.args[0])
            output_path = clean_path_input(args.args[1])
            if is_json_file(first):
                process_json_mode(
                    first,
                    output_path,
                    args.group,
                    args.in_depth,
                    args.out_depth,
                    **shared,
                )
            else:
                process_directory_mode(
                    first,
                    output_path,
                    args.in_depth,
                    args.out_depth,
                    **shared,
                )

        else:
            parser.print_help()
            sys.exit(1)

    except ProxyGeneratorError as exc:
        logger.error("%s", exc)
        sys.exit(1)
    except ValueError as exc:
        logger.error("%s", exc)
        sys.exit(1)
    except AttributeError as exc:
        # Typically: Resolve API returned None (Resolve not running or API call failed)
        logger.error("Resolve API error: %s", exc)
        logger.error("Make sure DaVinci Resolve is running.")
        sys.exit(1)
    except KeyboardInterrupt:
        logger.error("Aborted.")
        sys.exit(1)


if __name__ == "__main__":
    main()
