import {
  AGENT_VISUAL_EVENT,
  AGENT_WAKE_ALIASES,
  agentText,
  prepareSpeechText,
} from "./agentConfig.js";

const visual = (detail) =>
  window.dispatchEvent(new CustomEvent(AGENT_VISUAL_EVENT, { detail }));

function pickVoice() {
  const voices = window.speechSynthesis?.getVoices() || [];
  return (
    voices.find((voice) => /hoai\s*_?my/i.test(voice.name)) ||
    voices.find(
      (voice) =>
        /vi([-_]|$)/i.test(voice.lang) &&
        /natural|online|neural/i.test(voice.name),
    ) ||
    voices.find((voice) => /vi([-_]|$)/i.test(voice.lang)) ||
    null
  );
}

export function createVoiceEngine({
  onCommand,
  onHint,
  onListeningChange,
  onError,
}) {
  const Recognition =
    window.SpeechRecognition || window.webkitSpeechRecognition;
  let recognition = null;
  let listening = false;
  let armed = false;
  let armTimer = null;
  let audio = null;
  let serverTts = true;
  const wakes = [
    ...AGENT_WAKE_ALIASES,
    ...AGENT_WAKE_ALIASES.map((name) => `chào ${name}`),
    "em ơi",
    "tùng ơi",
    "xin chào",
  ];
  const normalize = (value) =>
    (value || "")
      .toLowerCase()
      .normalize("NFKD")
      .replace(/[\u0300-\u036f]/g, "")
      .replace(/đ/g, "d")
      .replace(/[^0-9a-z\s]/g, "")
      .replace(/\s+/g, " ")
      .trim();
  const normalizedWakes = wakes.map(normalize);

  const disarm = () => {
    armed = false;
    clearTimeout(armTimer);
    onListeningChange?.(listening, false);
  };
  const arm = () => {
    armed = true;
    onListeningChange?.(listening, true);
    onHint?.("Nghe rồi — mời bạn nói lệnh…");
    clearTimeout(armTimer);
    armTimer = setTimeout(() => {
      disarm();
      if (listening) onHint?.(agentText.wakeHint);
    }, 12000);
  };
  const parse = (raw) => {
    const words = raw.trim().split(/\s+/);
    const low = words.map(normalize);
    for (let index = 0; index < words.length; index++) {
      for (
        let length = Math.min(3, words.length - index);
        length >= 1;
        length--
      ) {
        if (
          normalizedWakes.includes(low.slice(index, index + length).join(" "))
        )
          return { wake: true, rest: words.slice(index + length).join(" ") };
      }
    }
    return { wake: false, rest: raw };
  };

  if (Recognition) {
    recognition = new Recognition();
    recognition.lang = "vi-VN";
    recognition.continuous = true;
    recognition.interimResults = false;
    recognition.onresult = (event) => {
      for (
        let index = event.resultIndex;
        index < event.results.length;
        index++
      ) {
        if (!event.results[index].isFinal) continue;
        const raw = event.results[index][0].transcript.trim();
        const utterance = parse(raw);
        if (utterance.wake && utterance.rest.trim()) {
          disarm();
          onCommand?.(utterance.rest.trim());
        } else if (utterance.wake) arm();
        else if (armed) {
          disarm();
          onCommand?.(raw);
        } else onHint?.(agentText.activationHint(raw));
      }
    };
    recognition.onerror = (event) => {
      if (
        event.error === "not-allowed" ||
        event.error === "service-not-allowed"
      ) {
        listening = false;
        disarm();
        onListeningChange?.(false, false);
        onError?.("Chưa cấp quyền microphone.");
      }
    };
    recognition.onend = () => {
      if (listening)
        setTimeout(() => {
          try {
            recognition.start();
          } catch (_) {}
        }, 250);
    };
  }

  const toggleListening = () => {
    if (!recognition) {
      onError?.("Trình duyệt không hỗ trợ nhận giọng nói.");
      return false;
    }
    listening = !listening;
    if (listening) {
      try {
        recognition.start();
      } catch (_) {}
      onHint?.(agentText.wakeHint);
    } else {
      disarm();
      try {
        recognition.stop();
      } catch (_) {}
      onHint?.("");
    }
    onListeningChange?.(listening, armed);
    return listening;
  };

  const speakBrowser = (text, done) => {
    if (!("speechSynthesis" in window)) return done();
    window.speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(text);
    const voice = pickVoice();
    if (voice) utterance.voice = voice;
    utterance.lang = voice?.lang || "vi-VN";
    utterance.rate = 1.18;
    utterance.onboundary = () => visual({ type: "voice-pulse", strength: 1 });
    utterance.onend = done;
    utterance.onerror = done;
    window.speechSynthesis.speak(utterance);
  };

  const speak = async (text, done = () => {}) => {
    if (!text) return done();
    const spokenText = prepareSpeechText(text);
    stopSpeaking();
    if (serverTts) {
      try {
        const response = await fetch("/api/tts", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ text: spokenText.slice(0, 800) }),
        });
        if (response.ok) {
          audio = new Audio(URL.createObjectURL(await response.blob()));
          const pulse = setInterval(() => {
            if (!audio) clearInterval(pulse);
            else visual({ type: "voice-pulse", strength: 0.85 });
          }, 180);
          audio.onended = () => {
            clearInterval(pulse);
            audio = null;
            done();
          };
          audio.onpause = () => clearInterval(pulse);
          await audio.play();
          return;
        }
        serverTts = false;
      } catch (_) {
        serverTts = false;
      }
    }
    speakBrowser(spokenText, done);
  };

  function stopSpeaking() {
    window.speechSynthesis?.cancel?.();
    if (audio) {
      audio.pause();
      audio = null;
    }
  }

  return {
    speak,
    stopSpeaking,
    toggleListening,
    destroy() {
      listening = false;
      disarm();
      try {
        recognition?.stop();
      } catch (_) {}
      stopSpeaking();
    },
  };
}
