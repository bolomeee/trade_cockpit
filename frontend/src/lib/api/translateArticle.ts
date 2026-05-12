import { callAiTask, type AiTaskResponse } from '@/cockpit/lib/api/aiApi'

export type TranslateArticleInput = {
  title: string
  contentText: string
  targetLang?: 'zh-CN'
}

export type TranslateArticleOutput = {
  titleZh: string
  contentZh: string
}

export type TranslateArticleResponse = AiTaskResponse<TranslateArticleOutput>

export function translateArticle(
  input: TranslateArticleInput,
): Promise<TranslateArticleResponse> {
  return callAiTask<TranslateArticleInput, TranslateArticleOutput>(
    'translate_article',
    input,
  )
}
