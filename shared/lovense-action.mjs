/** Browser-facing re-export. The copy that ships next to the server plugin is server/lovense-action.mjs. */
export {
    SPEED_MAX, STROKE_GAP, FUNCTION_RANGES,
    clampInt, clampSpeed, clampStroke, buildThrustAction, sceneToIntent,
    sanitizeFunctionAction, sanitizePresetName, sanitizePromptName,
    isAllowedHostPort, protocolForPort, commandUrl, normalizeUserHost, candidateHosts, patternToCommands,
} from '../server/lovense-action.mjs';
