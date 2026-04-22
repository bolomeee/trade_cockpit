export interface NewsArticle {
  title: string
  publishedAt: string
  contentHtml: string
  symbols: string[]
  imageUrl: string | null
  url: string | null
  author: string | null
  site: string | null
}
