export type Source = {
  file_path: string
  name: string
  start_line: number
  end_line: number
  content: string
}

export type Message = {
  role: 'user' | 'assistant'
  content: string
  sources?: Source[]
}

export type UploadResult = {
  repository_id: string
  file_count: number
  files: string[]
}

export type ApiError = {
  error?: string | string[]
}