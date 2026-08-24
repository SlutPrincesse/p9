export interface Shard {
  shard_id: string
  name: string
  shard_type: string
  category: string
  source_repo: string
  cyclomatic_complexity: number
  import_dependencies: string[]
  description: string
  selected: boolean
}

export interface SynthesisResult {
  status: string
  project_name: string
  output_path: string
  summary: string
  gaps: Array<{ type: string; description: string; severity: string }>
  files: Array<{ path: string; purpose: string; source_shard_ids: string[]; content: string }>
}

export interface GuideBreakdown {
  repoName: string
  repoUrl?: string
  tagline: string
  language: string
  category: string
  difficulty: string
  summary: string
  architectureOverview: string
  keyConcepts: Array<{ title: string; explanation: string; codeSnippet?: string; analogy: string }>
  fileStructure: Array<{ path: string; description: string; importance: string }>
  executionSteps: Array<{ stepNumber: number; title: string; description: string; codeExample?: string }>
  starterTemplate?: { title: string; fileName: string; code: string; explanation: string; runInstructions: string }
  quiz: Array<{ id: string; question: string; options: string[]; answerIndex: number; explanation: string }>
  commonPitfalls: Array<{ pitfall: string; solution: string }>
}
