import request from './index'

// 历年真题卷（按年份分组）
export const getPastPapers = () => request.get('/past-papers')
