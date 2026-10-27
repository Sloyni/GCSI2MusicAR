import copy
import math

import pytest
from pydantic import ValidationError

from musicar.gestures import InstrumentTracker, Layout, Settings
from musicar.performance import AssistedGuitarTracker, CHORDS, ExpressionTracker, StrikeTracker


def hand(identity=1, x=.25, y=.55, fingers=1):
    p=[[x,y,0] for _ in range(21)]
    p[0]=[x,y+.05,0]
    for i,base in enumerate((5,9,13,17)):
        px=x+(i-1.5)*.025
        p[base]=[px,y,0]
        p[base+1]=[px,y-.04,0]
        p[base+3]=[px,y-.13 if i<fingers else y+.025,0]
    p[3]=[x-.04,y+.01,0]
    p[4]=[x-.04,y+.02,0]  # folded thumb
    return {"id":identity,"label":"Left" if identity==1 else "Right","landmarks":p}


def point(x,y,identity=1):
    return dict(hand=identity,finger="index",x=x,y=y)


def move(h,dx=0,dy=0):
    result=copy.deepcopy(h)
    for p in result["landmarks"]:
        p[0]+=dx;p[1]+=dy
    return result


def test_pitch_is_normalized_by_palm_size_and_resets_on_loss_or_exit():
    settings=Settings(pitch_gesture=True,expression_zone="top")
    tracker=ExpressionTracker(settings)
    h=hand(y=.2)
    tracker.update([h],960,540,1)
    value=tracker.value.copy()
    assert value["zone"] and value["pinch"] is not None and abs(value["pitch"])<=2
    scaled=copy.deepcopy(h)
    for p in scaled["landmarks"]:
        p[0]=.25+(p[0]-.25)*1.5;p[1]=.2+(p[1]-.2)*1.5
    tracker.update([scaled],960,540,1.03)
    assert tracker.value["pinch"]==pytest.approx(value["pinch"],abs=.002)
    tracker.update([move(h,dy=.4)],960,540,1.06)
    assert tracker.value["pitch"]==0 and not tracker.value["zone"]
    tracker.update([],960,540,1.1)
    assert tracker.value["pitch"]==0 and tracker.value["pinch"] is None


def test_swipe_changes_style_once_and_ignores_playing_zone_and_vertical_motion():
    tracker=ExpressionTracker(Settings(expression_zone="top"))
    h=hand(y=.2,fingers=4)
    assert tracker.update([h],960,540,1)==[]
    events=tracker.update([move(h,dx=.22)],960,540,1.2)
    assert events==[{"kind":"style","style":"jazz"}]
    assert tracker.update([move(h,dx=.44)],960,540,1.4)==[]
    assert tracker.update([move(h,dy=.4)],960,540,3)==[]
    assert tracker.update([move(h,dx=.25,dy=.4)],960,540,3.2)==[]
    tracker.update([h],960,540,4)
    assert tracker.update([move(h,dx=.22,dy=-.12)],960,540,4.2)==[]
    tracker.update([h],960,540,5)
    assert tracker.update([move(h,dx=-.2)],960,540,5.2)==[{"kind":"style","style":"acoustic"}]


def test_swipe_can_be_disabled():
    tracker=ExpressionTracker(Settings(style_swipe=False))
    h=hand(y=.2,fingers=4)
    tracker.update([h],960,540,1)
    assert tracker.update([move(h,dx=.3)],960,540,1.2)==[]


def test_strikes_require_motion_and_rearm_inside_same_pad():
    tracker=StrikeTracker(Settings(instrument="drums"))
    pad=tracker.layout.pads[0];x,y=pad["x"],pad["y"]
    assert tracker.update([point(x,y-.035)],1)==[]
    assert tracker.update([point(x,y-.035)],1.03)==[]
    first=tracker.update([point(x,y)],1.06)
    assert [e["kind"] for e in first]==["on"] and first[0]["note"]=="kick"
    assert tracker.update([point(x,y)],1.09)==[]
    tracker.update([point(x,y-.03)],1.16)
    second=tracker.update([point(x,y)],1.2)
    assert [e["kind"] for e in second]==["off","on"]
    assert tracker.update([],1.23)[0]["kind"]=="off"


def test_fast_stroke_crosses_pad_and_no_stationary_reacquisition_hit():
    tracker=StrikeTracker(Settings(instrument="drums"))
    pad=tracker.layout.pads[0];x,y,r=pad["x"],pad["y"],pad["radius"]
    tracker.update([point(x,y-r-.01)],1)
    assert any(e["kind"]=="on" for e in tracker.update([point(x,y+r+.01)],1.1))
    tracker.update([],1.2)
    assert tracker.update([point(x,y)],2)==[]


def test_strike_velocity_tracks_speed_and_two_hands_can_hit_together():
    def strike(dt):
        t=StrikeTracker(Settings(instrument="drums",sensitivity=1))
        p=t.layout.pads[1]
        t.update([point(p["x"],p["y"]-.025)],1)
        return t.update([point(p["x"],p["y"])],1+dt)[0]["velocity"]
    assert strike(.025)>strike(.09)
    t=StrikeTracker(Settings(instrument="drums"));p=t.layout.pads[1]
    t.update([point(p["x"],p["y"]-.025,i) for i in (1,2)],1)
    assert len(t.update([point(p["x"],p["y"],i) for i in (1,2)],1.05))==2


def set_pick(pair,t,string_index,finger="index",offset=0):
    guitar=t.guitar
    a,b=guitar["neck"],guitar["body"]
    width,height=guitar["width"],guitar["height"]
    dx,dy=(b[0]-a[0])*width,(b[1]-a[1])*height
    length=math.hypot(dx,dy)
    v=(string_index-2.5)*guitar["spread"]/5+offset
    pair[1]["landmarks"][{"index":8,"middle":12}[finger]]=[
        a[0]+.95*(b[0]-a[0])-v*dy/length/width,
        a[1]+.95*(b[1]-a[1])+v*dx/length/height,0]


def test_chord_changes_are_debounced_and_one_touch_plays_one_string():
    t=AssistedGuitarTracker(Settings(instrument="guitar",fingers=["index"]))
    left,right=hand(),hand(2,x=.75)
    assert t.update([left,right],960,540,1)==[]
    left2=hand(fingers=2)
    t.update([left2,right],960,540,1.05)
    assert t.guitar["chord"]=="C"
    t.update([left2,right],960,540,1.19)
    assert t.guitar["chord"]=="G"
    pair=[left2,right]
    set_pick(pair,t,0,offset=-t.guitar["spread"]*.4)
    t.update(pair,960,540,1.21)
    set_pick(pair,t,0)
    events=t.update(pair,960,540,1.24)
    ons=[e for e in events if e["kind"]=="on"]
    assert [e["note"] for e in ons]==[CHORDS["G"][0]]
    assert t.update(pair,960,540,1.27)==[]
    assert t.update([left2],960,540,1.3)==[] and t.guitar["chord"]=="G"
    assert t.update([left2,right],960,540,1.35)==[]
    assert t.update([left2],960,540,1.6)==[] and t.guitar is None


def test_melody_pinches_trigger_once_and_release_rearms():
    t=AssistedGuitarTracker(Settings(instrument="guitar",guitar_mode="melody"))
    left,right=hand(),hand(2,x=.75)
    t.update([left,right],960,540,1)
    pinched=copy.deepcopy(right);pinched["landmarks"][4]=pinched["landmarks"][8][:]
    events=t.update([left,pinched],960,540,1.03)
    assert [e["kind"] for e in events]==["on","off"] and events[0]["note"]==48
    assert t.update([left,pinched],960,540,1.06)==[]
    t.update([left,right],960,540,1.09)
    assert t.update([left,pinched],960,540,1.12)[0]["kind"]=="on"
    t.update([left,right],960,540,1.15)
    assert t.update([hand(y=.2),pinched],960,540,1.18)[0]["kind"]=="on", "La main d’expression ne doit pas bloquer la mélodie"


def test_finger_sweep_reverses_strings_and_fist_stops_new_plucks():
    t=AssistedGuitarTracker(Settings(instrument="guitar",fingers=["index"]))
    left,right=hand(),hand(2,x=.75)
    t.update([left,right],960,540,1)
    pair=[left,right]
    set_pick(pair,t,5,offset=t.guitar["spread"]*.3)
    t.update(pair,960,540,1.03)
    set_pick(pair,t,0,offset=-t.guitar["spread"]*.3)
    events=t.update(pair,960,540,1.13)
    assert [e["note"] for e in events if e["kind"]=="on"]==list(reversed(CHORDS["C"]))
    delays=[e["delay"] for e in events if e["kind"]=="on"]
    assert len(set(delays))==6 and delays==sorted(delays)
    closed=hand(fingers=0)
    t.update([closed,right],960,540,1.2)
    t.update([closed,right],960,540,1.34)
    assert t.guitar["muted"]
    assert t.update([closed,move(right,dy=.07)],960,540,1.39)==[]


def test_piano_strikes_retrigger_and_chord_does_not_change_in_expression_zone():
    t=StrikeTracker(Settings(piano_mode="strike"))
    t.update([point(.09,.67)],1)
    assert t.update([point(.09,.70)],1.05)[0]["note"]==60
    t.update([point(.09,.67)],1.14)
    assert [e["kind"] for e in t.update([point(.09,.70)],1.19)]==["off","on"]
    guitar=AssistedGuitarTracker(Settings(instrument="guitar",expression_zone="top"))
    right=hand(2,x=.75)
    guitar.update([hand(),right],960,540,1)
    guitar.update([hand(y=.2,fingers=4),right],960,540,1.2)
    guitar.update([hand(y=.2,fingers=4),right],960,540,1.4)
    assert guitar.guitar["chord"]=="C"


def test_scale_hides_out_of_key_contacts_and_default_modes_are_playable():
    layout=Layout(Settings(scale="major"))
    black=next(k for k in layout.keys if k["note"]==61)
    assert not black["enabled"] and layout.hit(black["x"]+.005,black["y"]+.01) is None
    assert len(layout.pads)==6
    assert isinstance(InstrumentTracker(Settings(instrument="drums")).strikes,StrikeTracker)
    assert isinstance(InstrumentTracker(Settings(instrument="guitar")).strings,AssistedGuitarTracker)


def test_melody_groups_cover_the_full_scale_instead_of_repeating_four_notes():
    t=AssistedGuitarTracker(Settings(instrument="guitar",guitar_mode="melody"))
    right=hand(2,x=.75)
    notes=[]
    for count in range(1,5):
        left=hand(fingers=count)
        t.update([left,right],960,540,count)
        t.update([left,right],960,540,count+.14)
        notes.extend(t.guitar["melody"])
    assert notes==list(range(48,64))


def test_guitar_tracks_right_wrist_and_translation_never_strums():
    t=AssistedGuitarTracker(Settings(instrument="guitar"))
    left,right=hand(),hand(2,x=.75)
    t.update([left,right],960,540,1)
    body,neck=t.guitar["body"],t.guitar["neck"]
    for i in range(1,5):
        assert t.update([left,move(right,dx=.02*i,dy=.03*i)],960,540,1+i*.033)==[]
        assert t.guitar["body"]==pytest.approx([body[0]+.02*i,body[1]+.03*i])
        assert t.guitar["neck"]==pytest.approx([neck[0]+.02*i,neck[1]+.03*i])


def test_string_contacts_have_hysteresis_and_rearm_after_exit():
    t=AssistedGuitarTracker(Settings(instrument="guitar",fingers=["index"]))
    pair=[hand(),hand(2,x=.75)]
    t.update(pair,960,540,1)
    spacing=t.guitar["spread"]/5
    set_pick(pair,t,0,offset=-spacing)
    t.update(pair,960,540,1.03)
    set_pick(pair,t,0)
    assert len([e for e in t.update(pair,960,540,1.09) if e["kind"]=="on"])==1
    for i,offset in enumerate([.4,-.4,.5,-.2]):
        set_pick(pair,t,0,offset=offset*spacing)
        assert t.update(pair,960,540,1.12+i*.04)==[]
    set_pick(pair,t,0,offset=-spacing)
    t.update(pair,960,540,1.30)
    set_pick(pair,t,0)
    assert len([e for e in t.update(pair,960,540,1.36) if e["kind"]=="on"])==1


def test_two_fingers_on_same_string_do_not_double_it_and_left_motion_is_silent():
    t=AssistedGuitarTracker(Settings(instrument="guitar"))
    pair=[hand(),hand(2,x=.75)]
    t.update(pair,960,540,1)
    for finger in ("index","middle"):set_pick(pair,t,0,finger,offset=-t.guitar["spread"]*.3)
    t.update(pair,960,540,1.03)
    for finger in ("index","middle"):set_pick(pair,t,0,finger)
    events=t.update(pair,960,540,1.09)
    assert len([e for e in events if e["kind"]=="on"])==1
    pair[0]=move(pair[0],dx=.08,dy=.08)
    assert t.update(pair,960,540,1.14)==[]


def test_lost_hand_reacquires_without_a_cascade_of_notes():
    t=AssistedGuitarTracker(Settings(instrument="guitar",fingers=["index"]))
    pair=[hand(),hand(2,x=.75)]
    t.update(pair,960,540,1)
    set_pick(pair,t,0,offset=-t.guitar["spread"]*.3)
    t.update(pair,960,540,1.03)
    t.update(pair[:1],960,540,1.06)
    set_pick(pair,t,5)
    assert t.update(pair,960,540,1.09)==[]


def test_pitch_works_at_playing_height_and_tracks_thumb_index_distance():
    t=ExpressionTracker(Settings(pitch_gesture=True))
    h=hand(y=.55,fingers=3)
    h["landmarks"][4]=h["landmarks"][8][:]
    t.update([h],960,540,1)
    assert t.value["zone"] and t.value["pinching"] and t.value["pitch"]==-2
    h["landmarks"][4][0]-=.12
    t.update([h],960,540,1.1)
    assert t.value["pitch"]>0
    t.update([],960,540,1.2)
    assert t.value["pitch"]==0


def test_style_swipe_works_at_normal_height_with_relaxed_open_hand():
    t=ExpressionTracker(Settings())
    h=hand(y=.55,fingers=3)
    t.update([h],960,540,1)
    assert t.update([move(h,dx=.16,dy=.04)],960,540,1.35)==[{"kind":"style","style":"jazz"}]
    assert t.update([move(h,dx=.35)],960,540,1.5)==[]


def test_style_uses_control_hand_and_pitch_pose_does_not_replace_the_chord():
    t=ExpressionTracker(Settings())
    left,right=hand(fingers=2),hand(2,x=.7,fingers=4)
    t.update([left,right],960,540,1)
    assert t.update([left,move(right,dx=.2)],960,540,1.2)==[]
    guitar=AssistedGuitarTracker(Settings(instrument="guitar",pitch_gesture=True))
    guitar.update([left,right],960,540,1)
    guitar.update([left,right],960,540,1.14)
    assert guitar.guitar["chord"]=="G"
    pinched=hand(fingers=3)
    guitar.update([pinched,right],960,540,1.3,{"hand":1,"pinching":True})
    guitar.update([pinched,right],960,540,1.5,{"hand":1,"pinching":True})
    assert guitar.guitar["chord"]=="G"


@pytest.mark.parametrize("kwargs",[{"pitch_range":13},{"tone":1.1},{"transpose":-13},
    {"scale":"random"},{"guitar_mode":"unknown"},{"pitch_neutral":0},{"music_style":"unknown"}])
def test_expression_settings_are_validated(kwargs):
    with pytest.raises(ValidationError):Settings(**kwargs)
