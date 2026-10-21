import pytest
from pydantic import ValidationError
from musicar.gestures import Layout,Settings


def test_black_keys_win_and_white_keys_continue_below_them():
    layout=Layout(Settings())
    sharp=next(key for key in layout.keys if key["note"]==61)
    x=sharp["x"]+sharp["width"]/2
    assert layout.hit(x,.65)==61
    assert layout.hit(x-.001,.87)==60
    assert layout.hit(.01,.8) is None
    assert layout.hit(.2,.2) is None
    assert len(layout.keys)==25


@pytest.mark.parametrize("kwargs",[{"x":.8,"width":.9},{"y":.85,"height":.3},
    {"fingers":[]},{"fingers":["index","index"]},{"octave":1},{"instrument":"unknown"}])
def test_invalid_config_is_rejected(kwargs):
    with pytest.raises(ValidationError):Settings(**kwargs)
