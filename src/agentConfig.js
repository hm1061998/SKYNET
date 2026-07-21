import identity from '../agent.config.json';

export const AGENT_NAME = String(identity.name || 'AI Agent').trim();
export const AGENT_SPEECH_NAME = String(identity.speechName || AGENT_NAME).trim();
export const AGENT_WAKE_ALIASES = Array.from(new Set([
  AGENT_NAME.toLowerCase(),
  ...(identity.wakeAliases || [])
]));
export const AGENT_VISUAL_EVENT = 'agent:visual';

const escapedAgentName = AGENT_NAME.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
const spokenNamePattern = new RegExp(escapedAgentName, 'giu');

export function prepareSpeechText(text) {
  return String(text || '').replace(spokenNamePattern, AGENT_SPEECH_NAME);
}

export const agentText = {
  wakeHint: `Đang chờ · gọi “${AGENT_NAME} / Em ơi”`,
  activationHint: (heard) => `Nghe: “${heard}” · gọi “${AGENT_NAME} / Em ơi” để kích hoạt`,
  staleServer: `Server đang chạy phiên bản cũ. Hãy đóng cửa sổ ${AGENT_NAME} và chạy lại start-agent.bat.`
};
