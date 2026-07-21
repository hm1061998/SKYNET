import { AGENT_VISUAL_EVENT } from './agentConfig.js';

const emit = (detail) => window.dispatchEvent(new CustomEvent(AGENT_VISUAL_EVENT, { detail }));
const meaningful = /^\[(?:BƯỚC|VÒNG|TASK|i|>|~|\+|✓|✗|!)\]/i;

export function createExecutionTracker(task) {
  return { task, currentSkill: null, usedSkills: [] };
}

export function publishExecutionLogs(lines, tracker) {
  for (const rawLine of lines || []) {
    const line = String(rawLine).trim();
    if (!line || /^[-=]{6,}$/.test(line)) continue;

    const skillMatch = line.match(/Match skill:\s*([^\s]+)/i)
      || line.match(/tái dùng skill ['"]([^'"]+)['"]/i)
      || line.match(/Skill mới được sinh:\s*skills[\\/]([^\s.]+)\.py/i)
      || line.match(/Viết skill mới ['"]([^'"]+)['"]/i);

    if (skillMatch) {
      const skill = skillMatch[1].trim();
      const previousSkill = tracker.currentSkill;
      tracker.currentSkill = skill;
      if (!tracker.usedSkills.includes(skill)) tracker.usedSkills.push(skill);
      emit({ type: 'skill-activity', task: tracker.task, skill, previousSkill, usedSkills: [...tracker.usedSkills], phase: 'active' });
    }

    const step = line.match(/^\[BƯỚC\s+(\d+)\/(\d+)\]\s*(.*)/i);
    const round = line.match(/^\[VÒNG\s+(\d+)\]\s*(.*)/i);
    if (step) emit({ type: 'thought', task: tracker.task, label: step[3], step: Number(step[1]), total: Number(step[2]), skill: tracker.currentSkill });
    else if (round) emit({ type: 'thought', task: tracker.task, label: round[2] || `Vòng ${round[1]}`, step: Number(round[1]), skill: tracker.currentSkill });
    else if (meaningful.test(line) && !line.startsWith('[TASK]')) {
      emit({ type: 'thought', task: tracker.task, label: line.replace(/^\[[^\]]+\]\s*/, ''), skill: tracker.currentSkill });
    }

    if (/^\[✓\]/.test(line) && tracker.currentSkill) emit({ type: 'skill-activity', task: tracker.task, skill: tracker.currentSkill, usedSkills: [...tracker.usedSkills], phase: 'complete' });
    if (/^\[✗\]/.test(line) && tracker.currentSkill) emit({ type: 'skill-activity', task: tracker.task, skill: tracker.currentSkill, usedSkills: [...tracker.usedSkills], phase: 'error' });
  }
}
