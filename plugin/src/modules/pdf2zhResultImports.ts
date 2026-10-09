export class ResultImports {
    private pending = new Map<string, Promise<void>>();

    async run(key: string, operation: () => Promise<void>): Promise<void> {
        const existing = this.pending.get(key);
        if (existing) return existing;
        const pending = Promise.resolve().then(operation);
        this.pending.set(key, pending);
        try {
            await pending;
        } finally {
            this.pending.delete(key);
        }
    }
}

export function isTrackedResult(fileName: string): boolean {
    return /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}_/i.test(
        fileName,
    );
}
