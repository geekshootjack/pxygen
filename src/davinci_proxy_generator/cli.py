"""Command-line interface entry point.

Parses arguments and dispatches to :mod:`davinci_proxy_generator.modes`.
Supports both named flags and the legacy positional-argument syntax.
"""
from __future__ import annotations

import platform
import sys

from .modes import process_directory_mode, process_json_mode
from .paths import clean_path_input, is_json_file
from .resolve import ProxyGeneratorError


def _build_parser():
    import argparse

    class _Formatter(
        argparse.RawDescriptionHelpFormatter,
        argparse.ArgumentDefaultsHelpFormatter,
    ):
        pass

    default_depth = 5 if platform.system() == "Darwin" else 4

    parser = argparse.ArgumentParser(
        prog="proxy-generator",
        description=(
            "DaVinci Resolve Proxy Generator v1.5.2\n\n"
            "Pass a footage folder or a JSON comparison file to --input;\n"
            "the mode is detected automatically."
        ),
        formatter_class=_Formatter,
        epilog=(
            "Examples:\n"
            "  proxy-generator -i /Volumes/SSD/Footage -o /Volumes/SSD/Proxy\n"
            "  proxy-generator -i comparison.json -o /Volumes/SSD/Proxy --group 2\n"
            "  proxy-generator -i /Volumes/SSD/Footage -o /Proxy --select\n"
            '  proxy-generator -i /Volumes/SSD/Footage -o /Proxy --filter "Day1,Day2"\n'
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

    # Legacy positional arguments kept for backward compatibility
    parser.add_argument("args", nargs="*", help=argparse.SUPPRESS)

    return parser


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    filter_mode = "select" if args.select else ("filter" if args.filter else None)
    filter_list = args.filter if filter_mode == "filter" else None

    shared = dict(
        clean_image=args.clean_image,
        filter_mode=filter_mode,
        filter_list=filter_list,
        codec=args.codec,
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
                process_json_mode(first, output_path, args.group, args.in_depth, args.out_depth, **shared)
            else:
                process_directory_mode(first, output_path, args.in_depth, args.out_depth, **shared)

        else:
            parser.print_help()
            sys.exit(1)

    except ProxyGeneratorError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)
    except AttributeError as exc:
        # Typically: Resolve API returned None (Resolve not running or API call failed)
        print(f"Resolve API error: {exc}", file=sys.stderr)
        print("Make sure DaVinci Resolve is running.", file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nAborted.", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
