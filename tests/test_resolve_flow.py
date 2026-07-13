"""Tests for pxygen.resolve orchestration."""
from __future__ import annotations

import logging
import sys
import types
from pathlib import Path
from unittest.mock import patch

import pytest

from pxygen.plan import build_resolve_execution_plan
from pxygen.presenter import UserAbort
from pxygen.resolve import PxygenError, execute_resolve_plan


def _process(
    organized_files,
    selected_footage_folders,
    proxy_folder_path,
    _subfolder_depth=None,
    *,
    is_directory_mode=False,
    codec="auto",
    output=None,
    confirm_render=None,
):
    plan = build_resolve_execution_plan(
        organized_files,
        selected_footage_folders,
        proxy_folder_path,
        mode_name="directory" if is_directory_mode else "json",
        codec=codec,
    )
    execute_resolve_plan(plan, output=output, confirm_render=confirm_render)


class FakeClip:
    def __init__(self, resolution: str, audio_channels: str | None, clip_type: str = "Video"):
        self._properties = {
            "Resolution": resolution,
            "Audio Ch": audio_channels,
            "Type": clip_type,
        }

    def GetClipProperty(self, name: str | None = None):
        if name is None:
            return dict(self._properties)
        return self._properties.get(name)


class FakeTimeline:
    def __init__(self, name: str):
        self.name = name
        self.settings = {}
        self.clips = []

    def SetSetting(self, key: str, value: str):
        self.settings[key] = value
        return True

    def GetSetting(self, key: str):
        return self.settings.get(key)


class FakeFolder:
    def __init__(self, name: str):
        self._name = name
        self.subfolders: list[FakeFolder] = []
        self.clips: list[FakeClip] = []

    def GetName(self) -> str:
        return self._name

    def GetSubFolderList(self):
        return list(self.subfolders)

    def GetClipList(self):
        return list(self.clips)


class FakeMediaPool:
    def __init__(self):
        self.root_folder = FakeFolder("Root")
        self.timelines: list[FakeTimeline] = []
        self.active_timeline = None
        self.current_folder = None
        self.move_calls: list[tuple[list[FakeClip], FakeFolder]] = []
        self.current_folder_calls: list[FakeFolder] = []
        self.append_calls: list[dict] = []
        self.create_empty_timeline_calls: list[str] = []
        self.create_from_clips_calls: list[dict] = []

    def GetRootFolder(self):
        return self.root_folder

    def AddSubFolder(self, parent: FakeFolder, name: str):
        folder = FakeFolder(name)
        parent.subfolders.append(folder)
        return folder

    def CreateEmptyTimeline(self, timeline_name: str):
        self.create_empty_timeline_calls.append(timeline_name)
        timeline = FakeTimeline(timeline_name)
        self.timelines.append(timeline)
        return timeline

    def CreateTimelineFromClips(self, timeline_name: str, clips):
        self.create_from_clips_calls.append(
            {"timeline_name": timeline_name, "clips": list(clips)}
        )
        timeline = FakeTimeline(timeline_name)
        timeline.clips = list(clips)
        self.timelines.append(timeline)
        return timeline

    def AppendToTimeline(self, clips):
        self.append_calls.append(
            {
                "timeline": self.active_timeline,
                "clips": list(clips),
                "settings_snapshot": dict(self.active_timeline.settings)
                if self.active_timeline is not None
                else {},
            }
        )
        if self.active_timeline is None:
            return []
        self.active_timeline.clips.extend(clips)
        return list(clips)

    def MoveClips(self, clips, dest_bin: FakeFolder):
        self.move_calls.append((list(clips), dest_bin))
        dest_bin.clips.extend(clips)

    def SetCurrentFolder(self, folder):
        self.current_folder = folder
        self.current_folder_calls.append(folder)


class FakeMediaStorage:
    def __init__(self, imports):
        # imports maps tuple(items) -> [clips]; flatten to per-item lookup so
        # the fake serves both whole-batch and one-item-at-a-time calls
        self.calls: list[list[str]] = []
        self._clip_by_item: dict[str, FakeClip] = {}
        for key, clips in imports.items():
            for item, clip in zip(key, clips):
                self._clip_by_item[item] = clip

    def AddItemListToMediaPool(self, items):
        self.calls.append(list(items))
        return [self._clip_by_item[i] for i in items if i in self._clip_by_item]


class FakeProject:
    def __init__(self, media_pool: FakeMediaPool):
        self.media_pool = media_pool
        self.loaded_burn_in_presets: list[str] = []
        self.loaded_render_presets: list[str] = []
        self.render_settings: list[dict] = []
        self.render_jobs: list[dict] = []
        self.render_job_count = 0
        self.started_rendering = False
        self.current_timeline = None

    def GetName(self):
        return "fake-project"

    def GetMediaPool(self):
        return self.media_pool

    def LoadBurnInPreset(self, preset_name: str):
        self.loaded_burn_in_presets.append(preset_name)
        return True

    def LoadRenderPreset(self, preset_name: str):
        self.loaded_render_presets.append(preset_name)

    def SetRenderSettings(self, settings: dict):
        self.render_settings.append(dict(settings))

    def SetCurrentTimeline(self, timeline):
        self.current_timeline = timeline
        self.media_pool.active_timeline = timeline
        return True

    def AddRenderJob(self):
        self.render_jobs.append(
            {
                "timeline": self.current_timeline,
                "settings": self.render_settings[-1] if self.render_settings else None,
            }
        )
        self.render_job_count += 1

    def StartRendering(self):
        self.started_rendering = True


class FakeProjectManager:
    def __init__(self, project: FakeProject):
        self.project = project
        self.created_projects: list[str] = []
        self.saved = False

    def CreateProject(self, project_name: str):
        self.created_projects.append(project_name)
        return self.project

    def SaveProject(self):
        self.saved = True


class FakeResolve:
    def __init__(self, project_manager: FakeProjectManager, media_storage: FakeMediaStorage):
        self.project_manager = project_manager
        self.media_storage = media_storage

    def GetProjectManager(self):
        return self.project_manager

    def GetMediaStorage(self):
        return self.media_storage


def _install_fake_resolve(monkeypatch, imports):
    media_pool = FakeMediaPool()
    project = FakeProject(media_pool)
    project_manager = FakeProjectManager(project)
    media_storage = FakeMediaStorage(imports)
    resolve = FakeResolve(project_manager, media_storage)
    fake_module = types.SimpleNamespace(scriptapp=lambda _: resolve)
    monkeypatch.setitem(sys.modules, "DaVinciResolveScript", fake_module)
    return project_manager, project, media_pool


class TestProcessFilesInResolve:
    def test_auto_codec_uses_h265_for_standard_and_prores_for_multi_audio(self, monkeypatch):
        # still.xml is filtered out before import (non-media allowlist)
        items = ["/source/clip1.mov", "/source/clip2.mov", "/source/sidecar.xml"]
        imports = {
            ("/source/clip1.mov", "/source/clip2.mov"): [
                FakeClip("3840x2160", "2"),
                FakeClip("3840x2160", "8"),
            ]
        }
        project_manager, project, media_pool = _install_fake_resolve(monkeypatch, imports)

        monkeypatch.setattr("builtins.input", lambda *_: "n")
        _process(
            {"/footage/Day1": {"CamA": items}},
            ["/footage/Day1"],
            "/proxy",
            1,
            is_directory_mode=True,
            codec="auto",
        )

        assert project_manager.saved is True
        assert project.started_rendering is False
        assert project.loaded_burn_in_presets == ["burn-in-vertical"]
        assert project.loaded_render_presets == [
            "fhd-h265-5mbps",
            "fhd-prores-proxy",
        ]
        assert project.render_job_count == 2
        assert [timeline.name for timeline in media_pool.timelines] == [
            "0001-3840x2160",
            "0002-3840x2160-multi-audio",
        ]
        assert len(media_pool.move_calls) == 2
        assert [len(clips) for clips, _ in media_pool.move_calls] == [1, 1]
        assert len(media_pool.current_folder_calls) <= 1

        day_folder = media_pool.root_folder.GetSubFolderList()[0]
        cam_folder = day_folder.GetSubFolderList()[0]
        resolution_folder = cam_folder.GetSubFolderList()[0]
        assert resolution_folder.GetName() == "3840x2160"
        # standard and multi-audio clips share the resolution bin — no sub-bin
        assert len(resolution_folder.GetClipList()) == 2
        assert resolution_folder.GetSubFolderList() == []

    def test_skips_jpg_inputs_before_resolve_import(self, monkeypatch):
        items = [
            "/source/clip1.mov",
            "/source/poster.JPG",
            "/source/still.jpeg",
            "/source/clip2.mp4",
        ]
        filtered_items = ["/source/clip1.mov", "/source/clip2.mp4"]
        imports = {
            tuple(filtered_items): [
                FakeClip("3840x2160", "2"),
                FakeClip("3840x2160", "2"),
            ]
        }
        project_manager, project, media_pool = _install_fake_resolve(monkeypatch, imports)
        media_storage = sys.modules["DaVinciResolveScript"].scriptapp("Resolve").GetMediaStorage()

        monkeypatch.setattr("builtins.input", lambda *_: "n")
        _process(
            {"/footage/Day1": {"CamA": items}},
            ["/footage/Day1"],
            "/proxy",
            1,
            is_directory_mode=True,
            codec="h265",
        )

        assert media_storage.calls == [[item] for item in filtered_items]
        assert project_manager.saved is True
        assert project.render_job_count == 1
        assert [timeline.name for timeline in media_pool.timelines] == ["0001-3840x2160"]

    def test_expands_directory_inputs_and_skips_jpgs_before_resolve_import(
        self, monkeypatch, tmp_path
    ):
        source_dir = tmp_path / "CamA"
        source_dir.mkdir()
        clip1 = source_dir / "clip1.mov"
        poster = source_dir / "poster.JPG"
        nested_dir = source_dir / "nested"
        nested_dir.mkdir()
        clip2 = nested_dir / "clip2.mp4"
        still = nested_dir / "still.jpeg"
        for path in (clip1, poster, clip2, still):
            path.write_text("x", encoding="utf-8")

        filtered_items = [str(clip1), str(clip2)]
        imports = {
            tuple(filtered_items): [
                FakeClip("3840x2160", "2"),
                FakeClip("3840x2160", "2"),
            ]
        }
        project_manager, project, media_pool = _install_fake_resolve(monkeypatch, imports)
        media_storage = sys.modules["DaVinciResolveScript"].scriptapp("Resolve").GetMediaStorage()

        monkeypatch.setattr("builtins.input", lambda *_: "n")
        _process(
            {"/footage/Day1": {"CamA": [str(source_dir)]}},
            ["/footage/Day1"],
            "/proxy",
            1,
            is_directory_mode=True,
            codec="h265",
        )

        assert media_storage.calls == [[item] for item in filtered_items]
        assert project_manager.saved is True
        assert project.render_job_count == 1
        assert [timeline.name for timeline in media_pool.timelines] == ["0001-3840x2160"]

    def test_forced_prores_and_confirm_yes_start_rendering(self, monkeypatch):
        items = ["/source/clip1.mov"]
        imports = {tuple(items): [FakeClip("1920x1080", "2")]}
        project_manager, project, media_pool = _install_fake_resolve(monkeypatch, imports)

        monkeypatch.setattr("builtins.input", lambda *_: "y")
        _process(
            {"/footage/Day1": {"": items}},
            ["/footage/Day1"],
            "/proxy",
            0,
            is_directory_mode=False,
            codec="prores",
        )

        assert project_manager.saved is True
        assert project.started_rendering is True
        assert project.loaded_burn_in_presets == ["burn-in-vertical"]
        assert project.loaded_render_presets == ["fhd-prores-proxy"]
        assert project.render_job_count == 1
        assert [timeline.name for timeline in media_pool.timelines] == ["0001-1920x1080"]
        assert media_pool.timelines[0].settings["timelineResolutionWidth"] == "1920"

    def test_creates_one_render_job_per_resolution_bin(self, monkeypatch):
        items = ["/source/a.mov", "/source/b.mov"]
        imports = {
            tuple(items): [
                FakeClip("4096x2160", "2"),
                FakeClip("1920x1080", "2"),
            ]
        }
        _, project, media_pool = _install_fake_resolve(monkeypatch, imports)

        monkeypatch.setattr("builtins.input", lambda *_: "n")
        _process(
            {"/footage/Day1": {"CamA": items}},
            ["/footage/Day1"],
            "/proxy",
            1,
            is_directory_mode=True,
            codec="h265",
        )

        assert project.render_job_count == 2
        assert project.loaded_render_presets == [
            "fhd-h265-5mbps",
            "fhd-h265-5mbps",
        ]
        assert [timeline.name for timeline in media_pool.timelines] == [
            "0001-4096x2160",
            "0002-1920x1080",
        ]
        assert all(
            settings["TargetDir"] == str(Path("/proxy", "Day1", "CamA"))
            for settings in project.render_settings
        )

    def test_moves_same_resolution_group_in_single_batch(self, monkeypatch):
        items = ["/source/a.mov", "/source/b.mov", "/source/c.mov"]
        imports = {
            tuple(items): [
                FakeClip("4096x2160", "2"),
                FakeClip("4096x2160", "2"),
                FakeClip("4096x2160", "8"),
            ]
        }
        _, project, media_pool = _install_fake_resolve(monkeypatch, imports)

        monkeypatch.setattr("builtins.input", lambda *_: "n")
        _process(
            {"/footage/Day1": {"CamA": items}},
            ["/footage/Day1"],
            "/proxy",
            1,
            is_directory_mode=True,
            codec="auto",
        )

        assert project.render_job_count == 2
        assert len(media_pool.move_calls) == 2
        assert [len(clips) for clips, _ in media_pool.move_calls] == [2, 1]
        assert [timeline.name for timeline in media_pool.timelines] == [
            "0001-4096x2160",
            "0002-4096x2160-multi-audio",
        ]

    def test_outputs_render_jobs_as_table_instead_of_repeated_target_lines(self, monkeypatch):
        items = ["/source/a.mov", "/source/b.mov", "/source/c.mov"]
        imports = {
            tuple(items): [
                FakeClip("4096x2160", "2"),
                FakeClip("4096x2160", "2"),
                FakeClip("4096x2160", "8"),
            ]
        }
        _, project, _ = _install_fake_resolve(monkeypatch, imports)
        output_lines: list[str] = []

        _process(
            {"/footage/Day1": {"CamA": items}},
            ["/footage/Day1"],
            "/proxy",
            1,
            is_directory_mode=True,
            codec="auto",
            output=output_lines.append,
            confirm_render=lambda: False,
        )

        output_text = "\n".join(output_lines)
        assert "Processing Day1 (1/1)" in output_text
        assert "Render jobs:" in output_text
        assert "4096x2160" in output_text
        # actual channel counts, not standard/multi-audio labels
        assert "2ch" in output_text
        assert "8ch" in output_text
        assert "standard" not in output_text
        # the preset chosen per audio group and the target are shown inline
        assert "fhd-h265-5mbps" in output_text
        assert "fhd-prores-proxy" in output_text
        assert "->" in output_text
        assert project.render_job_count == 2

    def test_queues_each_render_job_on_its_created_timeline(self, monkeypatch):
        items = ["/source/a.mov", "/source/b.mov"]
        imports = {
            tuple(items): [
                FakeClip("3840x2160", "2"),
                FakeClip("2160x3840", "2"),
            ]
        }
        _, project, media_pool = _install_fake_resolve(monkeypatch, imports)

        monkeypatch.setattr("builtins.input", lambda *_: "n")
        _process(
            {"/footage/Day1": {"CamA": items}},
            ["/footage/Day1"],
            "/proxy",
            1,
            is_directory_mode=True,
            codec="h265",
        )

        assert [timeline.name for timeline in media_pool.timelines] == [
            "0001-3840x2160",
            "0002-2160x3840",
        ]
        assert [job["timeline"].name for job in project.render_jobs] == [
            "0001-3840x2160",
            "0002-2160x3840",
        ]
        assert media_pool.create_empty_timeline_calls == []
        assert [call["timeline_name"] for call in media_pool.create_from_clips_calls] == [
            "0001-3840x2160",
            "0002-2160x3840",
        ]
        assert [len(call["clips"]) for call in media_pool.create_from_clips_calls] == [1, 1]
        assert media_pool.timelines[0].settings["timelineResolutionWidth"] == "1920"
        assert media_pool.timelines[0].settings["timelineResolutionHeight"] == "1080"
        assert media_pool.timelines[1].settings["timelineResolutionWidth"] == "1080"
        assert media_pool.timelines[1].settings["timelineResolutionHeight"] == "1920"
        assert project.render_settings[0]["FormatWidth"] == 1920
        assert project.render_settings[0]["FormatHeight"] == 1080
        assert project.render_settings[1]["FormatWidth"] == 1080
        assert project.render_settings[1]["FormatHeight"] == 1920

    def test_skips_clips_with_missing_resolution_without_crashing(
        self, monkeypatch, caplog
    ):
        items = ["/source/a.mov", "/source/b.mov"]
        imports = {
            tuple(items): [
                FakeClip("", "2"),
                FakeClip("1920x1080", "2"),
            ]
        }
        _, project, media_pool = _install_fake_resolve(monkeypatch, imports)

        monkeypatch.setattr("builtins.input", lambda *_: "n")
        with caplog.at_level(logging.WARNING):
            _process(
                {"/footage/Day1": {"CamA": items}},
                ["/footage/Day1"],
                "/proxy",
                1,
                is_directory_mode=True,
                codec="h265",
            )

        assert "invalid resolution" in caplog.text.lower()
        assert project.render_job_count == 1
        assert [timeline.name for timeline in media_pool.timelines] == ["0001-1920x1080"]
        assert all(timeline.name != "0001-" for timeline in media_pool.timelines)

    def test_imports_items_one_at_a_time_with_progress(self, monkeypatch):
        items = ["/source/a.mov", "/source/b.mov", "/source/c.mov"]
        imports = {
            tuple(items): [
                FakeClip("3840x2160", "2"),
                FakeClip("3840x2160", "2"),
                FakeClip("3840x2160", "2"),
            ],
        }
        _, project, media_pool = _install_fake_resolve(monkeypatch, imports)
        output_lines: list[str] = []

        _process(
            {"/footage/Day1": {"CamA": items}},
            ["/footage/Day1"],
            "/proxy",
            1,
            is_directory_mode=True,
            output=output_lines.append,
            confirm_render=lambda: False,
        )

        # every item imported individually, merged into one render job
        assert project.render_job_count == 1
        assert len(media_pool.timelines[0].clips) == 3
        output_text = "\n".join(output_lines)
        assert "imported 1/3  a.mov" in output_text
        assert "imported 2/3  b.mov" in output_text
        assert "imported 3/3  c.mov" in output_text

    def _fresh_load_setup(self, monkeypatch, imports):
        """Simulate a first-time fusionscript load with the fake module."""
        media_pool = FakeMediaPool()
        project = FakeProject(media_pool)
        project_manager = FakeProjectManager(project)
        resolve = FakeResolve(project_manager, FakeMediaStorage(imports))
        fake_module = types.SimpleNamespace(scriptapp=lambda _: resolve)
        monkeypatch.setitem(sys.modules, "DaVinciResolveScript", fake_module)
        monkeypatch.setattr("pxygen.resolve._needs_fresh_load", lambda: True)
        monkeypatch.setattr("pxygen.resolve._setup_resolve_env", lambda: None)
        monkeypatch.setattr("pxygen.resolve.time.sleep", lambda _: None)
        return project

    def test_auto_launches_resolve_when_probe_fails(self, monkeypatch):
        items = ["/source/a.mov"]
        project = self._fresh_load_setup(
            monkeypatch, {tuple(items): [FakeClip("1920x1080", "2")]}
        )
        launched: list[Path] = []
        # Resolve not up until launched, then the next probe succeeds
        monkeypatch.setattr(
            "pxygen.resolve._probe_resolve_connection", lambda: bool(launched)
        )
        monkeypatch.setattr(
            "pxygen.resolve._resolve_executable", lambda: Path("/fake/Resolve.exe")
        )
        monkeypatch.setattr(
            "pxygen.resolve._launch_resolve", lambda exe: launched.append(exe)
        )
        output_lines: list[str] = []

        _process(
            {"/footage/Day1": {"CamA": items}},
            ["/footage/Day1"],
            "/proxy",
            1,
            is_directory_mode=True,
            output=output_lines.append,
            confirm_render=lambda: False,
        )

        assert launched == [Path("/fake/Resolve.exe")]
        assert project.render_job_count == 1
        output_text = "\n".join(output_lines)
        assert "launching it" in output_text
        assert "Resolve is up." in output_text

    def test_no_launch_when_probe_succeeds_immediately(self, monkeypatch):
        items = ["/source/a.mov"]
        project = self._fresh_load_setup(
            monkeypatch, {tuple(items): [FakeClip("1920x1080", "2")]}
        )
        monkeypatch.setattr("pxygen.resolve._probe_resolve_connection", lambda: True)
        launched: list[Path] = []
        monkeypatch.setattr(
            "pxygen.resolve._launch_resolve", lambda exe: launched.append(exe)
        )

        _process(
            {"/footage/Day1": {"CamA": items}},
            ["/footage/Day1"],
            "/proxy",
            1,
            is_directory_mode=True,
            confirm_render=lambda: False,
        )

        assert launched == []
        assert project.render_job_count == 1

    def test_clear_error_when_resolve_executable_not_found(self, monkeypatch):
        self._fresh_load_setup(monkeypatch, {})
        monkeypatch.setattr("pxygen.resolve._probe_resolve_connection", lambda: False)
        monkeypatch.setattr("pxygen.resolve._resolve_executable", lambda: None)

        with pytest.raises(PxygenError, match="could not locate"):
            _process(
                {"/footage/Day1": {"CamA": ["/source/a.mov"]}},
                ["/footage/Day1"],
                "/proxy",
                1,
                is_directory_mode=True,
                confirm_render=lambda: False,
            )

    def test_clear_error_when_launched_resolve_never_answers(self, monkeypatch):
        self._fresh_load_setup(monkeypatch, {})
        monkeypatch.setattr("pxygen.resolve._probe_resolve_connection", lambda: False)
        monkeypatch.setattr(
            "pxygen.resolve._resolve_executable", lambda: Path("/fake/Resolve.exe")
        )
        launched: list[Path] = []
        monkeypatch.setattr(
            "pxygen.resolve._launch_resolve", lambda exe: launched.append(exe)
        )
        monkeypatch.setattr("pxygen.resolve._RESOLVE_LAUNCH_TIMEOUT_SECONDS", 0)

        with pytest.raises(PxygenError, match="did not accept"):
            _process(
                {"/footage/Day1": {"CamA": ["/source/a.mov"]}},
                ["/footage/Day1"],
                "/proxy",
                1,
                is_directory_mode=True,
                confirm_render=lambda: False,
            )
        assert launched == [Path("/fake/Resolve.exe")]

    def test_q_at_render_confirm_aborts_after_saving(self, monkeypatch):
        items = ["/source/a.mov"]
        imports = {tuple(items): [FakeClip("3840x2160", "2")]}
        project_manager, project, _ = _install_fake_resolve(monkeypatch, imports)

        monkeypatch.setattr("builtins.input", lambda *_: "q")
        with pytest.raises(UserAbort, match="remain queued"):
            _process(
                {"/footage/Day1": {"CamA": items}},
                ["/footage/Day1"],
                "/proxy",
                1,
                is_directory_mode=True,
            )

        assert project_manager.saved is True
        assert project.started_rendering is False

    def test_aborts_with_clear_error_when_resolve_connection_dies(self, monkeypatch):
        items = ["/source/a.mov"]
        imports = {tuple(items): [FakeClip("3840x2160", "2")]}
        _, project, _ = _install_fake_resolve(monkeypatch, imports)
        # Simulate a crashed Resolve: remote attribute lookups return None
        project.GetName = lambda: None

        with pytest.raises(PxygenError, match="Lost connection"):
            _process(
                {"/footage/Day1": {"CamA": items}},
                ["/footage/Day1"],
                "/proxy",
                1,
                is_directory_mode=True,
                confirm_render=lambda: False,
            )

    def test_saves_project_after_each_footage_folder(self, monkeypatch):
        items_a = ["/source/a.mov"]
        items_b = ["/source/b.mov"]
        imports = {
            tuple(items_a): [FakeClip("3840x2160", "2")],
            tuple(items_b): [FakeClip("1920x1080", "2")],
        }
        project_manager, _, _ = _install_fake_resolve(monkeypatch, imports)
        save_counts: list[bool] = []
        original_save = project_manager.SaveProject
        project_manager.SaveProject = lambda: (save_counts.append(True), original_save())[1]

        _process(
            {"/footage/Day1": {"CamA": items_a}, "/footage/Day2": {"CamB": items_b}},
            ["/footage/Day1", "/footage/Day2"],
            "/proxy",
            1,
            is_directory_mode=True,
            confirm_render=lambda: False,
        )

        # one save per folder — queued jobs survive a later crash
        assert len(save_counts) == 2

    def test_defaults_to_console_output_instead_of_logger_info(self, monkeypatch):
        items = ["/source/a.mov"]
        imports = {tuple(items): [FakeClip("1920x1080", "2")]}
        _install_fake_resolve(monkeypatch, imports)

        with patch("builtins.print") as mock_print:
            _process(
                {"/footage/Day1": {"CamA": items}},
                ["/footage/Day1"],
                "/proxy",
                1,
                is_directory_mode=True,
                codec="h265",
                confirm_render=lambda: False,
            )

        assert mock_print.called
