"""Intentional gestures: separate expression controls from the playing surface."""
import math

from .gestures import ContactBase, FingerState, FINGERS, GUITAR_NOTES, note_name

STYLES = ("acoustic", "jazz", "electric", "ambient")
CHORDS = {"C": [48,52,55,60,64,67], "G": [43,47,50,55,59,67],
          "Am": [45,52,57,60,64,69], "F": [41,48,53,57,60,65],
          "Dm": [50,53,57,62,65,69], "Em": [40,47,52,55,59,64]}
FINGER_CHORDS = {1:"C", 2:"G", 3:"Am", 4:"F", 5:"Dm"}


def distance(a, b, aspect=1):
    return math.hypot((a[0]-b[0])*aspect, a[1]-b[1])


def extended(hand):
    p = hand["landmarks"]
    result = [name for name, tip in FINGERS.items() if name != "thumb" and
              distance(p[tip],p[0]) > distance(p[tip-2],p[0])*1.15]
    # The thumb opens sideways, unlike the other four fingers.
    if distance(p[4],p[17]) > distance(p[3],p[17])*1.2:
        result.append("thumb")
    return result


class ExpressionTracker:
    def __init__(self, settings):
        self.settings = settings
        self.reset()

    def reset(self):
        self.history = {}
        self.cooldown = 0
        self.control_id = None
        self.had_pair = False
        self.value = {"pitch":0, "pinch":None, "zone":False}

    def update(self, hands, width, height, now):
        events = []
        visible = {hand["id"] for hand in hands}
        self.history = {i:h for i,h in self.history.items() if i in visible}
        if self.control_id not in visible or (len(hands)==2 and not self.had_pair):
            ordered = sorted(hands, key=lambda h:h["landmarks"][0][0])
            self.control_id = (ordered[0 if self.settings.control_hand=="left" else -1]["id"]
                               if ordered else None)
        self.had_pair = len(hands)==2
        control = next((h for h in hands if h["id"]==self.control_id),None)
        pitch, ratio, zone = 0, None, False
        if control:
            p = control["landmarks"]
            zone = self.settings.expression_zone=="anywhere" or max(p[i][1] for i in (0,5,9,17)) < .32
            span = max(.025, distance(p[5],p[17],width/height))
            ratio = distance(p[4],p[8],width/height)/span
            if zone and self.settings.pitch_gesture and self.settings.instrument!="drums":
                pitch = max(-1,min(1,(ratio-self.settings.pitch_neutral)/.65))*self.settings.pitch_range
        # AudioParam smoothing handles the transition; loss always restores tuning.
        self.value = {"pitch":round(pitch,3), "pinch":round(ratio,3) if ratio is not None else None,
                      "zone":zone, "hand":self.control_id, "swiping":False,
                      "pinching":bool(zone and self.settings.pitch_gesture and ratio is not None and ratio<.55)}
        if not self.settings.style_swipe:
            self.history.clear()
            return events
        swiping=False
        for hand in hands:
            if hand["id"]!=self.control_id:
                continue
            p = hand["landmarks"]
            x,y = [sum(p[i][axis] for i in (0,5,9,13,17))/5 for axis in (0,1)]
            if not zone or len(extended(hand)) < 3:
                self.history.pop(hand["id"],None)
                continue
            history = self.history.setdefault(hand["id"],[])
            history.append((x,y,now))
            history[:] = [point for point in history if now-point[2] <= .65]
            if now < self.cooldown:
                history[:] = [(x,y,now)]
                continue
            if history:
                dx,dy,dt = x-history[0][0], y-history[0][1], now-history[0][2]
                swiping = abs(dx)>.045 and abs(dx)>2*abs(dy) and dt>0 and abs(dx)/dt>.30
                if .08 <= dt <= .65 and abs(dx) >= .14 and abs(dx)>2*abs(dy) and abs(dx)/dt > .35:
                    index = STYLES.index(self.settings.music_style)
                    style = STYLES[(index+(1 if dx>0 else -1))%len(STYLES)]
                    self.settings.music_style = style
                    events.append(dict(kind="style",style=style))
                    self.cooldown = now+1.1
                    self.history.clear()
        self.value["swiping"]=swiping
        return events


class StrikeTracker(ContactBase):
    """Downstrokes trigger; an upward lift rearms, including within a pad."""
    def __init__(self, settings):
        super().__init__(settings)
        self.motion = {}
        self.last_hits = {}

    def reset(self, settings=None):
        self.motion.clear()
        self.last_hits.clear()
        return super().reset(settings)

    def update(self, points, now):
        events, visible = [], set()
        for point in points:
            source = f'{point["hand"]}:{point["finger"]}'
            visible.add(source)
            x,y = point["x"],point["y"]
            old = self.states.get(source)
            note = self.layout.hit(x,y)
            motion = self.motion.setdefault(source,{"armed":True,"top":y,"bottom":y})
            if old and .008 <= now-old.seen <= .15:
                speed = (y-old.y)/(now-old.seen)
                motion["bottom"] = max(motion["bottom"],y)
                if motion["bottom"]-y >= .016 and speed < -.08:
                    motion.update(armed=True,top=y,bottom=y)
                motion["top"] = min(motion["top"],y)
                # Segment-circle collision catches a fast stroke passing through a pad.
                if self.settings.instrument=="drums" and note is None and speed>0:
                    dx,dy = x-old.x,y-old.y
                    crossings=[]
                    for pad in self.layout.pads:
                        t = max(0,min(1,((pad["x"]-old.x)*dx+(pad["y"]-old.y)*dy)/max(1e-9,dx*dx+dy*dy)))
                        if distance((old.x+t*dx,old.y+t*dy),(pad["x"],pad["y"])) <= pad["radius"]:
                            crossings.append((t,pad["note"]))
                    if crossings:note=min(crossings)[1]
                if old.note is not None and old.note!=note:
                    events.append(dict(kind="off",note=old.note,source=source))
                threshold = .38-.22*self.settings.sensitivity
                if (note is not None and motion["armed"] and speed>threshold and
                        y-motion["top"]>.012 and now-self.last_hits.get((point["hand"],note),-10)>.075):
                    if old.note==note:
                        events.append(dict(kind="off",note=note,source=source))
                    velocity = max(.2,min(1,.7*(1-self.settings.sensitivity)+
                                             (.18+speed*.65)*self.settings.sensitivity))
                    events.append(dict(kind="on",note=note,source=source,velocity=round(velocity,3)))
                    self.last_hits[(point["hand"],note)] = now
                    motion.update(armed=False,bottom=y)
                    self.states[source] = FingerState(x,y,now,note)
                    continue
            elif old:
                if old.note is not None:
                    events.append(dict(kind="off",note=old.note,source=source))
                motion.update(armed=True,top=y,bottom=y)
            self.states[source] = FingerState(x,y,now,old.note if old and old.note==note else None)
        for source in list(self.states):
            if source not in visible:
                old=self.states.pop(source)
                if old.note is not None:events.append(dict(kind="off",note=old.note,source=source))
                self.motion.pop(source,None)
        return events


class StringPicker:
    """Fingertip/string contacts in the wrist-relative frame, shared across fingers."""
    def __init__(self):
        self.states = {}
        self.last_hits = {}
        self.serial = 0

    def clear_motion(self):
        self.states.clear()

    def update(self, hand, guitar, fingers, now, sensitivity):
        width,height = guitar["width"],guitar["height"]
        a,b = guitar["neck"],guitar["body"]
        dx,dy = (b[0]-a[0])*width,(b[1]-a[1])*height
        length = math.hypot(dx,dy)
        ux,uy = dx/length,dy/length
        spacing = guitar["spread"]/5
        enter,leave = spacing*.36,spacing*.58
        def local(p):
            px,py = (p[0]-a[0])*width,(p[1]-a[1])*height
            return (px*ux+py*uy)/length,-px*uy+py*ux
        candidates=[]
        visible=set()
        contacts=set()
        for name in fingers:
            visible.add(name)
            u,v = local(hand["landmarks"][FINGERS[name]])
            previous = self.states.get(name)
            dt = now-previous["time"] if previous else 0
            valid_previous = previous is not None and .008<=dt<=.15
            previous_string = previous["string"] if previous else None
            inside = .45<=u<=1.24
            nearest = min(range(6),key=lambda i:abs(v-(i-2.5)*spacing))
            touching = nearest if inside and abs(v-(nearest-2.5)*spacing)<=enter else None
            if (inside and previous_string is not None and
                    abs(v-(previous_string-2.5)*spacing)<=leave):
                touching=previous_string
            emitted=set()
            if valid_previous:
                delta = v-previous["v"]
                if abs(delta)>enter*.35:
                    for i in range(6):
                        offset=(i-2.5)*spacing
                        fraction=(offset-previous["v"])/delta
                        crossing_u=previous["u"]+(u-previous["u"])*fraction
                        if 0<fraction<=1 and .45<=crossing_u<=1.24 and i!=previous_string:
                            candidates.append((fraction*dt,i,min(1,.6+abs(delta)/max(.008,dt)/1400*sensitivity)))
                            emitted.add(i)
            if touching is not None:
                contacts.add(touching)
                if previous is not None and touching!=previous_string and touching not in emitted:
                    candidates.append((dt if valid_previous else 0,touching,.78))
            self.states[name]={"u":u,"v":v,"time":now,"string":touching}
        self.states={name:state for name,state in self.states.items() if name in visible}
        guitar["contacts"]=sorted(contacts)
        events=[]
        played=set()
        origin=min((time for time,_,_ in candidates),default=0)
        for time,index,velocity in sorted(candidates):
            # Two fingertips or a tracking wobble must not double the same string.
            if index in played or now-self.last_hits.get(index,-10)<.055:
                continue
            played.add(index)
            self.last_hits[index]=now
            self.serial+=1
            source=f'guitar:pick:{hand["id"]}:{self.serial}'
            note=guitar["strings"][index]["note"]
            events.extend([dict(kind="on",note=note,source=source,velocity=round(velocity,3),
                                string=index,delay=round(min(.10,max(0,time-origin)),4)),
                           dict(kind="off",note=note,source=source)])
        return events


class AssistedGuitarTracker:
    """Debounced left-hand harmony; right fingertips pick a wrist-anchored guitar."""
    def __init__(self, settings):
        self.settings=settings
        self.reset()

    def reset(self):
        self.roles=None
        self.guitar=None
        self.chord=self.settings.guitar_chord
        self.candidate=None
        self.since=0
        self.picker=StringPicker()
        self.pinches={}
        self.serial=0
        self.muted=False
        self.note_group=0
        self.last_seen=-10
        return []

    def update(self, hands, width, height, now, expression=None):
        if len(hands)!=2:
            self.picker.clear_motion()
            # Brief occlusions must not discard the selected chord or fake a stroke.
            if now-self.last_seen>.18:
                return self.reset()
            return []
        self.last_seen=now
        by_id={h["id"]:h for h in hands}
        if self.roles is None or any(i not in by_id for i in self.roles):
            ordered=sorted(hands,key=lambda h:h["landmarks"][0][0])
            self.roles=(ordered[0]["id"],ordered[1]["id"])
        neck,pick=(by_id[i] for i in self.roles)
        count=len(extended(neck))
        control_zone=(self.settings.expression_zone=="top" and (self.settings.pitch_gesture or self.settings.style_swipe) and max(neck["landmarks"][i][1] for i in (0,5,9,17))<.32)
        if expression and expression.get("hand")==neck["id"]:
            control_zone=control_zone or (expression.get("pinching",False) and count>0) or expression.get("swiping",False)
        candidate=FINGER_CHORDS.get(count)
        if not control_zone:
            if candidate!=self.candidate:
                self.candidate,self.since=candidate,now
            elif now-self.since>=.13:
                self.muted=candidate is None
                if candidate:
                    self.chord=candidate
                    self.note_group=min(3,max(0,count-1))
        # Harmony is independent of the wrist-relative picking surface.
        notes=CHORDS[self.chord]
        intervals={"chromatic":tuple(range(12)),"major":(0,2,4,5,7,9,11),
                   "minor":(0,2,3,5,7,8,10),"pentatonic":(0,2,4,7,9)}[self.settings.scale]
        base=48+self.settings.root
        degrees=range(self.note_group*4,self.note_group*4+4)
        melody=[base+12*(degree//len(intervals))+intervals[degree%len(intervals)] for degree in degrees]
        wrist=pick["landmarks"][0]
        b=(wrist[0],wrist[1]-.065)
        a=(b[0]-.52,b[1]-.06)
        dx,dy=(b[0]-a[0])*width,(b[1]-a[1])*height
        length=math.hypot(dx,dy)
        ux,uy=dx/length,dy/length
        spread=height*.19
        def point(u,v):
            return [(a[0]*width+u*dx-v*uy)/width,(a[1]*height+u*dy+v*ux)/height]
        self.guitar=dict(neck=a,body=b,length=length,spread=spread,width=width,height=height,
            neck_hand=neck["id"],pick_hand=pick["id"],wrist=wrist[:2],chord=self.chord,muted=self.muted,
            melody=melody,mode=self.settings.guitar_mode,
            strings=[dict(index=i,note=note,label=note_name(note),fret=0,
                          start=point(-.08,(i-2.5)*spread/5),end=point(1.22,(i-2.5)*spread/5))
                     for i,note in enumerate(notes)])
        events=[]
        if self.settings.guitar_mode=="melody":
            p=pick["landmarks"]
            span=max(.025,distance(p[5],p[17],width/height))
            for i,name in enumerate(("index","middle","ring","pinky")):
                ratio=distance(p[4],p[FINGERS[name]],width/height)/span
                held=self.pinches.get(name,False)
                if ratio<.30 and not held and p[0][1]>.32:
                    self.serial+=1
                    source=f'guitar:melody:{self.serial}'
                    events.extend([dict(kind="on",note=melody[i],source=source,velocity=.75,string=i),
                                   dict(kind="off",note=melody[i],source=source)])
                    self.pinches[name]=True
                elif ratio>.48:self.pinches[name]=False
            return events
        if self.muted or wrist[1]<.32:
            self.picker.clear_motion()
            return events
        return self.picker.update(pick,self.guitar,self.settings.fingers,now,self.settings.sensitivity)
