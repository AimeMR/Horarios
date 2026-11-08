export class ChatError extends Error {
    constructor(code, message) {
        super(message);
        this.name = 'ChatError';
        this.code = code;
    }
}
