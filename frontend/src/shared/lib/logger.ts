const isDev = import.meta.env.DEV

type LogLevel = 'debug' | 'info' | 'warn' | 'error'

function emit(level: LogLevel, message: string, ...args: unknown[]): void {
  if (level === 'debug' && !isDev) return
  console[level](`[orderflow] ${message}`, ...args)
}

export const logger = {
  debug: (message: string, ...args: unknown[]) => emit('debug', message, ...args),
  info: (message: string, ...args: unknown[]) => emit('info', message, ...args),
  warn: (message: string, ...args: unknown[]) => emit('warn', message, ...args),
  error: (message: string, ...args: unknown[]) => emit('error', message, ...args),
}
