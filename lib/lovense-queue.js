/**
 * Chat command queue. Pause suspends advancement and stops the device.
 * Play resumes at the interrupted command. Stop clears the queue.
 */

export function createCommandQueue({ send, setTimer = (fn, ms) => setTimeout(fn, ms), clearTimer = (id) => clearTimeout(id) } = {}) {
    let commands = [];
    let index = 0;
    let timer = null;
    let paused = false;
    let stopped = true;

    function clear() {
        if (timer != null) clearTimer(timer);
        timer = null;
    }

    async function playCurrent() {
        if (paused || stopped || !commands.length) return;
        const command = commands[index];
        await send(command);
        const sec = Number(command?.timeSec);
        const ms = (Number.isFinite(sec) && sec > 0 ? Math.min(sec, 60) : 5) * 1000;
        clear();
        timer = setTimer(() => {
            if (paused || stopped || !commands.length) return;
            index = (index + 1) % commands.length;
            playCurrent();
        }, ms);
        if (timer && typeof timer.unref === 'function') timer.unref();
    }

    return {
        start(list) {
            clear();
            commands = Array.isArray(list) ? list.filter((item) => item && item.command) : [];
            index = 0;
            paused = false;
            stopped = commands.length === 0;
            if (!stopped) return playCurrent();
            return undefined;
        },
        pause() {
            if (stopped) return undefined;
            paused = true;
            clear();
            return send({ command: 'Function', action: 'Stop', timeSec: 0, apiVer: 1 });
        },
        resume() {
            if (stopped || !paused) return undefined;
            paused = false;
            return playCurrent();
        },
        stop() {
            const wasStopped = stopped && !commands.length;
            stopped = true;
            paused = false;
            commands = [];
            index = 0;
            clear();
            if (wasStopped) return undefined;
            return send({ command: 'Function', action: 'Stop', timeSec: 0, apiVer: 1 });
        },
        get paused() { return paused; },
        get active() { return !stopped; },
        get index() { return index; },
    };
}
