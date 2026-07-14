"""Command-line interface entry point.

Parses arguments and dispatches to :mod:`pxygen.modes`.
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path

from . import __version__
from .i18n import _
from .modes import process_directory_mode, process_json_mode
from .paths import clean_path_input, is_json_file
from .presenter import ConsolePresenter, UserAbort
from .resolve import PxygenError

logger = logging.getLogger(__name__)


def configure_logging(log_level: str = "warning", log_file: str | None = None) -> None:
    """Configure application logging with a standard detailed format."""
    level = getattr(logging, log_level.upper())
    handlers: list[logging.Handler] = [logging.StreamHandler()]
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        handlers.append(logging.FileHandler(log_path, encoding="utf-8"))

    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=handlers,
        force=True,
    )


def _build_parser():
    import argparse

    class _Formatter(
        argparse.RawDescriptionHelpFormatter,
        argparse.ArgumentDefaultsHelpFormatter,
    ):
        pass

    default_depth = 1

    parser = argparse.ArgumentParser(
        prog="pxygen",
        description=(
            f"pxygen v{__version__}\n\n"
            + _("把素材文件夹或 fcmp JSON 报告传给 --input, 自动识别模式")
        ),
        formatter_class=_Formatter,
        epilog=(
            _("示例:") + "\n"
            "  pxygen -i /Volumes/SSD/Footage -o /Volumes/SSD/Proxy\n"
            "  pxygen -i fcmp_report.json -o /Volumes/SSD/Proxy --group b\n"
            "  pxygen -i /Volumes/SSD/Footage -o /Proxy --select\n"
            "  pxygen -i /Volumes/SSD/Footage -o /Proxy --filter Day1 Day2\n"
        ),
    )

    parser.add_argument(
        "-v", "-V", "--version",
        action="version", version=f"pxygen v{__version__}",
    )
    parser.add_argument("-i", "--input", help=_("素材文件夹或 fcmp JSON 报告"))
    parser.add_argument("-o", "--output", help=_("代理输出文件夹"))
    parser.add_argument(
        "-n", "--in-depth",
        type=int, default=default_depth,
        help=_("输入文件夹之下第几层作为一个素材分组"),
    )
    parser.add_argument(
        "-d", "--out-depth",
        type=int, default=default_depth,
        help=_("输入文件夹之下第几层保留为子文件夹"),
    )
    parser.add_argument(
        "-g", "--group",
        choices=["a", "b"], default="a",
        help=_("JSON 模式: 渲染 fcmp 的哪一侧 (a = unique_in_a, b = unique_in_b)"),
    )

    selection_group = parser.add_mutually_exclusive_group()
    selection_group.add_argument(
        "-s", "--select", action="store_true",
        help=_("交互式选择要处理的文件夹"),
    )
    selection_group.add_argument(
        "-f", "--filter", nargs="+", metavar="NAME",
        help=_("只处理指定名称的文件夹 (如 Day1 Day2)"),
    )

    parser.add_argument(
        "-k", "--codec",
        choices=["auto", "prores", "h265", "hevc", "265"],
        default="auto",
        help=_("渲染编码 (≤4 音轨用 h265, 更多音轨用 ProRes)"),
    )
    parser.add_argument(
        "--log-level",
        choices=["debug", "info", "warning", "error"],
        default="warning",
        help=_("日志详细程度"),
    )
    parser.add_argument(
        "--log-file",
        help=_("可选: 详细运行日志的输出文件路径"),
    )

    return parser


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()
    configure_logging(args.log_level, args.log_file)
    presenter = ConsolePresenter()

    filter_mode = "select" if args.select else ("filter" if args.filter else None)
    filter_list = args.filter if filter_mode == "filter" else None

    shared = dict(
        filter_mode=filter_mode,
        filter_list=filter_list,
        codec=args.codec,
        input_func=presenter.read_line,
        output=presenter.show,
        confirm_render=lambda: presenter.confirm(
            "\n" + _("所有渲染任务已添加, 现在开始渲染? (y/n)")
        ),
    )

    try:
        if not args.input:
            parser.print_help()
            sys.exit(1)
        if not args.output:
            parser.error(_("缺少 -o/--output 输出目录"))
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

    except UserAbort as exc:
        presenter.show(str(exc) or _("已中止"))
        sys.exit(0)
    except PxygenError as exc:
        logger.error("%s", exc)
        sys.exit(1)
    except ValueError as exc:
        logger.error("%s", exc)
        sys.exit(1)
    except AttributeError as exc:
        # Typically: Resolve API returned None (Resolve not running or API call failed)
        logger.error(_("Resolve API 错误: %s"), exc)
        logger.error(_("请确认 DaVinci Resolve 正在运行"))
        sys.exit(1)
    except KeyboardInterrupt:
        logger.error(_("已中止"))
        sys.exit(1)


if __name__ == "__main__":
    main()
