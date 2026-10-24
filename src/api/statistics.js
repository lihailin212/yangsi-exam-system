import request from './index'

// 数据库在境外，一次请求光建连接就要好几秒，统计类查询连带多表，
// 默认的 15 秒超时很容易踩线，一超时就整页变成 0，比报错还难查。
const SLOW_TIMEOUT = 30000

export const getStatistics = () =>
  request.get('/statistics', { timeout: SLOW_TIMEOUT })

export const getStatisticsRecords = (params = {}) =>
  request.get('/statistics/records', { params, timeout: SLOW_TIMEOUT })

export const getRecentActivity = (limit = 10) =>
  request.get('/statistics/recent-activity', { params: { limit }, timeout: SLOW_TIMEOUT })

export const getStatisticsTrend = (days = 7) =>
  request.get('/statistics/trend', { params: { days }, timeout: SLOW_TIMEOUT })
