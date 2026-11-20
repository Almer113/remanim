"""Phase 6 step 5: what an export job may ask for."""

import pytest

from studio.server.export import ExportError, check_spec

SCENES = ["Intro", "Middle", "Outro"]


def test_defaults_and_join_rules():
    s = check_spec({"scenes": ["Intro", "Outro"], "join": True}, SCENES)
    assert s == {"scenes": ["Intro", "Outro"], "quality": "l", "format": "mp4", "transparent": False,
                 "join": True, "check": True}
    # one scene is already the whole video
    assert check_spec({"scenes": ["Intro"], "join": True}, SCENES)["join"] is False
    # no narration check for formats that carry no sound
    assert check_spec({"scenes": ["Intro"], "format": "gif"}, SCENES)["check"] is False
    assert check_spec({"scenes": ["Intro"], "format": "mov", "transparent": True}, SCENES)["check"] is False


@pytest.mark.parametrize("spec, why", [
    ({"scenes": []}, "at least one"),
    ({"scenes": ["Nope"]}, "not a scene"),
    ({"scenes": ["Intro", "Intro"]}, "twice"),
    ({"scenes": ["Intro"], "quality": "x"}, "quality"),
    ({"scenes": ["Intro"], "format": "avi"}, "format"),
    ({"scenes": ["Intro"], "format": "gif", "transparent": True}, "transparent"),
    ({"scenes": ["Intro", "Outro"], "format": "webm", "join": True}, "joining"),
    ({"scenes": "Intro"}, "at least one"),
])
def test_refusals(spec, why):
    with pytest.raises(ExportError) as e:
        check_spec(spec, SCENES)
    assert why in str(e.value)
