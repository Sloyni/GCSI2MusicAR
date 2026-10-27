const SAMPLE_NOTES = [];
for (let octave = 3; octave <= 6; octave++) {
  for (const [name, pitch] of [["C",0],["Ds",3],["Fs",6],["A",9]]) {
    SAMPLE_NOTES.push({name: name + octave, midi: 12 * (octave + 1) + pitch});
  }
}
SAMPLE_NOTES.push({name:"C7", midi:96});
const GUITAR_SAMPLES=[{name:"E2",midi:40},{name:"A2",midi:45},{name:"D3",midi:50},{name:"G3",midi:55},
  {name:"B3",midi:59},{name:"E4",midi:64},{name:"G4",midi:67},{name:"B4",midi:71}];
export const SOUND_STYLES = {
  acoustic:{label:"Acoustique",cutoff:15000,drive:0,echo:0,space:0,gain:1},
  jazz:{label:"Jazz · velouté",cutoff:4300,drive:0,echo:.07,space:.06,gain:1.05},
  electric:{label:"Électrique · drive",cutoff:9000,drive:7,echo:.14,space:.04,gain:.68},
  ambient:{label:"Ambient",cutoff:10000,drive:0,echo:.30,space:.36,gain:.85}
};

export class AudioEngine {
  constructor(onStatus) {
    this.onStatus = onStatus;
    this.voices = new Map();
    this.buffers = new Map();
    this.guitarBuffers = new Map();
    this.sustained = new Set();
    this.volume = .7;
    this.reverb = .18;
    this.sustain = false;
    this.loading = null;
    this.style = "acoustic";
    this.tone = .6;
    this.transpose = 0;
    this.pitch = 0;
  }

  async ensure(instrument="piano") {
    if (!this.context) this.createContext();
    // Resume inside the original user gesture, before waiting for downloads.
    await this.context.resume();
    if (this.context.state !== "running") throw new Error("Cliquez dans le studio pour autoriser le son.");
    if(instrument==="drums"){this.onStatus("Percussions · prêtes à jouer");return;}
    const samples=instrument==="guitar" ? GUITAR_SAMPLES : SAMPLE_NOTES;
    const buffers=instrument==="guitar" ? this.guitarBuffers : this.buffers;
    if (buffers.size === samples.length) return;
    // Serialize different sample-bank loads without dropping the requested bank.
    if(this.loading){await this.loading;if(buffers.size===samples.length)return;}
    if (!this.loading) {
      this.onStatus(instrument==="guitar"?"Chargement de la guitare…":"Chargement du piano…");
      this.loading = Promise.all(samples.map(async sample => {
        if (buffers.has(sample.midi)) return;
        const response = await fetch(`/assets/audio/${instrument==="guitar"?"guitar/":""}${sample.name}.mp3`);
        if (!response.ok) throw new Error("Échantillons absents. Relancez l’installation des sons.");
        const buffer = await this.context.decodeAudioData(await response.arrayBuffer());
        buffers.set(sample.midi, buffer);
      })).then(() => this.onStatus(instrument==="guitar"?"Guitare enregistrée · prête à jouer":"Piano enregistré · prêt à jouer"))
        .catch(error => { this.onStatus("Son indisponible · réessayer"); throw error; })
        .finally(() => { this.loading = null; });
    }
    await this.loading;
  }

  ready(instrument="piano") {
    return this.context?.state==="running" && (instrument==="drums" ||
      (instrument==="guitar"?this.guitarBuffers.size===GUITAR_SAMPLES.length:this.buffers.size===SAMPLE_NOTES.length));
  }

  createContext(context=new AudioContext({latencyHint:"interactive"})) {
    this.context = context;
    const ctx = this.context;
    this.input = ctx.createGain();
    this.dry = ctx.createGain();
    this.wet = ctx.createGain();
    this.master = ctx.createGain();
    this.convolver = ctx.createConvolver();
    this.compressor = ctx.createDynamicsCompressor();
    this.compressor.threshold.value = -12;
    this.compressor.knee.value = 12;
    this.compressor.ratio.value = 3;
    this.compressor.attack.value = .006;
    this.compressor.release.value = .16;
    this.analyser = ctx.createAnalyser();
    this.analyser.fftSize = 256;
    this.recordDestination = ctx.createMediaStreamDestination?.();
    this.toneFilter=ctx.createBiquadFilter();this.toneFilter.type="lowpass";this.toneFilter.Q.value=.5;
    this.drive=ctx.createWaveShaper();this.drive.oversample="2x";
    this.colorGain=ctx.createGain();
    this.delay=ctx.createDelay(1);this.delay.delayTime.value=.28;
    this.echo=ctx.createGain();this.feedback=ctx.createGain();this.feedback.gain.value=.24;
    this.input.connect(this.toneFilter).connect(this.drive).connect(this.colorGain);
    this.colorGain.connect(this.dry).connect(this.master);
    this.colorGain.connect(this.convolver).connect(this.wet).connect(this.master);
    this.colorGain.connect(this.delay).connect(this.echo).connect(this.master);
    this.delay.connect(this.feedback).connect(this.delay);
    this.master.connect(this.compressor).connect(this.analyser).connect(ctx.destination);
    if(this.recordDestination)this.compressor.connect(this.recordDestination);
    const impulse = ctx.createBuffer(2, ctx.sampleRate * 1.6, ctx.sampleRate);
    for (let channel = 0; channel < 2; channel++) {
      const values = impulse.getChannelData(channel);
      for (let i = 0; i < values.length; i++) {
        values[i] = (Math.random() * 2 - 1) * Math.pow(1 - i / values.length, 3.3);
      }
    }
    this.convolver.buffer = impulse;
    this.noise = ctx.createBuffer(1, ctx.sampleRate, ctx.sampleRate);
    const values = this.noise.getChannelData(0);
    for (let i = 0; i < values.length; i++) values[i] = Math.random() * 2 - 1;
    this.setVolume(this.volume);
    this.setReverb(this.reverb);
    this.configure({music_style:this.style,tone:this.tone,transpose:this.transpose});
  }

  configure({music_style=this.style,tone=this.tone,transpose=this.transpose}={}) {
    const styleChanged=music_style!==this.style;
    this.style=SOUND_STYLES[music_style]?music_style:"acoustic";
    this.tone=Math.max(0,Math.min(1,tone));this.transpose=transpose;
    if(!this.context)return;
    const preset=SOUND_STYLES[this.style],now=this.context.currentTime;
    if(this.toneFilter){
      this.toneFilter.frequency.setTargetAtTime(Math.min(19000,preset.cutoff)*Math.pow(.08,1-this.tone),now,.04);
      this.colorGain.gain.setTargetAtTime(preset.gain,now,.04);
      this.echo.gain.setTargetAtTime(preset.echo,now,.05);
      if(styleChanged||this.drive.curve===null){
        if(!preset.drive)this.drive.curve=null;
        else{const curve=new Float32Array(2048),amount=preset.drive;
          for(let i=0;i<curve.length;i++){const x=i*2/(curve.length-1)-1;curve[i]=Math.tanh(x*amount)/Math.tanh(amount);}
          this.drive.curve=curve;}
      }
    }
    this.setReverb(this.reverb);this.setPitch(this.pitch);
  }

  setPitch(semitones=0) {
    this.pitch=Math.max(-12,Math.min(12,semitones));
    if(!this.context)return;
    for(const voice of this.voices.values())if(!voice.drum&&voice.player.detune)
      voice.player.detune.setTargetAtTime((this.transpose-(voice.transpose||0)+this.pitch)*100,this.context.currentTime,.045);
  }

  setVolume(value) {
    this.volume = value;
    if (this.master) this.master.gain.setTargetAtTime(value * 1.30, this.context.currentTime, .02);
  }

  setReverb(value) {
    this.reverb = value;
    if (this.wet) {
      this.wet.gain.setTargetAtTime(Math.min(.8,value+SOUND_STYLES[this.style].space) * .65, this.context.currentTime, .02);
      this.dry.gain.setTargetAtTime(1 - value * .20, this.context.currentTime, .02);
    }
  }

  noteOn(note, source, velocity=.7, instrument="piano", options={}) {
    if (!this.context || this.context.state !== "running") return;
    const ctx = this.context;
    const now=Math.max(ctx.currentTime,Number.isFinite(options.when)?options.when:ctx.currentTime)+Math.max(0,Math.min(.15,options.delay||0));
    this.releaseVoice(source, .025, now);
    if (typeof note === "string") return this.drum(note, source, velocity);
    const buffers=instrument==="guitar" ? this.guitarBuffers : this.buffers;
    if (!buffers.size) return;
    while (this.voices.size >= 64) this.releaseVoice(this.voices.keys().next().value, .02);
    // Each guitar string has one sounding note: repeated strums damp the old one.
    if(instrument==="guitar"&&options.string!==undefined)
      for(const [id,voice] of this.voices)if(voice.plucked&&voice.string===options.string)this.releaseVoice(id,.025,now);
    const sounding=note+this.transpose;
    const nearest = [...buffers.keys()].reduce((a,b) => Math.abs(a-sounding) <= Math.abs(b-sounding) ? a : b);
    const player = ctx.createBufferSource();
    player.buffer = buffers.get(nearest);
    player.playbackRate.value = Math.pow(2, (sounding - nearest) / 12);
    player.detune.value=this.pitch*100;
    const filter = ctx.createBiquadFilter();
    filter.type = "lowpass";
    filter.frequency.value = 2200 + velocity * 13000;
    filter.Q.value = .5;
    const gain = ctx.createGain();
    gain.gain.setValueAtTime(0, now);
    gain.gain.linearRampToValueAtTime(Math.pow(velocity, 1.3) * (instrument==="guitar"?.55:.9), now + .004);
    player.connect(filter).connect(gain).connect(this.input);
    const voice = {player, gain, filter, note, transpose:this.transpose, string:options.string, plucked:instrument==="guitar"};
    this.voices.set(source, voice);
    player.onended = () => {
      player.disconnect(); filter.disconnect(); gain.disconnect();
      if (this.voices.get(source) === voice) this.voices.delete(source);
      this.sustained.delete(voice);
    };
    player.start(now);
  }

  noteOff(source,force=false) {
    const voice = this.voices.get(source);
    if (!voice || voice.drum || voice.plucked) return;
    if (this.sustain&&!force) {
      this.sustained.add(voice);
      return;
    }
    this.releaseVoice(source, force ? .065 : .28);
  }

  releaseVoice(source, release=.28, when=this.context.currentTime) {
    const voice = this.voices.get(source);
    if (!voice) return;
    this.voices.delete(source);
    this.sustained.delete(voice);
    this.fade(voice, release, when);
  }

  fade(voice, release, now=this.context.currentTime) {
    voice.gain.gain.cancelAndHoldAtTime(now);
    voice.gain.gain.linearRampToValueAtTime(0, now + release);
    try { voice.player.stop(now + release + .02); } catch { /* already ended */ }
    for (const extra of voice.extras || []) {
      try { extra.stop(now + release + .02); } catch { /* already ended */ }
    }
  }

  setSustain(value) {
    this.sustain = value;
    if (!value) {
      for (const [source, voice] of this.voices) if (this.sustained.has(voice)) this.releaseVoice(source);
      this.sustained.clear();
    }
  }

  panic() {
    if (!this.context) return;
    for (const source of [...this.voices.keys()]) this.releaseVoice(source, .035);
    this.sustained.clear();
  }

  drum(note, source, velocity) {
    const ctx = this.context, now = ctx.currentTime;
    if(note==="hat")for(const [id,voice] of this.voices)if(voice.note==="openhat")this.releaseVoice(id,.025);
    while(this.voices.size>=48)this.releaseVoice(this.voices.keys().next().value,.01);
    const gain = ctx.createGain();
    gain.connect(this.input);
    gain.gain.setValueAtTime(Math.max(.01, velocity * .8), now);
    let player, filter, length;
    const extras = [];
    if (note === "kick" || note === "tom") {
      player = ctx.createOscillator();
      player.type = "sine";
      const tune=this.style==="jazz"?1.15:this.style==="electric"?.85:1;
      player.frequency.setValueAtTime((note === "kick" ? 155 : 270)*tune, now);
      player.frequency.exponentialRampToValueAtTime((note === "kick" ? 43 : 90)*tune, now + .13);
      player.connect(gain);
      length = note === "kick" ? .5 : .35;
    } else {
      player = ctx.createBufferSource();
      player.buffer = this.noise;
      filter = ctx.createBiquadFilter();
      filter.type = "highpass";
      filter.frequency.value = ["hat","openhat"].includes(note) ? 6500 : note==="crash"?3800:1300;
      filter.Q.value=.65;
      player.connect(filter).connect(gain);
      length = note === "hat" ? .075 : note==="openhat"?.65:note==="crash"?1.5:this.style==="jazz"?.28:.20;
      if(note==="hat"||note==="openhat"||note==="crash") {
        for(const frequency of [4213,5879,7919]){
          const metal=ctx.createOscillator(),metalGain=ctx.createGain();
          metal.type="square";metal.frequency.value=frequency;metalGain.gain.value=.025;
          metal.connect(metalGain).connect(filter);metal.start(now);metal.stop(now+length);
          metal.onended=()=>{metal.disconnect();metalGain.disconnect();};extras.push(metal);
        }
      }
      if (note === "snare") {
        const tone = ctx.createOscillator();
        tone.type = "triangle";
        tone.frequency.value = 175;
        const toneGain = ctx.createGain();
        toneGain.gain.setValueAtTime(.28, now);
        toneGain.gain.exponentialRampToValueAtTime(.001, now + .10);
        tone.connect(toneGain).connect(gain);
        tone.onended = () => { tone.disconnect(); toneGain.disconnect(); };
        tone.start(); tone.stop(now + .12); extras.push(tone);
      }
    }
    gain.gain.exponentialRampToValueAtTime(.001, now + length);
    const voice = {player, gain, filter, extras, drum:true, note};
    this.voices.set(source, voice);
    player.onended = () => {
      player.disconnect(); gain.disconnect(); filter?.disconnect();
      if (this.voices.get(source) === voice) this.voices.delete(source);
    };
    player.start(now); player.stop(now + length + .01);
  }
}
