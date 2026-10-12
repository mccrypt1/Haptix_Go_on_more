/**
 * Consent gate in front of every output path.
 * A blocked route must not call the transport. The caller sends Stop itself.
 */

export function routeOutput({ armed = false, hidden = false, transport = 'lelo', runLovense, runLelo, runRumble } = {}) {
    if (!armed || hidden) return 'blocked';
    if (transport === 'lovense') {
        runLovense?.();
        return 'lovense';
    }
    runLelo?.();
    runRumble?.();
    return 'lelo';
}
