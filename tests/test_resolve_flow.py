"""Tests for davinci_proxy_generator.resolve orchestration."""
from __future__ import annotations

import logging
import sys
import types
from pathlib import PurePosixPath

from davinci_proxy_generator.resolve import process_files_in_resolve


class FakeClip:
    def __init__(self, resolution: str, audio_channels: str | None, clip_type: str = "Video"):
        self._properties = {
            "Resolution": resolution,
            "Audio Ch": audio_channels,
            "Type": clip_type,
        }

    def GetClipProperty(self, name: str):
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
        self.imports = imports

    def AddItemListToMediaPool(self, items):
        return self.imports.get(tuple(items), [])


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

    def GetMediaPool(self):
        return self.media_pool

    def LoadBurnInPreset(self, preset_name: str):
        self.loaded_burn_in_presets.append(preset_name)

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
        items = ["/source/clip1.mov", "/source/clip2.mov", "/source/still.dpx"]
        imports = {
            tuple(items): [
                FakeClip("3840x2160", "2"),
                FakeClip("3840x2160", "8"),
                FakeClip("3840x2160", None, clip_type="Still"),
            ]
        }
        project_manager, project, media_pool = _install_fake_resolve(monkeypatch, imports)

        monkeypatch.setattr("builtins.input", lambda: "n")
        process_files_in_resolve(
            {"/footage/Day1": {"CamA": items}},
            ["/footage/Day1"],
            "/proxy",
            1,
            is_directory_mode=True,
            codec="auto",
        )

        assert project_manager.saved is True
        assert project.started_rendering is False
        assert project.loaded_burn_in_presets == ["burn-in"]
        assert project.loaded_render_presets == [
            "FHD_h.265_420_8bit_5Mbps",
            "FHD_prores_proxy",
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
        assert len(resolution_folder.GetClipList()) == 1
        assert resolution_folder.GetSubFolderList()[0].GetName() == "MultiAudio_5+"
        assert len(resolution_folder.GetSubFolderList()[0].GetClipList()) == 1

    def test_forced_prores_and_confirm_yes_start_rendering(self, monkeypatch):
        items = ["/source/clip1.mov"]
        imports = {tuple(items): [FakeClip("1920x1080", "2")]}
        project_manager, project, media_pool = _install_fake_resolve(monkeypatch, imports)

        monkeypatch.setattr("builtins.input", lambda: "y")
        process_files_in_resolve(
            {"/footage/Day1": {"": items}},
            ["/footage/Day1"],
            "/proxy",
            0,
            is_directory_mode=False,
            clean_image=True,
            codec="prores",
        )

        assert project_manager.saved is True
        assert project.started_rendering is True
        assert project.loaded_burn_in_presets == []
        assert project.loaded_render_presets == ["FHD_prores_proxy"]
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

        monkeypatch.setattr("builtins.input", lambda: "n")
        process_files_in_resolve(
            {"/footage/Day1": {"CamA": items}},
            ["/footage/Day1"],
            "/proxy",
            1,
            is_directory_mode=True,
            codec="h265",
        )

        assert project.render_job_count == 2
        assert project.loaded_render_presets == [
            "FHD_h.265_420_8bit_5Mbps",
            "FHD_h.265_420_8bit_5Mbps",
        ]
        assert [timeline.name for timeline in media_pool.timelines] == [
            "0001-4096x2160",
            "0002-1920x1080",
        ]
        assert all(
            settings["TargetDir"] == PurePosixPath("/proxy", "Day1", "CamA").as_posix()
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

        monkeypatch.setattr("builtins.input", lambda: "n")
        process_files_in_resolve(
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

    def test_queues_each_render_job_on_its_created_timeline(self, monkeypatch):
        items = ["/source/a.mov", "/source/b.mov"]
        imports = {
            tuple(items): [
                FakeClip("3840x2160", "2"),
                FakeClip("2160x3840", "2"),
            ]
        }
        _, project, media_pool = _install_fake_resolve(monkeypatch, imports)

        monkeypatch.setattr("builtins.input", lambda: "n")
        process_files_in_resolve(
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

        monkeypatch.setattr("builtins.input", lambda: "n")
        with caplog.at_level(logging.WARNING):
            process_files_in_resolve(
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
