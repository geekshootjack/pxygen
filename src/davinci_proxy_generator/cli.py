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

    default_depth = 5 if platform.system() == "Darwin" else 4

    parser = argparse.ArgumentParser(
        prog="proxy-generator",
        description=(
            "DaVinci Resolve Proxy Generator v1.5.2\n\n"
            "Two modes:\n"
            "  Directory mode  (-f)  Import footage directly from a folder hierarchy.\n"
            "  JSON mode       (-j)  Re-generate missing proxies from a file-comparison JSON."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  proxy-generator -f /Volumes/SSD/Footage -p /Volumes/SSD/Proxy -i 4 -o 5\n"
            "  proxy-generator -j comparison.json -p /Volumes/SSD/Proxy -d 1 -i 4 -o 5\n"
            "  proxy-generator -f /Volumes/SSD/Footage -p /Proxy -i 4 -o 5 --select\n"
            '  proxy-generator -f /Volumes/SSD/Footage -p /Proxy -i 4 -o 5 --filter "Day1,Day2"\n'
        ),
    )

    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument("-f", "--footage", help="Footage folder path (Directory mode)")
    mode_group.add_argument("-j", "--json", help="Path to comparison JSON file (JSON mode)")

    parser.add_argument(
        "-d", "--dataset",
        type=int, choices=[1, 2], default=1,
        help="JSON mode: which group to use (default: 1)",
    )
    parser.add_argument("-p", "--proxy", help="Proxy output folder path")
    parser.add_argument(
        "-i", "--in-depth",
        type=int, default=default_depth,
        help=f"Depth of shooting-day folders (default: {default_depth})",
    )
    parser.add_argument(
        "-o", "--out-depth",
        type=int, default=default_depth,
        help=f"Depth of camera-reel folders (default: {default_depth})",
    )

    selection_group = parser.add_mutually_exclusive_group()
    selection_group.add_argument(
        "-s", "--select", action="store_true",
        help="Interactively select which folders to process",
    )
    selection_group.add_argument(
        "--filter", type=str,
        help="Comma-separated folder names to process (e.g. 'Day1,Day2')",
    )

    parser.add_argument(
        "-c", "--clean-image", action="store_true",
        help="Generate proxies without burn-in overlays",
    )
    parser.add_argument(
        "-C", "--codec",
        choices=["auto", "prores", "h265", "hevc", "265"],
        default="auto",
        help="Render codec override (default: auto — h265 for ≤4 audio ch, ProRes otherwise)",
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
        if args.json:
            if not args.proxy:
                parser.error("JSON mode requires -p/--proxy")
            process_json_mode(
                args.json,
                clean_path_input(args.proxy),
                args.dataset,
                args.in_depth,
                args.out_depth,
                **shared,
            )

        elif args.footage:
            if not args.proxy:
                parser.error("Directory mode requires -p/--proxy")
            process_directory_mode(
                clean_path_input(args.footage),
                clean_path_input(args.proxy),
                args.in_depth,
                args.out_depth,
                **shared,
            )

        elif len(args.args) >= 2:
            # Legacy positional: <footage_or_json> <proxy>
            first = clean_path_input(args.args[0])
            proxy_path = clean_path_input(args.args[1])
            if is_json_file(first):
                process_json_mode(first, proxy_path, args.dataset, args.in_depth, args.out_depth, **shared)
            else:
                process_directory_mode(first, proxy_path, args.in_depth, args.out_depth, **shared)

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
