"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.GrammyExecutionContext = void 0;
const execution_context_host_1 = require("@nestjs/core/helpers/execution-context-host");
class GrammyExecutionContext extends execution_context_host_1.ExecutionContextHost {
    static create(context) {
        const type = context.getType();
        const tgContext = new GrammyExecutionContext(context.getArgs(), context.getClass(), context.getHandler());
        tgContext.setType(type);
        return tgContext;
    }
    getType() {
        return super.getType();
    }
    getContext() {
        return this.getArgByIndex(0);
    }
    getNext() {
        return this.getArgByIndex(0);
    }
}
exports.GrammyExecutionContext = GrammyExecutionContext;
//# sourceMappingURL=grammy-execution-context.js.map