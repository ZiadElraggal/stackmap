export interface AslTransition {
  from: string
  to: string
  kind: string
  label?: string
  error_equals?: string[]
}

export interface AslWarning {
  state?: string
  code: string
  message: string
}

export interface AslState {
  name: string
  qualified_name: string
  type: string
  path?: string[]
  next?: string
  end?: boolean
  comment?: string
  integration?: string
  pattern?: string
  resource_kind?: string
  resource_arn?: string | null
  resource_node_id?: string | null
  parameters_summary?: string
  result_summary?: string
  timeout_seconds?: number
  heartbeat_seconds?: number
  retry?: Array<{ error_equals: string[]; interval_seconds?: number; max_attempts?: number; backoff_rate?: number }>
  catch?: Array<{ error_equals: string[]; next?: string; result_path?: string }>
  choices?: Array<{ condition_summary: string; next?: string }>
  default?: string
  branches?: Array<{ start_at?: string; states: string[] }>
  iterator?: { start_at?: string; states: string[] } | null
  items_path?: string
  max_concurrency?: number
  wait_seconds?: number
  wait_seconds_path?: string
  wait_timestamp?: string
  error?: string
  cause?: string
}

export interface AslGraph {
  start_at?: string
  timeout_seconds?: number
  version?: string
  comment?: string
  states?: AslState[]
  transitions?: AslTransition[]
  resources?: Array<{ arn: string; kind: string; integration?: string; pattern?: string; node_id?: string | null }>
  warnings?: AslWarning[]
  recent_executions?: Array<{ status?: string; start?: string; duration_ms?: number | null; failed_state?: string | null }>
  error?: string
}
