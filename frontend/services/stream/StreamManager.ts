
/**
 * StreamManager
 * Centralized management for stream cancellation and lifecycle.
 * Mimics backend's StreamTaskManager.
 */
export class StreamManager {
    private controllers: Map<string, AbortController> = new Map();

    /**
     * Registers a new stream task with an AbortController.
     * Returns the signal to be passed to fetch/axios.
     */
    public registerTask(taskId: string): AbortSignal {
        // Cancel existing task with same ID if any (debounce/cleanup)
        if (this.controllers.has(taskId)) {
            this.cancelTask(taskId, "New task started with same ID");
        }

        const controller = new AbortController();
        this.controllers.set(taskId, controller);
        return controller.signal;
    }

    /**
     * Cancels a running task.
     */
    public cancelTask(taskId: string, reason?: string) {
        const controller = this.controllers.get(taskId);
        if (controller) {
            controller.abort(reason);
            this.controllers.delete(taskId);
            console.log(`[StreamManager] Task ${taskId} cancelled: ${reason}`);
        }
    }

    /**
     * Cancels all running tasks (e.g., on app unmount or reset).
     */
    public cancelAll() {
        this.controllers.forEach((controller, id) => {
            controller.abort("Cancel All");
        });
        this.controllers.clear();
    }

    /**
     * Removes a task (cleanup) without aborting it (if it finished naturally).
     */
    public removeTask(taskId: string) {
        if (this.controllers.has(taskId)) {
            this.controllers.delete(taskId);
        }
    }

    public isTaskActive(taskId: string): boolean {
        return this.controllers.has(taskId);
    }
}

export const streamManager = new StreamManager();
