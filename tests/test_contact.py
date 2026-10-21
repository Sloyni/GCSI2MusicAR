import pytest
from musicar.gestures import ContactTracker,Settings,GuitarTracker,GUITAR_NOTES,InstrumentTracker


def point(x=.09,y=.65,hand=1,finger="index"):
    return {"x":x,"y":y,"hand":hand,"finger":finger}


def test_piano_plays_on_first_contact_without_downward_motion():
    tracker=ContactTracker(Settings())
    events=tracker.update([point()],1)
    assert len(events)==1 and events[0]["kind"]=="on" and events[0]["note"]==60
    assert tracker.update([point()],1.03)==[]


def test_horizontal_entry_plays_and_leaving_releases_immediately():
    tracker=ContactTracker(Settings())
    assert tracker.update([point(x=.01)],1)==[]
    assert tracker.update([point(x=.09)],1.03)[0]["kind"]=="on"
    assert tracker.update([point(x=.01)],1.04)[0]["kind"]=="off"


def test_moving_between_notes_releases_then_plays_without_rearming():
    tracker=ContactTracker(Settings())
    tracker.update([point()],1)
    events=tracker.update([point(x=.20)],1.033)
    assert [e["kind"] for e in events]==["off","on"]
    assert events[0]["note"]!=events[1]["note"]


def test_two_fingers_on_same_note_have_independent_release():
    tracker=ContactTracker(Settings())
    events=tracker.update([point(),point(finger="middle")],1)
    assert len(events)==2 and all(e["note"]==60 for e in events)
    events=tracker.update([point(y=.2),point(finger="middle")],1.03)
    assert len(events)==1 and events[0]["source"]=="1:index" and events[0]["kind"]=="off"


def test_contact_above_the_former_strike_line_also_plays():
    tracker=ContactTracker(Settings())
    assert tracker.settings.y<.6<tracker.layout.line
    assert tracker.update([point(y=.6)],1)[0]["kind"]=="on"


def test_loss_of_hand_releases_contact_notes():
    tracker=ContactTracker(Settings())
    tracker.update([point()],1)
    assert tracker.update([],1.11)[0]["kind"]=="off"


def test_drums_play_on_contact_and_reentry_without_speed_requirement():
    tracker=ContactTracker(Settings(instrument="drums"))
    pad=tracker.layout.pads[0]
    touch=point(pad["x"],pad["y"])
    assert tracker.update([touch],1)[0]["note"]=="kick"
    assert tracker.update([touch],1.03)==[]
    assert tracker.update([point(y=.1)],1.04)[0]["kind"]=="off"
    assert tracker.update([touch],1.05)[0]["kind"]=="on"


def hand(identity,x,y=.5):
    return {"id":identity,"label":"Left" if identity==1 else "Right","confidence":.9,
            "landmarks":[[x,y,0] for _ in range(21)]}


def hands():
    left,right=hand(1,.25),hand(2,.75)
    # Keep fingertips away from the initial strings while palms define anchors.
    for tip in [4,8,12,16,20]:
        left["landmarks"][tip]=[.20,.2,0]
        right["landmarks"][tip]=[.75,.2,0]
    return [left,right]


def test_guitar_requires_two_hands_and_has_six_strings():
    tracker=GuitarTracker(Settings(instrument="guitar"))
    assert tracker.update([hand(1,.2)],960,540,1)==[] and tracker.guitar is None
    tracker.update(hands(),960,540,1.1)
    assert len(tracker.guitar["strings"])==6
    assert [s["note"] for s in tracker.guitar["strings"]]==GUITAR_NOTES


def test_guitar_moves_with_both_palms_without_false_plucks():
    tracker=GuitarTracker(Settings(instrument="guitar"))
    first=hands();tracker.update(first,960,540,1)
    start=tracker.guitar["strings"][0]["start"][:]
    for item in first:
        for p in item["landmarks"]:p[0]+=.05;p[1]+=.1
    assert tracker.update(first,960,540,1.03)==[]
    end=tracker.guitar["strings"][0]["start"]
    assert end[0]-start[0]==pytest.approx(.05)
    assert end[1]-start[1]==pytest.approx(.1)


def test_guitar_string_contact_is_immediate_and_not_repeated_in_hold():
    tracker=GuitarTracker(Settings(instrument="guitar"))
    pair=hands();tracker.update(pair,960,540,1)
    string=tracker.guitar["strings"][2]
    pair[1]["landmarks"][8]=[.75,string["end"][1],0]
    events=tracker.update(pair,960,540,1.03)
    assert any(e["kind"]=="on" and e["note"]==50 for e in events)
    assert tracker.update(pair,960,540,1.06)==[]
    assert tracker.update(pair[:1],960,540,1.09)[0]["kind"]=="off"
    assert tracker.guitar is None


def test_fast_strum_does_not_skip_strings_between_frames():
    tracker=GuitarTracker(Settings(instrument="guitar"))
    pair=hands();pair[1]["landmarks"][8]=[.75,.38,0]
    tracker.update(pair,960,540,1)
    pair[1]["landmarks"][8]=[.75,.62,0]
    events=tracker.update(pair,960,540,1.03)
    assert len([e for e in events if e["kind"]=="on"])==6


def test_guitar_fretting_changes_a_string_note():
    tracker=GuitarTracker(Settings(instrument="guitar"))
    pair=hands();tracker.update(pair,960,540,1)
    string=tracker.guitar["strings"][0]
    pair[0]["landmarks"][8]=[.35,string["start"][1],0]
    tracker.update(pair,960,540,1.03)
    assert tracker.guitar["strings"][0]["fret"]>0
    assert tracker.guitar["strings"][0]["note"]>40


def test_instrument_change_cuts_old_contacts():
    tracker=InstrumentTracker(Settings())
    tracker.update([point()],1)
    assert tracker.reset(Settings(instrument="guitar"))[0]["kind"]=="off"

