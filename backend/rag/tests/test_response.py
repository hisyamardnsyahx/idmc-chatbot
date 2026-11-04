"""Response formatter tests: tidy shape, single rebuilt sources block."""

from rag.chat import response as response_mod
from rag.core.models import Passage


def _passage(**kw):
    base = {
        "dashboard": "Dashboard Simpeg (Kepegawaian)",
        "chart": "Jumlah Pegawai Berdasarkan Pendidikan",
        "slice_id": 602,
        "rows_covered": "1-14 of 14",
        "data_as_of": "2026-09-24",
        "possibly_outdated": False,
        "relevance": 0.82,
        "content": "Dashboard: Dashboard Simpeg (Kepegawaian)\nChart: Pendidikan",
    }
    base.update(kw)
    return Passage(**base)


def test_appends_sources_block_once():
    out = response_mod.format_reply("Berikut datanya.", [_passage()])
    assert "Sumber:" in out.text
    assert "Dashboard Simpeg (Kepegawaian)" in out.text
    assert "Jumlah Pegawai Berdasarkan Pendidikan" in out.text
    assert out.text.count("Sumber:") == 1


def test_replaces_model_invented_sources():
    raw = "Jawabannya 42.\nSumber: Dashboard Khayalan — Chart Fiktif"
    out = response_mod.format_reply(raw, [_passage()])
    assert "Khayalan" not in out.text
    assert "Jumlah Pegawai Berdasarkan Pendidikan" in out.text


def test_flags_fully_stale_passages():
    out = response_mod.format_reply("Data:", [_passage(possibly_outdated=True)])
    assert "mungkin basi" in out.text


def test_flags_partial_coverage():
    out = response_mod.format_reply("Data:", [_passage(rows_covered="1-10 of 145")])
    assert "parsial" in out.text


def test_plain_reply_without_passages_untouched():
    out = response_mod.format_reply("Halo! Ada yang bisa dibantu?", [])
    assert out.text == "Halo! Ada yang bisa dibantu?"


def test_empty_model_text_gets_fallback():
    out = response_mod.format_reply("   ", [_passage()])
    assert "tidak mendapatkan jawaban" in out.text
