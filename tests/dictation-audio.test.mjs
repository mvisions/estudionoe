import test from "node:test";
import assert from "node:assert/strict";
import { createDictationPlayer } from "../dictation-audio.mjs";

function setup(t, options = {}) {
  const states = [], errors = [], audios = [];
  const player = createDictationPlayer({
    chunks: [{ audio: "01.wav" }, { audio: "02.wav" }],
    onState: state => states.push(state), onError: message => errors.push(message),
    createAudio: source => {
      const audio = { source, pauses: 0, play: () => Promise.resolve(), pause() { this.pauses++; }, removeAttribute() {}, load() {} };
      audios.push(audio);
      return audio;
    },
    ...options,
  });
  t.after(() => player.stop());
  return { player, states, errors, audios };
}

test("Play reproduce los fragmentos con pausa y conserva la velocidad", async t => {
  t.mock.timers.enable({ apis: ["setTimeout"] });
  const { player, audios, states, errors } = setup(t);
  player.play(1);
  assert.equal(audios[0].source, "01.wav");
  assert.equal(audios[0].playbackRate, 1);
  audios[0].onplaying();
  assert.equal(player.status, "speaking");
  audios[0].onended();
  assert.equal(player.status, "waiting");
  t.mock.timers.tick(3999);
  assert.equal(audios.length, 1);
  t.mock.timers.tick(1);
  assert.equal(audios.length, 2);
  assert.equal(audios[1].source, "02.wav");
  assert.equal(audios[1].playbackRate, 1);
  audios[1].onplaying();
  audios[1].onended();
  assert.equal(player.status, "finished");
  assert.equal(states.at(-1).index, 1);
  assert.deepEqual(errors, []);
});

test("Detener cancela pausas y eventos antiguos; repetir no reinicia todo el dictado", t => {
  t.mock.timers.enable({ apis: ["setTimeout"] });
  const { player, audios } = setup(t);
  player.play(0.9);
  const first = audios[0];
  first.onplaying();
  first.onended();
  player.stop();
  t.mock.timers.tick(4000);
  assert.equal(audios.length, 1);
  player.next(0.75);
  const second = audios[1];
  assert.equal(second.source, "02.wav");
  player.repeat(0.9);
  assert.equal(second.pauses, 1);
  assert.equal(audios[2].source, "02.wav");
  assert.equal(audios[2].playbackRate, 0.9);
  second.onplaying();
  second.onended();
  assert.equal(player.status, "starting");
  audios[2].onplaying();
  audios[2].onended();
  assert.equal(player.status, "finished");
  player.play(0.75);
  assert.equal(audios.at(-1).source, "01.wav");
});

test("Errores de carga, bloqueo de reproducción y tiempos de espera se muestran", async t => {
  t.mock.timers.enable({ apis: ["setTimeout"] });
  const { player, audios, errors } = setup(t);
  player.play(0.75);
  audios[0].onerror();
  assert.equal(player.status, "idle");
  assert.match(errors[0], /No se pudo cargar/);
  player.play(0.75);
  t.mock.timers.tick(15000);
  assert.match(errors[1], /no está respondiendo/);
  const blocked = setup(t, { createAudio: () => ({
    play: () => Promise.reject(Object.assign(new Error("Bloqueado"), { name: "NotAllowedError" })),
    pause() {}, load() {}, removeAttribute() {},
  }) });
  blocked.player.play(0.75);
  await Promise.resolve();
  assert.equal(blocked.player.status, "idle");
  assert.match(blocked.errors[0], /NotAllowedError/);
});
