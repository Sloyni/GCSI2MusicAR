const SAMPLE_NOTES = [];
for (let octave = 3; octave <= 6; octave++) {
  for (const [name, pitch] of [["C",0],["Ds",3],["Fs",6],["A",9]]) {
    SAMPLE_NOTES.push({name: name + octave, midi: 12 * (octave + 1) + pitch});
  }
}
SAMPLE_NOTES.push({name:"C7", midi:96});
const GUITAR_SAMPLES=[{name:"E2",midi:40},{name:"A2",midi:45},{name:"D3",midi:50},{name:"G3",midi:55},
  {name:"B3",midi:59},{name:"E4",midi:64},{name:"G4",midi:67},{name:"B4",midi:71}];

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

  createContext() {
    this.context = new AudioContext({latencyHint:"interactive"});
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
    this.recordDestination = ctx.createMediaStreamDestination();
    this.input.connect(this.dry).connect(this.master);
    this.input.connect(this.convolver).connect(this.wet).connect(this.master);
    this.master.connect(this.compressor).connect(this.analyser).connect(ctx.destination);
    this.compressor.connect(this.recordDestination);
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
  }

  setVolume(value) {
    this.volume = value;
    if (this.master) this.master.gain.setTargetAtTime(value * 1.30, this.context.currentTime, .02);
  }

  setReverb(value) {
    this.reverb = value;
    if (this.wet) {
      this.wet.gain.setTargetAtTime(value * .65, this.context.currentTime, .02);
      this.dry.gain.setTargetAtTime(1 - value * .20, this.context.currentTime, .02);
    }
  }

  noteOn(note, source, velocity=.7, instrument="piano") {
    if (!this.context || this.context.state !== "running") return;
    this.releaseVoice(source, .025);
    if (typeof note === "string") return this.drum(note, source, velocity);
    const buffers=instrument==="guitar" ? this.guitarBuffers : this.buffers;
    if (!buffers.size) return;
    while (this.voices.size >= 64) this.releaseVoice(this.voices.keys().next().value, .02);
    const ctx = this.context;
    const nearest = [...buffers.keys()].reduce((a,b) => Math.abs(a-note) <= Math.abs(b-note) ? a : b);
    const player = ctx.createBufferSource();
    player.buffer = buffers.get(nearest);
    player.playbackRate.value = Math.pow(2, (note - nearest) / 12);
    const filter = ctx.createBiquadFilter();
    filter.type = "lowpass";
    filter.frequency.value = 2200 + velocity * 13000;
    filter.Q.value = .5;
    const gain = ctx.createGain();
    gain.gain.setValueAtTime(0, ctx.currentTime);
    gain.gain.linearRampToValueAtTime(Math.pow(velocity, 1.3) * .9, ctx.currentTime + .008);
    player.connect(filter).connect(gain).connect(this.input);
    const voice = {player, gain, filter, note, plucked:instrument==="guitar"};
    this.voices.set(source, voice);
    player.onended = () => {
      player.disconnect(); filter.disconnect(); gain.disconnect();
      if (this.voices.get(source) === voice) this.voices.delete(source);
      this.sustained.delete(voice);
    };
    player.start();
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

  releaseVoice(source, release=.28) {
    const voice = this.voices.get(source);
    if (!voice) return;
    this.voices.delete(source);
    this.sustained.delete(voice);
    this.fade(voice, release);
  }

  fade(voice, release) {
    const now = this.context.currentTime;
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
    const gain = ctx.createGain();
    gain.connect(this.input);
    gain.gain.setValueAtTime(Math.max(.01, velocity * .8), now);
    let player, filter, length;
    const extras = [];
    if (note === "kick" || note === "tom") {
      player = ctx.createOscillator();
      player.type = "sine";
      player.frequency.setValueAtTime(note === "kick" ? 155 : 270, now);
      player.frequency.exponentialRampToValueAtTime(note === "kick" ? 43 : 90, now + .13);
      player.connect(gain);
      length = note === "kick" ? .5 : .35;
    } else {
      player = ctx.createBufferSource();
      player.buffer = this.noise;
      filter = ctx.createBiquadFilter();
      filter.type = "highpass";
      filter.frequency.value = note === "hat" ? 7200 : 1300;
      player.connect(filter).connect(gain);
      length = note === "hat" ? .10 : .20;
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
