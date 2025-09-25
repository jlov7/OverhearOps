"use client";

import { SpanStatusCode, context, trace } from "@opentelemetry/api";

let tracer = trace.getTracer("overhearops-ui");

export function setTracerName(name: string) {
  tracer = trace.getTracer(name);
}

export function withUISpan<T>(name: string, fn: () => T | Promise<T>): T | Promise<T> {
  const span = tracer.startSpan(name);
  const callback = () => fn();
  try {
    const result = context.with(trace.setSpan(context.active(), span), callback);
    if (result instanceof Promise) {
      return result
        .catch((error) => {
          span.setStatus({ code: SpanStatusCode.ERROR, message: String(error) });
          throw error;
        })
        .finally(() => span.end());
    }
    span.end();
    return result;
  } catch (error) {
    span.setStatus({ code: SpanStatusCode.ERROR, message: String(error) });
    span.end();
    throw error;
  }
}
