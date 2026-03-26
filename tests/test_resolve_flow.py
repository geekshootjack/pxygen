"""Tests for davinci_proxy_generator.resolve orchestration."""
from __future__ import annotations

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

    def SetSetting(self, key: str, value: str):
        self.settings[key] = value


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
        self.current_folder = None

    def GetRootFolder(self):
        return self.root_folder

    def AddSubFolder(self, parent: FakeFolder, name: str):
        folder = FakeFolder(name)
        parent.subfolders.append(folder)
        return folder

    def CreateTimelineFromClips(self, timeline_name: str, clips):
        timeline = FakeTimeline(timeline_name)
        timeline.clips = list(clips)
        self.timelines.append(timeline)
        return timeline

    def MoveClips(self, clips, dest_bin: FakeFolder):
        dest_bin.clips.extend(clips)

    def SetCurrentFolder(self, folder):
        self.current_folder = folder


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
        self.render_job_count = 0
        self.started_rendering = False

    def GetMediaPool(self):
        return self.media_pool

    def LoadBurnInPreset(self, preset_name: str):
        self.loaded_burn_in_presets.append(preset_name)

    def LoadRenderPreset(self, preset_name: str):
        self.loaded_render_presets.append(preset_name)

    def SetRenderSettings(self, settings: dict):
        self.render_settings.append(dict(settings))

    def AddRenderJob(self):
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
        assert sorted(timeline.name for timeline in media_pool.timelines) == [
            "Video Resolution 1920x1080   #2",
            "Video Resolution 4096x2160   #1",
        ]
        assert all(
            settings["TargetDir"] == PurePosixPath("/proxy", "Day1", "CamA").as_posix()
            for settings in project.render_settings
        )
