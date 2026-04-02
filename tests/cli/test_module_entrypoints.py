import runpy
import sys

import pytest


def test_package_module_help(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["python", "-m", "skydiscover", "--help"])

    with pytest.raises(SystemExit) as exc_info:
        runpy.run_module("skydiscover", run_name="__main__")

    assert exc_info.value.code == 0
    captured = capsys.readouterr()
    assert "SkyDiscover - AI-Driven Scientific and Algorithmic Discovery" in captured.out
    assert "evaluation_file" in captured.out


def test_viewer_module_help(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["python", "-m", "skydiscover.viewer", "--help"])

    with pytest.raises(SystemExit) as exc_info:
        runpy.run_module("skydiscover.viewer", run_name="__main__")

    assert exc_info.value.code == 0
    captured = capsys.readouterr()
    assert "usage:" in captured.out.lower()
