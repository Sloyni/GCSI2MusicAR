"""Instant fingertip contacts and moving guitar strings in video coordinates."""
from dataclasses import dataclass
import math
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

FINGERS = {"thumb": 4, "index": 8, "middle": 12, "ring": 16, "pinky": 20}
WHITE_SEMITONES = [0, 2, 4, 5, 7, 9, 11, 12, 14, 16, 17, 19, 21, 23, 24]
NAMES = ["Do", "Do♯", "Ré", "Ré♯", "Mi", "Fa", "Fa♯", "Sol", "Sol♯", "La", "La♯", "Si"]


class Settings(BaseModel):
    model_config = ConfigDict(extra="forbid")
    instrument: Literal["piano", "drums", "guitar"] = "piano"
    octave: int = Field(default=4, ge=3, le=5)
    x: float = Field(default=0.07, ge=0, le=0.8)
    y: float = Field(default=0.58, ge=0.15, le=0.85)
    width: float = Field(default=0.86, ge=0.25, le=1)
    height: float = Field(default=0.34, ge=0.10, le=0.45)
    sensitivity: float = Field(default=0.6, ge=0, le=1)
    mirror: bool = True
    fingers: list[Literal["thumb", "index", "middle", "ring", "pinky"]] = ["index", "middle"]
    music_style: Literal["acoustic", "jazz", "electric", "ambient"] = "acoustic"
    tone: float = Field(default=.6, ge=0, le=1)
    transpose: int = Field(default=0, ge=-12, le=12)
    pitch_gesture: bool = False
    pitch_range: int = Field(default=2, ge=1, le=12)
    pitch_neutral: float = Field(default=.8, ge=.15, le=2.5)
    control_hand: Literal["left", "right"] = "left"
    style_swipe: bool = True
    expression_zone: Literal["anywhere", "top"] = "anywhere"
    guitar_mode: Literal["chords", "melody", "strings"] = "chords"
    guitar_chord: Literal["C", "G", "Am", "F", "Dm", "Em"] = "C"
    piano_mode: Literal["contact", "strike"] = "contact"
    drum_mode: Literal["strike", "contact"] = "strike"
    scale: Literal["chromatic", "major", "minor", "pentatonic"] = "chromatic"
    root: int = Field(default=0, ge=0, le=11)

    @model_validator(mode="after")
    def bounds(self):
        if self.x + self.width > 1.00001 or self.y + self.height > 1.00001:
            raise ValueError("L'instrument doit rester dans l'image.")
        if not self.fingers or len(self.fingers) != len(set(self.fingers)):
            raise ValueError("Choisissez au moins un doigt, sans doublon.")
        return self


def note_name(midi: int) -> str:
    return NAMES[midi % 12] + str(midi // 12 - 1)


class Layout:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.line = settings.y + settings.height * 0.24
        self.keys = []
        step = settings.width / 15
        root = 12 * (settings.octave + 1)
        for i, semitone in enumerate(WHITE_SEMITONES):
            self.keys.append(dict(note=root + semitone, label=note_name(root + semitone),
                                  black=False, x=settings.x + i * step, y=settings.y,
                                  width=step, height=settings.height))
        for i, semitone in enumerate(WHITE_SEMITONES[:-1]):
            if (semitone % 12) not in (4, 11):
                note = root + semitone + 1
                self.keys.append(dict(note=note, label=note_name(note), black=True,
                                      x=settings.x + (i + 1) * step - step * 0.30,
                                      y=settings.y, width=step * 0.60, height=settings.height * 0.63))
        intervals = {"chromatic": range(12), "major": (0,2,4,5,7,9,11),
                     "minor": (0,2,3,5,7,8,10), "pentatonic": (0,2,4,7,9)}[settings.scale]
        for key in self.keys:
            key["enabled"] = (key["note"] - settings.root) % 12 in intervals
        self.pads = [dict(note=note, label=label, x=settings.x + settings.width * px,
                         y=settings.y + settings.height * py,
                         radius=min(settings.width / 11, settings.height * .23))
                     for note, label, px, py in [("kick", "KICK", .18, .73), ("snare", "SNARE", .5, .73),
                         ("hat", "HI-HAT", .18, .23), ("tom", "TOM", .82, .73),
                         ("crash", "CRASH", .82, .23), ("openhat", "OPEN HAT", .5, .23)]]

    def hit(self, x: float, y: float):
        s = self.settings
        if not s.x <= x <= s.x + s.width:
            return None
        if s.instrument == "drums":
            for pad in self.pads:
                if (x - pad["x"]) ** 2 + (y - pad["y"]) ** 2 <= pad["radius"] ** 2:
                    return pad["note"]
            return None
        if y < s.y or y > s.y + s.height:
            return None
        # Black keys win only inside their actual drawn rectangle.
        for key in sorted(self.keys, key=lambda k: not k["black"]):
            if key["x"] <= x < key["x"] + key["width"] and y <= key["y"] + key["height"]:
                return key["note"] if key["enabled"] else None
        return None

    def dump(self):
        return {"line": self.line, "keys": self.keys, "pads": self.pads}


@dataclass
class FingerState:
    x: float
    y: float
    seen: float
    note: int | str | None = None


class ContactBase:
    """Common contact state and release-on-reset behavior."""
    def __init__(self, settings: Settings | None = None):
        self.settings = settings or Settings()
        self.layout = Layout(self.settings)
        self.states: dict[str, FingerState] = {}

    def reset(self, settings: Settings | None = None):
        events = [dict(kind="off", note=s.note, source=source) for source, s in self.states.items() if s.note is not None]
        self.states.clear()
        if settings:
            self.settings = settings
            self.layout = Layout(settings)
        return events


class ContactTracker(ContactBase):
    """Immediate circle/shape collision: enter = on, hold = quiet, leave = off."""
    def update(self, points: list[dict], now: float) -> list[dict]:
        events = []
        seen = set()
        for point in points:
            source = f'{point["hand"]}:{point["finger"]}'
            seen.add(source)
            x, y = point["x"], point["y"]
            previous = self.states.get(source)
            note = self.layout.hit(x, y)
            old_note = previous.note if previous else None
            if old_note != note:
                if old_note is not None:
                    events.append(dict(kind="off", note=old_note, source=source))
                if note is not None:
                    speed = math.hypot(x - previous.x, y - previous.y) / max(.008, now - previous.seen) if previous else .6
                    velocity = min(1, max(.25, .7 * (1-self.settings.sensitivity) +
                                             (.25 + speed * .45) * self.settings.sensitivity))
                    events.append(dict(kind="on", note=note, source=source, velocity=round(velocity, 3)))
            self.states[source] = FingerState(x=x, y=y, seen=now, note=note)
        for source, previous in list(self.states.items()):
            if source not in seen:
                if previous.note is not None:
                    events.append(dict(kind="off", note=previous.note, source=source))
                del self.states[source]
        return events


GUITAR_NOTES = [40, 45, 50, 55, 59, 64]  # E2 A2 D3 G3 B3 E4


class GuitarTracker:
    """Six strings anchored to palms; picking is evaluated in their moving frame."""
    def __init__(self, settings):
        self.settings = settings
        self.roles = None
        self.states = {}
        self.guitar = None

    def reset(self):
        events = [dict(kind="off",note=s["note"],source=source)
                  for source,s in self.states.items() if s.get("note") is not None]
        self.states.clear()
        self.guitar = None
        self.roles = None
        return events

    @staticmethod
    def palm(hand, width, height):
        points = [hand["landmarks"][i] for i in (0,5,9,13,17)]
        return (sum(p[0] for p in points) / 5 * width, sum(p[1] for p in points) / 5 * height)

    def update(self, hands, width, height, now):
        if len(hands) != 2:
            return self.reset()
        by_id = {hand["id"]:hand for hand in hands}
        if self.roles is None or any(identity not in by_id for identity in self.roles):
            ordered = sorted(hands,key=lambda hand:self.palm(hand,width,height)[0])
            self.roles = (ordered[0]["id"],ordered[1]["id"])
        neck_hand, pick_hand = [by_id[i] for i in self.roles]
        a, b = self.palm(neck_hand,width,height), self.palm(pick_hand,width,height)
        length = math.hypot(b[0]-a[0],b[1]-a[1])
        if length < min(width,height) * .22:
            return self.reset()
        ux, uy = (b[0]-a[0])/length, (b[1]-a[1])/length
        nx, ny = -uy, ux
        spread = max(30, min(min(width,height)*.19, length*.35))
        spacing = spread / 5
        tolerance = spacing * .42
        def local(point):
            dx,dy=point[0]*width-a[0],point[1]*height-a[1]
            return ((dx*ux+dy*uy)/length,dx*nx+dy*ny)
        def normalized(u,v):
            return [(a[0]+u*length*ux+v*nx)/width,(a[1]+u*length*uy+v*ny)/height]
        strings=[]
        for index,base in enumerate(GUITAR_NOTES):
            offset=(index-2.5)*spacing
            fret=0
            for name in ("index","middle","ring","pinky"):
                u,v=local(neck_hand["landmarks"][FINGERS[name]])
                if .04<u<.56 and abs(v-offset)<tolerance:
                    fret=max(fret,min(5,int(u/.11)+1))
            note=base+fret
            strings.append(dict(index=index,note=note,label=note_name(note),fret=fret,
                                start=normalized(-.08,offset),end=normalized(1.22,offset),offset=offset))
        self.guitar={"neck":normalized(0,0),"body":normalized(1,0),"length":length,
                     "spread":spread,"strings":strings,"neck_hand":neck_hand["id"],
                     "pick_hand":pick_hand["id"],"width":width,"height":height}
        events=[];seen=set()
        for name in self.settings.fingers:
            source=f'guitar:{pick_hand["id"]}:{name}'
            seen.add(source)
            u,v=local(pick_hand["landmarks"][FINGERS[name]])
            previous=self.states.get(source)
            inside=.56<=u<=1.25
            touching=next((string for string in strings if inside and abs(v-string["offset"])<=tolerance),None)
            previous_note=previous.get("note") if previous else None
            new_note=touching["note"] if touching else None
            if previous_note is not None and new_note!=previous_note:
                events.append(dict(kind="off",note=previous_note,source=source))
            # A first contact is immediate. At high speed, retain crossed strings
            # even if the tip jumps across several lines between camera frames.
            crossings=[]
            if previous and inside and .56<=previous["u"]<=1.25 and now-previous["time"]<.15:
                delta=v-previous["v"]
                if abs(delta)>tolerance:
                    for string in strings:
                        if (previous["v"]-string["offset"])*(v-string["offset"])<0:
                            if previous.get("string")!=string["index"]:
                                crossings.append(string)
                    crossings.sort(key=lambda string:string["offset"],reverse=delta<0)
            emitted=set()
            for string in crossings:
                token=f'{source}:pluck:{string["index"]}'
                events.append(dict(kind="on",note=string["note"],source=token,velocity=.85,string=string["index"]))
                events.append(dict(kind="off",note=string["note"],source=token))
                emitted.add(string["index"])
            if touching and new_note!=previous_note and touching["index"] not in emitted:
                speed=abs(v-previous["v"])/max(.01,now-previous["time"]) if previous else 0
                events.append(dict(kind="on",note=new_note,source=source,
                                   velocity=round(min(1,.72+speed/1300),3),string=touching["index"]))
            self.states[source]={"u":u,"v":v,"time":now,"note":new_note,
                                 "string":touching["index"] if touching else None}
        for source,previous in list(self.states.items()):
            if source not in seen:
                if previous["note"] is not None:events.append(dict(kind="off",note=previous["note"],source=source))
                del self.states[source]
        return events


class InstrumentTracker:
    def __init__(self, settings):
        from .performance import ExpressionTracker, AssistedGuitarTracker, StrikeTracker
        self.settings=settings
        self.contact=ContactTracker(settings)
        self.strings=GuitarTracker(settings) if settings.guitar_mode=="strings" else AssistedGuitarTracker(settings)
        self.strikes=StrikeTracker(settings)
        self.expression=ExpressionTracker(settings)
        self.layout=self.contact.layout

    @property
    def performance(self):
        return self.expression.value

    @property
    def guitar(self):
        return self.strings.guitar

    def reset(self,settings=None):
        events=self.contact.reset()+self.strings.reset()+self.strikes.reset()
        self.expression.reset()
        if settings:self.__init__(settings)
        return events

    def update(self,points,now,hands=None,width=960,height=540):
        expression=self.expression.update(hands or [],width,height,now)
        if self.settings.instrument=="guitar":
            if self.settings.guitar_mode=="strings":
                return expression+self.strings.update(hands or [],width,height,now)
            return expression+self.strings.update(hands or [],width,height,now,self.expression.value)
        mode=self.settings.drum_mode if self.settings.instrument=="drums" else self.settings.piano_mode
        tracker=self.strikes if mode=="strike" else self.contact
        return expression+tracker.update(points,now)

